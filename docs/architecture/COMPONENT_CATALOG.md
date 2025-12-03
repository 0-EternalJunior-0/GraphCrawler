# 3. Component Catalog (Каталог компонентів)

## 📋 Зміст

1. [Domain Entities](#domain-entities)
2. [Application Use Cases](#application-use-cases)
3. [Infrastructure Components](#infrastructure-components)
4. [Extensions Components](#extensions-components)

---

## Domain Entities

### Node (Вузол графу)

**Файл:** `domain/entities/node.py`

**Роль:** Представляє веб-сторінку в графі.

**Життєвий цикл:**
```
URL_STAGE (створення) → HTML_STAGE (після process_html)
```

**Ключові атрибути:**

| Атрибут | Тип | Опис |
|---------|-----|------|
| `url` | str | URL сторінки |
| `node_id` | str | UUID вузла |
| `depth` | int | Глибина від root |
| `should_scan` | bool | Чи сканувати |
| `can_create_edges` | bool | Чи створювати ребра |
| `metadata` | Dict | title, h1, description |
| `user_data` | Dict | Дані від плагінів |
| `content_hash` | str | SHA256 для incremental |
| `priority` | int | Пріоритет 1-10 (для Scheduler) |
| `lifecycle_stage` | NodeLifecycle | URL_STAGE або HTML_STAGE |

**Методи:**

```python
# Обробка HTML (async)
await node.process_html(html)  # → List[str] extracted_links

# Metadata accessors (Law of Demeter)
node.get_title()        # → Optional[str]
node.get_description()  # → Optional[str]
node.get_h1()           # → Optional[str]
node.get_keywords()     # → Optional[str]

# Incremental crawling
node.get_content_hash() # → str (SHA256)

# Serialization (Pydantic)
node.model_dump()       # → Dict
Node.model_validate(data, context={...})  # → Node

# Відновлення залежностей після десеріалізації
node.restore_dependencies(
    plugin_manager=pm,
    tree_parser=parser,
    hash_strategy=strategy
)
```

**Точки розширення:**

```python
# 1. Кастомний Node клас
class MLNode(Node):
    ml_score: Optional[float] = None
    ml_priority: Optional[int] = None
    embedding: Optional[List[float]] = None

graph = crawl(url, node_class=MLNode)

# 2. Кастомна hash strategy
class H1HashStrategy:
    def compute_hash(self, node: Node) -> str:
        return hashlib.sha256(node.metadata['h1'].encode()).hexdigest()

node.hash_strategy = H1HashStrategy()
```

---

### Edge (Ребро графу)

**Файл:** `domain/entities/edge.py`

**Роль:** Представляє посилання між сторінками.

**Ключові атрибути:**

| Атрибут | Тип | Опис |
|---------|-----|------|
| `edge_id` | str | UUID ребра |
| `source_node_id` | str | ID вузла-джерела |
| `target_node_id` | str | ID цільового вузла |
| `anchor_text` | str | Текст посилання |
| `link_type` | List[str] | Типи: internal, external, deeper |
| `metadata` | Dict | Redirect info, custom data |

**Точки розширення:**

```python
# Кастомний Edge клас
class SEOEdge(Edge):
    follow: bool = True
    sponsored: bool = False
    ugc: bool = False

graph = crawl(url, edge_class=SEOEdge)
```

---

### Graph (Менеджер графу)

**Файл:** `domain/entities/graph.py`

**Роль:** Управління вузлами та ребрами, операції над графами.

**CRUD операції:**

```python
# Додавання
graph.add_node(node, overwrite=False)  # → Node
graph.add_edge(edge)                    # → Edge

# Отримання
graph.get_node_by_url(url)              # → Optional[Node]
graph.get_node_by_id(node_id)           # → Optional[Node]
graph.has_edge(source_id, target_id)    # → bool (O(1))

# Видалення
graph.remove_node(node_id)              # → bool

# Редіректи
graph.handle_redirect(original_node, final_url, redirect_chain)
```

**Python API (операції):**

```python
# Колекційні
len(graph)              # Кількість вузлів
for node in graph:      # Ітерація
'url' in graph          # Перевірка наявності
graph['url']            # Доступ за URL
graph[0]                # Доступ за індексом

# Арифметичні
g3 = g1 + g2            # Union (об'єднання)
g3 = g2 - g1            # Difference (різниця)
g3 = g1 & g2            # Intersection (перетин)
g3 = g1 | g2            # Union (альтернатива)
g3 = g1 ^ g2            # Symmetric difference

# Порівняння
g1 == g2                # Рівність
g1 < g2                 # g1 є підграфом g2
g1 <= g2                # Підграф або рівний
g1 > g2                 # g1 є надграфом g2
```

**Merge Strategies (при union):**

```python
# Встановлення default стратегії
graph = Graph(default_merge_strategy='merge')

# Або через контекст
from graph_crawler.application.context import with_merge_strategy

with with_merge_strategy('newest'):
    g3 = g1 + g2  # Використає 'newest'
```

| Стратегія | Опис |
|-----------|------|
| `first` | Залишити node з першого графа |
| `last` | Взяти node з другого графа (default) |
| `merge` | Інтелектуальне об'єднання metadata |
| `newest` | Вибрати node з найновішим created_at |
| `oldest` | Вибрати node з найстарішим created_at |
| `custom` | Користувацька функція |

```python
# Кастомна стратегія merge
def my_merge(n1, n2):
    return n1 if n1.scanned else n2

from graph_crawler.domain.entities.merge_strategies import NodeMerger
merger = NodeMerger(strategy='custom', custom_merge_fn=my_merge)
```

---

### EventBus (Шина подій)

**Файл:** `domain/events/event_bus.py`

**Роль:** Observer Pattern для loose coupling компонентів.

```python
from graph_crawler.domain.events import EventBus, EventType, CrawlerEvent

bus = EventBus()

# Підписка
def on_node_scanned(event: CrawlerEvent):
    print(f"Scanned: {event.data['url']}")

bus.subscribe(EventType.NODE_SCANNED, on_node_scanned)

# Async підписка
async def async_handler(event: CrawlerEvent):
    await save_to_db(event.data)

bus.subscribe(EventType.NODE_SCANNED, async_handler)

# Публікація
bus.publish(CrawlerEvent.create(EventType.NODE_SCANNED, data={'url': '...'}))
await bus.publish_async(event)  # Для async handlers

# Історія подій
bus.enable_history(max_size=1000)
history = bus.get_history(EventType.NODE_SCANNED)
```

**50+ типів подій:**

| Категорія | Події |
|-----------|-------|
| Node | NODE_CREATED, NODE_SCANNED, NODE_FAILED, NODE_SKIPPED_UNCHANGED |
| Crawler | CRAWL_STARTED, CRAWL_COMPLETED, CRAWL_PAUSED, BATCH_COMPLETED |
| Scheduler | URL_ADDED_TO_QUEUE, URL_EXCLUDED, URL_PRIORITIZED |
| Middleware | RATE_LIMIT_WAIT, PROXY_SELECTED, RETRY_STARTED |
| Storage | GRAPH_SAVED, GRAPH_LOADED, STORAGE_UPGRADED |
| Plugin | PLUGIN_STARTED, PLUGIN_COMPLETED, PLUGIN_FAILED |
| Fetch | FETCH_STARTED, FETCH_SUCCESS, FETCH_ERROR |

---

## Application Use Cases

### Spider (Оркестратор)

**Файл:** `application/use_cases/crawling/spider.py`

**Роль:** Координація всього процесу краулінгу.

**Варіанти Spider:**

| Клас | Режим | Опис |
|------|-------|------|
| `GraphSpider` | sequential | Стандартний async spider |
| `MultiprocessingSpider` | multiprocessing | Паралельний (до 32 workers) |
| `CeleryBatchSpider` | celery | Розподілений (до 1000 workers) |
| `SitemapSpider` | sitemap | Для sitemap.xml |

```python
# Вибір режиму через config
config = CrawlerConfig(
    url="https://example.com",
    mode="multiprocessing",  # sequential, multiprocessing, celery
    workers=8
)
```

**Реєстрація кастомного Spider:**

```python
from graph_crawler.domain.entities.registries import register_crawl_mode

class MyDistributedSpider(BaseSpider):
    async def crawl(self):
        ...

register_crawl_mode("distributed", MyDistributedSpider)

# Тепер можна використовувати
config = CrawlerConfig(url="...", mode="distributed")
```

---

### Scheduler (Планувальник)

**Файл:** `application/use_cases/crawling/scheduler.py`

**Роль:** Черга URL з пріоритетами та правилами.

**Механізми пріоритизації:**

```python
# 1. URLRule (статичний пріоритет)
rules = [
    URLRule(pattern=r"/products/", priority=10),  # Високий
    URLRule(pattern=r"/blog/", priority=3),       # Низький
]

# 2. Dynamic Priority (через Node.priority)
class MLNode(Node):
    priority: Optional[int] = None

# ML плагін встановлює пріоритет динамічно
context.user_data['child_priorities'] = {url: 10}

# 3. Scheduler читає Node.priority ПЕРЕД URLRule
# Пріоритет: node.priority > URLRule.priority > default(5)
```

---

### LinkProcessor (Обробник посилань)

**Файл:** `application/use_cases/crawling/link_processor.py`

**Роль:** Фільтрація та обробка знайдених посилань.

**Edge Creation Strategies:**

```python
from graph_crawler.domain.value_objects.models import EdgeCreationStrategy

graph = crawl(
    url,
    edge_strategy="new_only",        # Тільки при першому знаходженні
    # edge_strategy="max_in_degree",  # Ліміт incoming edges
    # edge_strategy="deeper_only",    # Тільки вглиб
    max_in_degree_threshold=100       # Для max_in_degree
)
```

| Стратегія | Опис | Результат |
|-----------|------|-----------|
| `all` | Всі edges (default) | Повний граф |
| `new_only` | Edge тільки при створенні node | Дерево |
| `max_in_degree` | Ліміт incoming edges | Без hub-ів |
| `deeper_only` | Тільки вглиб | Без backlinks |
| `same_depth_only` | Тільки на тому ж рівні | Siblings |
| `first_encounter_only` | Перший edge на URL | Мінімальний граф |

**Explicit Filter Override (ML):**

```python
# ML плагін може перебивати фільтри!
context.user_data['explicit_scan_decisions'] = {
    'https://external-job-site.com/vacancy': True,  # Дозволити (перебиває domain filter)
    'https://spam-site.com': False                   # Заборонити
}
```

---

## Infrastructure Components

### Drivers (Транспорт)

**Базовий клас:** `infrastructure/transport/base.py`

| Driver | Технологія | Use Case |
|--------|------------|----------|
| `HTTPDriver` | aiohttp | Статичні сайти (default) |
| `AsyncDriver` | aiohttp + semaphore | High concurrency |
| `PlaywrightDriver` | Playwright | JavaScript SPA |
| `StealthDriver` | Playwright + stealth | Anti-bot bypass |

**Реєстрація кастомного драйвера:**

```python
from graph_crawler.application.services import register_driver

class SeleniumDriver(BaseDriver):
    async def fetch(self, url: str) -> FetchResponse:
        ...

register_driver("selenium", lambda cfg: SeleniumDriver(**cfg))

# Використання
graph = crawl(url, driver="selenium")
```

---

### Storage (Сховища)

**Базовий клас:** `infrastructure/persistence/base.py`

| Storage | Технологія | Рекомендовано для |
|---------|------------|-------------------|
| `MemoryStorage` | In-memory | < 1,000 nodes |
| `JSONStorage` | aiofiles | 1,000 - 10,000 nodes |
| `SQLiteStorage` | aiosqlite | 10,000 - 100,000 nodes |
| `PostgreSQLStorage` | asyncpg | 100,000+ nodes |
| `MongoDBStorage` | motor | 100,000+ nodes |
| `AutoStorage` | Auto-scale | Автоматичний вибір |

**Реєстрація кастомного storage:**

```python
from graph_crawler.application.services import register_storage

class RedisStorage(BaseStorage):
    async def save_graph(self, graph):
        ...

register_storage("redis", lambda cfg: RedisStorage(**cfg))

# Використання
graph = crawl(url, storage="redis", storage_config={"host": "localhost"})
```

---

### Adapters (HTML парсери)

**Базовий клас:** `infrastructure/adapters/base.py`

| Adapter | Бібліотека | Швидкість |
|---------|------------|----------|
| `BeautifulSoupAdapter` | BeautifulSoup4 | Середня (default) |
| `lxmlAdapter` | lxml | Висока |
| `ScrapyAdapter` | Scrapy | Висока |

```python
# Кастомний tree parser
from graph_crawler.infrastructure.adapters import get_default_parser

# Або свій
class MyAdapter:
    def parse(self, html: str):
        return my_tree

node.tree_parser = MyAdapter()
```

---

## Extensions Components

### Node Plugins

**Базовий клас:** `extensions/plugins/node/base.py`

**Типи плагінів (етапи виконання):**

```
ON_NODE_CREATED → ON_BEFORE_SCAN → ON_HTML_PARSED → ON_AFTER_SCAN
     ↑                                                    ↑
  URL_STAGE                                          HTML_STAGE
```

| Тип | Коли | Що доступно |
|-----|------|-------------|
| ON_NODE_CREATED | При створенні Node | url, depth |
| ON_BEFORE_SCAN | Перед fetch | url, depth, should_scan |
| ON_HTML_PARSED | Після парсингу | html, html_tree, metadata |
| ON_AFTER_SCAN | Після плагінів | metadata, user_data, links |

**Вбудовані плагіни:**

| Плагін | Тип | Результат |
|--------|-----|-----------|
| MetadataExtractorPlugin | ON_HTML_PARSED | title, h1, description |
| LinkExtractorPlugin | ON_HTML_PARSED | extracted_links |
| TextExtractorPlugin | ON_HTML_PARSED | text_content |
| PhoneExtractorPlugin | ON_HTML_PARSED | phones[] |
| EmailExtractorPlugin | ON_HTML_PARSED | emails[] |
| PriceExtractorPlugin | ON_HTML_PARSED | prices[] |
| RealTimeVectorizerPlugin | ON_AFTER_SCAN | embedding[] |

**Створення кастомного плагіна:**

```python
from graph_crawler.extensions.plugins.node import BaseNodePlugin, NodePluginType

class MLDecisionPlugin(BaseNodePlugin):
    @property
    def name(self):
        return "ml_decision"
    
    @property
    def plugin_type(self):
        return NodePluginType.ON_AFTER_SCAN
    
    def execute(self, context):
        # Аналіз контенту
        score = self.analyze(context.html_tree)
        
        # Зберігаємо результат
        context.user_data['ml_score'] = score
        
        # Dynamic priority для child nodes
        context.user_data['child_priorities'] = {
            url: 10 for url in context.extracted_links
            if self.is_important(url)
        }
        
        # Explicit filter override
        context.user_data['explicit_scan_decisions'] = {
            'https://external.com/job': True  # Перебиває domain filter!
        }
        
        return context

graph = crawl(url, plugins=[MLDecisionPlugin()])
```

---

### Middleware

**Базовий клас:** `extensions/middleware/base.py`

**Типи middleware:**

```
PRE_REQUEST → [Driver fetch] → POST_REQUEST → POST_RESPONSE
```

| Middleware | Тип | Опис |
|------------|-----|------|
| RateLimitMiddleware | PRE_REQUEST | Token bucket |
| ProxyMiddleware | PRE_REQUEST | Proxy rotation |
| UserAgentMiddleware | PRE_REQUEST | UA rotation |
| RetryMiddleware | POST_REQUEST | Retry з backoff |
| CacheMiddleware | PRE_REQUEST | HTTP кешування |
| RobotsMiddleware | PRE_REQUEST | robots.txt compliance |
| ErrorRecoveryMiddleware | POST_REQUEST | Error handling |

**Створення кастомного middleware:**

```python
from graph_crawler.extensions.middleware import BaseMiddleware, MiddlewareType

class AuthMiddleware(BaseMiddleware):
    @property
    def name(self):
        return "auth"
    
    @property
    def middleware_type(self):
        return MiddlewareType.PRE_REQUEST
    
    def process(self, context):
        context.headers['Authorization'] = f'Bearer {self.token}'
        return context
```

**MiddlewareChain:**

```python
from graph_crawler.extensions.middleware import MiddlewareChain

chain = MiddlewareChain()
chain.add(RateLimitMiddleware(requests_per_second=10))
chain.add(ProxyMiddleware(proxies=[...]))
chain.add(AuthMiddleware(token='...'))

context = await chain.execute(MiddlewareType.PRE_REQUEST, context)
```
