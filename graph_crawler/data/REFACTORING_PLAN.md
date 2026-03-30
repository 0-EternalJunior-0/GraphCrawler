"# Refactoring Plan: Backend Integration

## Статус Фаз

| Phase | Опис | Статус | Effort |
|-------|------|--------|--------|
| 1 | IGraphBackend + MemoryBackend | ✅ Done | - |
| 2 | Graph delegation (opt-in) | 🔲 TODO | 2-3 дні |
| 3 | Replace direct `_nodes` access | 🔲 TODO | 1-2 дні |
| 4 | SQLiteBackend implementation | 🔲 TODO | 3-4 дні |
| 5 | Streaming GraphOperations | 🔲 TODO | 2 дні |
| 6 | Integration testing | 🔲 TODO | 2 дні |

---

## Phase 2: Graph Delegation

### Мета
Graph приймає `backend` параметр. Якщо передано - делегує storage.

### Файли для зміни

**graph.py**

```python
# Line ~60: Add parameter
def __init__(
    self,
    backend: Optional[\"IGraphBackend\"] = None,  # NEW
    default_merge_strategy: Optional[str] = None,
    low_memory_mode: bool = False,
    ...
):
    self._backend = backend
    self._use_backend = backend is not None
    
    if not self._use_backend:
        # Поточна поведінка
        self._nodes: Dict[str, Node] = {}
        self._edges: List[Edge] = []
        ...

# Line ~373: Modify add_node
def add_node(self, node: Node, overwrite: bool = False) -> Node:
    if self._use_backend:
        if overwrite:
            return self._backend.insert_node_overwrite_sync(node)
        return self._backend.insert_node_sync(node)
    # Поточний код...

# Line ~433: Modify add_node_async
async def add_node_async(self, node: Node, overwrite: bool = False) -> Node:
    if self._use_backend:
        if overwrite:
            return await self._backend.insert_node_overwrite(node)
        return await self._backend.insert_node(node)
    # Поточний код...

# Line ~450: Modify get_node_by_url
def get_node_by_url(self, url: str, load_from_disk: bool = True) -> Optional[Node]:
    if self._use_backend:
        return self._backend.get_node_by_url_sync(url)
    # Поточний код...

# Line ~226: Modify iter_nodes
def iter_nodes(self) -> Iterator[Node]:
    if self._use_backend:
        return self._backend.iter_nodes_sync()
    return iter(self._nodes.values())

# Properties для backward compatibility
@property
def nodes(self) -> Dict[str, Node]:
    if self._use_backend:
        return self._backend.nodes  # Direct access for compat
    return self._nodes
```

### Тести

```python
# tests/unit/test_graph_with_backend.py

import pytest
from graph_crawler.domain.entities.graph import Graph
from graph_crawler.domain.entities.node import Node
from graph_crawler.data.backends.memory import MemoryBackend

@pytest.mark.asyncio
async def test_graph_with_backend_basic():
    \"\"\"Graph з MemoryBackend працює як звичайний Graph.\"\"\"
    backend = MemoryBackend()
    await backend.open()
    
    graph = Graph(backend=backend)
    
    node = Node(url=\"https://example.com\")
    result = graph.add_node(node)
    
    assert result.url == \"https://example.com\"
    assert len(graph) == 1
    assert graph.get_node_by_url(\"https://example.com\") is not None

@pytest.mark.asyncio
async def test_graph_without_backend():
    \"\"\"Graph без backend працює як раніше (backward compat).\"\"\"
    graph = Graph()
    
    node = Node(url=\"https://example.com\")
    graph.add_node(node)
    
    assert len(graph) == 1
    # Прямий доступ до _nodes працює
    assert \"https://example.com\" in [n.url for n in graph._nodes.values()]

@pytest.mark.asyncio
async def test_graph_backend_async():
    \"\"\"Async методи працюють з backend.\"\"\"
    backend = MemoryBackend()
    await backend.open()
    
    graph = Graph(backend=backend)
    
    node = Node(url=\"https://example.com\")
    result = await graph.add_node_async(node)
    
    assert result.url == \"https://example.com\"
```

### Checklist

- [ ] Add `backend` parameter to `Graph.__init__()`
- [ ] Add `_use_backend` flag
- [ ] Modify `add_node()` to delegate
- [ ] Modify `add_node_async()` to delegate
- [ ] Modify `get_node_by_url()` to delegate
- [ ] Modify `get_node_by_id()` to delegate
- [ ] Modify `add_edge()` to delegate
- [ ] Modify `iter_nodes()` to delegate
- [ ] Add backward-compatible `nodes` property
- [ ] Write unit tests
- [ ] Run existing tests (must pass!)

---

## Phase 3: Replace Direct Access

### Мета
Замінити `graph._nodes.values()` на `graph.iter_nodes()` у всіх файлах.

### Файли для зміни

**graph_operations.py**

```python
# Line ~117: union()
# BEFORE
for node in g1._nodes.values():
    result.add_node(node)

# AFTER
for node in g1.iter_nodes():
    result.add_node(node)
```

```python
# Line ~254: difference()
# BEFORE
for node in g1._nodes.values():
    if node.url not in other_urls:
        result.add_node(node)

# AFTER
for node in g1.iter_nodes():
    if node.url not in other_urls:
        result.add_node(node)
```

**graph_mapper.py**

```python
# Line ~76: to_dto()
# BEFORE
nodes_dto = NodeMapper.to_dto_list(list(graph.nodes.values()))

# AFTER
nodes_dto = NodeMapper.to_dto_list(list(graph.iter_nodes()))
```

### Grep команда для пошуку

```bash
grep -rn \"\._nodes\.\" graph_crawler/ --include=\"*.py\" | grep -v test | grep -v __pycache__
grep -rn \"\.nodes\.values()\" graph_crawler/ --include=\"*.py\" | grep -v test | grep -v __pycache__
```

### Checklist

- [ ] graph_operations.py: union()
- [ ] graph_operations.py: difference()
- [ ] graph_operations.py: intersection()
- [ ] graph_operations.py: symmetric_difference()
- [ ] graph_mapper.py: to_dto()
- [ ] graph_mapper.py: compute_stats()
- [ ] graph_statistics.py (якщо є прямий доступ)

---

## Phase 4: SQLiteBackend

### Мета
Backend для графів 10K-1M нод з aiosqlite.

### Файл: data/backends/sqlite.py

```python
\"\"\"
SQLiteBackend - Persistent storage for large graphs.

Uses aiosqlite for async operations.
Supports streaming iteration (no OOM for 10M+ nodes).
\"\"\"

import aiosqlite
import json
import logging
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class SQLiteBackend:
    \"\"\"
    SQLite-backed storage for Graph.
    
    Tables:
        nodes: node_id, url, depth, scanned, metadata_json, ...
        edges: edge_id, source_node_id, target_node_id, metadata_json
        
    Indexes:
        idx_nodes_url: UNIQUE on url
        idx_nodes_scanned: on scanned (for iter_unscanned)
        idx_edges_source: on source_node_id
        idx_edges_target: on target_node_id
    \"\"\"
    
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self._conn: Optional[aiosqlite.Connection] = None
    
    async def open(self) -> None:
        \"\"\"Opens database connection and creates schema.\"\"\"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(str(self.db_path))
        self._conn.row_factory = aiosqlite.Row
        
        await self._init_schema()
        await self._init_pragmas()
    
    async def _init_schema(self) -> None:
        \"\"\"Creates tables and indexes.\"\"\"
        await self._conn.executescript('''
            CREATE TABLE IF NOT EXISTS nodes (
                node_id TEXT PRIMARY KEY,
                url TEXT NOT NULL UNIQUE,
                depth INTEGER NOT NULL DEFAULT 0,
                scanned INTEGER NOT NULL DEFAULT 0,
                should_scan INTEGER NOT NULL DEFAULT 1,
                can_create_edges INTEGER NOT NULL DEFAULT 1,
                response_status INTEGER,
                content_hash TEXT,
                simhash TEXT,
                priority INTEGER,
                metadata_json TEXT,
                user_data_json TEXT,
                created_at TEXT
            );
            
            CREATE TABLE IF NOT EXISTS edges (
                edge_id TEXT PRIMARY KEY,
                source_node_id TEXT NOT NULL,
                target_node_id TEXT NOT NULL,
                metadata_json TEXT,
                UNIQUE(source_node_id, target_node_id)
            );
            
            CREATE INDEX IF NOT EXISTS idx_nodes_url ON nodes(url);
            CREATE INDEX IF NOT EXISTS idx_nodes_scanned ON nodes(scanned);
            CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_node_id);
            CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_node_id);
        ''')
        await self._conn.commit()
    
    async def _init_pragmas(self) -> None:
        \"\"\"Optimizes SQLite for performance.\"\"\"
        await self._conn.execute(\"PRAGMA journal_mode=WAL\")
        await self._conn.execute(\"PRAGMA synchronous=NORMAL\")
        await self._conn.execute(\"PRAGMA cache_size=-64000\")  # 64MB
        await self._conn.execute(\"PRAGMA temp_store=MEMORY\")
    
    async def close(self) -> None:
        \"\"\"Closes database connection.\"\"\"
        if self._conn:
            await self._conn.close()
            self._conn = None
    
    # ... (інші методи як в MemoryBackend, але з SQL)
    
    async def iter_nodes(self, batch_size: int = 1000) -> AsyncIterator[Any]:
        \"\"\"
        Streaming iteration - НЕ завантажує все в RAM!
        
        Використовує SQL LIMIT/OFFSET для пагінації.
        \"\"\"
        offset = 0
        while True:
            cursor = await self._conn.execute(
                \"SELECT * FROM nodes LIMIT ? OFFSET ?\",
                (batch_size, offset)
            )
            rows = await cursor.fetchall()
            
            if not rows:
                break
            
            for row in rows:
                yield self._row_to_node(row)
            
            offset += batch_size
    
    def _row_to_node(self, row) -> Any:
        \"\"\"Converts SQLite row to Node.\"\"\"
        from graph_crawler.domain.entities.node import Node
        
        return Node(
            node_id=row['node_id'],
            url=row['url'],
            depth=row['depth'],
            scanned=bool(row['scanned']),
            should_scan=bool(row['should_scan']),
            can_create_edges=bool(row['can_create_edges']),
            response_status=row['response_status'],
            content_hash=row['content_hash'],
            simhash=row['simhash'],
            priority=row['priority'],
            metadata=json.loads(row['metadata_json']) if row['metadata_json'] else {},
            user_data=json.loads(row['user_data_json']) if row['user_data_json'] else {},
        )
```

### Checklist

- [ ] Create `data/backends/sqlite.py`
- [ ] Implement all IGraphBackend methods
- [ ] Add streaming iter_nodes, iter_edges
- [ ] Write unit tests
- [ ] Benchmark vs MemoryBackend

---

## Phase 5: Streaming GraphOperations

### Мета
Операції union/diff/intersection що не вимагають весь граф в RAM.

### Файл: graph_operations.py changes

```python
@staticmethod
async def union_streaming(
    g1: \"Graph\",
    g2: \"Graph\",
    result_backend: \"IGraphBackend\",
    merge_strategy: str = \"last\",
) -> \"Graph\":
    \"\"\"
    Streaming union - працює з графами будь-якого розміру.
    
    Замість завантаження g1 + g2 в RAM:
    1. Iterate g1 nodes → write to result_backend
    2. Iterate g2 nodes → write to result_backend (with merge check)
    3. Iterate g1 edges → write to result_backend
    4. Iterate g2 edges → write to result_backend
    
    Memory: O(batch_size) замість O(|g1| + |g2|)
    \"\"\"
    from graph_crawler.domain.entities.graph import Graph
    
    # Створюємо result graph з backend
    result = Graph(backend=result_backend)
    
    # Step 1: Stream nodes from g1
    async for node in g1.iter_nodes_async():
        await result_backend.insert_node(node)
    
    # Step 2: Stream nodes from g2 with merge
    async for node in g2.iter_nodes_async():
        existing = await result_backend.get_node_by_url(node.url)
        if existing:
            # Apply merge strategy
            merged = NodeMerger(strategy=merge_strategy).merge(existing, node)
            await result_backend.update_node(merged)
        else:
            await result_backend.insert_node(node)
    
    # Step 3: Stream edges from g1
    async for edge in g1.iter_edges_async():
        await result_backend.insert_edge(edge)
    
    # Step 4: Stream edges from g2
    async for edge in g2.iter_edges_async():
        if not await result_backend.edge_exists(edge.source_node_id, edge.target_node_id):
            await result_backend.insert_edge(edge)
    
    return result
```

---

## Phase 6: Integration Testing

### Test Scenarios

1. **Crawl with MemoryBackend**
   - Small site (100 pages)
   - Verify same results as without backend

2. **Crawl with SQLiteBackend**
   - Medium site (10K pages)
   - Verify no OOM
   - Verify data persistence

3. **Large Graph Operations**
   - Union 100K + 100K nodes
   - Verify streaming works
   - Benchmark memory usage

4. **Migration Test**
   - Start with no backend
   - Switch to SQLiteBackend mid-crawl
   - Verify data integrity

---

## Backward Compatibility Guarantees

1. `Graph()` без параметрів = поточна поведінка
2. `graph.nodes` property працює
3. `graph._nodes` - доступний (deprecated warning?)
4. Всі існуючі тести проходять
5. Spider/Scheduler не знають про backend

---

## Ризики та Mitigation

| Ризик | Mitigation |
|-------|------------|
| Breaking changes | Opt-in через `backend` параметр |
| Performance degradation | Benchmark на кожній фазі |
| Async/sync issues | Sync wrappers в кожному backend |
| Data corruption | Transaction support в SQLiteBackend |

---

*Version: 2.0*
*Updated: 2026-01-20*
"