"""Application Layer - Use Cases та Application Services.

Містить:
- context: Система контексту для управління залежностями та merge strategies
- dto: Data Transfer Objects для ізоляції Domain Layer
- use_cases: Бізнес-логіка (Spider, Processors, etc.)
"""

from graph_crawler.application.context import (
    DependencyRegistry,
    DependencyConfig,
    MergeContext,
    MergeContextManager,
    GraphContext,
    with_merge_strategy,
    get_current_merge_strategy,
    get_graph_context,
    set_graph_context,
)

__all__ = [
    # Context System
    "DependencyRegistry",
    "DependencyConfig",
    "MergeContext",
    "MergeContextManager",
    "GraphContext",
    "with_merge_strategy",
    "get_current_merge_strategy",
    "get_graph_context",
    "set_graph_context",
]
