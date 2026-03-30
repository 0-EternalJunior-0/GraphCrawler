"""Crawl Engine плагіни - ML-керований краулінг.

Crawl Engine плагіни працюють на вищому рівні ніж Node плагіни і можуть:
"""

from graph_crawler.extensions.plugins.crawl_engine.base import (
    BaseEnginePlugin,
    EnginePluginContext,
    EnginePluginType,
)
from graph_crawler.extensions.plugins.crawl_engine.priority_provider import (
    EnginePriorityProvider,
)
from graph_crawler.extensions.plugins.crawl_engine.smart_crawl import (
    SmartCrawlEnginePlugin,
)
from graph_crawler.extensions.plugins.crawl_engine.vector_crawl import (
    VectorCrawlEnginePlugin,
)

__all__ = [
    "BaseEnginePlugin",
    "EnginePluginContext",
    "EnginePluginType",
    "EnginePriorityProvider",
    "SmartCrawlEnginePlugin",
    "VectorCrawlEnginePlugin",
]
