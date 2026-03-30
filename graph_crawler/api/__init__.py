"""Simple API для GraphCrawler.

Простий як requests, потужний як потрібно. Sync-First - не потрібно знати async/await!
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
