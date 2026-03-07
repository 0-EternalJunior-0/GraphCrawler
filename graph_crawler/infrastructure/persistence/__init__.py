"""Модуль STORAGE - Тимчасове зберігання графу під час краулінгу.

**ВАЖЛИВО**: Всі storage - тимчасові файли, не постійне сховище!

Після завершення краулінгу:
1. Граф повертається користувачеві
2. Тимчасові файли очищаються (storage.clear())
3. Постійне зберігання - завдання користувача, не бібліотеки

**Доступні типи:**

1. **MemoryStorage** (StorageType.MEMORY)
   - Все зберігається в RAM
   - Швидко, але обмежено пам'яттю
   - Використання: <1,000 сторінок
   - Приклад: малі сайти, швидкі тести

2. **JSONStorage** (StorageType.JSON)
   - Зберігання у JSON файли
   - Поетапне збереження (save_partial)
   - Використання: 1,000-10,000 сторінок
   - Приклад: середні сайти
   - Файл: temp_graph.json (очищається після)

3. **SQLiteStorage** (StorageType.SQLITE)
   - Локальна SQLite база (тимчасова)
   - Індексація для швидкого lookup
   - Використання: 10,000-100,000 сторінок
   - Приклад: великі сайти
   - Файл: temp_graph.db (очищається після)

4. **PostgreSQLStorage** (StorageType.POSTGRESQL)
   - PostgreSQL база даних (опціонально)
   - Висока продуктивність для великих графів
   - Використання: 100,000+ сторінок
   - Приклад: enterprise краулінг

5. **MongoDBStorage** (StorageType.MONGODB)
   - MongoDB база даних (опціонально)
   - NoSQL для гнучкої структури
   - Використання: 100,000+ сторінок
   - Приклад: складні метадані

**Рекомендації:**
- Немає жорсткого ліміту сторінок (попередження при 20,000+ сторінок)
- Тимчасові файли (не постійне сховище)
- Для великих проектів (100k+ сторінок) використовуйте PostgreSQL/MongoDB

**Архітектура:**

```python
class BaseStorage(ABC):
    @abstractmethod
    def save_graph(self, graph: Graph) -> bool:
        '''Зберегти весь граф'''
        pass

    @abstractmethod
    def load_graph(self) -> Optional[Graph]:
        '''Завантажити граф'''
        pass

    def save_partial(self, nodes: List[Node], edges: List[Edge]) -> bool:
        '''Поетапне збереження (для великих графів)'''
        pass

    def clear(self):
        '''Очистити тимчасові файли'''
        pass
```

**Приклад використання:**

```python
from graph_crawler.application.services import ApplicationContainer
from graph_crawler.domain.entities import Graph

# Створити контейнер
container = ApplicationContainer()

# Отримати storage (автоматично створюється та управляється)
storage = container.storage.json_storage()

# Зберегти граф
graph = Graph()
storage.save_graph(graph)

# Завантажити
loaded = storage.load_graph()

# Cleanup (автоматично закриє всі ресурси)
container.shutdown_resources()
```

**Repository Pattern:**

Використовуйте StorageRepository для unified interface:

```python
from graph_crawler.infrastructure.persistence import StorageRepository, JSONStorage

repo = StorageRepository(JSONStorage())
repo.save_graph(graph)
loaded = repo.load_graph()

# Легко переключити storage
repo.set_storage(SQLiteStorage())
```

** ВАЖЛИВО:**
StorageFactory видалено! Використовуйте DI контейнер замість Factory Pattern.

**Workflow:**
```
1. Початок краулінгу → створити temp storage
2. Під час краулінгу → save_partial() кожні N сторінок
3. Кінець краулінгу → save_graph() фінальний
4. Повернути Graph користувачеві
5. Очистити temp файли → storage.clear()
```
"""

from graph_crawler.infrastructure.persistence.auto_storage import AutoStorage
from graph_crawler.infrastructure.persistence.base import BaseStorage, StorageType
from graph_crawler.infrastructure.persistence.json_storage import JSONStorage
from graph_crawler.infrastructure.persistence.memory_storage import MemoryStorage
from graph_crawler.infrastructure.persistence.repository import StorageRepository
from graph_crawler.infrastructure.persistence.sqlite_storage import SQLiteStorage

# SQLiteEvictionStorage - опціональний import для low-memory mode
try:
    from graph_crawler.infrastructure.persistence.sqlite_eviction_storage import SQLiteEvictionStorage
    _SQLITE_EVICTION_AVAILABLE = True
except ImportError:
    SQLiteEvictionStorage = None
    _SQLITE_EVICTION_AVAILABLE = False

# LMDBEvictionStorage - high-performance eviction (Eviction System v3.0)
try:
    from graph_crawler.infrastructure.persistence.lmdb_eviction_storage import (
        LMDBEvictionStorage,
        is_lmdb_available,
        LMDB_AVAILABLE,
    )
    _LMDB_EVICTION_AVAILABLE = LMDB_AVAILABLE
except ImportError:
    LMDBEvictionStorage = None
    is_lmdb_available = lambda: False
    LMDB_AVAILABLE = False
    _LMDB_EVICTION_AVAILABLE = False


def get_eviction_storage(storage_path: str, storage_type: str = "auto", lightweight_mode: bool = False):
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
