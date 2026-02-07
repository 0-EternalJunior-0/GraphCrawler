# 6. Extension Points (Точки розширення)

## 📋 Зміст

1. [Огляд точок розширення](#огляд-точок-розширення)
2. [Кастомні Node та Edge класи](#кастомні-node-та-edge-класи)
3. [Кастомні драйвери](#кастомні-драйвери)
4. [Кастомні Storage](#кастомні-storage)
5. [Кастомні стратегії](#кастомні-стратегії)
6. [URL Rules](#url-rules)
7. [Плагіни та Middleware](#плагіни-та-middleware)
8. [Перевизначення фабрик](#перевизначення-фабрик)

---

## Огляд точок розширення

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         EXTENSION POINTS MAP                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ DOMAIN LAYER (Entities)                                              │    │
│  │                                                                      │    │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌─────────────────┐    │    │
│  │  │   Custom Node    │  │   Custom Edge    │  │ Custom Graph    │    │    │
│  │  │  (node_class)    │  │  (edge_class)    │  │ (graph_class)   │    │    │
│  │  └──────────────────┘  └──────────────────┘  └─────────────────┘    │    │
│  │                                                                      │    │
│  │  ┌──────────────────────────────────────────────────────────────┐   │    │
│  │  │                    STRATEGIES                                 │   │    │
│  │  │  • MergeStrategy (first, last, merge, newest, oldest, custom) │   │    │
│  │  │  • ChangeDetectionStrategy (hash, metadata, custom)           │   │    │
│  │  │  • HashStrategy (IContentHashStrategy Protocol)               │   │    │
│  │  │  • EdgeCreationStrategy (all, new_only, max_in_degree, ...)   │   │    │
│  │  └──────────────────────────────────────────────────────────────┘   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ INFRASTRUCTURE LAYER (Replaceable via Registry)                      │    │
│  │                                                                      │    │
│  │  ┌──────────────────────┐  ┌──────────────────────────────────┐     │    │
│  │  │    Custom Driver     │  │       Custom Storage              │     │    │
│  │  │  register_driver()   │  │    register_storage()             │     │    │
│  │  │                      │  │                                   │     │    │
│  │  │  • http (default)    │  │  • memory (default)               │     │    │
│  │  │  • async             │  │  • json                           │     │    │
│  │  │  • playwright        │  │  • sqlite                         │     │    │
│  │  │  • stealth           │  │  • postgresql                     │     │    │
│  │  │  • [your_driver]     │  │  • mongodb                        │     │    │
│  │  │                      │  │  • [your_storage]                 │     │    │
│  │  └──────────────────────┘  └──────────────────────────────────┘     │    │
│  │                                                                      │    │
│  │  ┌──────────────────────────────────────────────────────────────┐   │    │
│  │  │    Custom Adapters (HTML Parsers)                            │   │    │
│  │  │    • BeautifulSoup (default)                                 │   │    │
│  │  │    • lxml                                                    │   │    │
│  │  │    • [your_adapter]                                          │   │    │
│  │  └──────────────────────────────────────────────────────────────┘   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ EXTENSIONS LAYER (Plugins & Middleware)                              │    │
│  │                                                                      │    │
│  │  ┌──────────────────────┐  ┌──────────────────────────────────┐     │    │
│  │  │    Node Plugins      │  │       Middleware                  │     │    │
│  │  │  BaseNodePlugin      │  │    BaseMiddleware                 │     │    │
│  │  │                      │  │                                   │     │    │
│  │  │  • ON_NODE_CREATED   │  │  • PRE_REQUEST                    │     │    │
│  │  │  • ON_BEFORE_SCAN    │  │  • POST_REQUEST                   │     │    │
│  │  │  • ON_HTML_PARSED    │  │  • POST_RESPONSE                  │     │    │
│  │  │  • ON_AFTER_SCAN     │  │                                   │     │    │
│  │  │                      │  │                                   │     │    │
│  │  └──────────────────────┘  └──────────────────────────────────┘     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ APPLICATION LAYER (Crawl Modes via Registry)                         │    │
│  │                                                                      │    │
│  │  ┌──────────────────────────────────────────────────────────────┐   │    │
│  │  │    Crawl Mode Registry                                        │   │    │
│  │  │    register_crawl_mode()                                      │   │    │
│  │  │                                                               │   │    │
│  │  │    • sequential (default)                                     │   │    │
│  │  │    • multiprocessing                                          │   │    │
│  │  │    • celery                                                   │   │    │
│  │  │    • [your_mode]                                              │   │    │
│  │  └──────────────────────────────────────────────────────────────┘   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Кастомні Node та Edge класи

### Успадкування Node

**Файл:** `domain/entities/node.py`

Node можна розширити для додавання кастомних полів та логіки.

```python
from graph_crawler.domain.entities.node import Node
from typing import Optional, List
from pydantic import Field

class MLNode(Node):
    """
    Кастомний Node з ML полями.
    
    Pydantic автоматично серіалізує всі поля,
    включаючи кастомні.
    """
    
    # Кастомні поля (будуть збережені в JSON/SQLite)
    ml_score: Optional[float] = None
    ml_priority: Optional[int] = None
    embedding: Optional[List[float]] = None
    
    # Field з default_factory
    tags: List[str] = Field(default_factory=list)
    
    # Кастомний метод
    def calculate_relevance(self) -> float:
        """Обчислює релевантність на основі ML score та metadata."""
        base_score = self.ml_score or 0.5
        
        # Підвищуємо score якщо є ключові слова в title
        if self.get_title():
            keywords = ['job', 'vacancy', 'career']
            if any(kw in self.get_title().lower() for kw in keywords):
                base_score += 0.2
        
        return min(base_score, 1.0)

# Використання
graph = crawl(
    "https://example.com",
    node_class=MLNode,  # ← Передаємо кастомний клас
)

# Доступ до кастомних полів
for node in graph:
    if isinstance(node, MLNode):
        print(f"{node.url}: score={node.ml_score}, relevance={node.calculate_relevance()}")
```

### Кастомна Hash Strategy

```python
from graph_crawler.domain.entities.node import Node, IContentHashStrategy
import hashlib

class H1HashStrategy:
    """
    Обчислює hash тільки від H1 заголовка.
    
    Корисно якщо важливо відстежувати зміни тільки заголовків.
    
    Контракт IContentHashStrategy:
    - compute_hash() MUST повертати SHA256 hex digest (64 символи)
    - MUST бути детермінованим
    """
    
    def compute_hash(self, node: Node) -> str:
        h1 = node.metadata.get('h1', '') or ''
        return hashlib.sha256(h1.encode('utf-8')).hexdigest()

# Використання через node.hash_strategy
node = Node(url="https://example.com")
node.hash_strategy = H1HashStrategy()

# Після process_html:
await node.process_html(html)
hash_value = node.get_content_hash()  # Використає H1HashStrategy
```

### Успадкування Edge

```python
from graph_crawler.domain.entities.edge import Edge
from typing import Optional

class SEOEdge(Edge):
    """
    Edge з SEO атрибутами.
    
    Зберігає rel="nofollow", sponsored, ugc атрибути.
    """
    
    follow: bool = True
    sponsored: bool = False
    ugc: bool = False
    dofollow_weight: float = 1.0
    
    def get_seo_score(self) -> float:
        """Обчислює SEO вагу посилання."""
        if not self.follow:
            return 0.0
        if self.sponsored or self.ugc:
            return 0.3
        return self.dofollow_weight

# Використання
graph = crawl(
    "https://example.com",
    edge_class=SEOEdge,  # ← Передаємо кастомний клас
)
```

---

## Кастомні драйвери

### Реєстрація через Registry Pattern

**Файл:** `application/services/driver_factory.py`

```python
from graph_crawler.application.services import register_driver, create_driver
from graph_crawler.domain.interfaces.driver import IDriver
from graph_crawler.domain.value_objects.models import FetchResponse
from typing import List

class SeleniumDriver:
    """
    Кастомний Selenium драйвер.
    
    Реалізує IDriver Protocol:
    - async def fetch(url: str) -> FetchResponse
    - async def fetch_many(urls: List[str]) -> List[FetchResponse]
    - async def close() -> None
    """
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.driver = None  # Selenium WebDriver
    
    async def fetch(self, url: str) -> FetchResponse:
        """Завантажує сторінку через Selenium."""
        # Реалізація fetch через Selenium
        try:
            # self.driver.get(url)
            # html = self.driver.page_source
            html = "<html>...selenium content...</html>"  # приклад
            return FetchResponse(
                url=url,
                html=html,
                status_code=200,
                headers={},
                error=None
            )
        except Exception as e:
            return FetchResponse(
                url=url,
                html=None,
                status_code=None,
                headers={},
                error=str(e)
            )
    
    async def fetch_many(self, urls: List[str]) -> List[FetchResponse]:
        """Batch завантаження (послідовно для Selenium)."""
        return [await self.fetch(url) for url in urls]
    
    async def close(self) -> None:
        """Закриває браузер."""
        if self.driver:
            self.driver.quit()

# Реєстрація драйвера
register_driver("selenium", lambda cfg: SeleniumDriver(cfg))

# Перевірка доступних драйверів
from graph_crawler.application.services import get_available_drivers
print(get_available_drivers())
# ['http', 'async', 'playwright', 'stealth', 'selenium']

# Використання
graph = crawl(
    "https://example.com",
    driver="selenium",
    driver_config={"headless": True}
)

# Або через create_driver
driver = create_driver("selenium", {"headless": True})
```

### IDriver Protocol

```python
from typing import Protocol, List
from graph_crawler.domain.value_objects.models import FetchResponse

class IDriver(Protocol):
    """
    Інтерфейс драйвера (Protocol для Duck Typing).
    
    Будь-який клас з цими методами є валідним драйвером.
    """
    
    async def fetch(self, url: str) -> FetchResponse:
        """Завантажує одну сторінку."""
        ...
    
    async def fetch_many(self, urls: List[str]) -> List[FetchResponse]:
        """Batch завантаження множини URL."""
        ...
    
    async def close(self) -> None:
        """Закриває драйвер та звільняє ресурси."""
        ...
```

---

## Кастомні Storage

### Реєстрація через Registry Pattern

**Файл:** `application/services/storage_factory.py`

```python
from graph_crawler.application.services import register_storage, create_storage
from graph_crawler.domain.interfaces.storage import IStorage
from typing import Optional

class RedisStorage:
    """
    Кастомний Redis storage.
    
    Реалізує IStorage Protocol:
    - async def save_graph(graph) -> bool
    - async def load_graph() -> Optional[Graph]
    - async def exists() -> bool
    - async def close() -> None
    """
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.host = self.config.get('host', 'localhost')
        self.port = self.config.get('port', 6379)
        self.db = self.config.get('db', 0)
        self.client = None
    
    async def save_graph(self, graph) -> bool:
        """Зберігає граф в Redis."""
        import json
        try:
            data = {
                'nodes': [n.model_dump() for n in graph.nodes.values()],
                'edges': [e.model_dump() for e in graph.edges]
            }
            # await self.client.set('graph', json.dumps(data))
            return True
        except Exception:
            return False
    
    async def load_graph(self):
        """Завантажує граф з Redis."""
        # data = await self.client.get('graph')
        # ...
        return None
    
    async def exists(self) -> bool:
        """Перевіряє чи існує збережений граф."""
        return False
    
    async def clear(self) -> bool:
        """Очищає storage."""
        # await self.client.delete('graph')
        return True
    
    async def close(self) -> None:
        """Закриває з'єднання."""
        if self.client:
            await self.client.close()

# Реєстрація storage
register_storage("redis", lambda cfg: RedisStorage(cfg))

# Перевірка доступних типів
from graph_crawler.application.services import get_available_storage_types
print(get_available_storage_types())
# ['memory', 'json', 'sqlite', 'postgresql', 'mongodb', 'redis']

# Використання
graph = crawl(
    "https://example.com",
    storage="redis",
    storage_config={"host": "127.0.0.1", "port": 6380}
)
```

### IStorage Protocol

```python
from typing import Protocol, Optional
from graph_crawler.domain.entities.graph import Graph

class IStorage(Protocol):
    """
    Інтерфейс storage (Protocol для Duck Typing).
    
    Складається з:
    - IStorageReader: load_graph(), exists()
    - IStorageWriter: save_graph(), save_partial(), clear()
    - IStorageLifecycle: close(), __aenter__(), __aexit__()
    """
    
    async def save_graph(self, graph: Graph) -> bool:
        """Зберігає повний граф."""
        ...
    
    async def load_graph(self) -> Optional[Graph]:
        """Завантажує граф."""
        ...
    
    async def exists(self) -> bool:
        """Перевіряє наявність даних."""
        ...
    
    async def clear(self) -> bool:
        """Очищує storage."""
        ...
    
    async def close(self) -> None:
        """Закриває storage."""
        ...
```

---

## Кастомні стратегії

### Merge Strategies

**Файл:** `domain/entities/registries.py`

```python
from graph_crawler.domain.entities.registries import register_merge_strategy
from graph_crawler.domain.entities.merge_strategies import BaseMergeStrategy

class SmartMergeStrategy(BaseMergeStrategy):
    """
    Інтелектуальне злиття нод з урахуванням ML score .
    """
    
    def merge(self, node1, node2):
        """Повертає ноду з вищим ML score."""
        score1 = node1.user_data.get('ml_score', 0)
        score2 = node2.user_data.get('ml_score', 0)
        return node1 if score1 >= score2 else node2

# Реєстрація
register_merge_strategy("smart", SmartMergeStrategy)

# Використання
from graph_crawler.application.context import with_merge_strategy

with with_merge_strategy('smart'):
    g3 = g1 + g2  # Використає SmartMergeStrategy
```

### Доступні Merge Strategies

| Стратегія | Опис | Use Case |
|-----------|------|----------|
| `first` | Залишає node з першого графа | Зберегти оригінал |
| `last` | Бере node з другого графа (default) | Оновити на новий |
| `merge` | Інтелектуальне об'єднання metadata | Зберегти все |
| `newest` | Вибирає node з найновішим created_at | Incremental crawl |
| `oldest` | Вибирає node з найстарішим created_at | Історичні дані |
| `custom` | Користувацька функція | Специфічна логіка |

### Crawl Mode Registry

```python
from graph_crawler.domain.entities.registries import register_crawl_mode
from graph_crawler.application.use_cases.crawling.spider import BaseSpider

class DistributedSpider(BaseSpider):
    """Кастомний розподілений Spider."""
    
    async def crawl(self, start_url: str):
        # Кастомна логіка розподіленого краулінгу
        pass

# Реєстрація
register_crawl_mode("distributed", DistributedSpider)

# Використання
from graph_crawler.domain.value_objects.configs import CrawlerConfig

config = CrawlerConfig(
    url="https://example.com",
    mode="distributed",  # ← Кастомний режим
    workers=100
)
```

---

## URL Rules

### Фільтрація та пріоритизація URL

```python
from graph_crawler.domain.value_objects.models import URLRule

rules = [
    # Заборонити admin URLs
    URLRule(
        pattern=r"/admin/",
        should_scan=False
    ),
    
    # Пріоритет для продуктів
    URLRule(
        pattern=r"/products/",
        priority=10,  # 1-10, 10 = найвищий
        should_scan=True
    ),
    
    # Низький пріоритет для блогу
    URLRule(
        pattern=r"/blog/",
        priority=3
    ),
    
    # Не створювати edges для зовнішніх посилань
    URLRule(
        pattern=r"^https?://(?!example\.com)",
        create_edge=False,
        should_scan=False
    ),
    
    # Не переходити за посиланнями з форуму
    URLRule(
        pattern=r"/forum/",
        should_follow_links=False
    )
]

graph = crawl(
    "https://example.com",
    url_rules=rules
)
```

### URLRule атрибути

| Атрибут | Тип | Default | Опис |
|---------|-----|---------|------|
| `pattern` | str | - | Regex патерн для URL |
| `priority` | int | 5 | Пріоритет 1-10 |
| `should_scan` | bool | None | Перебиває default логіку сканування |
| `should_follow_links` | bool | None | Чи переходити за знайденими посиланнями |
| `create_edge` | bool | None | Чи створювати edge для цього URL |

---

## Плагіни та Middleware

### Детальна документація

Дивіться [Plugin System](./PLUGIN_SYSTEM.md) для повної документації:

- **Node Plugins**: ON_NODE_CREATED, ON_BEFORE_SCAN, ON_HTML_PARSED, ON_AFTER_SCAN
- **Middleware**: PRE_REQUEST, POST_REQUEST, POST_RESPONSE

### Швидкий приклад плагіна

```python
from graph_crawler.extensions.plugins.node import BaseNodePlugin, NodePluginType

class KeywordAnalyzerPlugin(BaseNodePlugin):
    """Аналізує наявність ключових слів на сторінці."""
    
    def __init__(self, keywords: list):
        self.keywords = keywords
    
    @property
    def name(self):
        return "keyword_analyzer"
    
    @property
    def plugin_type(self):
        return NodePluginType.ON_HTML_PARSED
    
    def execute(self, context):
        text = context.user_data.get('text_content', '').lower()
        
        found = [kw for kw in self.keywords if kw.lower() in text]
        context.user_data['keywords_found'] = found
        context.user_data['keyword_density'] = len(found) / len(self.keywords)
        
        return context

# Використання
graph = crawl(
    "https://example.com",
    plugins=[KeywordAnalyzerPlugin(['python', 'api', 'package_crawler'])]
)
```

---

## Перевизначення фабрик

### Driver Factory Override

```python
# Перезаписати існуючий драйвер
from graph_crawler.application.services import register_driver

def custom_http_factory(config):
    """Кастомна версія HTTP драйвера з додатковим логуванням."""
    from graph_crawler.infrastructure.transport import HTTPDriver
    
    driver = HTTPDriver(config)
    # Додати wrapper для логування
    return LoggingDriverWrapper(driver)

# Перезаписуємо http драйвер (Warning буде в логах)
register_driver("http", custom_http_factory)
```

### Storage Factory Override

```python
# Перезаписати існуючий storage
from graph_crawler.application.services import register_storage

def custom_sqlite_factory(config):
    """SQLite з шифруванням."""
    from graph_crawler.infrastructure.persistence import SQLiteStorage
    
    storage = SQLiteStorage(config)
    return EncryptedStorageWrapper(storage)

register_storage("sqlite", custom_sqlite_factory)
```

---

## 📊 Таблиця точок розширення

| Компонент | Спосіб розширення | Файл | Інтерфейс |
|-----------|-------------------|------|----------|
| Node | Успадкування | `domain/entities/node.py` | - |
| Edge | Успадкування | `domain/entities/edge.py` | - |
| Driver | Registry Pattern | `application/services/driver_factory.py` | IDriver Protocol |
| Storage | Registry Pattern | `application/services/storage_factory.py` | IStorage Protocol |
| Crawl Mode | Registry Pattern | `domain/entities/registries.py` | BaseSpider |
| Merge Strategy | Registry Pattern | `domain/entities/registries.py` | BaseMergeStrategy |
| Hash Strategy | Protocol | `domain/entities/node.py` | IContentHashStrategy |
| URL Filtering | URLRule | `domain/value_objects/models.py` | - |
| Node Plugin | BaseNodePlugin | `extensions/plugins/node/base.py` | NodePluginType |
| Middleware | BaseMiddleware | `extensions/middleware/base.py` | MiddlewareType |

---

## 🔗 Навігація

- [Architecture Overview](./ARCHITECTURE_OVERVIEW.md)
- [Layer Specification](./LAYER_SPECIFICATION.md)
- [Component Catalog](./COMPONENT_CATALOG.md)
- [Communication Channels](./COMMUNICATION_CHANNELS.md)
- [Plugin System](./PLUGIN_SYSTEM.md)
- **Extension Points** (поточний документ)
- [Factory & Lifecycle](./FACTORY_LIFECYCLE.md)
