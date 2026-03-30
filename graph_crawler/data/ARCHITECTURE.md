"# Graph Crawler - Deep Architecture Analysis

## Огляд системи

Web crawler з Clean Architecture принципами. Код організовано в шари:

```
┌────────────────────────────────────────────────────────────────────┐
│                           API Layer                                 │
│  (api/, cli.py, rest_api.py, websocket_manager.py)                 │
├────────────────────────────────────────────────────────────────────┤
│                       Application Layer                             │
│  (application/use_cases/, application/dto/, application/services/) │
├────────────────────────────────────────────────────────────────────┤
│                         Domain Layer                                │
│  (domain/entities/, domain/interfaces/, domain/value_objects/)     │
├────────────────────────────────────────────────────────────────────┤
│                     Infrastructure Layer                            │
│  (infrastructure/persistence/, infrastructure/transport/)          │
├────────────────────────────────────────────────────────────────────┤
│                      Data Layer (ACTIVE)                            │
│  (data/interfaces.py, data/backends/)                              │
└────────────────────────────────────────────────────────────────────┘
```

---

## BACKEND INTEGRATION STATUS (Updated: 2026-01-21)

### ✅ Completed Phases (Steps 1-50)

| Phase | Steps | Status | Description |
|-------|-------|--------|-------------|
| 1 | 1-10 | ✅ Done | MemoryBackend unit tests |
| 2 | 11-20 | ✅ Done | Graph backend delegation |
| 3 | 21-25 | ✅ Done | Property accessors |
| 4 | 26-35 | ✅ Done | Replace _nodes access with iter_nodes() |
| 5 | 36-45 | ✅ Done | SQLiteBackend implementation |
| 6 | 46-50 | ✅ Done | Streaming operations & final integration |

### Key Features Implemented

**Graph Class (domain/entities/graph.py):**
- `backend` parameter for delegation
- `iter_nodes()` - sync streaming iterator
- `iter_nodes_async()` - async streaming iterator
- `iter_edges()` - sync edge iterator
- `iter_edges_async()` - async edge iterator
- Full backward compatibility (no backend = RAM mode)

**GraphOperations Class:**
- `union_streaming()` - memory-efficient union for large graphs
- `difference_streaming()` - memory-efficient difference

**Backends (data/backends/):**
- `MemoryBackend` - in-memory storage (RAM)
- `SQLiteBackend` - persistent SQLite storage

---

## Usage Examples

### Basic Usage (RAM Mode)
```python
from graph_crawler.domain.entities.graph import Graph
from graph_crawler.domain.entities.node import Node

# Standard RAM mode (backward compatible)
graph = Graph()
graph.add_node(Node(url="https://example.com"))

for node in graph.iter_nodes():
    print(node.url)
```

### With MemoryBackend
```python
from graph_crawler.data import MemoryBackend
from graph_crawler.domain.entities.graph import Graph

backend = MemoryBackend()
await backend.open()

graph = Graph(backend=backend)
graph.add_node(Node(url="https://example.com"))

# Async streaming
async for node in graph.iter_nodes_async():
    print(node.url)

await backend.close()
```

### With SQLiteBackend (Large Graphs)
```python
from graph_crawler.data import SQLiteBackend
from graph_crawler.domain.entities.graph import Graph

backend = SQLiteBackend("./crawl.db")
await backend.open()

graph = Graph(backend=backend)

# Add millions of nodes - persisted to SQLite
for i in range(1_000_000):
    await graph.add_node_async(Node(url=f"https://example.com/{i}"))

# Memory-efficient streaming (only batch_size in RAM)
async for node in graph.iter_nodes_async(batch_size=1000):
    process(node)

await backend.close()
```

### Streaming Union (Memory-Efficient)
```python
from graph_crawler.data import SQLiteBackend
from graph_crawler.domain.entities.graph import Graph
from graph_crawler.domain.entities.graph_operations import GraphOperations

# Two large graphs
backend1 = SQLiteBackend("graph1.db")
backend2 = SQLiteBackend("graph2.db")
result_backend = SQLiteBackend("result.db")

await backend1.open()
await backend2.open()
await result_backend.open()

g1 = Graph(backend=backend1)
g2 = Graph(backend=backend2)

# Union without loading all nodes to RAM
result = await GraphOperations.union_streaming(g1, g2, result_backend)

print(f"Union result: {len(result)} nodes")
```

---

## 1. DATA FLOW - Як дані рухаються

### 1.1 Crawl Flow (Happy Path)

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ GraphSpider │────▶│   Scheduler │────▶│ NodeScanner │────▶│LinkProcessor│
│             │     │             │     │             │     │             │
│ crawl()     │     │ get_next()  │     │ scan_node() │     │process_links│
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │                   │
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│    Graph    │◀────│    Node     │◀────│   Driver    │     │   Filters   │
│             │     │             │     │             │     │             │
│ _nodes      │     │process_html │     │ fetch()     │     │DomainFilter │
│ _edges      │     │ plugins     │     │ HTTP client │     │ PathFilter  │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
```

### 1.2 Детальний Flow

```
1. Spider.crawl()
   ├── Scheduler.add_node(root_node)
   └── CrawlCoordinator.coordinate()
       │
       └── LOOP while !scheduler.is_empty():
           │
           ├── node = Scheduler.get_next()
           │   └── heappop(queue) → URL → Graph.get_node_by_url() → Node
           │
           ├── NodeScanner.scan_node(node)
           │   ├── Driver.fetch(url) → FetchResponse(html, status, headers)
           │   ├── Node.process_html(html)
           │   │   ├── parse_html_async() → ThreadPoolExecutor → html_tree
           │   │   ├── Plugin: ON_BEFORE_SCAN
           │   │   ├── Plugin: ON_HTML_PARSED (MetadataExtractor, LinkExtractor)
           │   │   ├── Plugin: ON_AFTER_SCAN
           │   │   └── return extracted_links
           │   └── return (links, fetch_response)
           │
           ├── LinkProcessor.process_links_async(node, links)
           │   └── for link in links:
           │       ├── _should_scan_url() → (should_scan, can_create_edges)
           │       │   ├── Check explicit_scan_decisions (plugins)
           │       │   ├── Check URLRule
           │       │   ├── Check DomainFilter
           │       │   └── Check PathFilter
           │       │
           │       ├── if new_url:
           │       │   ├── Graph.add_node_async(target_node)
           │       │   └── Scheduler.add_node(target_node, priority)
           │       │
           │       └── if should_create_edge:
           │           └── Graph.add_edge_async(edge)
           │
           └── checkpoint/progress update
```

---

## 2. STORAGE - 3 Незалежні Системи

### 2.1 Поточний стан: Три паралельні абстракції

```
┌─────────────────────────────────────────────────────────────────────┐
│                          STORAGE LANDSCAPE                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌────────────────────┐  ┌────────────────────┐  ┌────────────────┐ │
│  │    IStorage        │  │ IEvictionStorage   │  │ IGraphBackend  │ │
│  │  (domain/          │  │  (domain/          │  │  (data/        │ │
│  │   interfaces/)     │  │   interfaces/)     │  │   interfaces/) │ │
│  └─────────┬──────────┘  └─────────┬──────────┘  └───────┬────────┘ │
│            │                       │                     │          │
│            │                       │                     │          │
│  ┌─────────▼──────────┐  ┌─────────▼──────────┐  ┌───────▼────────┐ │
│  │  MemoryStorage     │  │SQLiteEvictionStorage│ │  MemoryBackend │ │
│  │  JSONStorage       │  │LMDBEvictionStorage │  │  (SQLite?)     │ │
│  │  SQLiteStorage     │  │                    │  │                │ │
│  │  PostgreSQLStorage │  │                    │  │                │ │
│  │  MongoDBStorage    │  │                    │  │                │ │
│  └────────────────────┘  └────────────────────┘  └────────────────┘ │
│                                                                      │
│  ПРИЗНАЧЕННЯ:           ПРИЗНАЧЕННЯ:            ПРИЗНАЧЕННЯ:        │
│  Save/Load ВЕСЬ граф    Evict/Load ОКРЕМІ ноди  CRUD для Graph     │
│  (Checkpoint/Restore)   (Low-memory mode)       (Single Source     │
│                                                  of Truth) - NEW    │
│                                                                      │
│  СТАТУС: ✅ Працює      СТАТУС: ✅ Працює       СТАТУС: ⚠️ Написано │
│                                                  але НЕ інтегровано │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 IStorage - Checkpoint/Restore

**Призначення**: Зберегти/завантажити ВЕСЬ граф (GraphDTO)

**Використання**:
- Spider завершив роботу → `storage.save_graph(GraphDTO)`
- Spider стартує → `storage.load_graph() → GraphDTO`

**Ключові методи**:
```python
async def save_graph(self, graph_dto: GraphDTO) -> bool
async def load_graph(self) -> Optional[GraphDTO]
```

**Реалізації**:
| Implementation | Ліміт | Файл |
|----------------|-------|------|
| MemoryStorage | <1K нод | RAM only |
| JSONStorage | <10K нод | JSON файли |
| SQLiteStorage | <100K нод | SQLite DB |
| PostgreSQLStorage | 100K+ | PostgreSQL |
| MongoDBStorage | 100K+ | MongoDB |

### 2.3 IEvictionStorage - Low-Memory Mode

**Призначення**: Переміщувати ОКРЕМІ ноди RAM ↔ Disk

**Використання**:
- Graph в RAM > threshold → evict older nodes to disk
- Потрібна нода що evicted → lazy load from disk

**Ключові методи**:
```python
def save_nodes_sync(self, nodes: List[Node]) -> None
def load_node_sync(self, url: str) -> Optional[Dict]
```

**Реалізації**:
| Implementation | Файл |
|----------------|------|
| SQLiteEvictionStorage | infrastructure/persistence/ |
| LMDBEvictionStorage | infrastructure/persistence/ |

### 2.4 IGraphBackend - CRUD Operations (NEW, НЕ інтегровано)

**Призначення**: Single Source of Truth для Graph data

**Ідея**: Graph делегує ВСІ операції до backend замість RAM

**Ключові методи**:
```python
async def insert_node(self, node: Node) -> Node
async def get_node_by_url(self, url: str) -> Optional[Node]
async def iter_nodes(self, batch_size: int) -> AsyncIterator[Node]  # Streaming!
```

**Реалізації**:
| Implementation | Статус |
|----------------|--------|
| MemoryBackend | ✅ Готово (data/backends/memory.py) |
| SQLiteBackend | 🔲 TODO |

---

## 3. GRAPH.py - Детальний Аналіз

### 3.1 Primary Storage (RAM)

```python
class Graph:
    def __init__(self):
        # PRIMARY DATA
        self._nodes: Dict[str, Node] = {}        # node_id → Node
        self._edges: List[Edge] = []             # All edges
        
        # INDEXES
        self._url_to_node: Dict[str, Node] = {}  # url → Node (O(1) lookup)
        self._edge_index: Set[tuple] = set()     # (source_id, target_id)
        self._adjacency_list_out: Dict[str, Set[str]]  # source → {targets}
        self._adjacency_list_in: Dict[str, Set[str]]   # target → {sources}
        
        # LOW-MEMORY MODE
        self._evicted_url_hashes: Set[int] = set()  # hash(url) for evicted
        self._eviction_storage = None  # IEvictionStorage
```

### 3.2 Кількість прямих доступів

```
Файл                                    | _nodes | _edges | _url_to_node
----------------------------------------|--------|--------|-------------
domain/entities/graph.py                |   45   |   25   |     20
domain/entities/graph_operations.py     |   12   |   10   |      8
application/dto/mappers/graph_mapper.py |    3   |    2   |      0
application/use_cases/.../scheduler.py  |    0   |    0   |      0 (через Graph)
----------------------------------------|--------|--------|-------------
TOTAL                                   |   60   |   37   |     28
```

### 3.3 Методи що читають _nodes напряму

```python
# graph.py
def add_node() → self._nodes[node.node_id] = node
def get_node_by_url() → self._url_to_node.get(url)
def get_node_by_id() → self._nodes.get(node_id)
def remove_node() → del self._nodes[node_id]
def __len__() → len(self._nodes)
def __iter__() → iter(self._nodes.values())
def get_stats() → len(self._nodes), sum(n.scanned for n in self._nodes.values())

# graph_operations.py
def union() → for node in g1._nodes.values(): ...
def difference() → for node in g1._nodes.values(): ...
def intersection() → for url in common_urls: g1.get_node_by_url(url)
```

---

## 4. ПРОБЛЕМА: RAM як Primary Storage

### 4.1 Memory Usage при різних масштабах

| Ноди | RAM (тільки nodes) | RAM (з edges, indexes) |
|------|--------------------|-----------------------|
| 10K | ~50 MB | ~100 MB |
| 100K | ~500 MB | ~1 GB |
| 1M | ~5 GB | OOM на 8GB машині |
| 10M | OOM | OOM |

### 4.2 Поточний Workaround: Low-Memory Mode

```python
Graph(
    low_memory_mode=True,
    evict_threshold=500,           # Max nodes in RAM
    eviction_storage=SQLiteEvictionStorage(\"/tmp\")
)
```

**Як працює**:
1. Crawl node
2. `len(_nodes) > threshold * trigger_mult` → evict old nodes to SQLite
3. Access evicted node → lazy load from SQLite

**Проблеми**:
- Постійний RAM ↔ Disk shuffle
- Eviction heuristics не оптимальні
- Edges все ще в RAM
- `_adjacency_list_*` все ще в RAM

---

## 5. РІШЕННЯ: Backend Delegation

### 5.1 Цільова архітектура

```
┌──────────────────────────────────────────────────────────────────┐
│                         Graph (Facade)                            │
│  - Публічний API залишається незмінним                           │
│  - Делегує операції до backend                                   │
└──────────────────────────────────────────────────────────────────┘
                              │
                              │ (delegation)
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                     IGraphBackend                                 │
│  - insert_node(), get_node_by_url(), iter_nodes()               │
│  - insert_edge(), edge_exists(), iter_edges()                   │
│  - count_nodes(), get_stats()                                    │
└──────────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│MemoryBackend │    │SQLiteBackend │    │PostgreSQL    │
│  (Dict/List) │    │ (aiosqlite)  │    │Backend       │
│  <10K nodes  │    │ <1M nodes    │    │ 100M+ nodes  │
└──────────────┘    └──────────────┘    └──────────────┘
```

### 5.2 Зміни в Graph

```python
class Graph:
    def __init__(
        self,
        backend: Optional[IGraphBackend] = None,  # NEW
        ...
    ):
        if backend:
            self._backend = backend
            self._use_backend = True
        else:
            # Current behavior - RAM storage
            self._nodes = {}
            self._edges = []
            ...
    
    def add_node(self, node: Node) -> Node:
        if self._use_backend:
            return self._backend.insert_node_sync(node)
        # Current code...
    
    async def add_node_async(self, node: Node) -> Node:
        if self._use_backend:
            return await self._backend.insert_node(node)
        # Current code...
    
    def iter_nodes(self) -> Iterator[Node]:
        if self._use_backend:
            return self._backend.iter_nodes_sync()
        return iter(self._nodes.values())
```

### 5.3 Streaming Operations для OOM Prevention

```python
# Замість завантаження всіх нод в RAM:
all_nodes = list(graph.nodes.values())  # OOM при 10M нод!

# Streaming:
async for node in backend.iter_nodes(batch_size=1000):
    process(node)  # Одночасно в RAM тільки batch_size нод
```

---

## 6. ПЛАН МІГРАЦІЇ

### Phase 1: Interface + MemoryBackend ✅ DONE
- `data/interfaces.py` - IGraphBackend Protocol
- `data/backends/memory.py` - MemoryBackend implementation

### Phase 2: Graph Delegation 🔲 TODO
```python
# graph.py changes
def __init__(self, backend: Optional[IGraphBackend] = None):
    ...

def add_node(self, node):
    if self._use_backend:
        return self._backend.insert_node_sync(node)
```

### Phase 3: Replace Direct Access 🔲 TODO
```python
# BEFORE
for node in g1._nodes.values():

# AFTER  
for node in g1.iter_nodes():
```

### Phase 4: SQLiteBackend 🔲 TODO
- `data/backends/sqlite.py`
- aiosqlite based
- Streaming queries

### Phase 5: Testing + Migration 🔲 TODO
- Unit tests для кожного backend
- Integration tests
- Benchmark: Memory vs SQLite performance

---

## 7. ЩО НЕ ЗМІНЮЄМО

1. **IStorage** - залишається для checkpoint/restore (повний граф)
2. **IEvictionStorage** - залишається для legacy low_memory_mode
3. **Graph public API** - `add_node()`, `get_node_by_url()` - без змін
4. **Spider/Scheduler/Coordinator** - не знають про backend

---

## 8. РИЗИКИ

| Ризик | Ймовірність | Mitigation |
|-------|-------------|------------|
| Breaking changes | Medium | Opt-in через `backend` параметр |
| Performance regression | Medium | Benchmark кожної фази |
| Async/sync mixing | High | Sync wrappers в backend |
| Race conditions | Medium | Proper locking в backend |

---

## 9. METRICS

| Сценарій | Зараз | Після (з SQLiteBackend) |
|----------|-------|-------------------------|
| 10K нод | RAM: 50MB | RAM: 10MB + SQLite 5MB |
| 100K нод | RAM: 500MB → slow | RAM: 10MB + SQLite 50MB |
| 1M нод | ❌ OOM | RAM: 10MB + SQLite 500MB |
| Union 10M + 10M | ❌ OOM | Streaming: 20MB RAM |

---

*Document version: 2.0*
*Last updated: 2026-01-20*
*Author: E1 Deep Analysis*
"