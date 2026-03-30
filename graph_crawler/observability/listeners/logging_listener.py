"""Listener для логування через події."""

import logging

from graph_crawler.domain.events import CrawlerEvent


class LoggingListener:
    """
    Listener для логування подій краулінгу.

    Замінює жорстко закодоване логування в Spider на event-driven підхід.

    Приклад:
        event_bus = EventBus()
        listener = LoggingListener(level='INFO')

        event_bus.subscribe(EventType.CRAWL_STARTED, listener.on_crawl_started)
        event_bus.subscribe(EventType.NODE_SCANNED, listener.on_node_scanned)
        event_bus.subscribe(EventType.CRAWL_COMPLETED, listener.on_crawl_completed)
    """

    def __init__(self, logger=None, level="INFO"):
        """
        Ініціалізує listener.

        Args:
            logger: Logger instance (optional)
            level: Log level (INFO, DEBUG, ERROR)
        """
        self.logger = logger or logging.getLogger("graph_crawler")
        self.level = getattr(logging, level.upper(), logging.INFO)

    def on_crawl_started(self, event: CrawlerEvent):
        """Обробляє початок краулінгу."""
        url = event.data.get("url")
        max_pages = event.data.get("max_pages")
        max_depth = event.data.get("max_depth")

        self.logger.log(
            self.level,
            "Crawl started: %s (max_pages=%s, max_depth=%s)",
            url,
            max_pages,
            max_depth,
        )

    def on_node_scanned(self, event: CrawlerEvent):
        """Обробити скановану ноду."""
        url = event.data.get("url")
        links_found = event.data.get("links_found", 0)
        fetch_time = event.data.get("fetch_time", 0)

        self.logger.debug("Scanned: %s (%s links, %.2fs)", url, links_found, fetch_time)

    def on_progress_update(self, event: CrawlerEvent):
        """Обробляє progress update."""
        pages = event.data.get("pages_crawled")
        max_pages = event.data.get("max_pages")
        progress = event.data.get("progress_pct", 0)

        self.logger.log(
            self.level,
            "Progress: %s/%s (%.1f%%)",
            pages,
            max_pages,
            progress,
        )

    def on_crawl_completed(self, event: CrawlerEvent):
        """Обробляє завершення краулінгу."""
        total = event.data.get("total_pages")
        duration = event.data.get("duration", 0)
        avg_time = event.data.get("avg_time_per_page", 0)

        self.logger.log(
            self.level,
            "Crawl completed! Pages: %s, Duration: %.2fs, Avg: %.2fs/page",
            total,
            duration,
            avg_time,
        )

    def on_error_occurred(self, event: CrawlerEvent):
        """Обробляє помилку."""
        error = event.data.get("error")
        error_type = event.data.get("error_type")

        self.logger.error("Error occurred: %s - %s", error_type, error)
