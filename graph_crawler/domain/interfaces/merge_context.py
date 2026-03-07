"""
Interface for Merge Context Provider (Clean Architecture).

This interface allows Graph to depend on abstraction for merge strategy context.

Usage:
    Graph can receive IMergeContextProvider through DI or use thread-local context.
"""

from typing import Any, Callable, Optional, Protocol, Tuple, runtime_checkable


@runtime_checkable
class IMergeContext(Protocol):
    """
    Interface for merge context data.
    
    Holds the merge strategy and optional custom merge function
    for Graph union operations.
    """
    
    @property
    def strategy(self) -> str:
        """Returns the merge strategy name."""
        ...
    
    @property
    def custom_merge_fn(self) -> Optional[Callable]:
        """Returns the custom merge function, if any."""
        ...


@runtime_checkable
class IMergeContextProvider(Protocol):
    """
    Interface for merge context provider (Dependency Injection).
    
        without importing Application layer directly.
    
    Example:
        >>> # In Graph.__init__ or through DI
        >>> graph = Graph(merge_context_provider=MergeContextManager)
        >>> strategy, fn = graph._get_effective_merge_strategy()
    """
    
    @classmethod
    def current(cls) -> Optional[IMergeContext]:
        """
        Returns the current merge context from thread-local storage.
        
        Returns:
            IMergeContext or None if no context is active
        """
        ...


__all__ = [
    "IMergeContext",
    "IMergeContextProvider",
]
