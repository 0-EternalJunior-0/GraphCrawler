"""Listener для логування через події."""

import logging

from graph_crawler.domain.events import CrawlerEvent, EventType


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
        """Обробити початок краулінгу."""
        url = event.data.get("url")
        max_pages = event.data.get("max_pages")
        max_depth = event.data.get("max_depth")

        self.logger.log(
            self.level,
            f" Crawl started: {url} (max_pages={max_pages}, max_depth={max_depth})",
        )

    def on_node_scanned(self, event: CrawlerEvent):
        """Обробити скановану ноду."""
        url = event.data.get("url")
        links_found = event.data.get("links_found", 0)
        fetch_time = event.data.get("fetch_time", 0)

        self.logger.debug(f"Scanned: {url} ({links_found} links, {fetch_time:.2f}s)")

    def on_progress_update(self, event: CrawlerEvent):
        """Обробити progress update."""
        pages = event.data.get("pages_crawled")
        max_pages = event.data.get("max_pages")
        progress = event.data.get("progress_pct", 0)

        self.logger.log(self.level, f" Progress: {pages}/{max_pages} ({progress:.1f}%)")

    def on_crawl_completed(self, event: CrawlerEvent):
        """Обробити завершення краулінгу."""
        total = event.data.get("total_pages")
        duration = event.data.get("duration", 0)
        avg_time = event.data.get("avg_time_per_page", 0)

        self.logger.log(
            self.level,
            f" Crawl completed! Pages: {total}, Duration: {duration:.2f}s, Avg: {avg_time:.2f}s/page",
        )

    def on_error_occurred(self, event: CrawlerEvent):
        """Обробити помилку."""
        error = event.data.get("error")
        error_type = event.data.get("error_type")

        self.logger.error(f" Error occurred: {error_type} - {error}")
