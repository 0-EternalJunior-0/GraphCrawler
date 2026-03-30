"""Listener для збору метрик краулінгу."""

import logging
from collections import deque
from typing import Dict

from graph_crawler.domain.events import CrawlerEvent

logger = logging.getLogger(__name__)

# Ліміт для запобігання memory leak при тривалому краулінгу
DEFAULT_MAX_FETCH_TIMES = 10000


class MetricsListener:
    """
    Listener для збору метрик краулінгу.

    Збирає статистику про краулінг для аналізу performance.

    Приклад:
        client = GraphCrawlerClient()
        metrics = MetricsListener()
        client.add_listener(metrics)

        graph = client.crawl("https://example.com")

        # Отримати метрики
        stats = metrics.get_metrics()
        logger.info("Total pages: %s", stats['total_pages'])
        logger.info("Average fetch time: %.2fs", stats['avg_fetch_time'])
    """

    def __init__(self, max_fetch_times: int = DEFAULT_MAX_FETCH_TIMES):
        """
        Ініціалізує metrics listener.

        Args:
            max_fetch_times: Максимальна кількість fetch_times для зберігання
                           (запобігає memory leak при тривалому краулінгу)
        """
        self._max_fetch_times = max_fetch_times
        self.metrics = {
            "total_pages": 0,
            "failed_pages": 0,
            "total_links": 0,
            "fetch_times": deque(maxlen=max_fetch_times),
        }

    def on_node_scanned(self, event: CrawlerEvent):
        """Обробити скановану ноду."""
        self.metrics["total_pages"] += 1
        self.metrics["total_links"] += event.data.get("links_found", 0)

        # Fetch time
        fetch_time = event.data.get("fetch_time")
        if fetch_time:
            self.metrics["fetch_times"].append(fetch_time)

    def on_node_failed(self, event: CrawlerEvent):
        """Обробити failed ноду."""
        self.metrics["failed_pages"] += 1

    def on_page_fetch_time(self, event: CrawlerEvent):
        """Обробити час завантаження."""
        fetch_time = event.data.get("time", 0)
        if fetch_time:
            self.metrics["fetch_times"].append(fetch_time)

    def get_metrics(self) -> Dict:
        """
        Повертає зібрані метрики з обчисленнями.

        Returns:
            Dict з метриками:
                - total_pages: Загальна кількість сторінок
                - failed_pages: Кількість failed сторінок
                - total_links: Загальна кількість знайдених посилань
                - avg_fetch_time: Середній час завантаження
                - min_fetch_time: Мінімальний час
                - max_fetch_time: Максимальний час
        """
        metrics = {
            "total_pages": self.metrics["total_pages"],
            "failed_pages": self.metrics["failed_pages"],
            "total_links": self.metrics["total_links"],
            "fetch_times": list(self.metrics["fetch_times"]),  # Convert deque to list
        }

        # Обчислення середніх значень
        fetch_times = self.metrics["fetch_times"]
        if fetch_times:
            metrics["avg_fetch_time"] = sum(fetch_times) / len(fetch_times)
            metrics["min_fetch_time"] = min(fetch_times)
            metrics["max_fetch_time"] = max(fetch_times)
        else:
            metrics["avg_fetch_time"] = 0.0
            metrics["min_fetch_time"] = 0.0
            metrics["max_fetch_time"] = 0.0

        return metrics

    def reset(self):
        """Скинути метрики."""
        self.metrics = {
            "total_pages": 0,
            "failed_pages": 0,
            "total_links": 0,
            "fetch_times": deque(maxlen=self._max_fetch_times),
        }
