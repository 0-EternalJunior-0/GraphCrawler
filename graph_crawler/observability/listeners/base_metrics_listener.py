"""BaseMetricsListener - події метрик."""

from graph_crawler.domain.events import CrawlerEvent


class BaseMetricsListener:
    """
    Базовий listener для метрик.

        Відповідальність: збір метрик продуктивності.

        Події:
        - on_page_fetch_time() - час завантаження сторінки
    """

    def on_page_fetch_time(self, event: CrawlerEvent) -> None:
        """Викликається після завантаження сторінки з часом."""
        pass
