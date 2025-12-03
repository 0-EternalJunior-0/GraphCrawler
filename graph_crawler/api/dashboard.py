"""
Real-time Dashboard with WebSocket Support

Features:
- WebSocket для real-time updates
- Broadcasting crawler events до всіх підключених клієнтів
- Metrics tracking та статистика
- Control panel endpoints (pause/resume/stop)

Architecture:
- Використовує Facade pattern для координації компонентів
- Розділено на окремі модулі з Single Responsibility
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from graph_crawler.api.crawl_monitor import CrawlMonitor
from graph_crawler.shared.constants import MAX_DASHBOARD_HISTORY_SIZE

logger = logging.getLogger(__name__)

# Global monitor instance
monitor = CrawlMonitor(max_history_size=MAX_DASHBOARD_HISTORY_SIZE)

# FastAPI app
app = FastAPI(
    title="GraphCrawler Dashboard API",
    description="Real-time monitoring and control API for GraphCrawler",
    version="2.0.0-alpha",
)

# CORS middleware для підтримки frontend з різних доменів
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В production використовувати конкретні домени
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.websocket("/ws/crawl")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint для real-time моніторингу.

    Events:
    - initial_state: Поточний стан при підключенні
    - stats_update: Оновлення статистики
    - page_crawled: Нова сторінка проскануана
    - error: Помилка краулінгу
    """
    await monitor.connect(websocket)
    try:
        while True:
            # Чекаємо на повідомлення від клієнта (heartbeat або commands)
            data = await websocket.receive_text()

            # Можна додати обробку команд від клієнта
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        await monitor.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await monitor.disconnect(websocket)


@app.get("/api/stats")
async def get_stats():
    """
    HTTP endpoint для отримання поточної статистики.

    Returns:
        Dict з статистикою краулінгу
    """
    return monitor.get_current_stats()


@app.get("/api/health")
async def health_check():
    """
    Health check endpoint.

    Returns:
        Dict з статусом сервісу
    """
    return {
        "status": "healthy",
        "version": "2.0.0-alpha",
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/api/reset")
async def reset_stats():
    """
    Скинути статистику моніторингу.

    Returns:
        Dict з підтвердженням
    """
    monitor.reset_stats()
    await monitor.broadcast(
        {"type": "stats_reset", "data": monitor.get_current_stats()}
    )
    return {"status": "reset", "message": "Statistics reset successfully"}


# Event handlers для інтеграції з crawler
class DashboardEventHandler:
    """
    Event handler для інтеграції Dashboard з GraphCrawler EventBus.

    Підписується на події краулера та транслює їх у Dashboard.
    """

    def __init__(self, monitor_instance: CrawlMonitor):
        """
        Initialize handler.

        Args:
            monitor_instance: Instance of CrawlMonitor
        """
        self.monitor = monitor_instance
        self._loop = None

    def handle_event(self, event_type: str, data: Dict[str, Any]):
        """
        Обробка події від crawler.

        Args:
            event_type: Тип події
            data: Дані події
        """
        # Оновити статистику
        self.monitor.update_stats(event_type, data)

        # Broadcast до WebSocket клієнтів (в async context)
        if self._loop is None:
            try:
                self._loop = asyncio.get_event_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)

        # Створити task для broadcast
        asyncio.create_task(
            self.monitor.broadcast(
                {
                    "type": event_type,
                    "data": data,
                    "timestamp": datetime.now().isoformat(),
                }
            )
        )


# Create global event handler
dashboard_event_handler = DashboardEventHandler(monitor)


def integrate_with_crawler(event_bus):
    """
    Інтеграція Dashboard з GraphCrawler EventBus.

    Args:
        event_bus: Instance EventBus з crawler

    Example:
        >>> from graph_crawler.api.dashboard import integrate_with_crawler
        >>> from graph_crawler.domain.events import EventBus
        >>>
        >>> event_bus = EventBus()
        >>> integrate_with_crawler(event_bus)
    """
    # Підписатися на всі важливі події
    events = [
        "crawl_started",
        "crawl_finished",
        "page_crawled",
        "error",
        "queue_update",
    ]

    for event_type in events:
        event_bus.subscribe(event_type, dashboard_event_handler.handle_event)

    logger.info("Dashboard integrated with crawler EventBus")
