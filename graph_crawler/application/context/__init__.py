"""Context System для GraphCrawler.

Система контексту забезпечує:
"""

from graph_crawler.application.context.dependency_registry import (
    DependencyConfig,
    DependencyRegistry,
)
from graph_crawler.application.context.graph_context import (
    GraphContext,
    get_graph_context,
    set_graph_context,
)
from graph_crawler.application.context.merge_context import (
    MergeContext,
    MergeContextManager,
    get_current_merge_strategy,
    with_merge_strategy,
)

__all__ = [
    # Dependency Registry
    "DependencyRegistry",
    "DependencyConfig",
    # Merge Context
    "MergeContext",
    "MergeContextManager",
    "with_merge_strategy",
    "get_current_merge_strategy",
    # Graph Context
    "GraphContext",
    "get_graph_context",
    "set_graph_context",
]
