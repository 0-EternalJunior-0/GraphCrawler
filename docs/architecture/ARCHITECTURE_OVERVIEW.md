# 1. Architecture Overview (Огляд архітектури)

## 🏗️ Високорівнева діаграма системи

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           GraphCrawler Architecture                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                          API LAYER (Presentation)                        │    │
│  │  ┌─────────┐  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐       │    │
│  │  │ crawl() │  │async_crawl()│  │ Crawler      │  │ AsyncCrawler │       │    │
│  │  │ (sync)  │  │  (async)    │  │ (context mgr)│  │ (async ctx)  │       │    │
│  │  └────┬────┘  └──────┬──────┘  └──────┬───────┘  └──────┬───────┘       │    │
│  │       │              │                │                  │               │    │
│  │       └──────────────┴────────────────┴──────────────────┘               │    │
│  │                               │                                          │    │
│  └───────────────────────────────┼──────────────────────────────────────────┘    │
│                                  ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                      APPLICATION LAYER (Use Cases)                       │    │
│  │  ┌──────────┐  ┌──────────────┐  ┌───────────────┐  ┌────────────────┐  │    │
│  │  │ Spider   │  │ Scheduler    │  │ LinkProcessor │  │ NodeScanner    │  │    │
│  │  │          │  │ (Queue + URL │  │ (Link Extract)│  │ (HTML Parse)   │  │    │
│  │  │ Orchestr.│  │   Rules)     │  │               │  │                │  │    │
│  │  └────┬─────┘  └──────┬───────┘  └───────┬───────┘  └────────┬───────┘  │    │
│  │       │               │                  │                   │          │    │
│  │  ┌────┴───────────────┴──────────────────┴───────────────────┴────┐     │    │
│  │  │                    SERVICES & FACTORIES                         │     │    │
│  │  │  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────┐  │     │    │
│  │  │  │ DriverFactory   │  │ StorageFactory  │  │ ApplicationCont.│ │     │    │
│  │  │  │ (OCP Registry)  │  │ (OCP Registry)  │  │ (DI Container)  │ │     │    │
│  │  │  └─────────────────┘  └─────────────────┘  └────────────────┘  │     │    │
│  │  └────────────────────────────────────────────────────────────────┘     │    │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                  │                                               │
│                                  ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                         DOMAIN LAYER (Core)                              │    │
│  │  ┌─────────────────────────────────────────────────────────────────┐    │    │
│  │  │                       ENTITIES                                   │    │    │
│  │  │  ┌────────┐  ┌────────┐  ┌────────┐  ┌─────────────────────┐   │    │    │
│  │  │  │ Node   │  │ Edge   │  │ Graph  │  │ GraphOperations     │   │    │    │
│  │  │  │(Pydanti)│  │(Pydant)│  │(Manager)│ │ GraphStatistics     │   │    │    │
│  │  │  └────────┘  └────────┘  └────────┘  └─────────────────────┘   │    │    │
│  │  └─────────────────────────────────────────────────────────────────┘    │    │
│  │  ┌──────────────────────────────────────────────────────────────────┐   │    │
│  │  │                    VALUE OBJECTS                                  │   │    │
│  │  │  ┌─────────────┐  ┌──────────────┐  ┌──────────────────────┐    │   │    │
│  │  │  │ URLRule     │  │ FetchResponse│  │ CrawlerConfig        │    │   │    │
│  │  │  │ (Filtering) │  │ (HTTP Result)│  │ (Settings)           │    │   │    │
│  │  │  └─────────────┘  └──────────────┘  └──────────────────────┘    │   │    │
│  │  └──────────────────────────────────────────────────────────────────┘   │    │
│  │  ┌──────────────────────────────────────────────────────────────────┐   │    │
│  │  │                    INTERFACES (Protocols)                         │   │    │
│  │  │  ┌─────────┐  ┌─────────┐  ┌───────────┐  ┌──────────────────┐  │   │    │
│  │  │  │ IDriver │  │IStorage │  │ IFilter   │  │ IEventBus        │  │   │    │
│  │  │  │(Fetch)  │  │(Save/Load)│ │ (URL Rule)│  │ (Observer)       │  │   │    │
│  │  │  └─────────┘  └─────────┘  └───────────┘  └──────────────────┘  │   │    │
│  │  └──────────────────────────────────────────────────────────────────┘   │    │
│  │  ┌──────────────────────────────────────────────────────────────────┐   │    │
│  │  │                    EVENTS (Event-Driven)                          │   │    │
│  │  │  ┌─────────────┐  ┌─────────────┐  ┌───────────────────────────┐ │   │    │
│  │  │  │ EventType   │  │ CrawlerEvent│  │ EventBus (Observer Pattern)│ │   │    │
│  │  │  │ (50+ types) │  │ (Data Model)│  │ (Pub/Sub)                  │ │   │    │
│  │  │  └─────────────┘  └─────────────┘  └───────────────────────────┘ │   │    │
│  │  └──────────────────────────────────────────────────────────────────┘   │    │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                  │                                               │
│                                  ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                    INFRASTRUCTURE LAYER                                  │    │
│  │  ┌──────────────────────┐  ┌──────────────────────────────────────────┐ │    │
│  │  │  TRANSPORT (Drivers) │  │  PERSISTENCE (Storage)                   │ │    │
│  │  │  ┌───────────────┐   │  │  ┌──────────────┐  ┌──────────────┐     │ │    │
│  │  │  │ HTTPDriver    │   │  │  │MemoryStorage │  │ JSONStorage  │     │ │    │
│  │  │  │ (aiohttp)     │   │  │  │ (<1K nodes)  │  │ (<10K nodes) │     │ │    │
│  │  │  ├───────────────┤   │  │  ├──────────────┤  ├──────────────┤     │ │    │
│  │  │  │ AsyncDriver   │   │  │  │ SQLiteStorage│  │ PostgreSQL   │     │ │    │
│  │  │  │ (concurrent)  │   │  │  │ (<100K nodes)│  │ (100K+)      │     │ │    │
│  │  │  ├───────────────┤   │  │  ├──────────────┤  ├──────────────┤     │ │    │
│  │  │  │ Playwright    │   │  │  │ MongoDB      │  │ AutoStorage  │     │ │    │
│  │  │  │ (JS Rendering)│   │  │  │ (100K+)      │  │ (Auto-scale) │     │ │    │
│  │  │  └───────────────┘   │  │  └──────────────┘  └──────────────┘     │ │    │
│  │  └──────────────────────┘  └──────────────────────────────────────────┘ │    │
│  │  ┌──────────────────────┐  ┌──────────────────────────────────────────┐ │    │
│  │  │  ADAPTERS            │  │  MESSAGING (Distributed)                 │ │    │
│  │  │  ┌───────────────┐   │  │  ┌──────────────┐  ┌──────────────┐     │ │    │
│  │  │  │ BeautifulSoup │   │  │  │ Celery App   │  │ CelerySpider │     │ │    │
│  │  │  │ Adapter       │   │  │  │ (Task Queue) │  │ (Distributed)│     │ │    │
│  │  │  ├───────────────┤   │  │  ├──────────────┤  ├──────────────┤     │ │    │
│  │  │  │ lxml Adapter  │   │  │  │ Redis Broker │  │ EasyDist     │     │ │    │
│  │  │  │ (Fast Parse)  │   │  │  │              │  │ Crawler      │     │ │    │
│  │  │  └───────────────┘   │  │  └──────────────┘  └──────────────┘     │ │    │
│  │  └──────────────────────┘  └──────────────────────────────────────────┘ │    │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                  │                                               │
│                                  ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                       EXTENSIONS LAYER                                   │    │
│  │  ┌──────────────────────────────────────────────────────────────────┐   │    │
│  │  │                      PLUGINS (Node Processing)                    │   │    │
│  │  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐   │   │    │
│  │  │  │ Metadata    │  │ Links       │  │ Content Extractors      │   │   │    │
│  │  │  │ Extractor   │  │ Extractor   │  │ (Goose3, Newspaper...)  │   │   │    │
│  │  │  ├─────────────┤  ├─────────────┤  ├─────────────────────────┤   │   │    │
│  │  │  │ Phone       │  │ Email       │  │ Price Extractor         │   │   │    │
│  │  │  │ Extractor   │  │ Extractor   │  │                         │   │   │    │
│  │  │  ├─────────────┤  ├─────────────┤  ├─────────────────────────┤   │   │    │
│  │  │  │ Vectorizer  │  │ Text        │  │ Custom Plugins          │   │   │    │
│  │  │  │ (Embeddings)│  │ Extractor   │  │ (User Defined)          │   │   │    │
│  │  │  └─────────────┘  └─────────────┘  └─────────────────────────┘   │   │    │
│  │  └──────────────────────────────────────────────────────────────────┘   │    │
│  │  ┌──────────────────────────────────────────────────────────────────┐   │    │
│  │  │                    MIDDLEWARE (Request/Response)                  │   │    │
│  │  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐   │   │    │
│  │  │  │ RateLimit   │  │ Retry       │  │ Cache Middleware        │   │   │    │
│  │  │  │ Middleware  │  │ Middleware  │  │                         │   │   │    │
│  │  │  ├─────────────┤  ├─────────────┤  ├─────────────────────────┤   │   │    │
│  │  │  │ Proxy       │  │ UserAgent   │  │ Robots.txt Middleware   │   │   │    │
│  │  │  │ Rotation    │  │ Rotation    │  │                         │   │   │    │
│  │  │  ├─────────────┤  ├─────────────┤  ├─────────────────────────┤   │   │    │
│  │  │  │ Error       │  │ Logging     │  │ MiddlewareChain         │   │   │    │
│  │  │  │ Recovery    │  │ Middleware  │  │ (Orchestrator)          │   │   │    │
│  │  │  └─────────────┘  └─────────────┘  └─────────────────────────┘   │   │    │
│  │  └──────────────────────────────────────────────────────────────────┘   │    │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## 📐 Опис шарів (Layers)

### 1. API Layer (Presentation)

**Відповідальність:** Публічний інтерфейс для користувачів бібліотеки

| Компонент | Призначення |
|-----------|-------------|
| `crawl()` | Синхронна функція для простого старту |
| `async_crawl()` | Асинхронна функція для async контексту |
| `Crawler` | Context manager для reusable краулінгу |
| `AsyncCrawler` | Async context manager для паралельного краулінгу |

### 2. Application Layer (Use Cases)

**Відповідальність:** Бізнес-логіка та оркестрація процесу краулінгу

| Компонент | Призначення |
|-----------|-------------|
| `Spider` | Основний оркестратор процесу краулінгу |
| `Scheduler` | Управління чергою URL та пріоритетами |
| `LinkProcessor` | Обробка та фільтрація знайдених посилань |
| `NodeScanner` | Сканування вузлів та парсинг HTML |
| `DriverFactory` | Фабрика для створення драйверів (OCP) |
| `StorageFactory` | Фабрика для створення сховищ (OCP) |

### 3. Domain Layer (Core Business Logic)

**Відповідальність:** Бізнес-сутності та правила домену

| Підшар | Компоненти |
|--------|------------|
| **Entities** | `Node`, `Edge`, `Graph`, `GraphOperations`, `GraphStatistics` |
| **Value Objects** | `URLRule`, `FetchResponse`, `CrawlerConfig`, `NodeLifecycle` |
| **Interfaces** | `IDriver`, `IStorage`, `IFilter`, `IEventBus` (Protocols) |
| **Events** | `EventType`, `CrawlerEvent`, `EventBus` (Observer Pattern) |

### 4. Infrastructure Layer

**Відповідальність:** Технічні деталі реалізації

| Підшар | Компоненти |
|--------|------------|
| **Transport** | `HTTPDriver`, `AsyncDriver`, `PlaywrightDriver`, `StealthDriver` |
| **Persistence** | `MemoryStorage`, `JSONStorage`, `SQLiteStorage`, `PostgreSQL`, `MongoDB` |
| **Adapters** | `BeautifulSoupAdapter`, `lxmlAdapter`, `ScrapyAdapter` |
| **Messaging** | Celery App, CelerySpider, EasyDistributedCrawler |

### 5. Extensions Layer

**Відповідальність:** Розширення базової функціональності

| Підшар | Компоненти |
|--------|------------|
| **Plugins** | `MetadataExtractor`, `LinkExtractor`, `PhoneExtractor`, `EmailExtractor`, `Vectorizer` |
| **Middleware** | `RateLimitMiddleware`, `RetryMiddleware`, `ProxyMiddleware`, `CacheMiddleware` |

---

## 🎯 Основні архітектурні принципи

### 1. Event-Driven Architecture

```
┌──────────────┐     publish      ┌──────────────┐     subscribe    ┌──────────────┐
│   Spider     │────────────────▶│   EventBus   │◀─────────────────│  Dashboard   │
│  (Producer)  │                 │  (Observer)  │                  │  (Consumer)  │
└──────────────┘                 └──────────────┘                  └──────────────┘
                                        │
                                        │ notify
                                        ▼
                                 ┌──────────────┐
                                 │   Loggers    │
                                 │  Analytics   │
                                 │  Monitors    │
                                 └──────────────┘
```

**50+ типів подій** для моніторингу та реакції:
- Node events: `NODE_CREATED`, `NODE_SCANNED`, `NODE_FAILED`
- Crawler events: `CRAWL_STARTED`, `CRAWL_COMPLETED`
- Middleware events: `RATE_LIMIT_WAIT`, `PROXY_SELECTED`
- Storage events: `GRAPH_SAVED`, `GRAPH_LOADED`

### 2. Plugin-Based Architecture

```
                                  ┌─────────────────────┐
                                  │   NodePluginManager │
                                  │    (Coordinator)    │
                                  └─────────┬───────────┘
                                            │
              ┌─────────────────────────────┼─────────────────────────────┐
              │                             │                             │
              ▼                             ▼                             ▼
    ┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
    │ ON_NODE_CREATED │         │ ON_HTML_PARSED  │         │ ON_AFTER_SCAN   │
    │    Plugins      │         │    Plugins      │         │    Plugins      │
    │                 │         │                 │         │                 │
    │ • URL Analysis  │         │ • Metadata      │         │ • Vectorizer    │
    │ • should_scan   │         │ • Links         │         │ • Stats Export  │
    │ • Priority      │         │ • Phone/Email   │         │ • Analytics     │
    └─────────────────┘         └─────────────────┘         └─────────────────┘
```

### 3. Modular Architecture

**Принцип:** "Все є модулем - драйвер, storage, плагін"

```python
# Кожен компонент можна замінити
graph = crawl(
    "https://example.com",
    driver="playwright",      # Замінний драйвер
    storage="sqlite",         # Замінний storage
    plugins=[CustomPlugin()], # Кастомні плагіни
    url_rules=[URLRule(...)], # URL правила
)
```

### 4. Distributed-Capable Architecture

```
┌────────────────────────────────────────────────────────────┐
│                    DISTRIBUTED TOPOLOGY                     │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  ┌─────────────┐          ┌─────────────────────┐          │
│  │ Coordinator │─────────▶│ Redis/RabbitMQ      │          │
│  │  (Master)   │          │ (Message Broker)    │          │
│  └─────────────┘          └──────────┬──────────┘          │
│                                      │                     │
│                    ┌─────────────────┼─────────────────┐   │
│                    │                 │                 │   │
│                    ▼                 ▼                 ▼   │
│           ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│           │   Worker 1   │  │   Worker 2   │  │   Worker N   │
│           │  (Celery)    │  │  (Celery)    │  │  (Celery)    │
│           └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
│                  │                 │                 │       │
│                  └─────────────────┼─────────────────┘       │
│                                    │                         │
│                                    ▼                         │
│                           ┌──────────────────┐               │
│                           │ MongoDB/PostgreSQL│              │
│                           │  (Result Storage) │              │
│                           └──────────────────┘               │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 📋 SOLID Principles Implementation

| Принцип | Реалізація |
|---------|------------|
| **S**ingle Responsibility | Кожен клас має одну відповідальність (Node, Edge, Graph окремо) |
| **O**pen/Closed | Registry Pattern для драйверів та storage (можна додавати без зміни коду) |
| **L**iskov Substitution | Protocols (IDriver, IStorage) гарантують взаємозамінність |
| **I**nterface Segregation | `IStorageReader`, `IStorageWriter`, `IStorageLifecycle` |
| **D**ependency Inversion | Залежність від абстракцій (Protocols), не від конкретних класів |

---

## 🔗 Навігація по документації

| # | Документ | Опис | Аудиторія |
|---|----------|------|-----------|
| 1 | **[Architecture Overview](./ARCHITECTURE_OVERVIEW.md)** | Поточний документ | Архітектори, Senior Dev |
| 2 | [Layer Specification](./LAYER_SPECIFICATION.md) | Детальна специфікація шарів | Middle/Senior Dev |
| 3 | [Component Catalog](./COMPONENT_CATALOG.md) | Каталог компонентів | All Developers |
| 4 | [Communication Channels](./COMMUNICATION_CHANNELS.md) | Канали комунікації | Middle/Senior Dev |
| 5 | [Plugin System](./PLUGIN_SYSTEM.md) | Система плагінів | All Developers |
| 6 | [Extension Points](./EXTENSION_POINTS.md) | Точки розширення | Middle/Senior Dev |
| 7 | [Factory & Lifecycle](./FACTORY_LIFECYCLE.md) | Фабрики та життєвий цикл | Middle/Senior Dev |
| - | [API Reference](./API.md) | Публічне API | All Developers |
| - | [Distributed Crawling](./DISTRIBUTED_CRAWLING_QUICKSTART.md) | Quick start для розподіленого краулінгу | DevOps, Senior Dev |
