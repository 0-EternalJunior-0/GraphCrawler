"""
Crawl Monitor - Facade Pattern

Координатор який об'єднує всі компоненти моніторингу краулінгу.
"""

from typing import Any, Dict, Optional

from fastapi import WebSocket

from graph_crawler.api.history_manager import CrawlHistoryManager
from graph_crawler.api.stats_collector import CrawlStatsCollector
from graph_crawler.api.websocket_manager import WebSocketConnectionManager


class CrawlMonitor:
    """
    Facade для моніторингу краулінгу.

    Координує роботу компонентів:
    - WebSocketConnectionManager: управління WebSocket з'єднаннями
    - CrawlStatsCollector: збір та обчислення статистики
    - CrawlHistoryManager: управління історією краулінгу

    Responsibilities:
    - Facade/координація між компонентами
    - High-level API для dashboard
    """

    def __init__(self, max_history_size: int = 1000):
        """
        Initialize monitor with all components.

        Args:
            max_history_size: Максимальний розмір історії
        """
        self.connection_manager = WebSocketConnectionManager()
        self.stats_collector = CrawlStatsCollector()
        self.history_manager = CrawlHistoryManager(max_history_size=max_history_size)

    async def connect(self, websocket: WebSocket) -> None:
        """
        Підключення нового WebSocket клієнта.

        Args:
            websocket: WebSocket connection
        """
        await self.connection_manager.connect(websocket)

        # Відправити поточний стан новому клієнту
        await websocket.send_json(
            {"type": "initial_state", "data": self.get_current_stats()}
        )

    async def disconnect(self, websocket: WebSocket) -> None:
        """
        Відключення WebSocket клієнта.

        Args:
            websocket: WebSocket connection
        """
        await self.connection_manager.disconnect(websocket)

    async def broadcast(self, data: Dict[str, Any]) -> None:
        """
        Broadcast повідомлення всім підключеним клієнтам.

        Args:
            data: Дані для відправки
        """
        await self.connection_manager.broadcast(data)

    def update_stats(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Оновлення статистики на основі події краулера.

        Args:
            event_type: Тип події (page_crawled, error, etc.)
            data: Дані події
        """
        # Оновити статистику
        self.stats_collector.update_stats(event_type, data)

        # Додати запис до історії
        history_entry = {
            "timestamp": None,  # CrawlHistoryManager додасть автоматично
            "total_pages": self.stats_collector.stats["total_pages"],
            "queue_size": self.stats_collector.stats["queue_size"],
            "errors": self.stats_collector.stats["errors"],
            "pages_per_second": self.stats_collector.pages_per_second,
        }
        self.history_manager.add_entry(history_entry)

    def get_current_stats(self, history_preview: Optional[int] = 10) -> Dict[str, Any]:
        """
        Отримати поточну статистику з історією.

        Args:
            history_preview: Кількість останніх записів історії для включення.
                             None = вся історія

        Returns:
            Dict з повною статистикою включаючи історію
        """
        stats = self.stats_collector.get_stats()

        return {
            **stats,
            "history": self.history_manager.get_history(limit=history_preview),
            "connected_clients": self.connection_manager.get_connection_count(),
        }

    def reset_stats(self) -> None:
        """Скинути статистику та історію (для нового краулінгу)."""
        self.stats_collector.reset_stats()
        self.history_manager.clear_history()

    @property
    def elapsed_time(self) -> float:
        """
        Час з початку краулінгу (delegates to stats_collector).

        Returns:
            Час в секундах
        """
        return self.stats_collector.elapsed_time

    @property
    def pages_per_second(self) -> float:
        """
        Швидкість краулінгу (delegates to stats_collector).

        Returns:
            Швидкість краулінгу (pages/sec)
        """
        return self.stats_collector.pages_per_second

    @property
    def avg_time_per_page(self) -> float:
        """
        Середній час на сторінку (delegates to stats_collector).

        Returns:
            Середній час в секундах
        """
        return self.stats_collector.avg_time_per_page
