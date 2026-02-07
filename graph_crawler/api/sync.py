"""
Синхронний API для GraphCrawler - простий як requests.

Приклади:
    >>> import graph_crawler as gc
    >>> graph = gc.crawl("https://example.com")
    >>> print(f"Знайдено {len(graph.nodes)} сторінок")

    З параметрами:
    >>> graph = gc.crawl(
    ...     "https://example.com",
    ...     max_depth=5,
    ...     max_pages=200,
    ...     driver="playwright"
    ... )

    Reusable Crawler:
    >>> with gc.Crawler(max_depth=5) as package_crawler:
    ...     graph1 = package_crawler.crawl("https://site1.com")
    ...     graph2 = package_crawler.crawl("https://site2.com")
"""

import asyncio
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


def crawl(
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
    wrapper: Optional[dict] = None,
    follow_links: bool = True,
) -> Graph:
    """
    Краулінг веб-сайту - СИНХРОННИЙ, простий як requests.

     DISTRIBUTED MODE: Додай `wrapper` для автоматичного розподіленого краулінгу!

    Args:
        url: URL веб-сайту для краулінгу (використовується якщо seed_urls не передано)
        seed_urls: Список URL для початку краулінгу (множинні точки входу)
        base_graph: Існуючий граф для продовження краулінгу (incremental crawling)
        max_depth: Максимальна глибина обходу (default: 3)
        max_pages: Максимальна кількість сторінок (default: 100)
        same_domain: Сканувати тільки поточний домен (default: True)
        timeout: Максимальний час краулінгу в секундах
        request_delay: Затримка між запитами (default: 0.5)
        driver: Драйвер ("http", "async", "playwright") або інстанс
        driver_config: Конфігурація драйвера
        storage: Storage ("memory", "json", "sqlite") або інстанс
        storage_config: Конфігурація storage
        plugins: Список плагінів
        node_class: Кастомний клас Node
        edge_class: Кастомний клас Edge
        url_rules: Правила URL
        on_progress: Callback для прогресу
        on_node_scanned: Callback для скан ованого node
        on_error: Callback для помилок
        on_completed: Callback для завершення
        edge_strategy: Стратегія створення ребер
        wrapper: Конфігурація distributed crawling (broker + database)
        follow_links: Переходити за посиланнями на сторінках (default: True).
                     False = сканувати тільки seed URL без переходу за посиланнями

    Returns:
        Graph: Побудований граф веб-сайту

    Examples:
        Базове використання:
        >>> graph = crawl("https://example.com")
        >>> print(f"Знайдено {len(graph.nodes)} сторінок")

        Множинні точки входу (NEW):
        >>> graph = crawl(
        ...     seed_urls=[
        ...         "https://www.work.ua/jobs/vacancy1/",
        ...         "https://www.work.ua/jobs/vacancy2/",
        ...         "https://www.work.ua/jobs/vacancy3/",
        ...     ],
        ...     max_depth=3
        ... )

        Продовження існуючого краулінгу (NEW):
        >>> # День 1: початковий краулінг
        >>> graph1 = crawl("https://example.com")
        >>> # Зберегти граф...
        >>> 
        >>> # День 2: продовжити краулінг
        >>> graph2 = crawl(base_graph=graph1, max_pages=100)

        Комбінація: граф з сайтмапи + нові URL (NEW):
        >>> sitemap_graph = crawl_sitemap("https://example.com")
        >>> # Видалити непотрібні ноди...
        >>> filtered_graph = ... 
        >>> # Продовжити краулінг від залишкових
        >>> result = crawl(base_graph=filtered_graph, seed_urls=["https://example.com/new"])

        Distributed режим:
        >>> config = {
        ...     "broker": {"type": "redis", "host": "server.com", "port": 6379},
        ...     "database": {"type": "mongodb", "host": "server.com", "port": 27017}
        ... }
        >>> graph = crawl(
        ...     "https://example.com",
        ...     max_depth=5,
        ...     wrapper=config
        ... )
    """
    # Валідація вхідних параметрів
    if url is None and seed_urls is None and base_graph is None:
        raise ValueError(
            "Потрібно передати хоча б один з параметрів: url, seed_urls або base_graph"
        )

    # ========== DISTRIBUTED MODE ==========
    if wrapper is not None:
        from graph_crawler.api._distributed import distributed_crawl

        # Для distributed режиму потрібен хоча б один URL
        if url is None and seed_urls:
            url = seed_urls[0]  # Використовуємо перший URL як base

        return distributed_crawl(
            url=url,
            max_depth=max_depth,
            max_pages=max_pages,
            wrapper_config=wrapper,
            driver=driver,
            driver_config=driver_config,
            plugins=plugins,
            node_class=node_class,
            url_rules=url_rules,
            edge_strategy=edge_strategy,
            timeout=timeout,
        )

    # ========== LOCAL MODE ==========
    from graph_crawler.api._core import async_crawl_impl

    # Параметри для async_crawl_impl
    crawl_kwargs = dict(
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

    # Handle nested event loops (e.g., Jupyter, pytest-asyncio)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None:
        # Already inside an event loop
        # Strategy 1: Try nest_asyncio if available (recommended for Jupyter)
        try:
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(async_crawl_impl(**crawl_kwargs))
        except ImportError:
            pass
        
        # Strategy 2: Run in separate thread (fallback)
        # Use a shared executor to avoid creating new threads for each call
        import concurrent.futures
        
        def _run_in_new_loop():
            """Run async code in a fresh event loop in this thread."""
            return asyncio.run(async_crawl_impl(**crawl_kwargs))
        
        # ThreadPoolExecutor with max_workers=None uses optimal thread count
        with concurrent.futures.ThreadPoolExecutor(max_workers=None) as executor:
            future = executor.submit(_run_in_new_loop)
            try:
                # Timeout slightly longer than crawl timeout to allow cleanup
                result_timeout = (timeout + 30) if timeout else None
                return future.result(timeout=result_timeout)
            except concurrent.futures.TimeoutError:
                logger.warning(f"Crawl exceeded timeout in nested event loop")
                raise TimeoutError(f"Crawl operation timed out after {timeout}s")
    else:
        return asyncio.run(async_crawl_impl(**crawl_kwargs))


class Crawler(_BaseCrawler):
    """
    Синхронний Crawler для повторного використання.

    Простий клас без async/await - використовуй як звичайний Python об'єкт.

    Examples:
        Базове використання:
        >>> package_crawler = Crawler(max_depth=5)
        >>> graph = package_crawler.crawl("https://example.com")
        >>> package_crawler.close()

        Context manager (рекомендовано):
        >>> with Crawler(max_depth=5) as package_crawler:
        ...     graph1 = package_crawler.crawl("https://site1.com")
        ...     graph2 = package_crawler.crawl("https://site2.com")
    """

    def __init__(self, **kwargs):
        """Створює Crawler з default налаштуваннями."""
        super().__init__(**kwargs)
        logger.info(
            f"Crawler initialized: max_depth={self.max_depth}, max_pages={self.max_pages}"
        )

    def crawl(
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
        Краулить сайт - синхронно, без async/await.

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

        return crawl(
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

    def close(self) -> None:
        """Закриває ресурси."""
        if self._closed:
            return
        logger.info("Closing Crawler...")
        self._closed = True
        logger.info("Crawler closed")

    def __enter__(self) -> "Crawler":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Context manager exit."""
        self.close()
        return False

    def __repr__(self) -> str:
        status = "closed" if self._closed else "open"
        return (
            f"Crawler(max_depth={self.max_depth}, "
            f"max_pages={self.max_pages}, driver={self.driver}, status={status})"
        )


# SITEMAP API


def crawl_sitemap(
    url: str,
    *,
    max_urls: Optional[int] = None,
    include_urls: bool = True,
    timeout: Optional[int] = None,
    driver: Optional[DriverType] = None,
    driver_config: Optional[dict[str, Any]] = None,
    storage: Optional[StorageType] = None,
    storage_config: Optional[dict[str, Any]] = None,
    wrapper: Optional[dict] = None,
    url_rules: Optional[list[URLRule]] = None,
    max_sitemaps: Optional[int] = None,
    max_depth: Optional[int] = None,
    on_progress: Optional[EventCallback] = None,
    on_error: Optional[EventCallback] = None,
    on_completed: Optional[EventCallback] = None,
) -> Graph:
    r"""
    Краулінг sitemap структури сайту - СИНХРОННИЙ.

    Парсить robots.txt → знаходить sitemap → рекурсивно обробляє всі sitemap файли.

     DISTRIBUTED MODE: Додай `wrapper` для розподіленого краулінгу!

    Args:
        url: Базовий URL сайту (https://example.com)
        max_urls: Максимальна кількість URL для обробки (None = всі)
        include_urls: Чи додавати кінцеві URL до графу (False = тільки структура sitemap)
        timeout: Максимальний час краулінгу в секундах
        driver: Драйвер ("http", "async") або інстанс
        driver_config: Конфігурація драйвера
        storage: Storage ("memory", "json", "sqlite") або інстанс
        storage_config: Конфігурація storage
        wrapper: Конфігурація distributed crawling (broker + database)
        url_rules: Правила для фільтрації та пріоритизації sitemap URLs
        max_sitemaps: Максимальна кількість sitemap файлів (None = всі)
        max_depth: Максимальна глибина вкладеності sitemap (None = 10)
        on_progress: Callback для прогресу
        on_error: Callback для помилок
        on_completed: Callback для завершення

    Returns:
        Graph: Граф sitemap структури:
            - robots.txt (root)
            - sitemap_index.xml
            - sitemap-posts.xml (URLs: 100)
            - sitemap-pages.xml (URLs: 50)

    Examples:
        Базове використання:
        >>> graph = crawl_sitemap("https://example.com")
        >>> print(f"Знайдено {len(graph.nodes)} елементів")

        Тільки структура (без кінцевих URL):
        >>> graph = crawl_sitemap("https://example.com", include_urls=False)

        З лімітом URL:
        >>> graph = crawl_sitemap("https://example.com", max_urls=1000)

        З фільтрацією архівів:
        >>> from graph_crawler.domain.value_objects.models import URLRule
        >>> rules = [
        ...     URLRule(pattern=r'\.xml\.gz$', should_scan=False),  # Ігнорувати .gz
        ...     URLRule(pattern=r'sitemap-news', priority=10),  # Пріоритет новинам
        ... ]
        >>> graph = crawl_sitemap("https://example.com", url_rules=rules)

        З обмеженням кількості та глибини:
        >>> graph = crawl_sitemap(
        ...     "https://example.com",
        ...     max_sitemaps=50,  # Максимум 50 sitemap файлів
        ...     max_depth=3  # Максимум 3 рівні вкладеності
        ... )

        Distributed режим:
        >>> config = {
        ...     "broker": {"type": "redis", "host": "server.com", "port": 6379},
        ...     "database": {"type": "memory"}
        ... }
        >>> graph = crawl_sitemap("https://example.com", wrapper=config, max_urls=10000)
    """
    # ========== DISTRIBUTED MODE ==========
    if wrapper is not None:
        from graph_crawler.api._sitemap_distributed import distributed_crawl_sitemap

        return distributed_crawl_sitemap(
            url=url,
            max_urls=max_urls,
            include_urls=include_urls,
            wrapper_config=wrapper,
            driver=driver,
            driver_config=driver_config,
            timeout=timeout,
            url_rules=url_rules,
            max_sitemaps=max_sitemaps,
            max_depth=max_depth,
        )

    # ========== LOCAL MODE ==========
    return asyncio.run(
        _crawl_sitemap_impl(
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
    )


async def _crawl_sitemap_impl(
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
    """Async імплементація crawl_sitemap."""
    from graph_crawler.application.services import create_driver, create_storage
    from graph_crawler.application.use_cases.crawling.sitemap_spider import (
        SitemapSpider,
    )
    from graph_crawler.domain.events import EventBus
    from graph_crawler.domain.value_objects.configs import CrawlerConfig, DriverConfig

    logger.info(f"Starting sitemap crawl: {url}")
    logger.info(
        f"Config: max_urls={max_urls}, include_urls={include_urls}, timeout={timeout}, "
        f"url_rules={len(url_rules) if url_rules else 0}, max_sitemaps={max_sitemaps}, "
        f"max_depth={max_depth}"
    )

    config = CrawlerConfig(
        url=url,
        max_depth=max_depth or 3,
        max_pages=max_urls or 100000,
        driver=DriverConfig(**(driver_config or {})),
    )

    actual_driver = create_driver(driver, driver_config)
    actual_storage = create_storage(storage, storage_config)
    event_bus = EventBus()

    # Реєструємо callbacks
    if on_progress:
        from graph_crawler.domain.events import EventType

        event_bus.subscribe(EventType.PAGE_CRAWLED, lambda e: on_progress(e.data))
    if on_error:
        from graph_crawler.domain.events import EventType

        event_bus.subscribe(EventType.ERROR_OCCURRED, lambda e: on_error(e.data))
    if on_completed:
        from graph_crawler.domain.events import EventType

        event_bus.subscribe(
            EventType.SITEMAP_CRAWL_COMPLETED, lambda e: on_completed(e.data)
        )

    # Запускаємо SitemapSpider
    spider = SitemapSpider(
        config=config,
        driver=actual_driver,
        storage=actual_storage,
        event_bus=event_bus,
        include_urls=include_urls,
        max_urls=max_urls,
        url_rules=url_rules,
        max_sitemaps=max_sitemaps,
    )

    try:
        if timeout:
            graph = await asyncio.wait_for(spider.crawl(), timeout=timeout)
        else:
            graph = await spider.crawl()

        logger.info(f"Sitemap crawl completed: {spider.get_stats()}")
        return graph
    
    except asyncio.TimeoutError:
        logger.warning(f"Sitemap crawl timeout after {timeout}s, returning partial results")
        return spider.graph
    
    except asyncio.CancelledError:
        logger.warning("Sitemap crawl cancelled, returning partial results")
        return spider.graph

    finally:
        await spider.close()


__all__ = [
    "crawl",
    "crawl_sitemap",
    "Crawler",
]
