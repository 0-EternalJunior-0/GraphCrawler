# 2. Layer Specification (Специфікація шарів)

## 📑 Зміст

1. [API Layer](#api-layer)
2. [Application Layer](#application-layer)
3. [Domain Layer](#domain-layer)
4. [Infrastructure Layer](#infrastructure-layer)
5. [Extensions Layer](#extensions-layer)

---

## API Layer

### Призначення
Публічний інтерфейс бібліотеки - точка входу для користувачів.

### Компоненти

| Файл | Компоненти | Опис |
|------|------------|------|
| `api/__init__.py` | `crawl`, `async_crawl`, `Crawler`, `AsyncCrawler`, `crawl_sitemap` | Головні функції API |
| `api/sync.py` | `crawl()`, `Crawler` | Синхронне API |
| `api/async_.py` | `async_crawl()`, `AsyncCrawler` | Асинхронне API |
| `api/client/client.py` | `GraphCrawlerClient` | HTTP клієнт для REST API |
| `api/rest_api.py` | FastAPI endpoints | REST API сервер |
| `api/websocket_manager.py` | WebSocket Manager | Real-time оновлення |

### Канали комунікації

```
┌────────────────────────────────────────────────────────────────────┐
│                        API LAYER                                   │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│   USER CODE ─────▶ crawl() ─────▶ Spider ─────▶ Graph             │
│                        │                                           │
│                        │ (creates internally)                      │
│                        ▼                                           │
│               ApplicationContainer                                 │
│               (DI: driver, storage, plugins, event_bus)           │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

### Інтерфейси та контракти

**Вхідні (очікує від інших шарів):**
- `Spider` - з Application Layer
- `Graph`, `Node`, `Edge` - з Domain Layer
- `IDriver`, `IStorage` - з Infrastructure Layer

**Вихідні (надає іншим):**
- `crawl(url, **config) -> Graph`
- `async_crawl(url, **config) -> Graph`
- `Crawler` context manager
- `AsyncCrawler` async context manager

### Варіанти розширення

```python
# 1. Кастомний драйвер
graph = crawl("https://example.com", driver=MyCustomDriver())

# 2. Кастомний storage
graph = crawl("https://example.com", storage=MyCustomStorage())

# 3. URL Rules
rules = [URLRule(pattern=r"/admin/", should_scan=False)]
graph = crawl("https://example.com", url_rules=rules)

# 4. Плагіни
graph = crawl("https://example.com", plugins=[MyPlugin()])
```

---

## Application Layer

### Призначення
Бізнес-логіка краулінгу, оркестрація процесу, use cases.

### Компоненти

| Директорія | Компоненти | Опис |
|------------|------------|------|
| `application/use_cases/crawling/` | Spider, Scheduler, LinkProcessor | Основна логіка краулінгу |
| `application/services/` | DriverFactory, StorageFactory | Фабрики (OCP) |
| `application/context/` | ApplicationContainer, MergeContext | DI контейнери |
| `application/dto/` | NodeDTO, EdgeDTO, GraphDTO | Data Transfer Objects |

### Ключові класи

#### Spider (Оркестратор)

```python
class Spider:
    """
    Основний компонент краулінгу.
    
    Відповідальність:
    - Оркестрація процесу сканування
    - Координація Scheduler, Driver, Storage
    - Публікація подій в EventBus
    """
    
    async def crawl(self, start_url: str) -> Graph:
        """Головний метод краулінгу."""
        pass
```

#### Scheduler (Планувальник)

```python
class Scheduler:
    """
    Управління чергою URL.
    
    Відповідальність:
    - Черга URL з пріоритетами (PriorityQueue)
    - Застосування URLRule
    - Фільтрація дублікатів (Bloom Filter)
    - Domain/Path фільтрація
    """
    
    def add_url(self, url: str, depth: int) -> bool:
        """Додає URL в чергу з урахуванням правил."""
        pass
    
    def get_next_url(self) -> Optional[Tuple[str, int]]:
        """Повертає наступний URL для сканування."""
        pass
```

#### LinkProcessor

```python
class LinkProcessor:
    """
    Обробка посилань.
    
    Відповідальність:
    - Нормалізація URL
    - Валідація посилань
    - Визначення типу (internal/external)
    """
```

### Канали комунікації

```
┌────────────────────────────────────────────────────────────────────┐
│                     APPLICATION LAYER                              │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  Spider ◀────────▶ Scheduler                                       │
│    │                   │                                           │
│    │  fetch()          │ add_url(), get_next_url()                │
│    ▼                   │                                           │
│  IDriver               │                                           │
│  (Infrastructure)      │                                           │
│    │                   │                                           │
│    │  FetchResponse    │                                           │
│    ▼                   │                                           │
│  NodeScanner ──────────┤                                           │
│    │                   │                                           │
│    │ process_html()    │                                           │
│    ▼                   │                                           │
│  LinkProcessor ────────┘                                           │
│    │                                                               │
│    │ extracted_links                                               │
│    ▼                                                               │
│  Graph (Domain)                                                    │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

### Factories (OCP Pattern)

```python
# Реєстрація нового драйвера без зміни коду фабрики
from graph_crawler.application.services import register_driver

register_driver("selenium", lambda cfg: SeleniumDriver(**cfg))
driver = create_driver("selenium", {"headless": True})
```

---

## Domain Layer

### Призначення
Бізнес-сутності та правила домену. **Чиста бізнес-логіка без залежностей від інфраструктури.**

### Підшари

#### 1. Entities (Сутності)

| Клас | Файл | Опис |
|------|------|------|
| `Node` | `domain/entities/node.py` | Вузол графу (веб-сторінка) |
| `Edge` | `domain/entities/edge.py` | Ребро графу (посилання) |
| `Graph` | `domain/entities/graph.py` | Менеджер графу |
| `GraphOperations` | `domain/entities/graph_operations.py` | Арифметичні операції (+, -, &, \|) |
| `GraphStatistics` | `domain/entities/graph_statistics.py` | Статистика графу |

#### 2. Value Objects (Об'єкти-значення)

| Клас | Файл | Опис |
|------|------|------|
| `URLRule` | `domain/value_objects/models.py` | Правила фільтрації URL |
| `FetchResponse` | `domain/value_objects/models.py` | Результат HTTP запиту |
|| `ContentType` | `domain/value_objects/models.py` | Тип контенту сторінки (HTML, JSON, image, empty тощо) |
| `NodeLifecycle` | `domain/value_objects/lifecycle.py` | Етапи життєвого циклу Node |
| `CrawlerConfig` | `domain/value_objects/configs.py` | Конфігурація краулера |

#### 3. Interfaces (Protocols)

| Protocol | Файл | Методи |
|----------|------|--------|
| `IDriver` | `domain/interfaces/driver.py` | `fetch()`, `fetch_many()`, `close()` |
| `IStorage` | `domain/interfaces/storage.py` | `save_graph()`, `load_graph()`, `close()` |
| `IFilter` | `domain/interfaces/filter.py` | `should_scan()`, `apply()` |
| `IEventBus` | `domain/interfaces/event_bus.py` | `subscribe()`, `publish()` |

#### 4. Events (Event-Driven)

| Клас | Файл | Опис |
|------|------|------|
| `EventType` | `domain/events/events.py` | Enum з 50+ типами подій |
| `CrawlerEvent` | `domain/events/events.py` | Модель події |
| `EventBus` | `domain/events/event_bus.py` | Observer Pattern реалізація |

### Node Lifecycle (Життєвий цикл)

```
┌─────────────────────────────────────────────────────────────────────┐
│                      NODE LIFECYCLE                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ЕТАП 1: URL_STAGE (Створення)                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ Node(url="...")                                               │   │
│  │                                                               │   │
│  │ Доступно:                                                     │   │
│  │  • url, depth, should_scan, can_create_edges                  │   │
│  │                                                               │   │
│  │ Plugins: ON_NODE_CREATED                                      │   │
│  │  • Аналіз URL                                                 │   │
│  │  • Встановлення should_scan                                   │   │
│  │  • Визначення пріоритету                                      │   │
│  └────────────────────────────────┬─────────────────────────────┘   │
│                                   │                                  │
│                                   │ fetch HTML                       │
│                                   ▼                                  │
│  ЕТАП 2: HTML_STAGE (Обробка HTML)                                  │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ await node.process_html(html)                                 │   │
│  │                                                               │   │
│  │ INPUT:                                                        │   │
│  │  • html - HTML контент                                        │   │
│  │  • html_tree - DOM дерево                                     │   │
│  │                                                               │   │
│  │ Plugins: ON_BEFORE_SCAN → ON_HTML_PARSED → ON_AFTER_SCAN     │   │
│  │  • MetadataExtractor: title, h1, description                  │   │
│  │  • LinkExtractor: extracted_links                             │   │
│  │  • Custom plugins: user_data                                  │   │
│  │                                                               │   │
│  │ OUTPUT:                                                       │   │
│  │  • metadata - заповнені метадані                              │   │
│  │  • user_data - дані від плагінів                              │   │
│  │  • extracted_links - список URL                               │   │
│  │  • HTML ВИДАЛЕНО з пам'яті!                                   │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Контракти інтерфейсів

#### IDriver Protocol

```python
@runtime_checkable
class IDriver(Protocol):
    """Async-First інтерфейс для драйвера."""
    
    async def fetch(self, url: str) -> FetchResponse:
        """Завантажує сторінку за URL."""
        ...
    
    async def fetch_many(self, urls: List[str]) -> List[FetchResponse]:
        """Batch завантаження множини URL."""
        ...
    
    async def close(self) -> None:
        """Закриває драйвер."""
        ...
```

#### IStorage Protocol

```python
@runtime_checkable
class IStorage(IStorageReader, IStorageWriter, IStorageLifecycle, Protocol):
    """Повний Async-First інтерфейс для зберігання."""
    pass

class IStorageReader(Protocol):
    async def load_graph(self): ...
    async def exists(self) -> bool: ...

class IStorageWriter(Protocol):
    async def save_graph(self, graph) -> bool: ...
    async def save_partial(self, nodes, edges) -> bool: ...
    async def clear(self) -> bool: ...

class IStorageLifecycle(Protocol):
    async def close(self) -> None: ...
    async def __aenter__(self) -> "IStorageLifecycle": ...
    async def __aexit__(self, ...): ...
```

---

## Infrastructure Layer

### Призначення
Технічні деталі реалізації - драйвери, сховища, адаптери.

### Підшари

#### 1. Transport (Драйвери)

| Клас | Технологія | Use Case |
|------|------------|----------|
| `HTTPDriver` | aiohttp | Статичні сайти (default) |
| `AsyncDriver` | aiohttp + concurrency | Високопродуктивний краулінг |
| `PlaywrightDriver` | Playwright | JavaScript сайти, SPA |
| `StealthDriver` | Playwright + stealth | Anti-bot bypass |

#### 2. Persistence (Сховища)

| Клас | Технологія | Рекомендовано для |
|------|------------|-------------------|
| `MemoryStorage` | In-memory | < 1,000 nodes |
| `JSONStorage` | aiofiles | 1,000 - 10,000 nodes |
| `SQLiteStorage` | aiosqlite | 10,000 - 100,000 nodes |
| `PostgreSQLStorage` | asyncpg | 100,000+ nodes |
| `MongoDBStorage` | motor | 100,000+ nodes |

#### 3. Adapters (HTML Парсери)

| Клас | Бібліотека | Швидкість |
|------|------------|----------|
| `BeautifulSoupAdapter` | BeautifulSoup4 | Середня (default) |
| `lxmlAdapter` | lxml | Висока |
| `ScrapyAdapter` | Scrapy | Висока |

#### 4. Messaging (Distributed)

| Компонент | Призначення |
|-----------|-------------|
| `celery_app.py` | Celery application config |
| `celery_spider.py` | Distributed Spider |
| `easy_crawler.py` | EasyDistributedCrawler |

### Канали комунікації з іншими шарами

```
┌────────────────────────────────────────────────────────────────────┐
│                    INFRASTRUCTURE LAYER                            │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  Application Layer                                                 │
│       │                                                            │
│       │ IDriver (Protocol)                                         │
│       ▼                                                            │
│  ┌─────────────┐                                                   │
│  │ HTTPDriver  │ ◀───── implements IDriver                        │
│  │ Playwright  │                                                   │
│  │ Stealth     │                                                   │
│  └──────┬──────┘                                                   │
│         │                                                          │
│         │ FetchResponse                                            │
│         ▼                                                          │
│  Application Layer                                                 │
│                                                                    │
│  ─────────────────────────────────────────────────────────────     │
│                                                                    │
│  Application Layer                                                 │
│       │                                                            │
│       │ IStorage (Protocol)                                        │
│       ▼                                                            │
│  ┌─────────────┐                                                   │
│  │MemoryStorage│ ◀───── implements IStorage                       │
│  │ JSONStorage │                                                   │
│  │SQLiteStorage│                                                   │
│  └──────┬──────┘                                                   │
│         │                                                          │
│         │ Graph (serialized)                                       │
│         ▼                                                          │
│  File System / Database                                            │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

---

## Extensions Layer

### Призначення
Розширення базової функціональності через плагіни та middleware.

### 1. Plugins (Node Processing)

```
┌────────────────────────────────────────────────────────────────────┐
│                      PLUGIN TYPES                                   │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ON_NODE_CREATED ─▶ ON_BEFORE_SCAN ─▶ ON_HTML_PARSED ─▶ ON_AFTER_SCAN
│        │                  │                 │                │     │
│        ▼                  ▼                 ▼                ▼     │
│  ┌──────────┐      ┌──────────┐      ┌──────────┐      ┌──────────┐│
│  │URL-based │      │ Pre-HTML │      │Extractors│      │ Post-    ││
│  │ analysis │      │ setup    │      │          │      │ process  ││
│  └──────────┘      └──────────┘      └──────────┘      └──────────┘│
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

#### Вбудовані плагіни

| Плагін | Тип | Опис |
|--------|-----|------|
| `MetadataExtractorPlugin` | ON_HTML_PARSED | title, h1, description, keywords |
| `LinkExtractorPlugin` | ON_HTML_PARSED | Витягує <a href> посилання |
| `TextExtractorPlugin` | ON_HTML_PARSED | Чистий текст сторінки |
| `PhoneExtractorPlugin` | ON_HTML_PARSED | Телефонні номери |
| `EmailExtractorPlugin` | ON_HTML_PARSED | Email адреси |
| `PriceExtractorPlugin` | ON_HTML_PARSED | Ціни та зарплати |
| `RealTimeVectorizerPlugin` | ON_AFTER_SCAN | Векторизація тексту |

### 2. Middleware (Request/Response)

```
┌────────────────────────────────────────────────────────────────────┐
│                    MIDDLEWARE CHAIN                                 │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  Request ─▶ RateLimit ─▶ Proxy ─▶ UserAgent ─▶ Driver ─▶ Response │
│                                                       │            │
│            ◀── Retry ◀── ErrorRecovery ◀── Cache ◀────┘            │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

#### Вбудовані middleware

| Middleware | Тип | Опис |
|------------|-----|------|
| `RateLimitMiddleware` | PRE_REQUEST | Обмеження частоти запитів |
| `ProxyMiddleware` | PRE_REQUEST | Proxy rotation |
| `UserAgentMiddleware` | PRE_REQUEST | User-Agent rotation |
| `RetryMiddleware` | POST_REQUEST | Retry при помилках |
| `CacheMiddleware` | PRE_REQUEST | HTTP кешування |
| `RobotsMiddleware` | PRE_REQUEST | robots.txt compliance |
| `ErrorRecoveryMiddleware` | POST_REQUEST | Відновлення після помилок |

### Варіанти розширення

```python
# Кастомний плагін
class MyPlugin(BaseNodePlugin):
    @property
    def name(self):
        return "my_plugin"
    
    @property
    def plugin_type(self):
        return NodePluginType.ON_HTML_PARSED
    
    def execute(self, context):
        context.user_data['custom'] = "value"
        return context

# Кастомний middleware
class MyMiddleware(BaseMiddleware):
    @property
    def name(self):
        return "my_middleware"
    
    @property
    def middleware_type(self):
        return MiddlewareType.PRE_REQUEST
    
    def process(self, context):
        context.headers['X-Custom'] = 'value'
        return context
```

---

## 📊 Залежності між шарами

```
┌────────────────────────────────────────────────────────────────────┐
│                    DEPENDENCY FLOW                                  │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│                     API Layer                                      │
│                        │                                           │
│                        │ uses                                      │
│                        ▼                                           │
│  Extensions Layer ◀── Application Layer ──▶ Infrastructure Layer  │
│  (Plugins,Middleware)  │                    (Drivers, Storage)     │
│                        │ uses                                      │
│                        ▼                                           │
│                    Domain Layer                                    │
│                  (Entities, Events)                                │
│                                                                    │
│  ПРАВИЛО: Залежності йдуть ВНИЗ. Domain Layer не залежить від     │
│           жодного іншого шару.                                     │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```
