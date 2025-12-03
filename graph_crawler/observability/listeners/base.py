"""
Базові інтерфейси для Listeners.

Розділено на спеціалізовані listeners відповідно до Single Responsibility Principle.
Alpha 2.0: Оновлено імпорти після реструктуризації (прибрано specialized/)
"""

from typing import Protocol, runtime_checkable

from graph_crawler.domain.events import CrawlerEvent
from graph_crawler.observability.listeners.base_metrics_listener import (
    BaseMetricsListener,
)
from graph_crawler.observability.listeners.crawl_listener import BaseCrawlListener
from graph_crawler.observability.listeners.error_listener import BaseErrorListener
from graph_crawler.observability.listeners.node_listener import BaseNodeListener
from graph_crawler.observability.listeners.plugin_listener import BasePluginListener
from graph_crawler.observability.listeners.storage_listener import BaseStorageListener
from graph_crawler.observability.listeners.url_listener import BaseURLListener


@runtime_checkable
class IEventListener(Protocol):
    """
    Protocol інтерфейс для Event Listeners.

        Замість reflection і магії імен (dir(listener), startswith('on_')),
        використовуємо явний інтерфейс через Protocol.

        Це покращує:
        - Читабельність коду (явно видно які методи потрібні)
        - Type safety (перевірка на етапі статичного аналізу)
        - IDE підтримку (autocomplete)
        - Документацію (явний контракт)

        Listener може реалізувати тільки ті методи які йому потрібні.
        Всі методи опціональні завдяки @runtime_checkable.

        Example:
            >>> class MyListener:
            ...     def on_crawl_started(self, event: CrawlerEvent):
            ...         print(f"Started: {event.data['url']}")
            ...
            ...     def on_node_scanned(self, event: CrawlerEvent):
            ...         print(f"Scanned: {event.data['url']}")
            >>>
            >>> listener = MyListener()
            >>> isinstance(listener, IEventListener)  # True через @runtime_checkable
    """

    # Основні події краулінгу
    def on_crawl_started(self, event: CrawlerEvent) -> None:
        """Викликається при початку краулінгу."""
        ...

    def on_node_scanned(self, event: CrawlerEvent) -> None:
        """Викликається після сканування ноди."""
        ...

    def on_progress_update(self, event: CrawlerEvent) -> None:
        """Викликається при оновленні прогресу."""
        ...

    def on_crawl_completed(self, event: CrawlerEvent) -> None:
        """Викликається при завершенні краулінгу."""
        ...

    def on_error_occurred(self, event: CrawlerEvent) -> None:
        """Викликається при виникненні помилки."""
        ...


class BaseListener(
    BaseCrawlListener,
    BaseNodeListener,
    BaseURLListener,
    BasePluginListener,
    BaseMetricsListener,
    BaseStorageListener,
    BaseErrorListener,
):
    """
    Уніфікований базовий клас (Multiple Inheritance).

        Об'єднує всі спеціалізовані listeners через множинне наслідування:
        - BaseCrawlListener - події краулінгу
        - BaseNodeListener - події нод
        - BaseURLListener - події URL
        - BasePluginListener - події плагінів
        - BaseMetricsListener - метрики
        - BaseStorageListener - storage події
        - BaseErrorListener - помилки

        Можна наслідувати BaseListener і перевизначити тільки потрібні методи.

        Example:
            >>> class MyListener(BaseListener):
            ...     def on_crawl_started(self, event):
            ...         print(f"Started: {event.data['url']}")
            >>>
            >>> listener = MyListener()
            >>> listener.on_crawl_started(event)  # OK
            >>> listener.on_node_scanned(event)   # OK (порожня реалізація)
    """

    pass  # Всі методи успадковані від спеціалізованих класів
