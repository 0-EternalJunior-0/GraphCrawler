"""BaseCrawlListener - події краулінгу."""

from graph_crawler.domain.events import CrawlerEvent


class BaseCrawlListener:
    """
    Базовий listener для подій краулінгу.

        Відповідальність: події життєвого циклу краулінгу.

        Події:
        - on_crawl_started() - початок краулінгу
        - on_crawl_completed() - завершення краулінгу
        - on_progress_update() - оновлення прогресу
    """

    def on_crawl_started(self, event: CrawlerEvent) -> None:
        """Викликається при початку краулінгу."""
        pass

    def on_crawl_completed(self, event: CrawlerEvent) -> None:
        """Викликається при завершенні краулінгу."""
        pass

    def on_progress_update(self, event: CrawlerEvent) -> None:
        """Викликається при оновленні прогресу."""
        pass
