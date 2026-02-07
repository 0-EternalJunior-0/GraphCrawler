"""
Асинхронний API для GraphCrawler - для максимальної продуктивності.

Приклади:
    >>> graph = await async_crawl("https://example.com")
    >>> print(f"Знайдено {len(graph.nodes)} сторінок")

    Паралельний краулінг:
    >>> async with AsyncCrawler() as package_crawler:
    ...     graphs = await asyncio.gather(
    ...         package_crawler.crawl("https://site1.com"),
    ...         package_crawler.crawl("https://site2.com"),
    ...     )
"""

import logging
from typing import Any, Optional

from graph_crawler.api._shared import (
    DriverType,
    EventCallback,
    StorageType,
    _BaseCrawler,
)
from graph_crawler.domain.entities.edge import Edge
from graph_crawler.domain.entities.graph import Graph
from graph_crawler.domain.entities.node import Node
from graph_crawler.domain.value_objects.models import URLRule

logger = logging.getLogger(__name__)


async def async_crawl(
    url: Optional[str] = None,
    *,
    seed_urls: Optional[list[str]] = None,
    base_graph: Optional[Graph] = None,
    max_depth: int = 3,
    max_pages: Optional[int] = 100,
    same_domain: bool = True,
    timeout: Optional[int] = None,
    request_delay: float = 0.5,
    driver: Optional[DriverType] = None,
    driver_config: Optional[dict[str, Any]] = None,
    storage: Optional[StorageType] = None,
    storage_config: Optional[dict[str, Any]] = None,
    plugins: Optional[list] = None,
    node_class: Optional[type[Node]] = None,
    edge_class: Optional[type[Edge]] = None,
    url_rules: Optional[list[URLRule]] = None,
    on_progress: Optional[EventCallback] = None,
    on_node_scanned: Optional[EventCallback] = None,
    on_error: Optional[EventCallback] = None,
    on_completed: Optional[EventCallback] = None,
    edge_strategy: str = "all",
    follow_links: bool = True,
) -> Graph:
    """
    Async краулінг веб-сайту - для максимальної продуктивності.

    NEW: Підтримка seed_urls та base_graph!

    Використовуй якщо:
    - Вже працюєш з async кодом
    - Потрібен паралельний краулінг декількох сайтів
    - Інтегруєш з async фреймворком (FastAPI, aiohttp)

    Args:
        url: URL веб-сайту для краулінгу (якщо seed_urls не передано)
        seed_urls: Список URL для початку краулінгу
        base_graph: Існуючий граф для продовження
        max_depth: Максимальна глибина обходу (default: 3)
        max_pages: Максимальна кількість сторінок (default: 100)
        same_domain: Сканувати тільки поточний домен (default: True)
        timeout: Максимальний час краулінгу в секундах
        request_delay: Затримка між запитами (default: 0.5)
        driver: Драйвер ("http", "async", "playwright")
        driver_config: Конфігурація драйвера
        storage: Storage ("memory", "json", "sqlite") або інстанс
        storage_config: Конфігурація storage
        plugins: Список плагінів
        node_class: Кастомний клас Node
        edge_class: Кастомний клас Edge
        url_rules: Правила URL
        on_progress: Callback для прогресу
        on_node_scanned: Callback для сканованого node
        on_error: Callback для помилок
        on_completed: Callback для завершення
        edge_strategy: Стратегія створення ребер
        follow_links: Переходити за посиланнями на сторінках (default: True).
                     False = сканувати тільки seed URL без переходу за посиланнями

    Returns:
        Graph: Побудований граф веб-сайту

    Examples:
        >>> graph = await async_crawl("https://example.com")
        >>> print(f"Знайдено {len(graph.nodes)} сторінок")

        Множинні точки входу (NEW):
        >>> graph = await async_crawl(
        ...     seed_urls=[
        ...         "https://example.com/page1",
        ...         "https://example.com/page2",
        ...     ]
        ... )

        Паралельний краулінг:
        >>> graphs = await asyncio.gather(
        ...     async_crawl("https://site1.com"),
        ...     async_crawl("https://site2.com"),
        ... )
    """
    from graph_crawler.api._core import async_crawl_impl

    return await async_crawl_impl(
        url=url,
        seed_urls=seed_urls,
        base_graph=base_graph,
        max_depth=max_depth,
        max_pages=max_pages,
        same_domain=same_domain,
        timeout=timeout,
        request_delay=request_delay,
        driver=driver,
        driver_config=driver_config,
        storage=storage,
        storage_config=storage_config,
        plugins=plugins,
        node_class=node_class,
        edge_class=edge_class,
        url_rules=url_rules,
        on_progress=on_progress,
        on_node_scanned=on_node_scanned,
        on_error=on_error,
        on_completed=on_completed,
        edge_strategy=edge_strategy,
        follow_links=follow_links,
    )


class AsyncCrawler(_BaseCrawler):
    """
    Async Crawler для повторного використання.

    Використовуй якщо потрібен async context manager або
    паралельний краулінг декількох сайтів.

    Examples:
        >>> async with AsyncCrawler(max_depth=5) as package_crawler:
        ...     graph1 = await package_crawler.crawl("https://site1.com")
        ...     graph2 = await package_crawler.crawl("https://site2.com")

        Паралельний краулінг:
        >>> async with AsyncCrawler() as package_crawler:
        ...     graphs = await asyncio.gather(
        ...         package_crawler.crawl("https://site1.com"),
        ...         package_crawler.crawl("https://site2.com"),
        ...         package_crawler.crawl("https://site3.com"),
        ...     )
    """

    def __init__(self, **kwargs):
        """Створює AsyncCrawler з default налаштуваннями."""
        super().__init__(**kwargs)
        logger.info(
            f"AsyncCrawler initialized: max_depth={self.max_depth}, max_pages={self.max_pages}"
        )

    async def crawl(
        self,
        url: str,
        *,
        max_depth: Optional[int] = None,
        max_pages: Optional[int] = None,
        same_domain: Optional[bool] = None,
        timeout: Optional[int] = None,
        url_rules: Optional[list[URLRule]] = None,
        **kwargs,
    ) -> Graph:
        """
        Async краулить сайт.

        Args:
            url: URL для краулінгу
            max_depth: Перевизначити default max_depth
            max_pages: Перевизначити default max_pages
            same_domain: Перевизначити default same_domain
            timeout: Максимальний час краулінгу
            url_rules: Правила URL

        Returns:
            Graph: Побудований граф
        """
        self._check_closed()
        actual_depth, actual_pages, actual_domain = self._get_crawl_params(
            max_depth, max_pages, same_domain
        )

        return await async_crawl(
            url=url,
            max_depth=actual_depth,
            max_pages=actual_pages,
            same_domain=actual_domain,
            request_delay=self.request_delay,
            driver=self.driver,
            driver_config=self.driver_config,
            storage=self.storage,
            storage_config=self.storage_config,
            plugins=self.plugins,
            node_class=self.node_class,
            on_progress=self.on_progress,
            on_node_scanned=self.on_node_scanned,
            on_error=self.on_error,
            timeout=timeout,
            url_rules=url_rules,
            edge_strategy=self.edge_strategy,
            **kwargs,
        )

    async def close(self) -> None:
        """Async закриває ресурси."""
        if self._closed:
            return
        logger.info("Closing AsyncCrawler...")
        self._closed = True
        logger.info("AsyncCrawler closed")

    async def __aenter__(self) -> "AsyncCrawler":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Async context manager exit."""
        await self.close()
        return False

    def __repr__(self) -> str:
        status = "closed" if self._closed else "open"
        return (
            f"AsyncCrawler(max_depth={self.max_depth}, "
            f"max_pages={self.max_pages}, driver={self.driver}, status={status})"
        )


async def async_crawl_sitemap(
    url: str,
    *,
    max_urls: Optional[int] = None,
    include_urls: bool = True,
    timeout: Optional[int] = None,
    driver: Optional[DriverType] = None,
    driver_config: Optional[dict[str, Any]] = None,
    storage: Optional[StorageType] = None,
    storage_config: Optional[dict[str, Any]] = None,
    url_rules: Optional[list[URLRule]] = None,
    max_sitemaps: Optional[int] = None,
    max_depth: Optional[int] = None,
    on_progress: Optional[EventCallback] = None,
    on_error: Optional[EventCallback] = None,
    on_completed: Optional[EventCallback] = None,
) -> Graph:
    r"""
    Async краулінг sitemap структури сайту.

    Парсить robots.txt → знаходить sitemap → рекурсивно обробляє всі sitemap файли.

    Args:
        url: Базовий URL сайту (https://example.com)
        max_urls: Максимальна кількість URL для обробки (None = всі)
        include_urls: Чи додавати кінцеві URL до графу (False = тільки структура sitemap)
        timeout: Максимальний час краулінгу в секундах
        driver: Драйвер ("http", "async") або інстанс
        driver_config: Конфігурація драйвера
        storage: Storage ("memory", "json", "sqlite") або інстанс
        storage_config: Конфігурація storage
        url_rules: Правила для фільтрації та пріоритизації sitemap URLs
        max_sitemaps: Максимальна кількість sitemap файлів (None = всі)
        max_depth: Максимальна глибина вкладеності sitemap (None = 10)
        on_progress: Callback для прогресу
        on_error: Callback для помилок
        on_completed: Callback для завершення

    Returns:
        Graph: Граф sitemap структури

    Examples:
        >>> graph = await async_crawl_sitemap("https://example.com")
        >>> print(f"Знайдено {len(graph.nodes)} елементів")

        З url_rules:
        >>> from graph_crawler.domain.value_objects.models import URLRule
        >>> rules = [
        ...     URLRule(pattern=r'\.xml\.gz$', should_scan=False),
        ...     URLRule(pattern=r'sitemap-news', priority=10),
        ... ]
        >>> graph = await async_crawl_sitemap("https://example.com", url_rules=rules)
    """
    from graph_crawler.api.sync import _crawl_sitemap_impl

    return await _crawl_sitemap_impl(
        url=url,
        max_urls=max_urls,
        include_urls=include_urls,
        timeout=timeout,
        driver=driver,
        driver_config=driver_config,
        storage=storage,
        storage_config=storage_config,
        url_rules=url_rules,
        max_sitemaps=max_sitemaps,
        max_depth=max_depth,
        on_progress=on_progress,
        on_error=on_error,
        on_completed=on_completed,
    )


__all__ = [
    "async_crawl",
    "async_crawl_sitemap",
    "AsyncCrawler",
]
