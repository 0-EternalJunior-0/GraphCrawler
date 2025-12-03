"""BaseURLListener - події обробки URL."""

from graph_crawler.domain.events import CrawlerEvent


class BaseURLListener:
    """
    Базовий listener для подій URL.

        Відповідальність: події управління URL (додавання, фільтрація, пріоритезація).

        Події:
        - on_url_added_to_queue() - URL додано в чергу
        - on_url_excluded() - URL виключено
        - on_url_prioritized() - URL отримав пріоритет
        - on_url_filtered_out() - URL відфільтровано
    """

    def on_url_added_to_queue(self, event: CrawlerEvent) -> None:
        """Викликається при додаванні URL в чергу."""
        pass

    def on_url_excluded(self, event: CrawlerEvent) -> None:
        """Викликається коли URL виключається."""
        pass

    def on_url_prioritized(self, event: CrawlerEvent) -> None:
        """Викликається коли URL отримує пріоритет."""
        pass

    def on_url_filtered_out(self, event: CrawlerEvent) -> None:
        """Викликається коли URL відфільтровується."""
        pass
