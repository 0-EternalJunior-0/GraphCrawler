"""
Distributed Sitemap Crawling через Celery.

Парсить robots.txt → sitemap → розподіляє URL обробку на workers.
"""

import logging
import time
from typing import Any, Optional

from graph_crawler.api._shared import DriverType
from graph_crawler.application.services import create_driver
from graph_crawler.domain.entities.graph import Graph
from graph_crawler.domain.value_objects.configs import (
    CeleryConfig,
    CrawlerConfig,
    DriverConfig,
)

logger = logging.getLogger(__name__)


def distributed_crawl_sitemap(
    url: str,
    *,
    max_urls: Optional[int] = None,
    include_urls: bool = True,
    wrapper_config: dict,
    driver: Optional[DriverType] = None,
    driver_config: Optional[dict[str, Any]] = None,
    timeout: Optional[int] = None,
    url_rules: Optional[list] = None,
    max_sitemaps: Optional[int] = None,
    max_depth: Optional[int] = None,
) -> Graph:
    """
    Distributed sitemap crawling через Celery.

    Returns:
        Graph з sitemap структурою та (опціонально) кінцевими сторінками
    """
    from graph_crawler.application.use_cases.crawling.sitemap_parser import (
        SitemapParser,
    )
    from graph_crawler.application.use_cases.crawling.sitemap_processor import (
        SitemapProcessor,
    )
    from graph_crawler.domain.entities.graph import Graph
    from graph_crawler.domain.events import EventBus

    start_time = time.time()
    logger.info("=" * 60)
    logger.info("  DISTRIBUTED SITEMAP CRAWL")
    logger.info("=" * 60)
    logger.info("   URL: %s", url)
    logger.info("   Max URLs: %s", max_urls or "unlimited")
    logger.info("   Include URLs content: %s", include_urls)
    logger.info("   Timeout: %ss", timeout or "none")
    broker_config = wrapper_config.get("broker", {})
    broker_type = broker_config.get("type", "redis")
    broker_host = broker_config.get("host", "localhost")
    broker_port = broker_config.get("port", 6379)

    broker_url = f"{broker_type}://{broker_host}:{broker_port}/0"
    backend_url = f"{broker_type}://{broker_host}:{broker_port}/1"

    logger.info("   Broker: %s", broker_url)
    if url_rules:
        logger.info("   URL rules: %d rules", len(url_rules))
    if max_sitemaps:
        logger.info("   Max sitemaps: %s", max_sitemaps)
    if max_depth:
        logger.info("   Max depth: %s", max_depth)
    logger.info("\n Step 1: Parsing robots.txt...")

    parser = SitemapParser()
    graph = Graph()
    event_bus = EventBus()
    processor = SitemapProcessor(graph=graph, event_bus=event_bus, include_urls=False)

    # Ініціалізуємо змінні перед try блоком для уникнення reference before assignment
    sitemap_urls = []
    all_urls = []

    try:
        sitemap_data = parser.parse_from_robots(url)
        sitemap_urls = sitemap_data.get("sitemap_urls", [])
        all_urls = sitemap_data.get("urls", [])

        # Застосовуємо max_sitemaps якщо вказано
        if max_sitemaps and len(sitemap_urls) > max_sitemaps:
            logger.info("   Limiting sitemaps from %d to %d", len(sitemap_urls), max_sitemaps)
            sitemap_urls = sitemap_urls[:max_sitemaps]

        logger.info("   Found %d sitemap(s)", len(sitemap_urls))
        logger.info("   Found %d URLs in sitemaps", len(all_urls))

        # Створюємо nodes для robots.txt та sitemaps
        from urllib.parse import urljoin

        robots_url = urljoin(url, "/robots.txt")
        processor.create_robots_node(
            url=robots_url,
            sitemap_urls=sitemap_urls,
        )

        for sitemap_url in sitemap_urls:
            processor.create_sitemap_node(
                url=sitemap_url,
                parent_url=robots_url,
                url_list=[],
                depth=1,
            )

    except Exception as e:
        logger.error("   Error parsing robots.txt: %s", e)
        # Змінні вже ініціалізовані вище, але явно скидаємо на випадок часткової помилки
        all_urls = []
        sitemap_urls = []

    finally:
        # parser.close() є async, тому викликаємо через asyncio
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Якщо вже є event loop - просто ігноруємо close
                pass
            else:
                loop.run_until_complete(parser.close())
        except RuntimeError:
            # Якщо немає event loop - створюємо новий
            asyncio.run(parser.close())
    if include_urls and all_urls:
        logger.info("\n Step 2: Distributed crawl of %d URLs...", len(all_urls))

        # Обмежуємо кількість URL
        if max_urls and len(all_urls) > max_urls:
            all_urls = all_urls[:max_urls]
            logger.info("   Limited to %d URLs", max_urls)

        # Використовуємо CeleryBatchSpider для краулінгу URLs
        from graph_crawler.application.use_cases.crawling.celery_batch_spider import (
            CeleryBatchSpider,
        )
        from graph_crawler.infrastructure.persistence import MemoryStorage

        actual_driver = create_driver(driver or "async", driver_config)
        storage = MemoryStorage()

        # Визначаємо batch_size
        batch_size = wrapper_config.get("batch_size")
        if batch_size is None:
            # Використовуємо getattr для безпечного доступу
            max_concurrent = getattr(actual_driver, "max_concurrent", None)
            if max_concurrent is not None:
                batch_size = max_concurrent
            else:
                batch_size = 24

        crawler_config = CrawlerConfig(
            url=url,
            max_depth=1,
            max_pages=len(all_urls),
            driver=DriverConfig(**(driver_config or {})),
            celery=CeleryConfig(
                enabled=True,
                broker_url=broker_url,
                backend_url=backend_url,
                workers=wrapper_config.get("workers", 10),
                task_time_limit=wrapper_config.get("task_time_limit", 600),
                worker_prefetch_multiplier=wrapper_config.get("worker_prefetch_multiplier", 4),
            ),
        )

        spider = CeleryBatchSpider(
            config=crawler_config,
            driver=actual_driver,
            storage=storage,
            batch_size=batch_size,
            timeout=timeout,
        )

        # CeleryBatchSpider використовує crawl() для повного краулінгу з root URL.
        # Для sitemap сценарію нам потрібно обробити конкретний список URLs.
        # Використовуємо внутрішні методи spider для batch обробки.
        logger.info("   Processing %d URLs via batch tasks...", len(all_urls))

        # Створюємо список URLs з depth=2 для обробки
        urls_to_crawl = [(page_url, 2) for page_url in all_urls]

        # Запускаємо batch обробку
        try:
            spider.start_time = time.time()

            # Серіалізуємо конфігурацію для передачі воркерам
            config_dict = spider._serialize_config()

            # Створюємо batches та виконуємо tasks
            batches = spider._create_batches(urls_to_crawl)
            spider.total_batches_sent = len(batches)

            results = spider._execute_batch_tasks(batches, config_dict)

            # Обробляємо результати
            spider._process_batch_results(results)

            crawled_graph = spider.graph

            # Мержимо графи (streaming через iter_nodes)
            for node in crawled_graph.iter_nodes():
                graph.add_node(node)
            for edge in crawled_graph.iter_edges():
                graph.add_edge(edge)

            logger.info("   Crawled %d pages", len(crawled_graph.nodes))

        except Exception as e:
            logger.error("   Error in distributed crawl: %s", e)
    duration = time.time() - start_time
    stats = graph.get_stats()

    logger.info("\n" + "=" * 60)
    logger.info(" SITEMAP CRAWL COMPLETED")
    logger.info("=" * 60)
    logger.info("   Duration: %.2fs", duration)
    logger.info("   Total nodes: %d", stats.get("total_nodes", 0))
    logger.info("   Total edges: %d", stats.get("total_edges", 0))
    logger.info("   Sitemaps: %d", len(sitemap_urls) if "sitemap_urls" in dir() else 0)
    logger.info("   URLs processed: %d", len(all_urls) if "all_urls" in dir() else 0)
    logger.info("=" * 60)

    return graph


__all__ = ["distributed_crawl_sitemap"]
