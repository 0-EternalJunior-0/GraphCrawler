"""Factory для створення storage з Registry Pattern.

Приклади:
    >>> storage = create_storage("memory")
    >>> storage = create_storage("sqlite", db_path="/tmp/graph.db")
    >>> storage = create_storage(CustomStorage())

    # Реєстрація custom storage:
    >>> register_storage("redis", lambda cfg: RedisStorage(**cfg))
    >>> storage = create_storage("redis", host="localhost")
"""

import logging
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Union

if TYPE_CHECKING:
    from graph_crawler.domain.interfaces.storage import IStorage

logger = logging.getLogger(__name__)

# Type alias
StorageType = Union[str, "IStorage", None]

# =====================================
# REGISTRY PATTERN
# =====================================
_STORAGE_REGISTRY: Dict[str, Callable[[dict], "IStorage"]] = {}


def register_storage(name: str, factory: Callable[[dict], "IStorage"]) -> None:
    """
    Реєструє storage factory (OCP - Open/Closed Principle).

    Дозволяє користувачам додавати власні storage типи без модифікації
    основного коду.

    Args:
        name: Назва storage типу (наприклад, "redis", "elasticsearch")
        factory: Функція, яка приймає config dict і повертає IStorage

    Examples:
        >>> from graph_crawler.application.services.storage_factory import register_storage
        >>>
        >>> class RedisStorage:
        ...     def __init__(self, host="localhost", port=6379):
        ...         self.host = host
        ...         self.port = port
        ...     def save_graph(self, graph): ...
        ...     def load_graph(self): ...
        >>>
        >>> register_storage("redis", lambda cfg: RedisStorage(**cfg))
        >>> storage = create_storage("redis", host="127.0.0.1", port=6380)
    """
    name = name.lower()
    _STORAGE_REGISTRY[name] = factory
    logger.debug(f"Registered storage type: {name}")


def get_available_storage_types() -> list:
    """
    Повертає список доступних storage типів.

    Returns:
        list: Список назв зареєстрованих storage типів

    Examples:
        >>> types = get_available_storage_types()
        >>> print(types)  # ['memory', 'json', 'sqlite', 'postgresql', 'mongodb']
    """
    return list(_STORAGE_REGISTRY.keys())


def _register_builtin_storages() -> None:
    """
    Реєструє вбудовані storage типи.

    Викликається автоматично при імпорті модуля.
    """

    # Memory Storage (до 1K nodes)
    def create_memory(cfg: dict) -> "IStorage":
        from graph_crawler.infrastructure.persistence.memory_storage import (
            MemoryStorage,
        )

        return MemoryStorage()

    register_storage("memory", create_memory)

    # JSON Storage (до 10K nodes)
    def create_json(cfg: dict) -> "IStorage":
        from graph_crawler.infrastructure.persistence.json_storage import JSONStorage

        storage_dir = cfg.get("storage_dir") or cfg.get(
            "db_path", "/tmp/graph_crawler_json"
        )
        return JSONStorage(storage_dir=storage_dir)

    register_storage("json", create_json)

    # SQLite Storage (до 100K nodes)
    def create_sqlite(cfg: dict) -> "IStorage":
        from graph_crawler.infrastructure.persistence.sqlite_storage import (
            SQLiteStorage,
        )

        storage_dir = cfg.get("storage_dir") or cfg.get("db_path", "/tmp/graph_crawler")
        return SQLiteStorage(storage_dir=storage_dir)

    register_storage("sqlite", create_sqlite)

    # PostgreSQL Storage (100K+ nodes) - опціонально
    def create_postgresql(cfg: dict) -> "IStorage":
        try:
            from graph_crawler.infrastructure.persistence.postgresql_storage import (
                PostgreSQLStorage,
            )

            return PostgreSQLStorage(cfg)
        except ImportError:
            raise ImportError(
                "PostgreSQLStorage requires asyncpg. "
                "Install with: pip install asyncpg"
            )

    register_storage("postgresql", create_postgresql)

    # MongoDB Storage (100K+ nodes) - опціонально
    def create_mongodb(cfg: dict) -> "IStorage":
        try:
            from graph_crawler.infrastructure.persistence.mongodb_storage import (
                MongoDBStorage,
            )

            return MongoDBStorage(cfg)
        except ImportError:
            raise ImportError(
                "MongoDBStorage requires motor. " "Install with: pip install motor"
            )

    register_storage("mongodb", create_mongodb)


# Auto-registration при імпорті модуля
_register_builtin_storages()


def create_storage(
    storage: StorageType = None, config: Optional[Dict[str, Any]] = None, **kwargs
) -> "IStorage":
    """
    Створює storage з Registry Pattern.

    Factory pattern для простого створення storage.
    Дозволяє використовувати string shortcuts замість імпортування класів.


    Args:
        storage: Тип storage або готовий instance
            - "memory" (default): В пам'яті (до 1K nodes)
            - "json": JSON файл (до 10K nodes)
            - "sqlite": SQLite база (до 100K nodes)
            - "postgresql": PostgreSQL (100K+ nodes)
            - "mongodb": MongoDB (100K+ nodes)
            - IStorage instance: Повертається як є
        config: Конфігурація storage як dict (опціонально)
        **kwargs: Конфігурація storage як keyword arguments

    Returns:
        IStorage: Готовий до використання storage

    Raises:
        ValueError: Якщо невідомий тип storage
        ImportError: Якщо потрібний пакет не встановлено

    Examples:
        In-memory storage:
        >>> storage = create_storage("memory")

        SQLite з шляхом (kwargs):
        >>> storage = create_storage("sqlite", db_path="/tmp/graphs.db")

        SQLite з шляхом (dict):
        >>> storage = create_storage("sqlite", {"db_path": "/tmp/graphs.db"})

        Кастомний storage:
        >>> class RedisStorage:
        ...     def save_graph(self, graph): ...
        ...     def load_graph(self): ...
        >>>
        >>> storage = create_storage(RedisStorage())

        Реєстрація та використання custom storage:
        >>> register_storage("redis", lambda cfg: RedisStorage(**cfg))
        >>> storage = create_storage("redis", host="localhost")
    """
    # Merge config dict з kwargs
    final_config = config.copy() if config else {}
    final_config.update(kwargs)

    # Якщо передали готовий storage - повертаємо як є
    if storage is not None and not isinstance(storage, str):
        # Перевіряємо чи це схоже на storage (має метод save_graph)
        if hasattr(storage, "save_graph"):
            logger.debug(f"Using custom storage: {type(storage).__name__}")
            return storage
        else:
            raise ValueError(
                f"Invalid storage instance: {type(storage).__name__}. "
                f"Storage must have 'save_graph' method."
            )

    # String shortcuts через Registry
    storage_type = (storage or "memory").lower()

    if storage_type not in _STORAGE_REGISTRY:
        available = ", ".join(get_available_storage_types())
        raise ValueError(
            f"Unknown storage type: '{storage_type}'. "
            f"Available: {available}. "
            f"Or provide IStorage instance, or register custom with register_storage()."
        )

    factory = _STORAGE_REGISTRY[storage_type]
    logger.debug(f"Creating {storage_type} storage via Registry")
    return factory(final_config)
