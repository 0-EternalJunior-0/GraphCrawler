"""MergeContext - Контекст для динамічної зміни merge_strategy.

Дозволяє змінювати стратегію merge під час виконання:
- Глобально через DependencyRegistry
- Локально через context manager
- На рівні окремої операції

Приклад використання з вашого завдання:
    >>> # Дефолт: 'last'
    >>> graph1 = load_graph('data1.json')
    >>> graph2 = load_graph('data2.json')
    >>> merged = graph1 + graph2  # Використає 'last'
    >>>
    >>> # Локальна зміна на 'merge' для batch операцій
    >>> with with_merge_strategy('merge'):
    ...     for chunk in data_chunks:
    ...         merged = merged + chunk  # Використає 'merge'
    >>>
    >>> # Знову 'last' після виходу з контексту
    >>> another_merged = graph1 + graph3  # Використає 'last'
    >>>
    >>> # Ще один приклад - часткове сканування з 'newest'
    >>> with with_merge_strategy('newest'):
    ...     partial_scan = await crawler.scan(urls[:100])
    ...     merged = base_graph + partial_scan  # Використає 'newest'
"""

import logging
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class MergeContext:
    """
    Контекст для однієї merge операції.
    
    Attributes:
        strategy: Стратегія merge ('first', 'last', 'merge', 'newest', 'oldest', 'custom')
        custom_merge_fn: Кастомна функція для 'custom' стратегії
        source: Джерело контексту (для debugging)
    """
    strategy: str = "last"
    custom_merge_fn: Optional[Callable] = None
    source: str = "default"
    
    def __post_init__(self):
        """Валідація після створення."""
        valid_strategies = ['first', 'last', 'merge', 'newest', 'oldest', 'custom']
        if self.strategy not in valid_strategies:
            raise ValueError(
                f"Invalid merge strategy: {self.strategy}. "
                f"Valid: {valid_strategies}"
            )
        
        if self.strategy == 'custom' and self.custom_merge_fn is None:
            raise ValueError(
                "custom_merge_fn is required for 'custom' strategy"
            )


class MergeContextManager:
    """
    Thread-local стек контекстів для merge операцій.
    
    Дозволяє вкладені контексти:
    >>> with with_merge_strategy('merge'):
    ...     # Тут стратегія 'merge'
    ...     with with_merge_strategy('newest'):
    ...         # Тут стратегія 'newest'
    ...     # Знову 'merge'
    
    Thread-safety:
    - Кожен thread має свій стек контекстів
    - Використовує threading.local()
    """
    
    _local = threading.local()
    
    @classmethod
    def _get_stack(cls) -> List[MergeContext]:
        """Отримує стек контекстів для поточного thread."""
        if not hasattr(cls._local, 'stack'):
            cls._local.stack = []
        return cls._local.stack
    
    @classmethod
    def push(cls, context: MergeContext) -> None:
        """
        Додає контекст на стек.
        
        Args:
            context: MergeContext для додавання
        """
        stack = cls._get_stack()
        stack.append(context)
        logger.debug(
            f"MergeContext pushed: {context.strategy} "
            f"(source={context.source}, depth={len(stack)})"
        )
    
    @classmethod
    def pop(cls) -> Optional[MergeContext]:
        """
        Знімає контекст зі стеку.
        
        Returns:
            Знятий MergeContext або None якщо стек порожній
        """
        stack = cls._get_stack()
        if stack:
            context = stack.pop()
            logger.debug(
                f"MergeContext popped: {context.strategy} "
                f"(source={context.source}, depth={len(stack)})"
            )
            return context
        return None
    
    @classmethod
    def current(cls) -> Optional[MergeContext]:
        """
        Повертає поточний контекст (top of stack).
        
        Returns:
            Поточний MergeContext або None якщо стек порожній
        """
        stack = cls._get_stack()
        return stack[-1] if stack else None
    
    @classmethod
    def get_strategy(cls) -> str:
        """
        Отримує поточну стратегію merge.
        
        Пріоритет:
        1. Локальний контекст (якщо є)
        2. Глобальний дефолт з DependencyRegistry
        
        Returns:
            Назва стратегії
        """
        context = cls.current()
        if context:
            return context.strategy
        
        # Fallback до DependencyRegistry
        from graph_crawler.application.context.dependency_registry import DependencyRegistry
        return DependencyRegistry.get_default_merge_strategy()
    
    @classmethod
    def get_custom_merge_fn(cls) -> Optional[Callable]:
        """
        Отримує кастомну функцію merge (якщо стратегія 'custom').
        
        Returns:
            Callable або None
        """
        context = cls.current()
        if context and context.strategy == 'custom':
            return context.custom_merge_fn
        return None
    
    @classmethod
    def clear(cls) -> None:
        """
        Очищає стек контекстів для поточного thread.
        
        Корисно для тестування.
        """
        if hasattr(cls._local, 'stack'):
            cls._local.stack = []
            logger.debug("MergeContext stack cleared")
    
    @classmethod
    def depth(cls) -> int:
        """Повертає глибину стеку контекстів."""
        return len(cls._get_stack())


@contextmanager
def with_merge_strategy(
    strategy: str,
    custom_merge_fn: Optional[Callable] = None,
    source: str = "with_merge_strategy",
):
    """
    Context manager для тимчасової зміни merge strategy.
    
    Дозволяє змінити стратегію для блоку коду, після чого
    автоматично повертається попередня стратегія.
    
    Args:
        strategy: Стратегія merge
        custom_merge_fn: Кастомна функція для 'custom' стратегії
        source: Джерело контексту (для debugging)
        
    Yields:
        MergeContext для поточного блоку
        
    Example:
        >>> # Проста зміна стратегії
        >>> with with_merge_strategy('merge'):
        ...     result = graph1 + graph2
        >>>
        >>> # Кастомна функція
        >>> def my_merge(n1, n2):
        ...     return n1 if n1.scanned else n2
        >>>
        >>> with with_merge_strategy('custom', custom_merge_fn=my_merge):
        ...     result = graph1 + graph2
        >>>
        >>> # Вкладені контексти
        >>> with with_merge_strategy('merge'):
        ...     # 'merge'
        ...     with with_merge_strategy('newest'):
        ...         # 'newest'
        ...         result1 = g1 + g2
        ...     # 'merge'
        ...     result2 = g1 + g3
    """
    context = MergeContext(
        strategy=strategy,
        custom_merge_fn=custom_merge_fn,
        source=source,
    )
    
    MergeContextManager.push(context)
    try:
        yield context
    finally:
        MergeContextManager.pop()


def get_current_merge_strategy() -> str:
    """
    Shortcut для отримання поточної стратегії merge.
    
    Використовуйте в коді де потрібно знати поточну стратегію.
    
    Returns:
        Назва поточної стратегії
        
    Example:
        >>> strategy = get_current_merge_strategy()
        >>> print(f"Using merge strategy: {strategy}")
    """
    return MergeContextManager.get_strategy()


def get_current_custom_merge_fn() -> Optional[Callable]:
    """
    Shortcut для отримання поточної кастомної функції merge.
    
    Returns:
        Callable або None
    """
    return MergeContextManager.get_custom_merge_fn()
