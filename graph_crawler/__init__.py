"""GraphCrawler - Sync-First Web Crawler.

>>> import graph_crawler as gc
>>> graph = gc.crawl("https://example.com")
>>> print(f"Знайдено {len(graph.nodes)} сторінок")

З параметрами:
>>> graph = gc.crawl("https://example.com", max_depth=5, max_pages=200, driver="playwright")

Async:
>>> graph = await gc.async_crawl("https://example.com")
"""

from __future__ import annotations

from graph_crawler.api import AsyncCrawler, Crawler, async_crawl, crawl, crawl_sitemap
from graph_crawler.domain.entities.edge import Edge
from graph_crawler.domain.entities.graph import Graph
from graph_crawler.domain.entities.node import Node
from graph_crawler.domain.value_objects.models import (
    ContentType,
    EdgeCreationStrategy,
    Rule,
    RuleScope,
    SmartURLRule,
    URLRule,
    build_smart_rules,
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
from graph_crawler.application.services.exporters.edge_exporter import EdgeExporter
from graph_crawler.application.services.exporters.node_exporter import NodeExporter
from graph_crawler.application.use_cases.crawling.dead_letter_queue import (
    DeadLetterQueue,
    FailedURL,
)
from graph_crawler.application.use_cases.graph_export import GraphExportUseCase
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


def save_graph(graph: Graph, filepath: str, format: str = "json") -> None:
    """Зберігає граф у файл. При low_memory_mode об'єднує evicted ноди з RAM."""
    import asyncio

    async def _save_and_close():
        await async_save_graph(graph, filepath, format)

    try:
        asyncio.get_running_loop()
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(lambda: asyncio.run(_save_and_close()))
            future.result()
    except RuntimeError:
        asyncio.run(_save_and_close())


async def async_save_graph(graph: Graph, filepath: str, format: str = "json") -> None:
    """Асинхронно зберігає граф. При low_memory_mode об'єднує evicted ноди."""
    import logging

    from graph_crawler.application.dto.mappers import GraphMapper
    from graph_crawler.application.dto.mappers.edge_mapper import EdgeMapper
    from graph_crawler.application.dto.mappers.node_mapper import NodeMapper
    from graph_crawler.shared.dto import GraphDTO, GraphStatsDTO

    logger = logging.getLogger(__name__)

    if graph._low_memory_mode and graph._eviction_storage:
        eviction_stats = graph._eviction_storage.get_stats()
        evicted_nodes_count = eviction_stats.get("evicted_nodes", 0)
        evicted_edges_count = eviction_stats.get("evicted_edges", 0)

        logger.info(
            "LOW-MEMORY MODE: Merging %d evicted nodes and %d evicted edges with %d RAM nodes",
            evicted_nodes_count,
            evicted_edges_count,
            len(graph._nodes),
        )

        ram_nodes_dto = NodeMapper.to_dto_list(list(graph.iter_nodes()))
        ram_edges_dto = EdgeMapper.to_dto_list(list(graph.iter_edges()))

        evicted_urls = graph._eviction_storage.get_all_evicted_urls()
        evicted_nodes_dto = []

        batch_size = 1000
        evicted_urls_list = list(evicted_urls)

        for i in range(0, len(evicted_urls_list), batch_size):
            batch_urls = evicted_urls_list[i : i + batch_size]
            batch_data = graph._eviction_storage.load_nodes_batch_sync(batch_urls)

            for _url, node_data in batch_data.items():
                from datetime import datetime, timezone

                from graph_crawler.shared.dto import NodeDTO

                node_dto = NodeDTO(
                    node_id=node_data["node_id"],
                    url=node_data["url"],
                    depth=node_data["depth"],
                    scanned=node_data["scanned"],
                    should_scan=True,
                    can_create_edges=True,
                    metadata=node_data.get("metadata", {}),
                    user_data=node_data.get("user_data", {}),
                    response_status=node_data.get("response_status"),
                    content_hash=node_data.get("content_hash"),
                    simhash=node_data.get("simhash"),
                    priority=node_data.get("priority", 0),
                    created_at=datetime.now(timezone.utc),
                    lifecycle_stage="scanned" if node_data["scanned"] else "url_stage",
                )
                evicted_nodes_dto.append(node_dto)

        conn = graph._eviction_storage._get_connection()
        evicted_edges_rows = conn.execute("SELECT * FROM evicted_edges").fetchall()
        evicted_edges_dto = []

        import json

        from graph_crawler.shared.dto import EdgeDTO

        for row in evicted_edges_rows:
            edge_dto = EdgeDTO(
                edge_id=row["edge_id"],
                source_node_id=row["source_node_id"],
                target_node_id=row["target_node_id"],
                metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                created_at=row["created_at"] or datetime.now(timezone.utc).isoformat(),
            )
            evicted_edges_dto.append(edge_dto)

        all_nodes_by_url = {}
        for node_dto in ram_nodes_dto:
            all_nodes_by_url[node_dto.url] = node_dto
        for node_dto in evicted_nodes_dto:
            if node_dto.url not in all_nodes_by_url:
                all_nodes_by_url[node_dto.url] = node_dto

        all_nodes_dto = list(all_nodes_by_url.values())

        all_edges_by_key = {}
        for edge_dto in ram_edges_dto:
            key = (edge_dto.source_node_id, edge_dto.target_node_id)
            all_edges_by_key[key] = edge_dto
        for edge_dto in evicted_edges_dto:
            key = (edge_dto.source_node_id, edge_dto.target_node_id)
            if key not in all_edges_by_key:
                all_edges_by_key[key] = edge_dto

        all_edges_dto = list(all_edges_by_key.values())

        scanned_count = sum(1 for n in all_nodes_dto if n.scanned)
        depths = [n.depth for n in all_nodes_dto]

        stats = GraphStatsDTO(
            total_nodes=len(all_nodes_dto),
            scanned_nodes=scanned_count,
            unscanned_nodes=len(all_nodes_dto) - scanned_count,
            total_edges=len(all_edges_dto),
            avg_depth=sum(depths) / len(depths) if depths else 0.0,
            max_depth=max(depths) if depths else 0,
        )

        graph_dto = GraphDTO(nodes=all_nodes_dto, edges=all_edges_dto, stats=stats)

        logger.info(
            "Merged graph: %d total nodes, %d total edges",
            len(all_nodes_dto),
            len(all_edges_dto),
        )
    else:
        graph_dto = GraphMapper.to_dto(graph)

    if format == "json":
        storage = JSONStorage(filepath)
    elif format == "sqlite":
        storage = SQLiteStorage(filepath)
    else:
        raise ValueError(f"Unknown format: {format}. Use 'json' or 'sqlite'")

    try:
        await storage.save_graph(graph_dto)
    finally:
        if hasattr(storage, "close"):
            await storage.close()


def load_graph(filepath: str, format: str = "json") -> Graph:
    """Завантажує граф з файлу."""
    import asyncio

    from graph_crawler.application.dto.mappers import GraphMapper

    result_holder = [None]

    async def _load_and_close():
        if format == "json":
            storage = JSONStorage(filepath)
        elif format == "sqlite":
            storage = SQLiteStorage(filepath)
        else:
            raise ValueError(f"Unknown format: {format}. Use 'json' or 'sqlite'")

        try:
            result_holder[0] = await storage.load_graph()
        finally:
            if hasattr(storage, "close"):
                await storage.close()

    try:
        asyncio.get_running_loop()
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(lambda: asyncio.run(_load_and_close()))
            future.result()
    except RuntimeError:
        asyncio.run(_load_and_close())

    graph_dto = result_holder[0]
    if graph_dto is None:
        raise ValueError(f"Could not load graph from {filepath}")
    return GraphMapper.to_domain(graph_dto)


def quick_stats(graph: Graph) -> str:
    """Швидка статистика графу одним рядком."""
    stats = graph.get_stats()
    total = stats["total_nodes"]
    scanned = stats["scanned_nodes"]
    edges = stats["total_edges"]
    return f"📊 {total} nodes ({scanned} scanned) | {edges} edges"


__all__ = [
    "save_graph",
    "async_save_graph",
    "load_graph",
    "quick_stats",
    "crawl",
    "crawl_sitemap",
    "Crawler",
    "async_crawl",
    "AsyncCrawler",
    "Graph",
    "Node",
    "Edge",
    "URLRule",
    "SmartURLRule",
    "RuleScope",
    "Rule",
    "build_smart_rules",
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
    "GraphExportUseCase",
    "NodeExporter",
    "EdgeExporter",
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

from graph_crawler.application.bootstrap import bootstrap

bootstrap()
