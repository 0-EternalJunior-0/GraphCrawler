"""BasePluginListener - події плагінів."""

from graph_crawler.domain.events import CrawlerEvent


class BasePluginListener:
    """
    Базовий listener для подій плагінів.

        Відповідальність: події виконання плагінів.

        Події:
        - on_plugin_started() - початок виконання плагіна
        - on_plugin_completed() - плагін успішно виконано
        - on_plugin_failed() - помилка плагіна
    """

    def on_plugin_started(self, event: CrawlerEvent) -> None:
        """Викликається перед виконанням плагіна."""
        pass

    def on_plugin_completed(self, event: CrawlerEvent) -> None:
        """Викликається після успішного виконання плагіна."""
        pass

    def on_plugin_failed(self, event: CrawlerEvent) -> None:
        """Викликається при помилці плагіна."""
        pass
