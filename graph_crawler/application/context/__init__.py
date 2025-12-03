"""Context System для GraphCrawler.

Система контексту забезпечує:
1. DependencyRegistry - управління залежностями при десеріалізації
2. MergeContext - динамічна зміна merge_strategy під час виконання
3. GraphContext - об'єднаний контекст для роботи з графом

Принципи:
- Максимальна ізоляція Domain Layer через DTO
- Легке перевизначення на будь-якому рівні
- Thread-safe операції
- Zero backward compatibility - чиста архітектура

Приклад використання:
    >>> from graph_crawler.application.context import (
    ...     DependencyRegistry,
    ...     MergeContext,
    ...     GraphContext,
    ...     with_merge_strategy,
    ... )
    >>>
    >>> # Реєстрація дефолтних залежностей
    >>> DependencyRegistry.set_default_plugin_manager(my_plugin_manager)
    >>> DependencyRegistry.set_default_tree_parser(my_parser)
    >>>
    >>> # Створення контексту для роботи з графом
    >>> ctx = GraphContext(
    ...     plugin_manager=custom_pm,  # Override default
    ...     default_merge_strategy='merge',
    ... )
    >>>
    >>> # Динамічна зміна стратегії
    >>> with ctx.merge_strategy('newest'):
    ...     result = graph1 + graph2  # Використає 'newest'
    ... # Повернеться до 'merge'
    >>>
    >>> # Або через декоратор
    >>> with with_merge_strategy('last'):
    ...     result = graph1 + graph2
"""

from graph_crawler.application.context.dependency_registry import (
    DependencyRegistry,
    DependencyConfig,
)
from graph_crawler.application.context.merge_context import (
    MergeContext,
    MergeContextManager,
    with_merge_strategy,
    get_current_merge_strategy,
)
from graph_crawler.application.context.graph_context import (
    GraphContext,
    get_graph_context,
    set_graph_context,
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
