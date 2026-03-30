"""
Data Layer Backends.

Pluggable implementations of IGraphBackend for different storage needs.

Available Backends:
- MemoryBackend: Dict/List in RAM (tests, <10K nodes)
- SQLiteBackend: Local SQLite file (<1M nodes) [TODO]
- PostgreSQLBackend: Scalable PostgreSQL (100M+ nodes) [TODO]
- MongoDBBackend: Flexible schema [TODO]
"""

from graph_crawler.data.backends.memory import MemoryBackend

__all__ = [
    "MemoryBackend",
]
