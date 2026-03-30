"""
Backward compatibility module for eviction storage.

Provides SQLiteEvictionStorage import from the legacy path.
"""

from graph_crawler.infrastructure.persistence.sqlite_eviction_storage import (
    SQLiteEvictionStorage,
)

__all__ = ["SQLiteEvictionStorage"]
