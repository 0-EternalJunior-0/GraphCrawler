# 4. Communication Channels & Protocols (Канали комунікації)

## 📋 Зміст

1. [Огляд каналів](#огляд-каналів)
2. [Event Bus (Observer Pattern)](#event-bus)
3. [Direct Method Calls](#direct-method-calls)
4. [Async Messaging (Celery)](#async-messaging)
5. [Формати повідомлень](#формати-повідомлень)

---

## Огляд каналів

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         COMMUNICATION CHANNELS                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐                                                            │
│  │   Spider    │                                                            │
│  │ (Orchestr.) │                                                            │
│  └──────┬──────┘                                                            │
│         │                                                                   │
│         │ 1. Direct Method Calls (sync/async)                               │
│         │    Spider → Scheduler.add_url()                                   │
│         │    Spider → Driver.fetch()                                        │
│         │    Spider → Storage.save_graph()                                  │
│         │                                                                   │
│         ├─────────────────┬─────────────────┬─────────────────┐             │
│         ▼                 ▼                 ▼                 ▼             │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐      │
│  │  Scheduler  │   │   Driver    │   │   Storage   │   │   Plugins   │      │
│  └──────┬──────┘   └──────┬──────┘   └──────┬──────┘   └──────┬──────┘      │
│         │                 │                 │                 │             │
│         │ 2. Event Bus (Observer Pattern - async/sync)                      │
│         │    Компоненти публікують події → EventBus → Subscribers           │
│         │                                                                   │
│         └─────────────────┴─────────────────┴─────────────────┘             │
│                                   │                                         │
│                                   ▼                                         │
│                          ┌─────────────────┐                                │
│                          │    EventBus     │                                │
│                          │   (Pub/Sub)     │                                │
│                          └────────┬────────┘                                │
│                                   │                                         │
│                                   │ notify()                                │
│                    ┌──────────────┼──────────────┐                          │
│                    ▼              ▼              ▼                          │
│             ┌──────────┐  ┌──────────┐   ┌──────────┐                       │
│             │ Dashboard│  │ Loggers  │   │ Analytics│                       │
│             └──────────┘  └──────────┘   └──────────┘                       │
│                                                                             │
│  ════════════════════════════════════════════════════════════════════════   │
│                                                                             │
│  3. Async Messaging (Celery - для distributed mode)                         │
│                                                                             │
│  ┌─────────────┐    ┌─────────────────┐    ┌─────────────┐                  │
│  │ Coordinator │───▶│ Redis/RabbitMQ  │───▶│   Workers   │                  │
│  │  (Master)   │    │   (Broker)      │    │  (Celery)   │                  │
│  └─────────────┘    └─────────────────┘    └──────┬──────┘                  │
│                                                   │                         │
│                                                   ▼                         │
│                                           ┌─────────────┐                   │
│                                           │  MongoDB/   │                   │
│                                           │ PostgreSQL  │                   │
│                                           └─────────────┘                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Event Bus

### Призначення

Loose coupling між компонентами через Observer Pattern.

### Протокол

```python
# Публікація (Producer)
event = CrawlerEvent.create(
    event_type=EventType.NODE_SCANNED,
    data={'url': 'https://example.com', 'status': 200},
    metadata={'spider_id': 'spider-1'}
)
event_bus.publish(event)           # Sync
await event_bus.publish_async(event)  # Async

# Підписка (Consumer)
def handler(event: CrawlerEvent):
    print(f"Event: {event.event_type}, Data: {event.data}")

event_bus.subscribe(EventType.NODE_SCANNED, handler)
```

### Формат CrawlerEvent

```python
@dataclass
class CrawlerEvent:
    event_type: EventType      # Enum з 50+ типів
    timestamp: datetime        # Час події
    data: Dict[str, Any]       # Payload (JSON-serializable)
    metadata: Dict[str, Any]   # Додаткові метадані
```

### Категорії подій

| Категорія | Event Types | Опис |
|-----------|-------------|------|
| **Node** | NODE_CREATED, NODE_SCAN_STARTED, NODE_SCANNED, NODE_FAILED | Життєвий цикл вузла |
| **Crawler** | CRAWL_STARTED, CRAWL_COMPLETED, CRAWL_PAUSED, CRAWL_RESUMED | Стан краулера |
| **Scheduler** | URL_ADDED_TO_QUEUE, URL_EXCLUDED, URL_PRIORITIZED | Черга URL |
| **Storage** | GRAPH_SAVED, GRAPH_LOADED, STORAGE_UPGRADED | Операції зі сховищем |
| **Plugin** | PLUGIN_STARTED, PLUGIN_COMPLETED, PLUGIN_FAILED | Виконання плагінів |
| **Middleware** | RATE_LIMIT_WAIT, PROXY_SELECTED, RETRY_STARTED | Middleware events |
| **Fetch** | FETCH_STARTED, FETCH_SUCCESS, FETCH_ERROR | HTTP запити |
| **Progress** | PROGRESS_UPDATE, PAGE_FETCH_TIME | Моніторинг |

### Приклади використання

```python
# 1. Логування всіх подій
def log_handler(event):
    logger.info(f"{event.event_type.value}: {event.data}")

for event_type in EventType:
    event_bus.subscribe(event_type, log_handler)

# 2. Моніторинг прогресу
def progress_handler(event):
    data = event.data
    print(f"Progress: {data['scanned']}/{data['total']} ({data['percent']:.1f}%)")

event_bus.subscribe(EventType.PROGRESS_UPDATE, progress_handler)

# 3. Error alerting
async def error_alert(event):
    if event.data.get('severity') == 'critical':
        await send_slack_alert(event.data)

event_bus.subscribe(EventType.ERROR_OCCURRED, error_alert)

# 4. Analytics collection
class AnalyticsCollector:
    def __init__(self):
        self.events = []
    
    def collect(self, event):
        self.events.append(event.to_dict())

collector = AnalyticsCollector()
event_bus.subscribe(EventType.NODE_SCANNED, collector.collect)
```

---

## Direct Method Calls

### Протокол Spider → Components

```
Spider
  │
  ├──▶ Scheduler
  │      • add_url(url, depth) → bool
  │      • add_node(node) → bool  
  │      • get_next_url() → Optional[Tuple[str, int]]
  │      • is_empty() → bool
  │
  ├──▶ Driver (async)
  │      • await fetch(url) → FetchResponse
  │      • await fetch_many(urls) → List[FetchResponse]
  │      • await close()
  │
  ├──▶ Storage (async)
  │      • await save_graph(graph) → bool
  │      • await load_graph() → Optional[Graph]
  │      • await exists() → bool
  │      • await close()
  │
  ├──▶ NodeScanner
  │      • await scan_node(node, html) → List[str]
  │
  └──▶ LinkProcessor
         • process_links(source_node, links) → List[Node]
         • create_edge(source, target) → Edge
```

### Протокол Node → Plugins

```python
# Node.process_html() внутрішньо викликає:
await plugin_manager.execute(NodePluginType.ON_BEFORE_SCAN, context)
await plugin_manager.execute(NodePluginType.ON_HTML_PARSED, context)
await plugin_manager.execute(NodePluginType.ON_AFTER_SCAN, context)
```

### Інтерфейси (Protocols)

```python
# IDriver
class IDriver(Protocol):
    async def fetch(self, url: str) -> FetchResponse: ...
    async def fetch_many(self, urls: List[str]) -> List[FetchResponse]: ...
    async def close(self) -> None: ...

# IStorage  
class IStorage(Protocol):
    async def save_graph(self, graph) -> bool: ...
    async def load_graph(self) -> Optional[Graph]: ...
    async def exists(self) -> bool: ...
    async def close(self) -> None: ...

# IFilter
class IFilter(Protocol):
    def should_scan(self, url: str) -> bool: ...
    def apply(self, url: str, node: Node) -> bool: ...
```

---

## Async Messaging

### Celery Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                           DISTRIBUTED CRAWLING                              │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  LOCAL (Master)                                                            │
│  ┌─────────────────────┐                                                   │
│  │ EasyDistributedCrawler │                                                │
│  │                     │                                                   │
│  │ • from_yaml(config) │                                                   │
│  │ • crawl()           │                                                   │
│  │ • get_stats()       │                                                   │
│  └──────────┬──────────┘                                                   │
│             │                                                              │
│             │ 1. Push crawl_page_task                                      │
│             ▼                                                              │
│  ┌─────────────────────────────────────────────┐                           │
│  │           REDIS/RABBITMQ BROKER             │                           │
│  │                                             │                           │
│  │  Queue: graph_crawler                       │                           │
│  │  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐           │                           │
│  │  │Task1│ │Task2│ │Task3│ │...  │           │                           │
│  │  └─────┘ └─────┘ └─────┘ └─────┘           │                           │
│  │                                             │                           │
│  │  Format:                                    │                           │
│  │  {                                          │                           │
│  │    "url": "https://...",                   │                           │
│  │    "depth": 2,                              │                           │
│  │    "config": {...}                          │                           │
│  │  }                                          │                           │
│  └──────────────────┬──────────────────────────┘                           │
│                     │                                                      │
│                     │ 2. Workers pull tasks                                │
│                     ▼                                                      │
│  ┌─────────────────────────────────────────────────────────────┐           │
│  │                   CELERY WORKERS (N servers)                │           │
│  │                                                             │           │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐               │           │
│  │  │ Worker 1  │  │ Worker 2  │  │ Worker N  │               │           │
│  │  │           │  │           │  │           │               │           │
│  │  │ • Driver  │  │ • Driver  │  │ • Driver  │               │           │
│  │  │ • Plugins │  │ • Plugins │  │ • Plugins │               │           │
│  │  │ • Parser  │  │ • Parser  │  │ • Parser  │               │           │
│  │  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘               │           │
│  │        │              │              │                      │           │
│  │        │ 3. Fetch & Extract                                 │           │
│  │        ▼              ▼              ▼                      │           │
│  └────────────────────────┬────────────────────────────────────┘           │
│                           │                                                │
│                           │ 4. Save results                                │
│                           ▼                                                │
│  ┌─────────────────────────────────────────────┐                           │
│  │         MONGODB/POSTGRESQL (Results)        │                           │
│  │                                             │                           │
│  │  Collection: nodes                          │                           │
│  │  Collection: edges                          │                           │
│  │  Collection: queue (pending URLs)           │                           │
│  │                                             │                           │
│  └─────────────────────────────────────────────┘                           │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

### Task Protocol

```python
# Celery Task Definition
@celery.task(bind=True, max_retries=3)
def crawl_page_task(self, url: str, depth: int, config: dict):
    """
    Crawl single page task.
    
    Input:
        url: URL to crawl
        depth: Current depth
        config: Crawler configuration
        
    Output:
        {
            'url': str,
            'status': 'success' | 'error',
            'node': NodeDTO | None,
            'links': List[str],
            'error': str | None
        }
    """
    ...
```

### Configuration Protocol (YAML)

```yaml
# config.yaml
broker:
  type: redis           # redis | rabbitmq
  host: server11.example.com
  port: 6379
  db: 0

database:
  type: mongodb         # mongodb | postgresql
  host: server12.example.com
  port: 27017
  database: crawler_results

crawl_task:
  urls:
    - https://example.com
  max_depth: 3
  max_pages: 1000
  extractors:
    - phones
    - emails
    - prices

workers: 10
task_time_limit: 600
```

---

## Формати повідомлень

### FetchResponse

```python
@dataclass
class FetchResponse:
    url: str                        # Original URL
    html: Optional[str]             # HTML content
    status_code: Optional[int]      # HTTP status
    headers: Dict[str, str]         # Response headers
    error: Optional[str]            # Error message
    final_url: Optional[str]        # After redirects
    redirect_chain: List[str]       # Redirect history

# Properties
response.is_success  # error is None and html is not None
response.is_ok       # status_code 2xx
response.is_redirect # final_url != url
```

### NodePluginContext

```python
@dataclass
class NodePluginContext:
    # Basic (always available)
    node: Node
    url: str
    depth: int
    should_scan: bool
    can_create_edges: bool
    
    # HTML Stage (after fetch)
    html: Optional[str]
    html_tree: Optional[Any]       # BeautifulSoup/lxml tree
    parser: Optional[BaseAdapter]
    
    # Results (modifiable)
    metadata: Dict[str, Any]
    user_data: Dict[str, Any]
    extracted_links: List[str]
```

### MiddlewareContext

```python
@dataclass
class MiddlewareContext:
    url: str
    headers: Dict[str, str]
    cookies: Dict[str, str]
    proxy: Optional[str]
    timeout: int
    
    # Response (POST_REQUEST)
    response: Optional[FetchResponse]
    error: Optional[Exception]
    
    # Control
    skip_request: bool = False     # Skip fetch (cache hit)
    retry_count: int = 0
```

### GraphDTO (Clean Architecture)

```python
@dataclass
class GraphDTO:
    nodes: List[NodeDTO]
    edges: List[EdgeDTO]
    stats: GraphStatsDTO
    metadata: Dict[str, Any]

@dataclass
class NodeDTO:
    url: str
    node_id: str
    depth: int
    scanned: bool
    metadata: Dict[str, Any]
    user_data: Dict[str, Any]

@dataclass  
class EdgeDTO:
    edge_id: str
    source_node_id: str
    target_node_id: str
    anchor_text: str
    link_type: List[str]
```
