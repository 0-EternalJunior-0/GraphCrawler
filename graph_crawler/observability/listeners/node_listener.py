"""BaseNodeListener - події обробки нод."""

from graph_crawler.domain.events import CrawlerEvent


class BaseNodeListener:
    """
    Базовий listener для подій нод.

        Відповідальність: події обробки вузлів (сканування, зміни).

        Події:
        - on_node_scan_started() - початок сканування ноди
        - on_node_scanned() - нода просканована
        - on_node_skipped_unchanged() - нода пропущена (incremental)
        - on_node_detected_changed() - детектовано зміни в ноді
    """

    def on_node_scan_started(self, event: CrawlerEvent) -> None:
        """Викликається перед сканування ноди."""
        pass

    def on_node_scanned(self, event: CrawlerEvent) -> None:
        """Викликається після сканування ноди."""
        pass

    def on_node_skipped_unchanged(self, event: CrawlerEvent) -> None:
        """Викликається коли нода пропущена (incremental)."""
        pass

    def on_node_detected_changed(self, event: CrawlerEvent) -> None:
        """Викликається коли детектовано зміни в ноді."""
        pass
