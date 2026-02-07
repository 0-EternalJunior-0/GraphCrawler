"""GraphContext - Об'єднаний контекст для роботи з графом.

Об'єднує DependencyRegistry та MergeContext в єдиний інтерфейс
для зручної роботи з графом.

Приклад:
    >>> ctx = GraphContext(
    ...     plugin_manager=my_pm,
    ...     default_merge_strategy='merge',
    ... )
    >>>
    >>> # Встановлюємо як глобальний контекст
    >>> set_graph_context(ctx)
    >>>
    >>> # Тепер всі операції використовують цей контекст
    >>> graph_dto = await storage.load_graph()
    >>> graph = GraphMapper.to_domain(graph_dto, context=ctx.to_dict())
    >>>
    >>> # Локальна зміна стратегії
    >>> with ctx.merge_strategy('newest'):
    ...     result = graph1 + graph2
"""

import logging
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Type

logger = logging.getLogger(__name__)


@dataclass
class GraphContext:
    """
    Контекст для роботи з графом.
    
    Об'єднує:
    - Залежності для десеріалізації (plugin_manager, tree_parser, hash_strategy)
    - Класи для створення (node_class, edge_class)
    - Стратегію merge
    
    Attributes:
        plugin_manager: Plugin manager для Node
        tree_parser: Tree parser для HTML
        hash_strategy: Стратегія hash для content_hash
        node_class: Клас Node для створення
        edge_class: Клас Edge для створення
        default_merge_strategy: Дефолтна стратегія merge
        custom_merge_fn: Кастомна функція для 'custom' стратегії
    """
    plugin_manager: Optional[Any] = None
    tree_parser: Optional[Any] = None
    hash_strategy: Optional[Any] = None
    node_class: Optional[Type] = None
    edge_class: Optional[Type] = None
    default_merge_strategy: str = "last"
    custom_merge_fn: Optional[Callable] = None
    
    # Private - для tracking зміни стратегії
    _strategy_stack: list = field(default_factory=list, repr=False)
    
    def __post_init__(self):
        """Ініціалізація після створення."""
        # Заповнюємо з DependencyRegistry якщо не передано
        from graph_crawler.application.context.dependency_registry import DependencyRegistry
        
        defaults = DependencyRegistry.get_context()
        
        if self.plugin_manager is None:
            self.plugin_manager = defaults.get('plugin_manager')
        if self.tree_parser is None:
            self.tree_parser = defaults.get('tree_parser')
        if self.hash_strategy is None:
            self.hash_strategy = defaults.get('hash_strategy')
        if self.node_class is None:
            self.node_class = defaults.get('node_class')
        if self.edge_class is None:
            self.edge_class = defaults.get('edge_class')
        if self.default_merge_strategy == "last":
            # Тільки якщо не було явно встановлено
            registry_strategy = defaults.get('default_merge_strategy')
            if registry_strategy:
                self.default_merge_strategy = registry_strategy
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Конвертує контекст в dict для передачі в Mappers.
        
        Returns:
            Dict з усіма залежностями
            
        Example:
            >>> ctx = GraphContext(plugin_manager=pm)
            >>> graph = GraphMapper.to_domain(graph_dto, context=ctx.to_dict())
        """
        return {
            'plugin_manager': self.plugin_manager,
            'tree_parser': self.tree_parser,
            'hash_strategy': self.hash_strategy,
            'node_class': self.node_class,
            'edge_class': self.edge_class,
            'default_merge_strategy': self.get_current_strategy(),
        }
    
    def get_current_strategy(self) -> str:
        """
        Отримує поточну стратегію merge.
        
        Враховує локальний стек стратегій.
        
        Returns:
            Назва поточної стратегії
        """
        if self._strategy_stack:
            return self._strategy_stack[-1]
        return self.default_merge_strategy
    
    def get_current_custom_merge_fn(self) -> Optional[Callable]:
        """
        Отримує поточну кастомну функцію merge.
        
        Returns:
            Callable або None
        """
        if self.get_current_strategy() == 'custom':
            return self.custom_merge_fn
        return None
    
    @contextmanager
    def merge_strategy(self, strategy: str, custom_fn: Optional[Callable] = None):
        """
        Context manager для тимчасової зміни merge strategy.
        
        Args:
            strategy: Нова стратегія
            custom_fn: Кастомна функція для 'custom' стратегії
            
        Yields:
            self для chaining
            
        Example:
            >>> ctx = GraphContext(default_merge_strategy='last')
            >>> with ctx.merge_strategy('merge'):
            ...     result = graph1 + graph2  # Використає 'merge'
            ... # Повернеться до 'last'
        """
        valid_strategies = ['first', 'last', 'merge', 'newest', 'oldest', 'custom']
        if strategy not in valid_strategies:
            raise ValueError(
                f"Invalid merge strategy: {strategy}. "
                f"Valid: {valid_strategies}"
            )
        
        if strategy == 'custom' and custom_fn is None and self.custom_merge_fn is None:
            raise ValueError(
                "custom_fn is required for 'custom' strategy"
            )
        
        # Зберігаємо custom_fn якщо передано
        old_custom_fn = self.custom_merge_fn
        if custom_fn is not None:
            self.custom_merge_fn = custom_fn
        
        self._strategy_stack.append(strategy)
        logger.debug(
            f"GraphContext strategy pushed: {strategy} "
            f"(depth={len(self._strategy_stack)})"
        )
        
        try:
            yield self
        finally:
            self._strategy_stack.pop()
            self.custom_merge_fn = old_custom_fn
            logger.debug(
                f"GraphContext strategy popped: {strategy} "
                f"(depth={len(self._strategy_stack)})"
            )
    
    def with_plugin_manager(self, plugin_manager: Any) -> 'GraphContext':
        """
        Створює копію контексту з новим plugin_manager.
        
        Fluent API для зручного налаштування.
        
        Args:
            plugin_manager: Новий plugin_manager
            
        Returns:
            Новий GraphContext
            
        Example:
            >>> ctx2 = ctx.with_plugin_manager(custom_pm)
        """
        return GraphContext(
            plugin_manager=plugin_manager,
            tree_parser=self.tree_parser,
            hash_strategy=self.hash_strategy,
            node_class=self.node_class,
            edge_class=self.edge_class,
            default_merge_strategy=self.default_merge_strategy,
            custom_merge_fn=self.custom_merge_fn,
        )
    
    def with_tree_parser(self, tree_parser: Any) -> 'GraphContext':
        """Створює копію контексту з новим tree_parser."""
        return GraphContext(
            plugin_manager=self.plugin_manager,
            tree_parser=tree_parser,
            hash_strategy=self.hash_strategy,
            node_class=self.node_class,
            edge_class=self.edge_class,
            default_merge_strategy=self.default_merge_strategy,
            custom_merge_fn=self.custom_merge_fn,
        )
    
    def with_node_class(self, node_class: Type) -> 'GraphContext':
        """Створює копію контексту з новим node_class."""
        return GraphContext(
            plugin_manager=self.plugin_manager,
            tree_parser=self.tree_parser,
            hash_strategy=self.hash_strategy,
            node_class=node_class,
            edge_class=self.edge_class,
            default_merge_strategy=self.default_merge_strategy,
            custom_merge_fn=self.custom_merge_fn,
        )
    
    def with_merge_strategy_default(self, strategy: str) -> 'GraphContext':
        """Створює копію контексту з новою дефолтною стратегією."""
        return GraphContext(
            plugin_manager=self.plugin_manager,
            tree_parser=self.tree_parser,
            hash_strategy=self.hash_strategy,
            node_class=self.node_class,
            edge_class=self.edge_class,
            default_merge_strategy=strategy,
            custom_merge_fn=self.custom_merge_fn,
        )


# ==================== GLOBAL CONTEXT ====================

_global_context: Optional[GraphContext] = None
_global_lock = threading.Lock()


def get_graph_context() -> GraphContext:
    """
    Отримує глобальний контекст графу.
    
    Якщо не встановлено - створює дефолтний.
    
    Returns:
        GraphContext
        
    Example:
        >>> ctx = get_graph_context()
        >>> graph = GraphMapper.to_domain(graph_dto, context=ctx.to_dict())
    """
    global _global_context
    
    with _global_lock:
        if _global_context is None:
            _global_context = GraphContext()
            logger.debug("Global GraphContext created with defaults")
        return _global_context


def set_graph_context(context: GraphContext) -> None:
    """
    Встановлює глобальний контекст графу.
    
    Args:
        context: GraphContext для встановлення
        
    Example:
        >>> ctx = GraphContext(
        ...     plugin_manager=my_pm,
        ...     default_merge_strategy='merge',
        ... )
        >>> set_graph_context(ctx)
    """
    global _global_context
    
    with _global_lock:
        _global_context = context
        logger.info(
            f"Global GraphContext set: "
            f"strategy={context.default_merge_strategy}, "
            f"has_plugin_manager={context.plugin_manager is not None}"
        )


def reset_graph_context() -> None:
    """
    Скидає глобальний контекст до None.
    
    Корисно для тестування.
    """
    global _global_context
    
    with _global_lock:
        _global_context = None
        logger.debug("Global GraphContext reset")
