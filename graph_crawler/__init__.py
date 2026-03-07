"""GraphCrawler - Sync-First Web Crawler.

Sync-First - не потрібно знати async/await для базового використання.

Приклад:
    >>> import graph_crawler as gc
    >>> graph = gc.crawl("https://example.com")
    >>> print(f"Знайдено {len(graph.nodes)} сторінок")

З параметрами:
    >>> graph = gc.crawl("https://example.com", max_depth=5, max_pages=200, driver="playwright")

Reusable Crawler:
    >>> with gc.Crawler(max_depth=5) as package_crawler:
    ...     graph1 = package_crawler.crawl("https://site1.com")

Async:
    >>> graph = await gc.async_crawl("https://example.com")

Розширення: driver, storage, plugins, node_class, url_rules
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

# Пакет повинен встановлюватись через pip install або setup.py
from graph_crawler.api import AsyncCrawler, Crawler, async_crawl, crawl, crawl_sitemap
from graph_crawler.domain.entities.edge import Edge
from graph_crawler.domain.entities.graph import Graph
from graph_crawler.domain.entities.node import Node
from graph_crawler.domain.value_objects.models import (
    ContentType,
    EdgeCreationStrategy,
    URLRule,
)
from graph_crawler.domain.value_objects.settings import (
    CrawlerSettings,
    DriverSettings,
    StorageSettings,
)
from graph_crawler.extensions.plugins.node import BaseNodePlugin, NodePluginType
from graph_crawler.infrastructure.transport import HTTPDriver

try:
    from graph_crawler.infrastructure.transport import AsyncDriver
except ImportError:
    AsyncDriver = None

try:
    from graph_crawler.infrastructure.transport import PlaywrightDriver
except ImportError:
    PlaywrightDriver = None

from graph_crawler.api.client.client import GraphCrawlerClient
from graph_crawler.application.services import create_driver, create_storage
from graph_crawler.application.use_cases.crawling.dead_letter_queue import (
    DeadLetterQueue,
    FailedURL,
)
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

from graph_crawler.shared.constants import (
    DEFAULT_REQUEST_DELAY,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_USER_AGENT,
    MAX_DEPTH_DEFAULT,
    MAX_PAGES_DEFAULT,
)

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


# ==================== Shortcut Functions ====================

def save_graph(graph: Graph, filepath: str, format: str = "json") -> None:
    """
    Зберігає граф у файл (синхронно).

    Args:
        graph: Граф для збереження
        filepath: Шлях до файлу
        format: Формат файлу ("json" або "sqlite")

    Example:
        >>> graph = gc.crawl("https://example.com")
        >>> gc.save_graph(graph, "my_graph.json")
    """
    import asyncio

    from graph_crawler.application.dto.mappers import GraphMapper

    if format == "json":
        storage = JSONStorage(filepath)
    elif format == "sqlite":
        storage = SQLiteStorage(filepath)
    else:
        raise ValueError(f"Unknown format: {format}. Use 'json' or 'sqlite'")

    graph_dto = GraphMapper.to_dto(graph)
    asyncio.get_event_loop().run_until_complete(storage.save_graph(graph_dto))


def load_graph(filepath: str, format: str = "json") -> Graph:
    """
    Завантажує граф з файлу (синхронно).

    Args:
        filepath: Шлях до файлу
        format: Формат файлу ("json" або "sqlite")

    Returns:
        Завантажений граф

    Example:
        >>> graph = gc.load_graph("my_graph.json")
        >>> print(f"Loaded {len(graph)} nodes")
    """
    import asyncio

    from graph_crawler.application.dto.mappers import GraphMapper

    if format == "json":
        storage = JSONStorage(filepath)
    elif format == "sqlite":
        storage = SQLiteStorage(filepath)
    else:
        raise ValueError(f"Unknown format: {format}. Use 'json' or 'sqlite'")

    graph_dto = asyncio.get_event_loop().run_until_complete(storage.load_graph())
    return GraphMapper.to_domain(graph_dto)


def quick_stats(graph: Graph) -> str:
    """
    Повертає швидку статистику графу одним рядком.

    Args:
        graph: Граф для аналізу

    Returns:
        Форматований рядок зі статистикою

    Example:
        >>> graph = gc.crawl("https://example.com")
        >>> print(gc.quick_stats(graph))
        📊 47 nodes (45 scanned) | 156 edges
    """
    stats = graph.get_stats()
    return (
        f"📊 {stats['total_nodes']} nodes ({stats['scanned_nodes']} scanned) | "
        f"{stats['total_edges']} edges"
    )


__all__ = [
    # Shortcut functions
    "save_graph",
    "load_graph",
    "quick_stats",
    # Main API
    "crawl",
    "crawl_sitemap",
    "Crawler",
    "async_crawl",
    "AsyncCrawler",
    "Graph",
    "Node",
    "Edge",
    "URLRule",
    "EdgeCreationStrategy",
    "ContentType",
    "BaseNodePlugin",
    "NodePluginType",
    "CrawlerSettings",
    "DriverSettings",
    "StorageSettings",
    "HTTPDriver",
    "AsyncDriver",
    "PlaywrightDriver",
    "IDriver",
    "MemoryStorage",
    "JSONStorage",
    "SQLiteStorage",
    "IStorage",
    "StorageType",
    "create_driver",
    "create_storage",
    "GraphCrawlerClient",
    "DeadLetterQueue",
    "FailedURL",
    "ErrorHandler",
    "ErrorHandlerBuilder",
    "ErrorCategory",
    "ErrorSeverity",
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
    "celery",
    "crawl_page_task",
    "crawl_batch_task",
    "CeleryBatchSpider",
    "EasyDistributedCrawler",
]

# Auto-bootstrap при імпорті пакету (після всіх імпортів)
from graph_crawler.application.bootstrap import bootstrap
bootstrap()
