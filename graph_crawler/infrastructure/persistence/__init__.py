"""Модуль STORAGE - Тимчасове зберігання графу під час краулінгу.

**ВАЖЛИВО**: Всі storage - тимчасові файли, не постійне сховище!
"""

from graph_crawler.infrastructure.persistence.auto_storage import AutoStorage
from graph_crawler.infrastructure.persistence.base import BaseStorage, StorageType
from graph_crawler.infrastructure.persistence.json_storage import JSONStorage
from graph_crawler.infrastructure.persistence.memory_storage import MemoryStorage
from graph_crawler.infrastructure.persistence.repository import StorageRepository
from graph_crawler.infrastructure.persistence.sqlite_storage import SQLiteStorage

# SQLiteEvictionStorage - опціональний import для low-memory mode
try:
    from graph_crawler.infrastructure.persistence.sqlite_eviction_storage import (
        SQLiteEvictionStorage,
    )

    _SQLITE_EVICTION_AVAILABLE = True
except ImportError:
    SQLiteEvictionStorage = None
    _SQLITE_EVICTION_AVAILABLE = False

# LMDBEvictionStorage - high-performance eviction (Eviction System v3.0)
try:
    from graph_crawler.infrastructure.persistence.lmdb_eviction_storage import (
        LMDB_AVAILABLE,
        LMDBEvictionStorage,
        is_lmdb_available,
    )

    _LMDB_EVICTION_AVAILABLE = LMDB_AVAILABLE
except ImportError:
    LMDBEvictionStorage = None

    def is_lmdb_available():
        return False

    LMDB_AVAILABLE = False
    _LMDB_EVICTION_AVAILABLE = False


def get_eviction_storage(
    storage_path: str, storage_type: str = "auto", lightweight_mode: bool = False
):
    """
    Factory для створення eviction storage.

    Eviction System v3.0:
    - LMDB ~10x швидше за SQLite для write operations
    - lightweight_mode економить ~30-40% RAM

    Args:
        storage_path: Директорія для eviction storage
        storage_type: "lmdb", "sqlite", або "auto" (спробує LMDB, fallback на SQLite)
        lightweight_mode: Якщо True - НЕ зберігати metadata/user_data

    Returns:
        IEvictionStorage implementation (LMDB або SQLite)

    Raises:
        ImportError: Якщо жоден storage не доступний
    """
    if storage_type == "lmdb":
        if not _LMDB_EVICTION_AVAILABLE:
            raise ImportError("lmdb not installed. Install with: pip install lmdb")
        return LMDBEvictionStorage(storage_path, lightweight_mode=lightweight_mode)

    elif storage_type == "sqlite":
        if not _SQLITE_EVICTION_AVAILABLE:
            raise ImportError("SQLiteEvictionStorage not available")
        return SQLiteEvictionStorage(storage_path)

    elif storage_type == "auto":
        # Спробувати LMDB (швидший), fallback на SQLite
        if _LMDB_EVICTION_AVAILABLE:
            try:
                return LMDBEvictionStorage(storage_path, lightweight_mode=lightweight_mode)
            except Exception as e:
                import logging

                logging.getLogger(__name__).warning(
                    f"Failed to create LMDBEvictionStorage: {e}. Falling back to SQLite."
                )

        if _SQLITE_EVICTION_AVAILABLE:
            return SQLiteEvictionStorage(storage_path)

        raise ImportError(
            "No eviction storage available. "
            "Install lmdb (pip install lmdb) or ensure sqlite3 is available."
        )

    else:
        raise ValueError(f"Unknown storage_type: {storage_type}. Use 'lmdb', 'sqlite', or 'auto'.")


# PostgreSQL та MongoDB - опціональні, імпортуються динамічно
__all__ = [
    "BaseStorage",
    "StorageType",
    "MemoryStorage",
    "JSONStorage",
    "SQLiteStorage",
    "SQLiteEvictionStorage",
    "LMDBEvictionStorage",
    "AutoStorage",
    "StorageRepository",
    "get_eviction_storage",
    "is_lmdb_available",
    "LMDB_AVAILABLE",
]
