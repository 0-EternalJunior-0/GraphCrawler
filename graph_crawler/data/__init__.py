"""
Data Layer - Single Source of Truth для Graph Storage.

Example:
    >>> from graph_crawler.data import MemoryBackend, SQLiteBackend
    >>> from graph_crawler.domain.entities.graph import Graph
    >>>
    >>> # Простий випадок - все в RAM
    >>> graph = Graph(backend=MemoryBackend())
    >>>
    >>> # Великий граф - SQLite
    >>> backend = SQLiteBackend("./crawl.db")
    >>> graph = Graph(backend=backend)
"""

from graph_crawler.data.backends.memory import MemoryBackend
from graph_crawler.data.interfaces import (
    IGraphBackend,
    IQueueStorage,
)

# SQLiteBackend - optional, requires aiosqlite
try:
    from graph_crawler.data.backends.sqlite import SQLiteBackend

    _has_sqlite = True
except ImportError:
    SQLiteBackend = None  # type: ignore
    _has_sqlite = False

__all__ = [
    "IGraphBackend",
    "IQueueStorage",
    "MemoryBackend",
    "SQLiteBackend",
]
