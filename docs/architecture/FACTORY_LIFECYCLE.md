# 7. Factory & Object Creation Lifecycle (Фабрики та життєвий цикл)

## 📋 Зміст

1. [Огляд фабрик та DI](#огляд-фабрик-та-di)
2. [Driver Factory](#driver-factory)
3. [Storage Factory](#storage-factory)
4. [Registry Pattern](#registry-pattern)
5. [DependencyRegistry (Singleton)](#dependencyregistry)
6. [ApplicationContainer (DI)](#applicationcontainer)
7. [Життєвий цикл об'єктів](#життєвий-цикл-обєктів)
8. [Transient Objects](#transient-objects)

---

## Огляд фабрик та DI

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    FACTORY & DI ARCHITECTURE                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                         FACTORIES (OCP)                              │    │
│  │                                                                      │    │
│  │   ┌─────────────────────┐    ┌─────────────────────┐                │    │
│  │   │   DriverFactory     │    │   StorageFactory    │                │    │
│  │   │                     │    │                     │                │    │
│  │   │  _DRIVER_REGISTRY   │    │  _STORAGE_REGISTRY  │                │    │
│  │   │  {                  │    │  {                  │                │    │
│  │   │    "http": factory, │    │    "memory": factory│                │    │
│  │   │    "async": factory,│    │    "json": factory, │                │    │
│  │   │    "playwright": ..│    │    "sqlite": factory│                │    │
│  │   │  }                  │    │  }                  │                │    │
│  │   │                     │    │                     │                │    │
│  │   │  register_driver()  │    │  register_storage() │                │    │
│  │   │  create_driver()    │    │  create_storage()   │                │    │
│  │   └─────────────────────┘    └─────────────────────┘                │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    DOMAIN REGISTRIES (OCP)                           │    │
│  │                                                                      │    │
│  │   ┌─────────────────────┐    ┌─────────────────────┐                │    │
│  │   │ CrawlModeRegistry   │    │ MergeStrategyRegistry│               │    │
│  │   │                     │    │                     │                │    │
│  │   │ "sequential"        │    │ "first"             │                │    │
│  │   │ "multiprocessing"   │    │ "last"              │                │    │
│  │   │ "celery"            │    │ "merge"             │                │    │
│  │   │ [custom]            │    │ "newest"            │                │    │
│  │   │                     │    │ "oldest"            │                │    │
│  │   │                     │    │ "custom"            │                │    │
│  │   └─────────────────────┘    └─────────────────────┘                │    │
│  │                                                                      │    │
│  │   ┌─────────────────────────────────────────────────────────────┐   │    │
│  │   │           ChangeDetectionStrategyRegistry                    │   │    │
│  │   │                                                              │   │    │
│  │   │  "hash"     - SHA256 від text_content                        │   │    │
│  │   │  "metadata" - порівняння metadata полів                      │   │    │
│  │   │  [custom]   - кастомна стратегія                             │   │    │
│  │   └─────────────────────────────────────────────────────────────┘   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │              DEPENDENCY INJECTION (DI)                               │    │
│  │                                                                      │    │
│  │   ┌─────────────────────────────────────────────────────────────┐   │    │
│  │   │           DependencyRegistry (Singleton)                     │   │    │
│  │   │                                                              │   │    │
│  │   │  • plugin_manager_factory                                    │   │    │
│  │   │  • tree_parser_factory                                       │   │    │
│  │   │  • hash_strategy_factory                                     │   │    │
│  │   │  • node_class                                                │   │    │
│  │   │  • edge_class                                                │   │    │
│  │   │  • default_merge_strategy                                    │   │    │
│  │   │                                                              │   │    │
│  │   │  Thread-safe Singleton з lazy initialization                 │   │    │
│  │   └─────────────────────────────────────────────────────────────┘   │    │
│  │                                                                      │    │
│  │   ┌─────────────────────────────────────────────────────────────┐   │    │
│  │   │           ApplicationContainer                               │   │    │
│  │   │                                                              │   │    │
│  │   │  Об'єднує всі залежності для Spider:                         │   │    │
│  │   │  • driver (IDriver)                                          │   │    │
│  │   │  • storage (IStorage)                                        │   │    │
│  │   │  • scheduler (Scheduler)                                     │   │    │
│  │   │  • event_bus (EventBus)                                      │   │    │
│  │   │  • plugins (List[BaseNodePlugin])                            │   │    │
│  │   │  • config (CrawlerConfig)                                    │   │    │
│  │   └─────────────────────────────────────────────────────────────┘   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Driver Factory

### Розташування

**Файл:** `graph_crawler/application/services/driver_factory.py`

### Архітектура

```python
# Внутрішній Registry (Dict)
_DRIVER_REGISTRY: Dict[str, DriverFactory] = {}

# Тип фабрики
DriverFactory = Callable[[dict], IDriver]
```

### API

```python
# Реєстрація нового драйвера
def register_driver(name: str, factory: DriverFactory) -> None:
    """
    Реєструє новий тип драйвера (OCP).
    
    Args:
        name: Назва драйвера (lowercase)
        factory: Функція-фабрика яка приймає config і повертає IDriver
    """

# Створення драйвера
def create_driver(
    driver: DriverType = None,
    config: Optional[dict] = None
) -> IDriver:
    """
    Створює драйвер з string або повертає instance.
    
    Args:
        driver: "http" | "async" | "playwright" | "stealth" | IDriver instance
        config: Конфігурація драйвера
    """

# Список доступних драйверів
def get_available_drivers() -> list[str]:
    """Повертає список зареєстрованих драйверів."""
```

### Вбудовані драйвери

| Назва | Клас | Бібліотека | Опис |
|-------|------|------------|------|
| `http` | HTTPDriver | requests | Синхронний HTTP (default) |
| `async` | AsyncDriver | aiohttp | Асинхронний HTTP |
| `playwright` | PlaywrightDriver | playwright | JS rendering |
| `stealth` | StealthDriver | playwright | Anti-bot bypass |

### Ініціалізація

```python
def _register_builtin_drivers():
    """Реєструє вбудовані драйвери при імпорті модуля."""
    
    def http_factory(config: dict) -> IDriver:
        from graph_crawler.infrastructure.transport import HTTPDriver
        return HTTPDriver(config)
    
    def async_factory(config: dict) -> IDriver:
        from graph_crawler.infrastructure.transport.async_http import AsyncDriver
        return AsyncDriver(config)
    
    def playwright_factory(config: dict) -> IDriver:
        from graph_crawler.infrastructure.transport.playwright import PlaywrightDriver
        return PlaywrightDriver(config)
    
    def stealth_factory(config: dict) -> IDriver:
        from graph_crawler.infrastructure.transport.stealth_driver import StealthDriver
        return StealthDriver(config)
    
    _DRIVER_REGISTRY["http"] = http_factory
    _DRIVER_REGISTRY["async"] = async_factory
    _DRIVER_REGISTRY["playwright"] = playwright_factory
    _DRIVER_REGISTRY["stealth"] = stealth_factory

# Автоматична ініціалізація при імпорті
_register_builtin_drivers()
```

---

## Storage Factory

### Розташування

**Файл:** `graph_crawler/application/services/storage_factory.py`

### API

```python
# Реєстрація
def register_storage(name: str, factory: Callable[[dict], IStorage]) -> None:
    """Реєструє storage factory (OCP)."""

# Створення
def create_storage(
    storage: StorageType = None,
    config: Optional[Dict] = None,
    **kwargs
) -> IStorage:
    """Створює storage з Registry Pattern."""

# Список типів
def get_available_storage_types() -> list:
    """Повертає список доступних storage типів."""
```

### Вбудовані storage

| Назва | Клас | Рекомендовано для | Бібліотека |
|-------|------|-------------------|------------|
| `memory` | MemoryStorage | < 1K nodes | built-in |
| `json` | JSONStorage | 1K - 10K nodes | aiofiles |
| `sqlite` | SQLiteStorage | 10K - 100K nodes | aiosqlite |
| `postgresql` | PostgreSQLStorage | 100K+ nodes | asyncpg |
| `mongodb` | MongoDBStorage | 100K+ nodes | motor |

---

## Registry Pattern

### BaseRegistry

**Файл:** `graph_crawler/domain/entities/registries.py`

```python
class BaseRegistry(ABC):
    """Базовий клас для всіх реєстрів."""
    
    _registry: Dict[str, Any] = {}
    
    @classmethod
    def register(cls, name: str, item: Any) -> None:
        """Реєструє елемент."""
        
    @classmethod
    def unregister(cls, name: str) -> None:
        """Видаляє елемент."""
        
    @classmethod
    def get(cls, name: str) -> Optional[Any]:
        """Отримує елемент."""
        
    @classmethod
    def get_all_names(cls) -> List[str]:
        """Список всіх назв."""
        
    @classmethod
    def is_registered(cls, name: str) -> bool:
        """Перевіряє реєстрацію."""
        
    @classmethod
    def clear(cls) -> None:
        """Очищує реєстр (для тестів)."""
```

### Конкретні Registry

```python
class CrawlModeRegistry(BaseRegistry):
    """
    Реєстр режимів краулінгу.
    
    Дефолтні режими:
    - sequential: GraphSpider
    - multiprocessing: MultiprocessingSpider
    - celery: CeleryBatchSpider
    """

class MergeStrategyRegistry(BaseRegistry):
    """
    Реєстр стратегій merge для Graph.union().
    
    Дефолтні стратегії:
    - first, last, merge, newest, oldest, custom
    """

class ChangeDetectionStrategyRegistry(BaseRegistry):
    """
    Реєстр стратегій детекції змін.
    
    Дефолтні стратегії:
    - hash: SHA256 від text_content
    - metadata: порівняння metadata полів
    """
```

### Lazy Factory Pattern

Для уникнення circular imports використовується lazy factory:

```python
def _lazy_import_spider(mode: str):
    """Lazy factory для імпорту Spider класів."""
    
    def factory():
        if mode == "sequential":
            from graph_crawler.application.use_cases.crawling.spider import GraphSpider
            return GraphSpider
        elif mode == "multiprocessing":
            from graph_crawler.application.use_cases.crawling.multiprocessing_spider import (
                MultiprocessingSpider,
            )
            return MultiprocessingSpider
        elif mode == "celery":
            from graph_crawler.application.use_cases.crawling.celery_batch_spider import (
                CeleryBatchSpider,
            )
            return CeleryBatchSpider
        else:
            raise ValueError(f"Unknown crawl mode: {mode}")
    
    return factory

# Реєстрація з lazy factory
CrawlModeRegistry.register("sequential", _lazy_import_spider("sequential"))
```

---

## DependencyRegistry

### Призначення

**Файл:** `graph_crawler/application/context/dependency_registry.py`

Thread-safe Singleton для управління залежностями, які не серіалізуються:
- `plugin_manager` - управляє плагінами
- `tree_parser` - парсер HTML
- `hash_strategy` - стратегія обчислення hash

### Проблема

```python
# Node має поля які НЕ серіалізуються:
class Node(BaseModel):
    plugin_manager: Optional[Any] = Field(default=None, exclude=True)
    tree_parser: Optional[Any] = Field(default=None, exclude=True)
    hash_strategy: Optional[Any] = Field(default=None, exclude=True)
```

Після десеріалізації з JSON/SQLite ці поля будуть `None`.

### Рішення

```python
from graph_crawler.application.context import DependencyRegistry

# 1. Конфігурація при старті програми
DependencyRegistry.configure(
    plugin_manager_factory=lambda: NodePluginManager(),
    tree_parser_factory=lambda: BeautifulSoupAdapter(),
    hash_strategy_factory=lambda: DefaultHashStrategy(),
    default_merge_strategy='merge'
)

# 2. Отримання контексту для десеріалізації
context = DependencyRegistry.get_context()
graph = GraphMapper.to_domain(graph_dto, context=context)

# 3. Override для конкретного випадку
context = DependencyRegistry.get_context(
    plugin_manager=custom_pm,  # Override тільки plugin_manager
)
```

### API

```python
class DependencyRegistry:
    """Thread-safe Singleton."""
    
    @classmethod
    def configure(
        cls,
        plugin_manager: Optional[Any] = None,
        plugin_manager_factory: Optional[Callable] = None,
        tree_parser: Optional[Any] = None,
        tree_parser_factory: Optional[Callable] = None,
        hash_strategy: Optional[Any] = None,
        hash_strategy_factory: Optional[Callable] = None,
        node_class: Optional[Type] = None,
        edge_class: Optional[Type] = None,
        default_merge_strategy: str = "last",
    ) -> None:
        """Конфігурує дефолтні залежності."""
    
    @classmethod
    def get_context(
        cls,
        plugin_manager: Optional[Any] = None,
        tree_parser: Optional[Any] = None,
        hash_strategy: Optional[Any] = None,
        node_class: Optional[Type] = None,
        edge_class: Optional[Type] = None,
        default_merge_strategy: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Отримує контекст з можливістю override."""
    
    @classmethod
    def reset(cls) -> None:
        """Скидає до дефолтів (для тестів)."""
    
    # Shortcut методи
    @classmethod
    def set_plugin_manager(cls, pm: Any) -> None: ...
    @classmethod
    def get_plugin_manager(cls) -> Optional[Any]: ...
    @classmethod
    def set_tree_parser(cls, tp: Any) -> None: ...
    @classmethod
    def get_tree_parser(cls) -> Optional[Any]: ...
    @classmethod
    def set_default_merge_strategy(cls, strategy: str) -> None: ...
    @classmethod
    def get_default_merge_strategy(cls) -> str: ...
```

---

## ApplicationContainer

### Призначення

**Файл:** `graph_crawler/application/services/application_container.py`

DI контейнер який об'єднує всі залежності для Spider.

### Структура

```python
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class ApplicationContainer:
    """
    DI контейнер для Spider.
    
    Об'єднує всі залежності в одному місці.
    Spider отримує цей контейнер і використовує залежності.
    """
    
    # Основні залежності
    driver: IDriver
    storage: IStorage
    scheduler: Scheduler
    event_bus: EventBus
    
    # Плагіни та middleware
    plugins: List[BaseNodePlugin]
    middleware_chain: MiddlewareChain
    
    # Конфігурація
    config: CrawlerConfig
    
    # Кастомні класи
    node_class: type = Node
    edge_class: type = Edge
    
    # Factories
    node_factory: Optional[Callable] = None
    edge_factory: Optional[Callable] = None
```

### Створення контейнера

```python
# Всередині API Layer (crawl() функція)
def _create_container(config: CrawlerConfig) -> ApplicationContainer:
    """
    Створює DI контейнер з конфігурації.
    
    Використовує фабрики для створення компонентів.
    """
    
    # Створюємо driver через factory
    driver = create_driver(
        config.driver,
        config.driver_config
    )
    
    # Створюємо storage через factory
    storage = create_storage(
        config.storage,
        config.storage_config
    )
    
    # Створюємо event bus
    event_bus = EventBus()
    
    # Створюємо scheduler
    scheduler = Scheduler(
        url_rules=config.url_rules,
        max_depth=config.max_depth
    )
    
    # Створюємо plugin manager з плагінами
    plugins = config.plugins or get_default_node_plugins()
    
    return ApplicationContainer(
        driver=driver,
        storage=storage,
        scheduler=scheduler,
        event_bus=event_bus,
        plugins=plugins,
        middleware_chain=MiddlewareChain(),
        config=config,
        node_class=config.node_class or Node,
        edge_class=config.edge_class or Edge,
    )
```

---

## Життєвий цикл об'єктів

### Node Lifecycle

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           NODE LIFECYCLE                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────┐          │
│  │ ЕТАП 1: URL_STAGE (Створення)                                 │          │
│  │                                                               │          │
│  │ 1. Node.__init__(url="...")                                   │          │
│  │    │                                                          │          │
│  │    ▼                                                          │          │
│  │ 2. model_post_init()                                          │          │
│  │    │                                                          │          │
│  │    ▼                                                          │          │
│  │ 3. _trigger_node_created_hook()                               │          │
│  │    │                                                          │          │
│  │    ▼                                                          │          │
│  │ 4. ON_NODE_CREATED plugins (sync)                             │          │
│  │    • Аналіз URL                                               │          │
│  │    • Встановлення should_scan, can_create_edges               │          │
│  │    • Встановлення priority                                    │          │
│  │                                                               │          │
│  │ Доступно: url, depth, should_scan, can_create_edges           │          │
│  │ lifecycle_stage = URL_STAGE                                   │          │
│  └───────────────────────────────────────────────────────────────┘          │
│                              │                                              │
│                              │ (якщо should_scan == True)                   │
│                              ▼                                              │
│  ┌───────────────────────────────────────────────────────────────┐          │
│  │ ЕТАП 2: HTML_STAGE (Обробка HTML)                             │          │
│  │                                                               │          │
│  │ 5. await node.process_html(html)                              │          │
│  │    │                                                          │          │
│  │    ▼                                                          │          │
│  │ 6. _parse_html(html) → (parser, html_tree)                    │          │
│  │    │                                                          │          │
│  │    ▼                                                          │          │
│  │ 7. _execute_plugins() (async)                                 │          │
│  │    │                                                          │          │
│  │    ├──▶ ON_BEFORE_SCAN plugins                                │          │
│  │    │                                                          │          │
│  │    ├──▶ ON_HTML_PARSED plugins                                │          │
│  │    │    • MetadataExtractor → metadata                        │          │
│  │    │    • LinkExtractor → extracted_links                     │          │
│  │    │    • PhoneExtractor → user_data['phones']                │          │
│  │    │                                                          │          │
│  │    ├──▶ _update_from_context()                                │          │
│  │    │    • metadata = context.metadata                         │          │
│  │    │    • user_data.update(context.user_data)                 │          │
│  │    │                                                          │          │
│  │    └──▶ ON_AFTER_SCAN plugins                                 │          │
│  │         • Vectorization                                       │          │
│  │         • ML analysis                                         │          │
│  │    │                                                          │          │
│  │    ▼                                                          │          │
│  │ 8. _compute_content_hash()                                    │          │
│  │    │                                                          │          │
│  │    ▼                                                          │          │
│  │ 9. _cleanup_memory()                                          │          │
│  │    • del html                                                 │          │
│  │    • del html_tree                                            │          │
│  │    • context.html = None                                      │          │
│  │                                                               │          │
│  │ lifecycle_stage = HTML_STAGE                                  │          │
│  │ Доступно: metadata, user_data, content_hash                   │          │
│  │ HTML ВИДАЛЕНО з пам'яті!                                      │          │
│  └───────────────────────────────────────────────────────────────┘          │
│                              │                                              │
│                              ▼                                              │
│  ┌───────────────────────────────────────────────────────────────┐          │
│  │ ЗБЕРІГАННЯ / ВІДНОВЛЕННЯ                                      │          │
│  │                                                               │          │
│  │ 10. storage.save_graph(graph)                                 │          │
│  │     • node.model_dump() → JSON                                │          │
│  │     • plugin_manager, tree_parser EXCLUDED                    │          │
│  │                                                               │          │
│  │ 11. storage.load_graph()                                      │          │
│  │     • Node.model_validate(data, context=context)              │          │
│  │     • node.restore_dependencies(pm, tp, hs)                   │          │
│  │                                                               │          │
│  └───────────────────────────────────────────────────────────────┘          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Spider Lifecycle

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          SPIDER LIFECYCLE                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. СТВОРЕННЯ                                                               │
│     spider = GraphSpider(container)                                         │
│                                                                             │
│  2. ІНІЦІАЛІЗАЦІЯ                                                           │
│     │                                                                       │
│     ├──▶ scheduler.add_url(start_url, depth=0)                              │
│     │                                                                       │
│     ├──▶ event_bus.publish(CRAWL_STARTED)                                   │
│     │                                                                       │
│     └──▶ plugin_manager.setup() для кожного плагіна                         │
│                                                                             │
│  3. ГОЛОВНИЙ ЦИКЛ                                                           │
│     │                                                                       │
│     │  while not scheduler.is_empty() and pages < max_pages:                │
│     │  │                                                                    │
│     │  ├──▶ url, depth = scheduler.get_next_url()                           │
│     │  │                                                                    │
│     │  ├──▶ node = Node(url, depth, plugin_manager)                         │
│     │  │    └──▶ ON_NODE_CREATED plugins                                    │
│     │  │                                                                    │
│     │  ├──▶ if node.should_scan:                                            │
│     │  │    │                                                               │
│     │  │    ├──▶ response = await driver.fetch(url)                         │
│     │  │    │                                                               │
│     │  │    ├──▶ links = await node.process_html(response.html)             │
│     │  │    │    └──▶ ON_BEFORE_SCAN, ON_HTML_PARSED, ON_AFTER_SCAN         │
│     │  │    │                                                               │
│     │  │    ├──▶ for link in links:                                         │
│     │  │    │    scheduler.add_url(link, depth+1)                           │
│     │  │    │                                                               │
│     │  │    └──▶ graph.add_node(node)                                       │
│     │  │                                                                    │
│     │  └──▶ event_bus.publish(NODE_SCANNED)                                 │
│     │                                                                       │
│  4. ЗАВЕРШЕННЯ                                                              │
│     │                                                                       │
│     ├──▶ await storage.save_graph(graph)                                    │
│     │                                                                       │
│     ├──▶ event_bus.publish(CRAWL_COMPLETED)                                 │
│     │                                                                       │
│     ├──▶ plugin_manager.teardown() для кожного плагіна                      │
│     │                                                                       │
│     ├──▶ await driver.close()                                               │
│     │                                                                       │
│     └──▶ await storage.close()                                              │
│                                                                             │
│  5. РЕЗУЛЬТАТ                                                               │
│     return graph                                                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Transient Objects

### Що створюється автоматично

| Об'єкт | Створюється | Знищується | Примітка |
|--------|-------------|------------|----------|
| `html` | `driver.fetch()` | `_cleanup_memory()` | Не зберігається в Node |
| `html_tree` | `_parse_html()` | `_cleanup_memory()` | BeautifulSoup дерево |
| `NodePluginContext` | `process_html()` | після виконання | Передається між плагінами |
| `MiddlewareContext` | перед fetch | після fetch | Передається між middleware |
| `FetchResponse` | `driver.fetch()` | після process | DTO для відповіді |
| `CrawlerEvent` | EventBus | після notify | Зберігається в history якщо enabled |

### Що зберігається

| Об'єкт | Scope | Примітка |
|--------|-------|----------|
| `Node` | Graph lifetime | metadata, user_data зберігаються |
| `Edge` | Graph lifetime | anchor_text, link_type |
| `Graph` | Application | nodes, edges, stats |
| `EventBus.history` | Optional | Якщо enabled |

### Hidden Factories

```python
# 1. Node Factory (внутрішня)
# В Spider використовується:
node = container.node_class(
    url=url,
    depth=depth,
    plugin_manager=plugin_manager
)

# 2. Edge Factory (внутрішня)
# В LinkProcessor:
edge = container.edge_class(
    source_node_id=source.node_id,
    target_node_id=target.node_id,
    anchor_text=anchor,
    link_type=types
)

# 3. Plugin Context Factory
# В Node.process_html():
context = NodePluginContext(
    node=self,
    url=self.url,
    depth=self.depth,
    ...
)
```

---

## 📊 Діаграма залежностей

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      DEPENDENCY FLOW                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  crawl(url, ...)                                                            │
│       │                                                                     │
│       ▼                                                                     │
│  _create_container()                                                        │
│       │                                                                     │
│       ├──▶ DriverFactory.create_driver()                                    │
│       │         │                                                           │
│       │         └──▶ _DRIVER_REGISTRY["http"]() → HTTPDriver                │
│       │                                                                     │
│       ├──▶ StorageFactory.create_storage()                                  │
│       │         │                                                           │
│       │         └──▶ _STORAGE_REGISTRY["memory"]() → MemoryStorage          │
│       │                                                                     │
│       ├──▶ EventBus()                                                       │
│       │                                                                     │
│       ├──▶ Scheduler(url_rules)                                             │
│       │                                                                     │
│       └──▶ NodePluginManager(plugins)                                       │
│                   │                                                         │
│                   └──▶ get_default_node_plugins()                           │
│                             • MetadataExtractorPlugin                       │
│                             • LinkExtractorPlugin                           │
│                             • TextExtractorPlugin                           │
│       │                                                                     │
│       ▼                                                                     │
│  ApplicationContainer(driver, storage, scheduler, event_bus, plugins)       │
│       │                                                                     │
│       ▼                                                                     │
│  Spider(container)                                                          │
│       │                                                                     │
│       ▼                                                                     │
│  await spider.crawl(start_url)                                              │
│       │                                                                     │
│       ▼                                                                     │
│  return Graph                                                               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔗 Навігація

- [Architecture Overview](./ARCHITECTURE_OVERVIEW.md)
- [Layer Specification](./LAYER_SPECIFICATION.md)
- [Component Catalog](./COMPONENT_CATALOG.md)
- [Communication Channels](./COMMUNICATION_CHANNELS.md)
- [Plugin System](./PLUGIN_SYSTEM.md)
- [Extension Points](./EXTENSION_POINTS.md)
- **Factory & Lifecycle** (поточний документ)
