"""Simple API для GraphCrawler.

Простий як requests, потужний як потрібно. Sync-First - не потрібно знати async/await!

=====================================
ПРОСТИЙ СТАРТ (90% користувачів)
=====================================

    >>> import graph_crawler as gc
    >>>
    >>> # Один рядок - і готово!
    >>> graph = gc.crawl("https://example.com")
    >>> print(f"Знайдено {len(graph.nodes)} сторінок")

=====================================
SITEMAP CRAWLING
=====================================

    >>> # Краулінг через sitemap
    >>> graph = gc.crawl_sitemap("https://example.com")
    >>> print(f"Знайдено {len(graph.nodes)} сторінок")

    >>> # Distributed sitemap crawling
    >>> config = {"broker": {"type": "redis", "host": "server", "port": 6579}}
    >>> graph = gc.crawl_sitemap("https://example.com", wrapper=config, max_urls=10000)

=====================================
З ПАРАМЕТРАМИ
=====================================

    >>> graph = gc.crawl(
    ...     "https://example.com",
    ...     max_depth=5,
    ...     max_pages=200,
    ...     driver="playwright"
    ... )

=====================================
REUSABLE CRAWLER
=====================================

    >>> with gc.Crawler(max_depth=5) as crawler:
    ...     graph1 = crawler.crawl("https://site1.com")
    ...     graph2 = crawler.crawl("https://site2.com")

=====================================
ASYNC (для досвідчених)
=====================================

    >>> # Якщо вже працюєш з async кодом
    >>> graph = await gc.async_crawl("https://example.com")
    >>>
    >>> # Паралельний краулінг
    >>> async with gc.AsyncCrawler() as crawler:
    ...     graphs = await asyncio.gather(
    ...         crawler.crawl("https://site1.com"),
    ...         crawler.crawl("https://site2.com"),
    ...     )
"""

from graph_crawler.api.async_ import (
    AsyncCrawler,
    async_crawl,
)
from graph_crawler.api.sync import (
    Crawler,
    crawl,
    crawl_sitemap,
)

__all__ = [
    # Sync API (рекомендовано для більшості)
    "crawl",
    "crawl_sitemap",
    "Crawler",
    # Async API (для досвідчених)
    "async_crawl",
    "AsyncCrawler",
]
