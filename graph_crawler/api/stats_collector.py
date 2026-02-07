"""
Crawl Statistics Collector

Відповідає за збір та обчислення статистики краулінгу.
"""

import threading
from datetime import datetime
from typing import Any, Dict


class CrawlStatsCollector:
    """
    Збір та обчислення статистики краулінгу.

    Responsibilities:
    - Оновлення статистики на основі подій
    - Обчислення метрик (elapsed_time, pages_per_second, avg_time_per_page)
    - Thread-safe операції зі статистикою
    """

    def __init__(self):
        """Initialize collector with empty stats."""
        self.stats: Dict[str, Any] = {
            "total_pages": 0,
            "queue_size": 0,
            "errors": 0,
            "start_time": None,
            "status": "idle",  # idle, running, paused, stopped
        }
        self._lock = threading.Lock()

    def update_stats(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Оновлення статистики на основі події краулера.

        Args:
            event_type: Тип події (page_crawled, error, queue_update, etc.)
            data: Дані події
        """
        with self._lock:
            if event_type == "page_crawled":
                self.stats["total_pages"] += 1
            elif event_type == "error":
                self.stats["errors"] += 1
            elif event_type == "queue_update":
                self.stats["queue_size"] = data.get("queue_size", 0)
            elif event_type == "crawl_started":
                self.stats["start_time"] = datetime.now().isoformat()
                self.stats["status"] = "running"
            elif event_type == "crawl_finished":
                self.stats["status"] = "idle"

    @property
    def elapsed_time(self) -> float:
        """
        Повертає час з початку краулінгу.

        Returns:
            Час в секундах (0 якщо краулінг не розпочато)
        """
        if not self.stats.get("start_time"):
            return 0.0

        start = datetime.fromisoformat(self.stats["start_time"])
        return (datetime.now() - start).total_seconds()

    @property
    def pages_per_second(self) -> float:
        """
        Розраховує швидкість краулінгу (pages per second).

        Returns:
            Швидкість краулінгу
        """
        elapsed = self.elapsed_time
        if elapsed > 0:
            return self.stats["total_pages"] / elapsed
        return 0.0

    @property
    def avg_time_per_page(self) -> float:
        """
        Розраховує середній час на одну сторінку.

        Returns:
            Середній час в секундах
        """
        pps = self.pages_per_second
        return 1.0 / pps if pps > 0 else 0.0

    def get_stats(self) -> Dict[str, Any]:
        """
        Отримати поточну статистику з обчисленими метриками.

        Returns:
            Dict з поточною статистикою включаючи обчислені метрики
        """
        with self._lock:
            return {
                **self.stats,
                "pages_per_second": self.pages_per_second,
                "avg_time_per_page": self.avg_time_per_page,
                "elapsed_time": self.elapsed_time,
            }

    def reset_stats(self) -> None:
        """Скинути статистику (для нового краулінгу)."""
        with self._lock:
            self.stats = {
                "total_pages": 0,
                "queue_size": 0,
                "errors": 0,
                "start_time": None,
                "status": "idle",
            }
