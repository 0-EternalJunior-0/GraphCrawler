"""
REST API for Remote Control Використовує новий Sync-First Simple API.

Features:
- Start/stop/pause/resume crawling
- Query package_crawler status
- Manage crawl configurations
- Export results
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["package_crawler"])


# Pydantic models для request/response
class CrawlRequest(BaseModel):
    """Request model для запуску краулінгу."""

    url: str = Field(..., description="Start URL для краулінгу")
    max_depth: int = Field(3, ge=1, le=10, description="Максимальна глибина краулінгу")
    max_pages: int = Field(100, ge=1, le=100000, description="Максимальна кількість сторінок")
    allowed_domains: list[str] = Field(
        default=["domain+subdomains"],
        description="Дозволені домени: '*', 'domain', 'subdomains', 'domain+subdomains'",
    )
    follow_robots_txt: bool = Field(True, description="Дотримуватись robots.txt")
    enable_rate_limiting: bool = Field(True, description="Увімкнути rate limiting")
    rate_limit_rps: float = Field(2.0, ge=0.1, le=100.0, description="Запитів на секунду")
    enable_proxy: bool = Field(False, description="Використовувати proxy rotation")
    enable_captcha_solver: bool = Field(False, description="Увімкнути CAPTCHA solving")

    @validator("url")
    def validate_url(cls, v):
        """Валідація URL."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v


class CrawlResponse(BaseModel):
    """Response model для результатів краулінгу."""

    crawl_id: str
    status: str
    message: str
    stats: Optional[Dict[str, Any]] = None


class CrawlerStatus(BaseModel):
    """Status model для package_crawler state."""

    status: str  # idle, running, paused, stopped, error
    crawl_id: Optional[str] = None
    start_time: Optional[str] = None
    total_pages: int = 0
    queue_size: int = 0
    errors: int = 0
    pages_per_second: float = 0.0


# В production використовувати Redis або DB
_crawler_state: Dict[str, Any] = {
    "status": "idle",
    "crawl_id": None,
    "crawler_instance": None,  # Реальний GraphSpider instance
    "config": None,
    "result_graph": None,
}


@router.post("/crawl/start", response_model=CrawlResponse)
async def start_crawl(request: CrawlRequest, background_tasks: BackgroundTasks):
    """
    Запустити новий краулінг.

    Args:
        request: Конфігурація краулінгу
        background_tasks: FastAPI background tasks

    Returns:
        CrawlResponse з crawl_id та статусом

    Raises:
        HTTPException: Якщо краулінг вже запущений
    """
    if _crawler_state["status"] == "running":
        raise HTTPException(
            status_code=409,
            detail="Crawler is already running. Stop or wait for completion.",
        )

    # Генерувати crawl_id
    crawl_id = f"crawl_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Оновити state
    _crawler_state["status"] = "running"
    _crawler_state["crawl_id"] = crawl_id
    _crawler_state["config"] = request.dict()

    logger.info("Starting crawl %s for URL: %s", crawl_id, request.url)

    # Запустити краулінг у background (в production використовувати Celery)
    background_tasks.add_task(_run_crawl_background, crawl_id, request)

    return CrawlResponse(
        crawl_id=crawl_id,
        status="started",
        message=f"Crawl started successfully with ID: {crawl_id}",
        stats={
            "url": request.url,
            "max_depth": request.max_depth,
            "max_pages": request.max_pages,
        },
    )


@router.post("/crawl/{crawl_id}/pause")
async def pause_crawl(crawl_id: str):
    """
        Призупинити активний краулінг.

    Реалізовано pause logic через package_crawler.pause().

        Args:
            crawl_id: ID краулінгу

        Returns:
            Dict з підтвердженням

        Raises:
            HTTPException: Якщо краулінг не знайдено або не запущений
    """
    if _crawler_state["crawl_id"] != crawl_id:
        raise HTTPException(status_code=404, detail="Crawl not found")

    if _crawler_state["status"] != "running":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot pause crawl in state: {_crawler_state['status']}",
        )

    crawler = _crawler_state.get("crawler_instance")
    if crawler and crawler.pause():
        _crawler_state["status"] = "paused"
        logger.info("Crawl %s paused successfully", crawl_id)

        return {
            "crawl_id": crawl_id,
            "status": "paused",
            "message": "Crawl paused successfully",
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to pause package_crawler")


@router.post("/crawl/{crawl_id}/resume")
async def resume_crawl(crawl_id: str):
    """
        Відновити призупинений краулінг.

    Реалізовано resume logic через package_crawler.resume().

        Args:
            crawl_id: ID краулінгу

        Returns:
            Dict з підтвердженням

        Raises:
            HTTPException: Якщо краулінг не призупинений
    """
    if _crawler_state["crawl_id"] != crawl_id:
        raise HTTPException(status_code=404, detail="Crawl not found")

    if _crawler_state["status"] != "paused":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot resume crawl in state: {_crawler_state['status']}",
        )

    crawler = _crawler_state.get("crawler_instance")
    if crawler and crawler.resume():
        _crawler_state["status"] = "running"
        logger.info("Crawl %s resumed successfully", crawl_id)

        return {
            "crawl_id": crawl_id,
            "status": "running",
            "message": "Crawl resumed successfully",
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to resume package_crawler")


@router.post("/crawl/{crawl_id}/stop")
async def stop_crawl(crawl_id: str):
    """
        Зупинити активний краулінг.

    Реалізовано stop logic через package_crawler.stop().

        Args:
            crawl_id: ID краулінгу

        Returns:
            Dict з підтвердженням

        Raises:
            HTTPException: Якщо краулінг не знайдено
    """
    if _crawler_state["crawl_id"] != crawl_id:
        raise HTTPException(status_code=404, detail="Crawl not found")

    previous_status = _crawler_state["status"]

    crawler = _crawler_state.get("crawler_instance")
    if crawler:
        crawler.stop()
        _crawler_state["status"] = "stopped"
        logger.info("Crawl %s stopped successfully", crawl_id)

        return {
            "crawl_id": crawl_id,
            "status": "stopped",
            "previous_status": previous_status,
            "message": "Crawl stopped successfully",
        }
    else:
        # Навіть якщо немає package_crawler instance, змінюємо стан
        _crawler_state["status"] = "stopped"
        logger.warning("Crawl %s stopped (no active package_crawler)", crawl_id)

        return {
            "crawl_id": crawl_id,
            "status": "stopped",
            "previous_status": previous_status,
            "message": "Crawl stopped (no active package_crawler)",
        }


@router.get("/crawl/{crawl_id}/status", response_model=CrawlerStatus)
async def get_crawl_status(crawl_id: str):
    """
    Отримати статус краулінгу.

    Args:
        crawl_id: ID краулінгу

    Returns:
        CrawlerStatus з детальною інформацією

    Raises:
        HTTPException: Якщо краулінг не знайдено
    """
    if _crawler_state["crawl_id"] != crawl_id:
        raise HTTPException(status_code=404, detail="Crawl not found")

    # Отримати статистику з monitor
    from graph_crawler.api.dashboard import monitor

    stats = monitor.get_current_stats()

    return CrawlerStatus(
        status=_crawler_state["status"],
        crawl_id=crawl_id,
        start_time=stats.get("start_time"),
        total_pages=stats.get("total_pages", 0),
        queue_size=stats.get("queue_size", 0),
        errors=stats.get("errors", 0),
        pages_per_second=stats.get("pages_per_second", 0.0),
    )


@router.get("/crawl/list")
async def list_crawls(limit: int = Query(10, ge=1, le=100), offset: int = Query(0, ge=0)):
    """
    Список всіх краулінгів (history).

    Args:
        limit: Кількість записів
        offset: Offset для pagination
    Returns:
        List краулінгів
    """
    return {
        "total": 1 if _crawler_state["crawl_id"] else 0,
        "limit": limit,
        "offset": offset,
        "crawls": (
            [
                {
                    "crawl_id": _crawler_state["crawl_id"],
                    "status": _crawler_state["status"],
                    "config": _crawler_state.get("config"),
                }
            ]
            if _crawler_state["crawl_id"]
            else []
        ),
    }


async def _run_crawl_background(crawl_id: str, config: CrawlRequest):
    """
    Background task для запуску краулінгу. Використовує новий async_crawl API.

    Args:
        crawl_id: ID краулінгу
        config: Конфігурація

    Note:
        В production використовувати Celery для distributed tasks
    """
    try:
        logger.info("Background crawl %s started with URL: %s", crawl_id, config.url)

        from graph_crawler.api import async_crawl
        from graph_crawler.api.dashboard import monitor

        monitor.update_stats("crawl_started", {"crawl_id": crawl_id})

        request_delay = 1.0 / config.rate_limit_rps if config.enable_rate_limiting else 0.5

        graph = await async_crawl(
            url=config.url,
            max_depth=config.max_depth,
            max_pages=config.max_pages,
            same_domain=False,  # allowed_domains визначаються окремо
            request_delay=request_delay,
        )

        _crawler_state["result_graph"] = graph
        _crawler_state["status"] = "idle"

        # Статистика
        stats = graph.get_stats()
        logger.info("Crawl %s finished: %s", crawl_id, stats)
        monitor.update_stats("crawl_finished", {"crawl_id": crawl_id, "stats": stats})

    except Exception as e:
        logger.error("Error in background crawl %s: %s", crawl_id, e, exc_info=True)
        _crawler_state["status"] = "error"

        from graph_crawler.api.dashboard import monitor

        monitor.update_stats(
            "error",
            {"crawl_id": crawl_id, "error": str(e), "error_type": type(e).__name__},
        )
