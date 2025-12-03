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

**Приклад використання (Alpha 2.0 - через DI контейнер):**

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

** BREAKING CHANGE (Alpha 2.0):**
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

# PostgreSQL та MongoDB - опціональні, імпортуються динамічно
__all__ = [
    "BaseStorage",
    "StorageType",
    "MemoryStorage",
    "JSONStorage",
    "SQLiteStorage",
    "AutoStorage",
    "StorageRepository",
]
