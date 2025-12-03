"""REST API для керування distributed crawling workers.

Цей модуль надає FastAPI endpoints для:
- Запуску distributed crawling задач
- Моніторингу воркерів та задач
- Зупинки/відміни задач
- Отримання результатів

Usage:
    from fastapi import FastAPI
    from graph_crawler.infrastructure.messaging.worker_api import router as distributed_router

    app = FastAPI()
    app.include_router(distributed_router)
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/distributed", tags=["distributed"])

# =====================================
# Pydantic Models
# =====================================


class BrokerType(str, Enum):
    """Типи брокерів."""

    REDIS = "redis"
    # KAFKA = "kafka"  # Для майбутнього


class DatabaseType(str, Enum):
    """Типи storage."""

    MEMORY = "memory"
    MONGODB = "mongodb"
    POSTGRESQL = "postgresql"


class BrokerConfig(BaseModel):
    """Конфігурація брокера."""

    type: BrokerType = BrokerType.REDIS
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None


class DatabaseConfig(BaseModel):
    """Конфігурація бази даних."""

    type: DatabaseType = DatabaseType.MEMORY
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None


class CrawlTaskRequest(BaseModel):
    """Request для запуску distributed crawl."""

    urls: List[str] = Field(..., min_length=1, description="Список URL для краулінгу")
    max_depth: int = Field(3, ge=1, le=10, description="Максимальна глибина")
    max_pages: int = Field(100, ge=1, le=100000, description="Максимум сторінок")
    extractors: List[str] = Field(
        default_factory=list, description="Extractors: phones, emails, prices"
    )
    plugins: List[str] = Field(default_factory=list, description="Custom plugin paths")
    timeout_minutes: Optional[int] = Field(
        None, ge=1, le=120, description="Таймаут в хвилинах"
    )

    @field_validator("urls")
    @classmethod
    def validate_urls(cls, v):
        """Валідація URL."""
        for url in v:
            if not url.startswith(("http://", "https://")):
                raise ValueError(f"URL must start with http:// or https://: {url}")
        return v


class DistributedCrawlRequest(BaseModel):
    """Повний request для distributed crawling."""

    broker: BrokerConfig = Field(default_factory=BrokerConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    crawl_task: CrawlTaskRequest
    workers: int = Field(10, ge=1, le=1000, description="Кількість воркерів")


class CrawlJobResponse(BaseModel):
    """Response для crawl job."""

    job_id: str
    status: str
    message: str
    created_at: str
    config: Optional[Dict[str, Any]] = None


class CrawlJobStatus(BaseModel):
    """Статус crawl job."""

    job_id: str
    status: str  # pending, running, completed, failed, cancelled
    progress: Dict[str, Any]
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None


class WorkerStatus(BaseModel):
    """Статус одного воркера."""

    hostname: str
    status: str
    active_tasks: int
    processed: int
    uptime: Optional[str] = None


class WorkersInfoResponse(BaseModel):
    """Інформація про всіх воркерів."""

    total_workers: int
    active_workers: int
    workers: List[WorkerStatus]
    broker_connected: bool


# =====================================
# Unified Storage for jobs
# =====================================

from graph_crawler.infrastructure.persistence.unified import UnifiedStorage

# Storage інстанс (створюється при першому запиті)
_storage: Optional[UnifiedStorage] = None
_active_crawlers: Dict[str, Any] = {}


def _get_storage() -> UnifiedStorage:
    """Отримує або створює UnifiedStorage.

    За замовчуванням використовує файлову систему ./crawl_data/
    для persistence між сесіями.
    """
    global _storage
    if _storage is None:
        _storage = UnifiedStorage(
            backend="file", storage_dir="./crawl_data"  # SQLite в ./crawl_data/
        )
        logger.info(" UnifiedStorage initialized for worker_api")
    return _storage


# =====================================
# API Endpoints
# =====================================


@router.post("/crawl/start", response_model=CrawlJobResponse)
async def start_distributed_crawl(
    request: DistributedCrawlRequest, background_tasks: BackgroundTasks
):
    """
    Запустити новий distributed crawl job.

    Приймає конфігурацію брокера, БД та задачі краулінгу.
    Запускає краулінг у фоні та повертає job_id для моніторингу.

    Example:
        POST /api/v1/distributed/crawl/start
        {
            "broker": {"type": "redis", "host": "localhost", "port": 6379},
            "database": {"type": "memory"},
            "crawl_task": {
                "urls": ["https://example.com"],
                "extractors": ["phones", "emails"]
            }
        }
    """
    storage = _get_storage()

    # Генеруємо job_id
    jobs = await storage.jobs.list_jobs(limit=1)
    job_count = len(jobs)
    job_id = f"dist_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{job_count}"
    created_at = datetime.now().isoformat()

    # Зберігаємо job в unified storage (SQLite)
    await storage.jobs.create_job(
        job_id=job_id,
        config={
            **request.model_dump(),
            "created_at": created_at,
            "max_pages": request.crawl_task.max_pages,
        },
        status="pending",
    )

    # Оновлюємо progress
    await storage.jobs.update_job(
        job_id,
        {
            "progress": {
                "pages_crawled": 0,
                "pages_total": request.crawl_task.max_pages,
                "urls_in_queue": len(request.crawl_task.urls),
            }
        },
    )

    logger.info(f"Created distributed crawl job: {job_id} (stored in SQLite)")

    # Запускаємо у фоні
    background_tasks.add_task(_run_distributed_crawl, job_id, request)

    return CrawlJobResponse(
        job_id=job_id,
        status="pending",
        message=f"Distributed crawl job created: {job_id}",
        created_at=created_at,
        config=request.model_dump(),
    )


@router.get("/crawl/{job_id}/status", response_model=CrawlJobStatus)
async def get_crawl_status(job_id: str):
    """
    Отримати статус crawl job.

    Args:
        job_id: ID задачі

    Returns:
        CrawlJobStatus з детальною інформацією про прогрес
    """
    storage = _get_storage()
    job = await storage.jobs.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    return CrawlJobStatus(
        job_id=job_id,
        status=job["status"],
        progress=job.get("progress", {}),
        created_at=job["created_at"],
        started_at=job.get("started_at"),
        completed_at=job.get("completed_at"),
        error=job.get("error"),
    )


@router.post("/crawl/{job_id}/stop")
async def stop_crawl(job_id: str):
    """
    Зупинити crawl job.

    Args:
        job_id: ID задачі

    Returns:
        Dict з підтвердженням
    """
    storage = _get_storage()
    job = await storage.jobs.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    if job["status"] not in ["pending", "running"]:
        raise HTTPException(
            status_code=400, detail=f"Cannot stop job in status: {job['status']}"
        )

    # Зупиняємо crawler якщо є (proper cancellation implemented)
    if job_id in _active_crawlers:
        crawler = _active_crawlers[job_id]
        # Викликаємо cancel() якщо доступно
        if hasattr(crawler, "cancel") and callable(crawler.cancel):
            try:
                if asyncio.iscoroutinefunction(crawler.cancel):
                    await crawler.cancel()
                else:
                    crawler.cancel()
            except Exception as e:
                logger.warning(f"Error cancelling crawler for job {job_id}: {e}")
        # Закриваємо ресурси якщо доступно
        if hasattr(crawler, "close") and callable(crawler.close):
            try:
                if asyncio.iscoroutinefunction(crawler.close):
                    await crawler.close()
                else:
                    crawler.close()
            except Exception as e:
                logger.warning(f"Error closing crawler for job {job_id}: {e}")
        del _active_crawlers[job_id]
        logger.info(f"Crawler for job {job_id} cancelled and cleaned up")

    await storage.jobs.update_job(
        job_id, {"status": "cancelled", "completed_at": datetime.now().isoformat()}
    )

    logger.info(f"Stopped crawl job: {job_id}")

    return {
        "job_id": job_id,
        "status": "cancelled",
        "message": f"Job {job_id} has been cancelled",
    }


@router.get("/crawl/{job_id}/results")
async def get_crawl_results(job_id: str):
    """
    Отримати результати crawl job.

    Args:
        job_id: ID задачі

    Returns:
        Dict з результатами краулінгу
    """
    storage = _get_storage()
    job = await storage.jobs.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    if job["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Results not available. Job status: {job['status']}",
        )

    return {
        "job_id": job_id,
        "status": "completed",
        "results": job.get("result", {}),
    }


@router.get("/jobs", response_model=List[CrawlJobStatus])
async def list_jobs(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    Список всіх crawl jobs.

    Args:
        status: Фільтр за статусом
        limit: Кількість записів
        offset: Offset для pagination

    Returns:
        List of CrawlJobStatus
    """
    storage = _get_storage()
    jobs = await storage.jobs.list_jobs(status=status, limit=limit, offset=offset)

    return [
        CrawlJobStatus(
            job_id=job["job_id"],
            status=job["status"],
            progress=job.get("progress", {}),
            created_at=job["created_at"],
            started_at=job.get("started_at"),
            completed_at=job.get("completed_at"),
            error=job.get("error"),
        )
        for job in jobs
    ]


@router.get("/workers", response_model=WorkersInfoResponse)
async def get_workers_info():
    """
    Отримати інформацію про Celery воркерів.

    Returns:
        WorkersInfoResponse з інформацією про всіх воркерів
    """
    try:
        # замість deprecated celery_app
        from graph_crawler.infrastructure.messaging.celery_batch import celery_batch

        # Отримуємо статистику воркерів
        inspect = celery_batch.control.inspect()

        # Active workers
        active = inspect.active() or {}
        stats = inspect.stats() or {}

        workers = []
        for hostname, worker_stats in stats.items():
            active_tasks = len(active.get(hostname, []))
            processed_batch = worker_stats.get("total", {}).get(
                "graph_crawler.crawl_batch", 0
            )
            processed_page = worker_stats.get("total", {}).get(
                "graph_crawler.crawl_page", 0
            )
            workers.append(
                WorkerStatus(
                    hostname=hostname,
                    status="online",
                    active_tasks=active_tasks,
                    processed=processed_batch + processed_page,
                    uptime=str(worker_stats.get("uptime", "unknown")),
                )
            )

        return WorkersInfoResponse(
            total_workers=len(workers),
            active_workers=len([w for w in workers if w.status == "online"]),
            workers=workers,
            broker_connected=True,
        )

    except Exception as e:
        logger.error(f"Failed to get workers info: {e}")
        return WorkersInfoResponse(
            total_workers=0,
            active_workers=0,
            workers=[],
            broker_connected=False,
        )


@router.post("/workers/health")
async def check_workers_health():
    """
    Перевірити здоров'я воркерів через health check task.

    Returns:
        Dict з результатами health check від кожного воркера
    """
    try:
        # Спочатку перевіряємо підключення до Redis
        from graph_crawler.shared.utils.celery_config import check_broker_connection

        broker_ok, broker_msg = check_broker_connection()
        if not broker_ok:
            return {
                "status": "unhealthy",
                "error": f"Redis broker not available: {broker_msg}",
            }

        # Перевіряємо воркерів через celery_batch
        from graph_crawler.infrastructure.messaging.celery_batch import celery_batch

        inspect = celery_batch.control.inspect(timeout=5)
        stats = inspect.stats()

        if not stats:
            return {
                "status": "unhealthy",
                "error": "No workers found. Start workers with: celery -A graph_crawler.celery_batch worker -Q graph_crawler_batch",
            }

        return {
            "status": "healthy",
            "workers_count": len(stats),
            "workers": list(stats.keys()),
            "broker_connected": True,
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "error",
            "error": str(e),
        }


# =====================================
# Background Tasks
# =====================================


async def _run_distributed_crawl(job_id: str, request: DistributedCrawlRequest):
    """
    Background task для запуску distributed crawling.

    Args:
        job_id: ID задачі
        request: Конфігурація краулінгу
    """
    try:
        from graph_crawler.infrastructure.messaging import EasyDistributedCrawler

        job = _jobs_storage[job_id]
        job["status"] = "running"
        job["started_at"] = datetime.now().isoformat()

        logger.info(f"Starting distributed crawl job: {job_id}")

        # Формуємо конфіг для EasyDistributedCrawler
        config_dict = {
            "broker": request.broker.model_dump(),
            "database": request.database.model_dump(),
            "crawl_task": {
                "urls": request.crawl_task.urls,
                "max_depth": request.crawl_task.max_depth,
                "max_pages": request.crawl_task.max_pages,
                "extractors": request.crawl_task.extractors,
                "plugins": request.crawl_task.plugins,
            },
            "workers": request.workers,
        }

        # Створюємо crawler
        crawler = EasyDistributedCrawler.from_dict(config_dict)
        _active_crawlers[job_id] = crawler

        # Запускаємо краулінг
        results = crawler.crawl()

        # Зберігаємо результати
        stats = results.get_stats()

        # Збираємо extracted data
        extracted_data = []
        for url, node in results.nodes.items():
            node_data = {
                "url": url,
                "phones": node.user_data.get("phones", []),
                "emails": node.user_data.get("emails", []),
                "prices": node.user_data.get("prices", []),
            }
            if node_data["phones"] or node_data["emails"] or node_data["prices"]:
                extracted_data.append(node_data)

        job["status"] = "completed"
        job["completed_at"] = datetime.now().isoformat()
        job["progress"]["pages_crawled"] = stats.get("total_nodes", 0)
        job["result"] = {
            "stats": stats,
            "extracted_data": extracted_data,
            "total_nodes": stats.get("total_nodes", 0),
            "total_edges": stats.get("total_edges", 0),
        }

        logger.info(
            f"Completed distributed crawl job: {job_id}, nodes: {stats.get('total_nodes', 0)}"
        )

    except Exception as e:
        logger.error(f"Failed distributed crawl job {job_id}: {e}")
        job = _jobs_storage[job_id]
        job["status"] = "failed"
        job["completed_at"] = datetime.now().isoformat()
        job["error"] = str(e)

    finally:
        # Видаляємо з активних
        if job_id in _active_crawlers:
            del _active_crawlers[job_id]
