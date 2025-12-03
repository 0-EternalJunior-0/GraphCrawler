"""GraphCrawler - Sync-First Web Crawler.

Принцип: "Просто для початківців, потужно для експертів" Sync-First - не потрібно знати async/await!

=====================================
ПРОСТИЙ СТАРТ (90% користувачів)
=====================================

    >>> import graph_crawler as gc
    >>>
    >>> # Один рядок - і готово! Без async/await!
    >>> graph = gc.crawl("https://example.com")
    >>> print(f"Знайдено {len(graph.nodes)} сторінок")

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
    >>> # Паралельний краулінг декількох сайтів
    >>> async with gc.AsyncCrawler() as crawler:
    ...     graphs = await asyncio.gather(
    ...         crawler.crawl("https://site1.com"),
    ...         crawler.crawl("https://site2.com"),
    ...     )

=====================================
EXTENSION POINTS
=====================================

- driver: "http", "async", "playwright", "stealth" або CustomDriver()
- storage: "memory", "json", "sqlite", "postgresql", "mongodb" або CustomStorage()
- plugins: [Plugin1(), Plugin2(), ...]
- node_class: CustomNode (для додаткових полів)
- url_rules: [URLRule(...), ...]

=====================================
ВЕРСІЯ: Sync-First Architecture
=====================================
"""

# =====================================
# SIMPLE API (Рекомендовано)
# =====================================
from graph_crawler.api import AsyncCrawler, Crawler, async_crawl, crawl, crawl_sitemap
from graph_crawler.domain.entities.edge import Edge
from graph_crawler.domain.entities.graph import Graph

# =====================================
# Domain Entities (Core Classes)
# =====================================
from graph_crawler.domain.entities.node import Node

# Моделі з нової структури
from graph_crawler.domain.value_objects.models import EdgeCreationStrategy, URLRule

# =====================================
# Extensions - Plugins
# =====================================
from graph_crawler.extensions.plugins.node import BaseNodePlugin, NodePluginType

# =====================================
# Infrastructure - Drivers
# =====================================
from graph_crawler.infrastructure.transport import HTTPDriver

# Опціональні драйвери
try:
    from graph_crawler.infrastructure.transport import AsyncDriver
except ImportError:
    AsyncDriver = None

try:
    from graph_crawler.infrastructure.transport import PlaywrightDriver
except ImportError:
    PlaywrightDriver = None

# =====================================
# Client (API Layer)
# =====================================
from graph_crawler.api.client.client import GraphCrawlerClient

# =====================================
# Application Services (Factories)
# =====================================
from graph_crawler.application.services import create_driver, create_storage

# =====================================
# Application Use Cases
# =====================================
from graph_crawler.application.use_cases.crawling.dead_letter_queue import (
    DeadLetterQueue,
    FailedURL,
)

# =====================================
# Domain Interfaces (для type hints)
# =====================================
from graph_crawler.domain.interfaces.driver import IDriver
from graph_crawler.domain.interfaces.storage import IStorage
from graph_crawler.infrastructure.persistence import (
    JSONStorage,
    MemoryStorage,
    SQLiteStorage,
)
from graph_crawler.infrastructure.persistence.base import StorageType
from graph_crawler.shared.error_handling.error_handler import (
    ErrorCategory,
    ErrorHandler,
    ErrorHandlerBuilder,
    ErrorSeverity,
)

# =====================================
# Shared - Exceptions
# =====================================
from graph_crawler.shared.exceptions import (
    ConfigurationError,
    CrawlerError,
    DriverError,
    FetchError,
    GraphCrawlerError,
    InvalidURLError,
    LoadError,
    MaxDepthReachedError,
    MaxPagesReachedError,
    SaveError,
    StorageError,
    URLBlockedError,
    URLError,
)

try:
    from importlib.metadata import version

    __version__ = version("graph-crawler")
except ImportError:
    from graph_crawler.__version__ import __version__

__author__ = "0-EternalJunior-0"

# =====================================
# Backward Compatibility - Constants
# =====================================
from graph_crawler.shared.constants import (
    DEFAULT_REQUEST_DELAY,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_USER_AGENT,
    MAX_DEPTH_DEFAULT,
    MAX_PAGES_DEFAULT,
)

# =====================================
# Celery для distributed crawling
# =====================================
try:
    from graph_crawler.infrastructure.messaging import (
        EasyDistributedCrawler,
        celery,
        crawl_batch_task,
        crawl_page_task,
    )
except ImportError:
    celery = None
    crawl_page_task = None
    crawl_batch_task = None
    EasyDistributedCrawler = None

try:
    from graph_crawler.application.use_cases.crawling.celery_batch_spider import (
        CeleryBatchSpider,
    )
except ImportError:
    CeleryBatchSpider = None

__all__ = [
    # Simple API (Sync-First)
    "crawl",
    "crawl_sitemap",
    "Crawler",
    # Async API (advanced)
    "async_crawl",
    "AsyncCrawler",
    # Core
    "Graph",
    "Node",
    "Edge",
    "URLRule",
    "EdgeCreationStrategy",
    # Plugins
    "BaseNodePlugin",
    "NodePluginType",
    # Drivers
    "HTTPDriver",
    "AsyncDriver",
    "PlaywrightDriver",
    "IDriver",
    # Storage
    "MemoryStorage",
    "JSONStorage",
    "SQLiteStorage",
    "IStorage",
    "StorageType",
    # Factories
    "create_driver",
    "create_storage",
    # Client
    "GraphCrawlerClient",
    # Dead Letter Queue & Error Handler
    "DeadLetterQueue",
    "FailedURL",
    "ErrorHandler",
    "ErrorHandlerBuilder",
    "ErrorCategory",
    "ErrorSeverity",
    # Exceptions
    "GraphCrawlerError",
    "ConfigurationError",
    "URLError",
    "InvalidURLError",
    "URLBlockedError",
    "CrawlerError",
    "MaxPagesReachedError",
    "MaxDepthReachedError",
    "DriverError",
    "FetchError",
    "StorageError",
    "SaveError",
    "LoadError",
    # Celery (distributed crawling)
    "celery",
    "crawl_page_task",
    "crawl_batch_task",
    "CeleryBatchSpider",
    "EasyDistributedCrawler",
]
