# API Reference (Публічне API)

> **Цільова аудиторія:** Всі розробники, від Junior до Senior  
> **Версія:** 4.0.19

## Огляд

```
graph_crawler module
├── crawl()           - Синхронний краулінг (рекомендовано)
├── async_crawl()     - Асинхронний краулінг
├── crawl_sitemap()   - Краулінг через sitemap.xml
├── Crawler           - Reusable синхронний краулер
├── AsyncCrawler      - Reusable асинхронний краулер
├── GraphCrawlerClient - Клієнт для збереження та порівняння графів
│
├── Domain Objects
│   ├── Graph         - Граф веб-сайту
│   ├── Node          - Вузол (веб-сторінка)
│   ├── Edge          - Ребро (посилання)
│   ├── URLRule       - Правило URL
│   ├── EdgeRule      - Правило для edges
│   ├── ContentType   - Тип контенту
│   └── EdgeCreationStrategy - Стратегії створення edges
│
├── Settings
│   ├── CrawlerSettings   - Головні налаштування
│   ├── DriverSettings    - Налаштування драйвера
│   └── StorageSettings   - Налаштування storage
│
├── Drivers
│   ├── HTTPDriver        - HTTP драйвер (aiohttp)
│   ├── AsyncDriver       - Async HTTP драйвер
│   └── PlaywrightDriver  - Browser драйвер
│
├── Storage
│   ├── MemoryStorage     - RAM storage
│   ├── JSONStorage       - JSON файл
│   └── SQLiteStorage     - SQLite база
│
├── Plugins
│   ├── BaseNodePlugin    - Базовий плагін
│   ├── MetadataExtractorPlugin
│   ├── LinkExtractorPlugin
│   ├── TextExtractorPlugin
│   ├── PhoneExtractorPlugin
│   ├── EmailExtractorPlugin
│   ├── PriceExtractorPlugin
│   ├── SmartPageFinderPlugin
│   ├── StructuredDataPlugin
│   ├── RealTimeVectorizerPlugin
│   └── BatchVectorizerPlugin
│
├── Exceptions
│   ├── GraphCrawlerError
│   ├── ConfigurationError
│   ├── URLError, InvalidURLError, URLBlockedError
│   ├── CrawlerError, MaxPagesReachedError, MaxDepthReachedError
│   ├── DriverError, FetchError
│   └── StorageError, SaveError, LoadError
│
└── Factories
    ├── create_driver()   - Створення драйвера
    └── create_storage()  - Створення storage
```

---

## crawl()

```python
def crawl(
    url: Optional[str] = None,
    *,
    seed_urls: Optional[list[str]] = None,
    base_graph: Optional[Graph] = None,

    # Основні параметри
    max_depth: int = 3,
    max_pages: Optional[int] = 100,
    same_domain: bool = True,
    timeout: Optional[int] = None,
    request_delay: float = 0.5,
    follow_links: bool = True,

    # Компоненти
    driver: Optional[str | IDriver] = None,
    driver_config: Optional[dict] = None,
    storage: Optional[str | IStorage] = None,
    storage_config: Optional[dict] = None,
    plugins: Optional[list[BaseNodePlugin]] = None,

    # Кастомізація
    node_class: Optional[type[Node]] = None,
    edge_class: Optional[type[Edge]] = None,
    url_rules: Optional[list[URLRule]] = None,
    edge_rules: Optional[list[EdgeRule]] = None,
    edge_strategy: str = "all",

    # Callbacks
    on_progress: Optional[Callable] = None,
    on_node_scanned: Optional[Callable] = None,
    on_error: Optional[Callable] = None,
    on_completed: Optional[Callable] = None,

    # Distributed mode
    wrapper: Optional[dict] = None,
) -> Graph
```

Синхронний краулінг веб-сайту - **простий як requests**.

🆕 **NEW in v3.2.0:** Підтримка множинних точок входу (`seed_urls`) та продовження існуючого краулінгу (`base_graph`)!

**Параметри:**

| Параметр          | Тип          | Default  | Опис                                                    |
| ----------------- | ------------ | -------- | ------------------------------------------------------- |
| `url`             | str          | None     | URL для початку краулінгу (якщо seed_urls не передано)  |
| `seed_urls` 🆕    | list[str]    | None     | Список URL для початку краулінгу (множинні точки входу) |
| `base_graph` 🆕   | Graph        | None     | Існуючий граф для продовження краулінгу (incremental)   |
| `max_depth`       | int          | 3        | Максимальна глибина обходу                              |
| `max_pages`       | int          | 100      | Максимальна кількість сторінок                          |
| `same_domain`     | bool         | True     | Сканувати тільки поточний домен                         |
| `timeout`         | int          | None     | Максимальний час в секундах                             |
| `request_delay`   | float        | 0.5      | Затримка між запитами                                   |
| `follow_links` 🆕 | bool         | True     | Переходити за посиланнями (False = тільки seed URLs)    |
| `driver`          | str/IDriver  | "http"   | "http", "async", "playwright", "stealth"                |
| `driver_config`   | dict         | None     | Конфігурація драйвера                                   |
| `storage`         | str/IStorage | "memory" | "memory", "json", "sqlite", "postgresql"                |
| `storage_config`  | dict         | None     | Конфігурація storage                                    |
| `plugins`         | list         | default  | Список плагінів                                         |
| `node_class`      | type         | Node     | Кастомний клас Node                                     |
| `edge_class`      | type         | Edge     | Кастомний клас Edge                                     |
| `url_rules`       | list         | None     | Список URLRule                                          |
| `edge_rules` 🆕   | list         | None     | Список EdgeRule для контролю edges                      |
| `edge_strategy`   | str          | "all"    | "all", "new_only", "max_in_degree", "deeper_only"       |
| `on_progress`     | Callable     | None     | Callback для прогресу                                   |
| `on_node_scanned` | Callable     | None     | Callback після сканування ноди                          |
| `on_error`        | Callable     | None     | Callback для помилок                                    |
| `on_completed`    | Callable     | None     | Callback після завершення                               |
| `wrapper`         | dict         | None     | Конфіг distributed crawling                             |

**Повертає:** `Graph`

**Приклади:**

```python
import graph_crawler as gc

# Базове використання
graph = gc.crawl("https://example.com")

# 🆕 NEW: Множинні точки входу
graph = gc.crawl(
    seed_urls=[
        "https://www.work.ua/jobs/by-category/it/",
        "https://www.work.ua/jobs/by-category/marketing/",
        "https://www.work.ua/jobs/by-category/sales/",
    ],
    max_depth=3
)

# 🆕 NEW: Продовження існуючого краулінгу
graph1 = gc.crawl("https://example.com", max_pages=50)
# ... зберегти граф ...
# Пізніше продовжити
graph2 = gc.crawl(base_graph=graph1, max_pages=100)

# 🆕 NEW: Комбінація обох
sitemap_graph = gc.crawl_sitemap("https://example.com")
# Відфільтрувати ноди...
result = gc.crawl(
    base_graph=filtered_graph,
    seed_urls=["https://example.com/new-section"],
    max_pages=100
)

# З параметрами
graph = gc.crawl(
    "https://example.com",
    max_depth=5,
    max_pages=200,
    driver="playwright"
)

# Distributed режим
config = {
    "broker": {"type": "redis", "host": "server.com", "port": 6379},
    "database": {"type": "mongodb", "host": "server.com", "port": 27017}
}
graph = gc.crawl("https://example.com", wrapper=config)
```

---

## async_crawl()

```python
async def async_crawl(
    url: str,
    *,
    # ... ті самі параметри що і crawl() (без wrapper)
) -> Graph
```

Async версія crawl() для максимальної продуктивності.

**Приклади:**

```python
import asyncio
import graph_crawler as gc

# Базове
graph = await gc.async_crawl("https://example.com")

# Паралельний краулінг
graphs = await asyncio.gather(
    gc.async_crawl("https://site1.com"),
    gc.async_crawl("https://site2.com"),
)
```

---

## crawl_sitemap()

```python
def crawl_sitemap(
    url: str,
    *,
    max_urls: Optional[int] = None,
    include_urls: bool = True,
    timeout: Optional[int] = None,
    driver: Optional[str | IDriver] = None,
    driver_config: Optional[dict] = None,
    storage: Optional[str | IStorage] = None,
    storage_config: Optional[dict] = None,
    wrapper: Optional[dict] = None,
    on_progress: Optional[Callable] = None,
    on_error: Optional[Callable] = None,
    on_completed: Optional[Callable] = None,
) -> Graph
```

Краулінг через sitemap.xml - парсить robots.txt → знаходить sitemap → обробляє всі URL.

**Приклади:**

```python
# Базове
graph = gc.crawl_sitemap("https://example.com")

# Тільки структура (без кінцевих URL)
graph = gc.crawl_sitemap("https://example.com", include_urls=False)

# З лімітом
graph = gc.crawl_sitemap("https://example.com", max_urls=1000)
```

---

## Crawler

```python
class Crawler:
    def __init__(
        self,
        *,
        max_depth: int = 3,
        max_pages: Optional[int] = 100,
        same_domain: bool = True,
        request_delay: float = 0.5,
        driver: Optional[str | IDriver] = None,
        driver_config: Optional[dict] = None,
        storage: Optional[str | IStorage] = None,
        storage_config: Optional[dict] = None,
        plugins: Optional[list[BaseNodePlugin]] = None,
        node_class: Optional[type[Node]] = None,
        edge_strategy: str = "all",
    ): ...

    def crawl(self, url: str, **kwargs) -> Graph: ...
    def close(self) -> None: ...
    def __enter__(self) -> Crawler: ...
    def __exit__(self, ...): ...
```

Reusable синхронний краулер.

**Приклад:**

```python
with gc.Crawler(max_depth=5) as crawler:
    graph1 = crawler.crawl("https://site1.com")
    graph2 = crawler.crawl("https://site2.com")
```

---

## AsyncCrawler

```python
class AsyncCrawler:
    async def crawl(self, url: str, **kwargs) -> Graph: ...
    async def close(self) -> None: ...
    async def __aenter__(self) -> AsyncCrawler: ...
    async def __aexit__(self, ...): ...
```

Async версія Crawler.

**Приклад:**

```python
async with gc.AsyncCrawler() as crawler:
    graphs = await asyncio.gather(
        crawler.crawl("https://site1.com"),
        crawler.crawl("https://site2.com"),
    )
```

---

## Graph

```python
class Graph:
    nodes: Dict[str, Node]       # {node_id: Node}
    edges: List[Edge]            # Список ребер

    def add_node(self, node: Node, overwrite: bool = False) -> Node: ...
    def add_edge(self, edge: Edge) -> Edge: ...
    def get_node_by_url(self, url: str) -> Optional[Node]: ...
    def get_node_by_id(self, node_id: str) -> Optional[Node]: ...
    def has_edge(self, source_id: str, target_id: str) -> bool: ...
    def remove_node(self, node_id: str) -> bool: ...
    def get_stats(self) -> Dict[str, int]: ...
    def copy(self) -> Graph: ...
    def clear(self) -> None: ...

    # Edge Analysis
    def get_popular_nodes(self, top_n: int = 10, by: str = 'in_degree') -> List[Node]: ...
    def get_edge_statistics(self) -> Dict[str, Any]: ...
    def find_cycles(self, max_cycles: Optional[int] = None) -> List[List[str]]: ...
    def export_edges(self, filepath: str, format: str = 'json') -> Any: ...

    # Операції
    def __add__(self, other: Graph) -> Graph: ...  # union
    def __sub__(self, other: Graph) -> Graph: ...  # difference
    def __and__(self, other: Graph) -> Graph: ...  # intersection
    def __or__(self, other: Graph) -> Graph: ...   # union
    def __xor__(self, other: Graph) -> Graph: ...  # symmetric_difference

    # Порівняння
    def __eq__(self, other: Graph) -> bool: ...
    def __lt__(self, other: Graph) -> bool: ...    # is_subgraph (strict)
    def __le__(self, other: Graph) -> bool: ...    # is_subgraph
    def __gt__(self, other: Graph) -> bool: ...    # is_supergraph (strict)
    def __ge__(self, other: Graph) -> bool: ...    # is_supergraph

    # Колекційні
    def __len__(self) -> int: ...
    def __iter__(self) -> Iterator[Node]: ...
    def __contains__(self, item: str | Node) -> bool: ...
    def __getitem__(self, key: str | int) -> Node: ...
```

---

## Node

```python
class Node(BaseModel):
    url: str
    node_id: str = Field(default_factory=uuid4)  # UUID (auto-generated)
    depth: int = 0
    scanned: bool = False
    should_scan: bool = True
    can_create_edges: bool = True
    priority: Optional[int] = None    # 1-10, None = default
    metadata: Dict[str, Any] = {}
    user_data: Dict[str, Any] = {}
    content_hash: Optional[str] = None
    response_status: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.now)
    lifecycle_stage: NodeLifecycle = NodeLifecycle.URL_STAGE

    async def process_html(self, html: str) -> List[str]: ...
    def mark_as_scanned(self) -> None: ...
    def get_content_hash(self) -> str: ...

    # Metadata helpers (Law of Demeter)
    def get_title(self) -> Optional[str]: ...
    def get_description(self) -> Optional[str]: ...
    def get_h1(self) -> Optional[str]: ...
    def get_keywords(self) -> Optional[str]: ...
    def get_meta_value(self, key: str, default: Any = None) -> Any: ...
```

---

## Edge

```python
class Edge(BaseModel):
    source_node_id: str
    target_node_id: str
    edge_id: str              # UUID (auto-generated)
    metadata: Dict[str, Any] = {}

    def add_metadata(self, key: str, value: Any) -> None: ...
    def get_meta_value(self, key: str, default: Any = None) -> Any: ...
```

---

## URLRule

```python
class URLRule(BaseModel):
    pattern: str                              # Regex патерн
    priority: int = 5                         # 1-10 (default: 5)
    should_scan: Optional[bool] = None        # Перебиває фільтри
    should_follow_links: Optional[bool] = None
    create_edge: Optional[bool] = None
```

---

## BaseNodePlugin

```python
class BaseNodePlugin(ABC):
    @property
    @abstractmethod
    def plugin_type(self) -> NodePluginType: ...

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def execute(self, context: NodePluginContext) -> NodePluginContext: ...

    def setup(self) -> None: ...
    def teardown(self) -> None: ...
```

**NodePluginType:**

- `ON_NODE_CREATED` - після створення Node (ЕТАП 1: URL)
- `ON_BEFORE_SCAN` - перед скануванням (ЕТАП 2: HTML)
- `ON_HTML_PARSED` - після парсингу HTML (ЕТАП 2: HTML)
- `ON_AFTER_SCAN` - після сканування (ЕТАП 2: HTML)
- `BEFORE_CRAWL` - перед початком краулінгу (ЕТАП 3: CRAWL)
- `AFTER_CRAWL` - після завершення краулінгу (ЕТАП 3: CRAWL)

**NodePluginContext:**

```python
@dataclass
class NodePluginContext:
    node: Any                           # Node об'єкт
    url: str
    depth: int
    should_scan: bool
    can_create_edges: bool
    html: Optional[str] = None          # Тільки ЕТАП 2
    html_tree: Optional[Any] = None     # Тільки ЕТАП 2
    parser: Optional[Any] = None        # Тільки ЕТАП 2
    metadata: Dict[str, Any] = {}
    extracted_links: List[str] = []
    user_data: Dict[str, Any] = {}
    skip_link_extraction: bool = False
    skip_metadata_extraction: bool = False
```


---

## EdgeRule

```python
class EdgeRule(BaseModel):
    """Правило для контролю створення edges."""
    
    source_pattern: Optional[str] = None   # Regex для source URL
    target_pattern: Optional[str] = None   # Regex для target URL  
    max_depth_diff: Optional[int] = None   # Макс. різниця глибини
    action: str                             # 'create' або 'skip'

    def matches(
        self, 
        source_url: str, 
        target_url: str, 
        source_depth: int, 
        target_depth: int
    ) -> bool: ...
    
    def should_create_edge(
        self,
        source_url: str,
        target_url: str,
        source_depth: int,
        target_depth: int
    ) -> Optional[bool]: ...
```

**Приклади:**

```python
from graph_crawler import EdgeRule

# Не створювати edges з blog на products
rule = EdgeRule(
    source_pattern=r'.*/blog/.*',
    target_pattern=r'.*/products/.*',
    action='skip'
)

# Обмежити edges по різниці глибини
rule = EdgeRule(max_depth_diff=2, action='skip')
```

---

## ContentType

```python
class ContentType(str, Enum):
    """
    Тип контенту сторінки (Value Object).
    
    Визначає що саме знаходиться за URL - HTML, JSON, зображення тощо.
    """
    
    # Невідомий тип
    UNKNOWN = "unknown"
    
    # Текстові формати
    HTML = "html"           # text/html
    JSON = "json"           # application/json
    XML = "xml"             # text/xml, application/xml
    TEXT = "text"           # text/plain
    CSS = "css"             # text/css
    JAVASCRIPT = "javascript"  # application/javascript
    
    # Медіа формати
    IMAGE = "image"         # image/*
    VIDEO = "video"         # video/*
    AUDIO = "audio"         # audio/*
    
    # Документи
    PDF = "pdf"             # application/pdf
    DOC = "doc"             # application/msword, etc.
    
    # Бінарні та архіви
    BINARY = "binary"       # application/octet-stream
    ARCHIVE = "archive"     # application/zip, etc.
    
    # Спеціальні стани
    EMPTY = "empty"         # HTTP 200, пустий body
    ERROR = "error"         # 4xx, 5xx, timeout
    REDIRECT = "redirect"   # HTTP 3xx без body

    # Методи детекції
    @classmethod
    def from_content_type_header(cls, content_type: Optional[str]) -> "ContentType": ...
    
    @classmethod
    def from_url(cls, url: str) -> "ContentType": ...
    
    @classmethod
    def detect(
        cls,
        content_type_header: Optional[str] = None,
        url: Optional[str] = None,
        content: Optional[str] = None,
        status_code: Optional[int] = None,
        has_error: bool = False,
    ) -> "ContentType": ...
    
    # Перевірки
    def is_text_based(self) -> bool: ...
    def is_media(self) -> bool: ...
    def is_scannable(self) -> bool: ...
```

**Приклади:**

```python
from graph_crawler import ContentType

# Детекція з HTTP header
content_type = ContentType.from_content_type_header("text/html; charset=utf-8")
print(content_type)  # ContentType.HTML

# Детекція з URL
content_type = ContentType.from_url("https://example.com/data.json")
print(content_type)  # ContentType.JSON

# Комплексна детекція
content_type = ContentType.detect(
    content_type_header="text/html",
    url="https://example.com/page",
    status_code=200
)

# Фільтрація nodes по типу
html_nodes = [n for n in graph if n.content_type == ContentType.HTML]
empty_nodes = [n for n in graph if n.content_type == ContentType.EMPTY]

# Перевірки
if content_type.is_text_based():
    print("Can parse text content")

if content_type.is_media():
    print("Skip text extraction for media")

if content_type.is_scannable():
    print("Can scan for links")
```

---

## EdgeCreationStrategy

```python
class EdgeCreationStrategy(str, Enum):
    """Стратегії створення edges в графі."""
    
    ALL = "all"                         # Всі edges (default)
    NEW_ONLY = "new_only"               # Тільки перший edge на кожну ноду
    MAX_IN_DEGREE = "max_in_degree"     # Ліміт incoming edges
    SAME_DEPTH_ONLY = "same_depth_only" # Тільки між нодами на одному рівні
    DEEPER_ONLY = "deeper_only"         # Тільки на глибші рівні
    FIRST_ENCOUNTER_ONLY = "first_encounter_only"  # Тільки перший encounter
```

**Приклади:**

```python
import graph_crawler as gc

# Мінімальний граф (дерево)
graph = gc.crawl("https://example.com", edge_strategy="new_only")

# Не створювати edges на популярні сторінки
graph = gc.crawl("https://example.com", edge_strategy="max_in_degree")

# Тільки вперед (не повертатись назад)
graph = gc.crawl("https://example.com", edge_strategy="deeper_only")
```

---

## CrawlerSettings

```python
from graph_crawler import CrawlerSettings, DriverSettings, StorageSettings

class CrawlerSettings(BaseSettings):
    """
    Головний клас конфігурації краулера.
    
    Аналог settings.py в Scrapy, але з типізацією та валідацією.
    Підтримує завантаження з .env, YAML, JSON файлів та env змінних.
    """
    
    # Basic
    project_name: str = "my_crawler"
    max_depth: int = 3                    # 1-100
    max_pages: Optional[int] = 100        # None = без ліміту
    request_delay: float = 0.5            # секунди
    timeout: Optional[int] = 300          # секунди
    
    # Domain Control
    same_domain: bool = True
    follow_links: bool = True
    allowed_domains: List[str] = []
    blocked_domains: List[str] = []
    blocked_paths: List[str] = ["/admin", "/login", "/logout", "/wp-admin"]
    
    # Components
    driver: DriverSettings = DriverSettings()
    storage: StorageSettings = StorageSettings()
    retry: RetrySettings = RetrySettings()
    concurrency: ConcurrencySettings = ConcurrencySettings()
    
    # Features
    respect_robots_txt: bool = True
    extract_metadata: bool = True
    calculate_content_hash: bool = True
    edge_strategy: str = "all"
    
    # Logging
    log_level: str = "INFO"
    
    # Custom Node Class
    node_class: Optional[str] = None      # "mymodule.MyNode"
    
    # Plugins
    plugins: List[str] = []               # ["mymodule.MyPlugin"]
    
    # URL Rules
    url_rules: List[Dict[str, Any]] = []
    
    # Class methods
    @classmethod
    def from_file(cls, path: str) -> "CrawlerSettings": ...
    
    def to_file(self, path: str) -> None: ...
    def to_crawl_kwargs(self) -> Dict[str, Any]: ...
    def get_node_class(self) -> Optional[type]: ...
    def get_plugins(self) -> list: ...
```

**Приклади:**

```python
from graph_crawler import CrawlerSettings, DriverSettings

# Базове використання
settings = CrawlerSettings()

# З параметрами
settings = CrawlerSettings(
    max_depth=5,
    max_pages=1000,
    driver=DriverSettings(type="playwright"),
)

# З YAML файлу
settings = CrawlerSettings.from_file("settings.yaml")

# З env змінних (GC_MAX_DEPTH=10, GC_DRIVER__TYPE=playwright)
settings = CrawlerSettings()  # автоматично читає env

# Використання з crawl()
graph = gc.crawl("https://example.com", **settings.to_crawl_kwargs())

# Зберегти налаштування
settings.to_file("my_settings.yaml")
```

**Приклад settings.yaml:**

```yaml
project_name: my_crawler
max_depth: 5
max_pages: 1000
request_delay: 0.5

driver:
  type: playwright
  headless: true
  browser_type: chromium

storage:
  type: sqlite
  path: ./crawl_data.db

url_rules:
  - pattern: "/products/"
    priority: 10
  - pattern: "/admin/"
    should_scan: false
```

---

## DriverSettings

```python
class DriverSettings(BaseModel):
    """Налаштування драйвера."""
    
    type: str = "http"                    # http, playwright, stealth
    user_agent: Optional[str] = None
    headers: Dict[str, str] = {}
    
    # Playwright specific
    headless: bool = True
    browser_type: str = "chromium"        # chromium, firefox, webkit
    viewport_width: int = 1920
    viewport_height: int = 1080
    block_resources: List[str] = ["image", "media", "font"]
    
    # Timeouts (ms)
    page_load_timeout: int = 30000
    navigation_timeout: int = 30000
```

---

## StorageSettings

```python
class StorageSettings(BaseModel):
    """Налаштування storage."""
    
    type: str = "memory"                  # memory, json, sqlite, postgresql, mongodb
    path: Optional[str] = None            # для файлового storage
    
    # Database specific
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
```

---

## RetrySettings

```python
class RetrySettings(BaseModel):
    """Налаштування retry."""
    
    max_retries: int = 3
    retry_delay: float = 1.0              # секунди
    backoff_factor: float = 2.0           # exponential backoff
    retry_on_status: List[int] = [429, 500, 502, 503, 504]
```

---

## ConcurrencySettings

```python
class ConcurrencySettings(BaseModel):
    """Налаштування паралелізму."""
    
    max_concurrent_requests: int = 200
    connector_limit: int = 500            # TCP з'єднання
    connector_limit_per_host: int = 200
    dns_cache_ttl: int = 300              # секунди
```

---

## FetchResponse

```python
class FetchResponse(BaseModel):
    """Відповідь від драйвера після завантаження сторінки."""
    
    url: str
    html: Optional[str] = None
    status_code: Optional[int] = None
    headers: dict[str, str] = {}
    error: Optional[str] = None
    
    # Redirect information
    final_url: Optional[str] = None
    redirect_chain: list[str] = []
    
    @property
    def is_success(self) -> bool: ...     # error is None and html is not None
    
    @property
    def is_ok(self) -> bool: ...          # status_code 2xx
    
    @property
    def is_redirect(self) -> bool: ...    # final_url != url
```

---

## Factory Functions

### create_driver()

```python
from graph_crawler import create_driver

def create_driver(
    driver: Optional[str | IDriver] = None,
    config: Optional[dict] = None
) -> IDriver:
    """
    Створює драйвер за типом або повертає переданий інстанс.
    
    Args:
        driver: "http", "async", "playwright", "stealth" або IDriver інстанс
        config: Конфігурація драйвера
    
    Returns:
        IDriver інстанс
    """
```

**Приклад:**

```python
from graph_crawler import create_driver

# HTTP драйвер (default)
driver = create_driver()

# Playwright з налаштуваннями
driver = create_driver("playwright", {
    "headless": True,
    "browser_type": "chromium"
})
```

### create_storage()

```python
from graph_crawler import create_storage

def create_storage(
    storage: Optional[str | IStorage] = None,
    config: Optional[dict] = None
) -> IStorage:
    """
    Створює storage за типом або повертає переданий інстанс.
    
    Args:
        storage: "memory", "json", "sqlite", "postgresql", "mongodb" або IStorage інстанс
        config: Конфігурація storage
    
    Returns:
        IStorage інстанс
    """
```

**Приклад:**

```python
from graph_crawler import create_storage

# Memory storage (default)
storage = create_storage()

# SQLite з шляхом
storage = create_storage("sqlite", {"path": "./data.db"})

# JSON файл
storage = create_storage("json", {"path": "./graph.json"})
```

---

## Exceptions

### Ієрархія винятків

```
GraphCrawlerError                 # Базовий виняток
├── ConfigurationError            # Помилка конфігурації
├── URLError                      # Базова помилка URL
│   ├── InvalidURLError           # URL недійсний
│   └── URLBlockedError           # URL заблокований (robots.txt)
├── CrawlerError                  # Базова помилка краулінгу
│   ├── MaxPagesReachedError      # Досягнуто max_pages
│   └── MaxDepthReachedError      # Досягнуто max_depth
├── DriverError                   # Помилка драйвера
│   └── FetchError                # Не вдалося завантажити
└── StorageError                  # Помилка storage
    ├── SaveError                 # Не вдалося зберегти
    └── LoadError                 # Не вдалося завантажити
```

**Приклади:**

```python
from graph_crawler import (
    GraphCrawlerError,
    InvalidURLError,
    MaxPagesReachedError,
    FetchError,
)

try:
    graph = gc.crawl("invalid-url")
except InvalidURLError as e:
    print(f"Invalid URL: {e}")

try:
    graph = gc.crawl("https://example.com", max_pages=10)
except MaxPagesReachedError:
    print("Page limit reached")

try:
    graph = gc.crawl("https://unreachable.com", timeout=5)
except FetchError as e:
    print(f"Fetch failed: {e}")
```

---

## GraphCrawlerClient

```python
from graph_crawler import GraphCrawlerClient

class GraphCrawlerClient:
    """
    Клієнт для збереження та управління графами.
    
    Підтримує:
    - Збереження/завантаження графів
    - Порівняння графів (diff)
    - Incremental crawling
    """
    
    def __init__(
        self,
        storage: Optional[str | IStorage] = None,
        storage_config: Optional[dict] = None
    ): ...
    
    def save_graph(
        self,
        graph: Graph,
        name: str,
        description: str = "",
        metadata: Optional[dict] = None
    ) -> str: ...
    
    def load_graph(self, name: str) -> Graph: ...
    
    def list_graphs(self) -> List[GraphMetadata]: ...
    
    def delete_graph(self, name: str) -> bool: ...
    
    def compare_graphs(
        self,
        old_graph_name: str,
        new_graph_name: str
    ) -> GraphComparisonResult: ...
```

**Приклади:**

```python
from graph_crawler import GraphCrawlerClient

# Створюємо клієнт
client = GraphCrawlerClient(storage="sqlite", storage_config={"path": "./graphs.db"})

# Зберігаємо граф
graph = gc.crawl("https://example.com")
client.save_graph(graph, "example_v1", description="Initial crawl")

# Список графів
graphs = client.list_graphs()
for g in graphs:
    print(f"{g.name}: {g.stats.total_nodes} nodes")

# Порівняння графів
graph2 = gc.crawl("https://example.com")
client.save_graph(graph2, "example_v2")

diff = client.compare_graphs("example_v1", "example_v2")
print(f"New pages: {diff.new_nodes_count}")
print(f"Removed pages: {diff.removed_nodes_count}")
```

---

## Interfaces

### IDriver

```python
from graph_crawler import IDriver

class IDriver(Protocol):
    """Інтерфейс драйвера для завантаження сторінок."""
    
    async def fetch(self, url: str) -> FetchResponse: ...
    async def close(self) -> None: ...
```

### IStorage

```python
from graph_crawler import IStorage

class IStorage(Protocol):
    """Інтерфейс storage для збереження графів."""
    
    async def save(self, graph: Graph, name: str) -> None: ...
    async def load(self, name: str) -> Graph: ...
    async def delete(self, name: str) -> bool: ...
    async def list_graphs(self) -> List[str]: ...
```

---

## Імпорти

### Основні

```python
# Функції краулінгу
from graph_crawler import crawl, async_crawl, crawl_sitemap

# Класи краулерів
from graph_crawler import Crawler, AsyncCrawler

# Domain об'єкти
from graph_crawler import Graph, Node, Edge, URLRule, EdgeRule

# Enum типи
from graph_crawler import ContentType, EdgeCreationStrategy

# Налаштування
from graph_crawler import CrawlerSettings, DriverSettings, StorageSettings

# Драйвери
from graph_crawler import HTTPDriver, AsyncDriver, PlaywrightDriver, IDriver

# Storage
from graph_crawler import MemoryStorage, JSONStorage, SQLiteStorage, IStorage

# Factories
from graph_crawler import create_driver, create_storage

# Client
from graph_crawler import GraphCrawlerClient

# Exceptions
from graph_crawler import (
    GraphCrawlerError,
    ConfigurationError,
    InvalidURLError,
    URLBlockedError,
    CrawlerError,
    MaxPagesReachedError,
    MaxDepthReachedError,
    DriverError,
    FetchError,
    StorageError,
    SaveError,
    LoadError,
)
```

### Плагіни

```python
# Base
from graph_crawler import BaseNodePlugin, NodePluginType, NodePluginContext

# Built-in плагіни
from graph_crawler.extensions.plugins.node import (
    MetadataExtractorPlugin,
    LinkExtractorPlugin,
    TextExtractorPlugin,
    get_default_node_plugins,
)

# Extractors
from graph_crawler.extensions.plugins.node.extractors import (
    PhoneExtractorPlugin,
    EmailExtractorPlugin,
    PriceExtractorPlugin,
)

# ML плагіни
from graph_crawler.extensions.plugins.node import (
    SmartPageFinderPlugin,
    SmartFinderNode,
    RelevanceLevel,
)

# Vectorization
from graph_crawler.extensions.plugins.node.vectorization import (
    RealTimeVectorizerPlugin,
    BatchVectorizerPlugin,
    search,
    cluster,
    compare,
)

# Structured Data
from graph_crawler.extensions.plugins.node.structured_data import (
    StructuredDataPlugin,
    StructuredDataOptions,
    StructuredDataResult,
    SchemaType,
)
```

---

## Наступні кроки

- [Getting Started →](../getting-started/quickstart.md)
- [Plugin System →](../extraction/plugins.md)
- [Architecture →](../architecture/ARCHITECTURE_OVERVIEW.md)
- [Changelog →](../changelog.md)

