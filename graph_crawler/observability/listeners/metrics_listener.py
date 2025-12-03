"""Listener для збору метрик краулінгу."""

from typing import Dict, List

from graph_crawler.domain.events import CrawlerEvent
import logging

logger = logging.getLogger(__name__)




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
        logger.info(f"Total pages: {stats['total_pages']}")
        logger.info(f"Average fetch time: {stats['avg_fetch_time']:.2f}s")
    """

    def __init__(self):
        """Ініціалізує metrics listener."""
        self.metrics = {
            "total_pages": 0,
            "failed_pages": 0,
            "total_links": 0,
            "fetch_times": [],
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
        metrics = self.metrics.copy()

        # Обчислення середніх значень
        if self.metrics["fetch_times"]:
            metrics["avg_fetch_time"] = sum(self.metrics["fetch_times"]) / len(
                self.metrics["fetch_times"]
            )
            metrics["min_fetch_time"] = min(self.metrics["fetch_times"])
            metrics["max_fetch_time"] = max(self.metrics["fetch_times"])
        else:
            metrics["avg_fetch_time"] = 0.0
            metrics["min_fetch_time"] = 0.0
            metrics["max_fetch_time"] = 0.0

        return metrics

    def reset(self):
        """Скинути метрики."""
        self.__init__()
