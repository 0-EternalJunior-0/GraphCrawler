"""
Interface for eviction storage (Clean Architecture).
This interface allows Graph to depend on abstraction instead of
concrete SQLiteEvictionStorage implementation.

Usage:
    Graph now accepts IEvictionStorage through Dependency Injection
    instead of creating SQLiteEvictionStorage internally.
"""

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

# Forward reference to avoid circular imports
# Node will be imported via TYPE_CHECKING if needed


@runtime_checkable
class IEvictionStorage(Protocol):
    """
    Interface for node eviction storage (ISP - Interface Segregation Principle).

    Supports Low-Memory Mode for large crawls (10k+ pages):
    - Evicts scanned nodes to disk when RAM threshold exceeded
    - Lazy loads nodes back when accessed
    - Preserves graph structure (edges, adjacency lists)

    Implementations:
    - SQLiteEvictionStorage (default, in infrastructure)
    - Could be extended: Redis, RocksDB, etc.

    Example:
        >>> # Dependency Injection in Graph
        >>> from graph_crawler.infrastructure.persistence import SQLiteEvictionStorage
        >>> storage = SQLiteEvictionStorage("/tmp/eviction")
        >>> graph = Graph(low_memory_mode=True, eviction_storage=storage)
    """

    def save_nodes_sync(self, nodes: List[Any]) -> None:
        """
        Synchronously saves nodes to eviction storage.

        Args:
            nodes: List of Node objects to evict to disk
        """
        ...

    def save_edges_sync(self, edges: List[Any]) -> None:
        """
        Synchronously saves edges related to evicted nodes.

        Args:
            edges: List of Edge objects to save
        """
        ...

    def load_node_sync(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Synchronously loads a node by URL from eviction storage.

        Args:
            url: URL of the node to load

        Returns:
            Node data as dictionary, or None if not found
        """
        ...

    def get_stats(self) -> Dict[str, Any]:
        """
        Returns statistics about eviction storage.

        Returns:
            Dictionary with storage statistics (nodes_count, size_bytes, etc.)
        """
        ...

    def close(self) -> None:
        """Closes the eviction storage connection."""
        ...


@runtime_checkable
class IEvictionStorageAsync(Protocol):
    """
    Async version of IEvictionStorage for async-first code.

    Use this when working in async context (Spider, async handlers).
    """

    async def save_nodes(self, nodes: List[Any]) -> None:
        """Asynchronously saves nodes to eviction storage."""
        ...

    async def save_edges(self, edges: List[Any]) -> None:
        """Asynchronously saves edges to eviction storage."""
        ...

    async def load_node(self, url: str) -> Optional[Dict[str, Any]]:
        """Asynchronously loads a node by URL."""
        ...

    async def close(self) -> None:
        """Asynchronously closes the storage."""
        ...


__all__ = [
    "IEvictionStorage",
    "IEvictionStorageAsync",
]
