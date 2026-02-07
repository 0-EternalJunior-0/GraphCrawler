"""Спільна логіка для sync та async API.

Винесений спільний код з Crawler/AsyncCrawler.
"""

import logging
from typing import TYPE_CHECKING, Any, Callable, Literal, Optional, Union

from graph_crawler.domain.entities.edge import Edge
from graph_crawler.domain.entities.node import Node
from graph_crawler.domain.value_objects.models import URLRule

if TYPE_CHECKING:
    from graph_crawler.domain.interfaces.driver import IDriver
    from graph_crawler.domain.interfaces.storage import IStorage
    from graph_crawler.extensions.plugins.node import BaseNodePlugin

logger = logging.getLogger(__name__)

DriverType = Union[Literal["http", "async", "playwright", "stealth"], "IDriver", None]
StorageType = Union[
    Literal["memory", "json", "sqlite", "postgresql", "mongodb"], "IStorage", None
]
EventCallback = Callable[[Any], None]


class _BaseCrawler:
    """Базовий клас для Crawler та AsyncCrawler.

    Винесено спільний код для уникнення дублювання.

    Attributes:
        max_depth: Максимальна глибина краулінгу
        max_pages: Максимальна кількість сторінок
        same_domain: Краулити тільки в межах домену
        request_delay: Затримка між запитами
        driver: Тип драйвера
        storage: Тип storage
        plugins: Список плагінів
        edge_strategy: Стратегія створення edges
    """

    def __init__(
        self,
        *,
        max_depth: int = 3,
        max_pages: Optional[int] = 100,
        same_domain: bool = True,
        request_delay: float = 0.5,
        driver: Optional[DriverType] = None,
        driver_config: Optional[dict[str, Any]] = None,
        storage: Optional[StorageType] = None,
        storage_config: Optional[dict[str, Any]] = None,
        plugins: Optional[list["BaseNodePlugin"]] = None,
        node_class: Optional[type[Node]] = None,
        on_progress: Optional[EventCallback] = None,
        on_node_scanned: Optional[EventCallback] = None,
        on_error: Optional[EventCallback] = None,
        edge_strategy: str = "all",
    ):
        """Ініціалізує базовий Crawler з налаштуваннями.

        Args:
            max_depth: Максимальна глибина
            max_pages: Максимальна кількість сторінок
            same_domain: Краулити тільки в межах домену
            request_delay: Затримка між запитами
            driver: Тип драйвера
            driver_config: Конфігурація драйвера
            storage: Тип storage
            storage_config: Конфігурація storage
            plugins: Список плагінів
            node_class: Кастомний клас Node
            on_progress: Callback для прогресу
            on_node_scanned: Callback після сканування
            on_error: Callback при помилці
            edge_strategy: Стратегія створення edges
        """
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.same_domain = same_domain
        self.request_delay = request_delay
        self.driver = driver
        self.driver_config = driver_config or {}
        self.storage = storage
        self.storage_config = storage_config or {}
        self.plugins = plugins or []
        self.node_class = node_class
        self.on_progress = on_progress
        self.on_node_scanned = on_node_scanned
        self.on_error = on_error
        self.edge_strategy = edge_strategy
        self._closed = False

    def _get_crawl_params(
        self,
        max_depth: Optional[int],
        max_pages: Optional[int],
        same_domain: Optional[bool],
    ) -> tuple:
        """Обчислює фактичні параметри з default значень.

        Args:
            max_depth: Максимальна глибина
            max_pages: Максимальна кількість сторінок
            same_domain: Краулити тільки в межах домену

        Returns:
            Tuple з фактичними параметрами
        """
        actual_depth = max_depth if max_depth is not None else self.max_depth
        actual_pages = max_pages if max_pages is not None else self.max_pages
        actual_domain = same_domain if same_domain is not None else self.same_domain
        return actual_depth, actual_pages, actual_domain

    def _check_closed(self):
        """Перевіряє чи краулер не закритий.

        Raises:
            RuntimeError: Якщо краулер вже закрито
        """
        if self._closed:
            raise RuntimeError(
                f"{self.__class__.__name__} is closed. Create a new instance."
            )


__all__ = [
    "DriverType",
    "StorageType",
    "EventCallback",
    "_BaseCrawler",
]
