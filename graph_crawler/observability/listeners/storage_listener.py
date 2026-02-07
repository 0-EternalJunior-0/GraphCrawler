"""BaseStorageListener - події storage."""

from graph_crawler.domain.events import CrawlerEvent


class BaseStorageListener:
    """
    Базовий listener для подій storage.

        Відповідальність: події зберігання даних.

        Події:
        - on_storage_upgraded() - зміна типу storage
        - on_batch_completed() - завершення batch обробки
    """

    def on_storage_upgraded(self, event: CrawlerEvent) -> None:
        """Викликається при зміні типу storage."""
        pass

    def on_batch_completed(self, event: CrawlerEvent) -> None:
        """Викликається після обробки batch (async mode)."""
        pass
