"""Application Layer - Use Cases та Application Services.

Містить:
- bootstrap: Application initialization (Clean Architecture)
- context: Система контексту для управління залежностями та merge strategies
- dto: Data Transfer Objects для ізоляції Domain Layer
- use_cases: Бізнес-логіка (Spider, Processors, etc.)

IMPORTANT: Call bootstrap() before using graph_crawler:
    from graph_crawler.application.bootstrap import bootstrap
    bootstrap()
"""

from graph_crawler.application.bootstrap import bootstrap, is_bootstrapped, require_bootstrap
from graph_crawler.application.context import (
    DependencyConfig,
    DependencyRegistry,
    GraphContext,
    MergeContext,
    MergeContextManager,
    get_current_merge_strategy,
    get_graph_context,
    set_graph_context,
    with_merge_strategy,
)

__all__ = [
    # Bootstrap
    "bootstrap",
    "is_bootstrapped",
    "require_bootstrap",
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
