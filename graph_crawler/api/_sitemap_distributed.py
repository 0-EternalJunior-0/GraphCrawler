"""
Distributed Sitemap Crawling через Celery.

Парсить robots.txt → sitemap → розподіляє URL обробку на workers.
"""

import logging
import time
from typing import Any, Optional

from graph_crawler.api._shared import DriverType
from graph_crawler.application.services import create_driver, create_storage
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
) -> Graph:
    """
    Distributed sitemap crawling через Celery.

    Процес:
    1. Парсить robots.txt локально
    2. Знаходить всі sitemap URLs
    3. Розподіляє обробку sitemap на Celery workers
    4. Workers парсять sitemap та повертають URLs
    5. URLs обробляються через CeleryBatchSpider

    Args:
        url: Базовий URL сайту
        max_urls: Максимальна кількість URL
        include_urls: Чи краулити кінцеві URL
        wrapper_config: Конфігурація broker/database
        driver: Драйвер для краулінгу
        driver_config: Конфігурація драйвера
        timeout: Таймаут в секундах

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
    logger.info(f"   URL: {url}")
    logger.info(f"   Max URLs: {max_urls or 'unlimited'}")
    logger.info(f"   Include URLs content: {include_urls}")
    logger.info(f"   Timeout: {timeout or 'none'}s")

    # ========== ПАРСИМО BROKER CONFIG ==========
    broker_config = wrapper_config.get("broker", {})
    broker_type = broker_config.get("type", "redis")
    broker_host = broker_config.get("host", "localhost")
    broker_port = broker_config.get("port", 6379)

    broker_url = f"{broker_type}://{broker_host}:{broker_port}/0"
    backend_url = f"{broker_type}://{broker_host}:{broker_port}/1"

    logger.info(f"   Broker: {broker_url}")

    # ========== КРОК 1: ПАРСИМО ROBOTS.TXT ==========
    logger.info("\n Step 1: Parsing robots.txt...")

    parser = SitemapParser()
    graph = Graph()
    event_bus = EventBus()
    processor = SitemapProcessor(graph=graph, event_bus=event_bus, include_urls=False)

    try:
        sitemap_data = parser.parse_from_robots(url)
        sitemap_urls = sitemap_data.get("sitemap_urls", [])
        all_urls = sitemap_data.get("urls", [])

        logger.info(f"   Found {len(sitemap_urls)} sitemap(s)")
        logger.info(f"   Found {len(all_urls)} URLs in sitemaps")

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
        logger.error(f"   Error parsing robots.txt: {e}")
        all_urls = []

    finally:
        parser.close()

    # ========== КРОК 2: ОБРОБЛЯЄМО URLs ЧЕРЕЗ DISTRIBUTED ==========
    if include_urls and all_urls:
        logger.info(f"\n Step 2: Distributed crawl of {len(all_urls)} URLs...")

        # Обмежуємо кількість URL
        if max_urls and len(all_urls) > max_urls:
            all_urls = all_urls[:max_urls]
            logger.info(f"   Limited to {max_urls} URLs")

        # Використовуємо CeleryBatchSpider для краулінгу URLs
        from graph_crawler.application.use_cases.crawling.celery_batch_spider import (
            CeleryBatchSpider,
        )
        from graph_crawler.infrastructure.persistence import MemoryStorage

        # Створюємо конфіг
        actual_driver = create_driver(driver or "async", driver_config)
        storage = MemoryStorage()

        # Визначаємо batch_size
        batch_size = wrapper_config.get("batch_size")
        if batch_size is None:
            if hasattr(actual_driver, "max_concurrent"):
                batch_size = actual_driver.max_concurrent
            else:
                batch_size = 24

        crawler_config = CrawlerConfig(
            url=url,
            max_depth=1,  # Тільки один рівень - самі URL
            max_pages=len(all_urls),
            driver=DriverConfig(**(driver_config or {})),
            celery=CeleryConfig(
                enabled=True,
                broker_url=broker_url,
                backend_url=backend_url,
                workers=wrapper_config.get("workers", 10),
                task_time_limit=wrapper_config.get("task_time_limit", 600),
                worker_prefetch_multiplier=wrapper_config.get(
                    "worker_prefetch_multiplier", 4
                ),
            ),
        )

        spider = CeleryBatchSpider(
            config=crawler_config,
            driver=actual_driver,
            storage=storage,
            batch_size=batch_size,
            timeout=timeout,
        )

        # Додаємо URLs до черги
        logger.info(f"   Adding {len(all_urls)} URLs to queue...")
        for page_url in all_urls:
            spider._add_to_queue(page_url, depth=2)

        # Запускаємо обробку
        try:
            crawled_graph = spider.crawl()

            # Мержимо графи
            for node in crawled_graph.nodes.values():
                graph.add_node(node)
            for edge in crawled_graph.edges:
                graph.add_edge(edge)

            logger.info(f"   Crawled {len(crawled_graph.nodes)} pages")

        except Exception as e:
            logger.error(f"   Error in distributed crawl: {e}")

    # ========== СТАТИСТИКА ==========
    duration = time.time() - start_time
    stats = graph.get_stats()

    logger.info("\n" + "=" * 60)
    logger.info(" SITEMAP CRAWL COMPLETED")
    logger.info("=" * 60)
    logger.info(f"   Duration: {duration:.2f}s")
    logger.info(f"   Total nodes: {stats.get('total_nodes', 0)}")
    logger.info(f"   Total edges: {stats.get('total_edges', 0)}")
    logger.info(f"   Sitemaps: {len(sitemap_urls) if 'sitemap_urls' in dir() else 0}")
    logger.info(f"   URLs processed: {len(all_urls) if 'all_urls' in dir() else 0}")
    logger.info("=" * 60)

    return graph


__all__ = ["distributed_crawl_sitemap"]
