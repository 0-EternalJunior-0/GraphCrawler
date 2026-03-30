"""Module: infrastructure/persistence/sqlite

Re-exports SQLiteStorage for backward compatibility.
"""

from graph_crawler.infrastructure.persistence.sqlite_storage import SQLiteStorage

__all__ = ["SQLiteStorage"]
