"""BaseErrorListener - події помилок."""

from graph_crawler.domain.events import CrawlerEvent


class BaseErrorListener:
    """
    Базовий listener для обробки помилок.

        Відповідальність: події помилок під час краулінгу.

        Події:
        - on_error_occurred() - виникнення помилки
    """

    def on_error_occurred(self, event: CrawlerEvent) -> None:
        """Викликається при виникненні помилки."""
        pass
