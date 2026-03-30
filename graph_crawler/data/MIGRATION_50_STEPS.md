# 50-Step Migration Plan: Backend Integration

## Огляд

Поетапний план інтеграції `IGraphBackend` в `Graph` з тестами після кожного кроку.
Кожен крок - мінімальна зміна що не ламає існуючий функціонал.

**Принцип**: Opt-in через параметр `backend`. Без параметра - працює як раніше.

---

## Phase 1: Підготовка та Тести для MemoryBackend (Кроки 1-10)

### Крок 1: Встановити залежності
**Файл**: `requirements.txt`
**Дія**: Перевірити що всі залежності встановлені
```bash
pip install pydantic-settings aiosqlite
```
**Тест**:
```bash
python -c "from graph_crawler.data.backends.memory import MemoryBackend; print('OK')"
```

---

### Крок 2: Unit тест для MemoryBackend.open/close
**Файл**: `tests/unit/test_memory_backend.py`
**Дія**: Створити базовий тест lifecycle
```python
import pytest
from graph_crawler.data.backends.memory import MemoryBackend

@pytest.mark.asyncio
async def test_memory_backend_lifecycle():
    backend = MemoryBackend()
    await backend.open()
    assert backend._is_open == True
    await backend.close()
    assert backend._is_open == False
```
**Тест**: `pytest tests/unit/test_memory_backend.py -v`

---

### Крок 3: Unit тест для insert_node
**Файл**: `tests/unit/test_memory_backend.py`
**Дія**: Додати тест insert
```python
@pytest.mark.asyncio
async def test_insert_node():
    from graph_crawler.domain.entities.node import Node
    
    backend = MemoryBackend()
    await backend.open()
    
    node = Node(url="https://example.com")
    result = await backend.insert_node(node)
    
    assert result.url == "https://example.com"
    assert await backend.count_nodes() == 1
```
**Тест**: `pytest tests/unit/test_memory_backend.py::test_insert_node -v`

---

### Крок 4: Unit тест для URL normalization
**Файл**: `tests/unit/test_memory_backend.py`
**Дія**: Тест нормалізації URL
```python
@pytest.mark.asyncio
async def test_url_normalization():
    backend = MemoryBackend()
    await backend.open()
    
    # Trailing slash
    node1 = Node(url="https://example.com/")
    result1 = await backend.insert_node(node1)
    
    # Without trailing slash - should be same
    node2 = Node(url="https://example.com")
    result2 = await backend.insert_node(node2)
    
    assert result1.node_id == result2.node_id  # Same node
    assert await backend.count_nodes() == 1
```
**Тест**: `pytest tests/unit/test_memory_backend.py::test_url_normalization -v`

---

### Крок 5: Unit тест для get_node_by_url
**Файл**: `tests/unit/test_memory_backend.py`
**Дія**: Тест отримання ноди
```python
@pytest.mark.asyncio
async def test_get_node_by_url():
    backend = MemoryBackend()
    await backend.open()
    
    node = Node(url="https://example.com/page")
    await backend.insert_node(node)
    
    found = await backend.get_node_by_url("https://example.com/page")
    assert found is not None
    assert found.url == "https://example.com/page"
    
    not_found = await backend.get_node_by_url("https://other.com")
    assert not_found is None
```
**Тест**: `pytest tests/unit/test_memory_backend.py::test_get_node_by_url -v`

---

### Крок 6: Unit тест для insert_edge
**Файл**: `tests/unit/test_memory_backend.py`
**Дія**: Тест додавання ребра
```python
@pytest.mark.asyncio
async def test_insert_edge():
    from graph_crawler.domain.entities.edge import Edge
    
    backend = MemoryBackend()
    await backend.open()
    
    node1 = Node(url="https://a.com")
    node2 = Node(url="https://b.com")
    await backend.insert_node(node1)
    await backend.insert_node(node2)
    
    edge = Edge(source_node_id=node1.node_id, target_node_id=node2.node_id)
    result = await backend.insert_edge(edge)
    
    assert await backend.count_edges() == 1
    assert await backend.edge_exists(node1.node_id, node2.node_id)
```
**Тест**: `pytest tests/unit/test_memory_backend.py::test_insert_edge -v`

---

### Крок 7: Unit тест для iter_nodes
**Файл**: `tests/unit/test_memory_backend.py`
**Дія**: Тест streaming iteration
```python
@pytest.mark.asyncio
async def test_iter_nodes():
    backend = MemoryBackend()
    await backend.open()
    
    for i in range(100):
        node = Node(url=f"https://example.com/page{i}")
        await backend.insert_node(node)
    
    count = 0
    async for node in backend.iter_nodes(batch_size=10):
        count += 1
    
    assert count == 100
```
**Тест**: `pytest tests/unit/test_memory_backend.py::test_iter_nodes -v`

---

### Крок 8: Unit тест для delete_node
**Файл**: `tests/unit/test_memory_backend.py`
**Дія**: Тест видалення з каскадом ребер
```python
@pytest.mark.asyncio
async def test_delete_node():
    backend = MemoryBackend()
    await backend.open()
    
    node1 = Node(url="https://a.com")
    node2 = Node(url="https://b.com")
    await backend.insert_node(node1)
    await backend.insert_node(node2)
    
    edge = Edge(source_node_id=node1.node_id, target_node_id=node2.node_id)
    await backend.insert_edge(edge)
    
    # Delete node1 - edge should be removed too
    deleted = await backend.delete_node(node1.node_id)
    assert deleted == True
    assert await backend.count_nodes() == 1
    assert await backend.count_edges() == 0
```
**Тест**: `pytest tests/unit/test_memory_backend.py::test_delete_node -v`

---

### Крок 9: Unit тест для batch operations
**Файл**: `tests/unit/test_memory_backend.py`
**Дія**: Тест batch insert
```python
@pytest.mark.asyncio
async def test_batch_operations():
    backend = MemoryBackend()
    await backend.open()
    
    nodes = [Node(url=f"https://example.com/{i}") for i in range(50)]
    count = await backend.insert_nodes_batch(nodes)
    
    assert count == 50
    assert await backend.count_nodes() == 50
```
**Тест**: `pytest tests/unit/test_memory_backend.py::test_batch_operations -v`

---

### Крок 10: Unit тест для sync wrappers
**Файл**: `tests/unit/test_memory_backend.py`
**Дія**: Тест sync методів
```python
def test_sync_wrappers():
    backend = MemoryBackend()
    
    node = Node(url="https://example.com")
    result = backend.insert_node_sync(node)
    
    assert result.url == "https://example.com"
    assert backend.count_nodes_sync() == 1
    
    found = backend.get_node_by_url_sync("https://example.com")
    assert found is not None
```
**Тест**: `pytest tests/unit/test_memory_backend.py::test_sync_wrappers -v`

---

## Phase 2: Graph Integration - Параметр backend (Кроки 11-20)

### Крок 11: Додати backend параметр в Graph.__init__
**Файл**: `graph_crawler/domain/entities/graph.py`
**Дія**: Додати параметр (без логіки)
```python
def __init__(
    self,
    backend: Optional["IGraphBackend"] = None,  # NEW LINE
    default_merge_strategy: Optional[str] = None,
    ...
):
    self._backend = backend
    self._use_backend = backend is not None
    # ... rest unchanged
```
**Тест**:
```bash
python -c "
from graph_crawler.domain.entities.graph import Graph
g = Graph()
print('Without backend:', g._use_backend)  # False

from graph_crawler.data.backends.memory import MemoryBackend
import asyncio
async def test():
    b = MemoryBackend()
    await b.open()
    g = Graph(backend=b)
    print('With backend:', g._use_backend)  # True
asyncio.run(test())
"
```

---

### Крок 12: Додати import IGraphBackend
**Файл**: `graph_crawler/domain/entities/graph.py`
**Дія**: Додати TYPE_CHECKING import
```python
from typing import TYPE_CHECKING
...
if TYPE_CHECKING:
    from graph_crawler.data.interfaces import IGraphBackend
```
**Тест**: `python -c "from graph_crawler.domain.entities.graph import Graph; print('OK')"`

---

### Крок 13: Змінити add_node - delegate при backend
**Файл**: `graph_crawler/domain/entities/graph.py`
**Дія**: Перший метод з delegation
```python
def add_node(self, node: Node, overwrite: bool = False) -> Node:
    if self._use_backend:
        if overwrite:
            return self._backend.insert_node_sync(node)  # type: ignore
        return self._backend.insert_node_sync(node)  # type: ignore
    # ... existing code
```
**Тест**:
```python
# test_graph_backend_integration.py
async def test_add_node_with_backend():
    from graph_crawler.data.backends.memory import MemoryBackend
    from graph_crawler.domain.entities.graph import Graph
    from graph_crawler.domain.entities.node import Node
    
    backend = MemoryBackend()
    await backend.open()
    
    graph = Graph(backend=backend)
    node = Node(url="https://example.com")
    result = graph.add_node(node)
    
    assert result.url == "https://example.com"
    assert len(graph) == 1  # Should work!
```

---

### Крок 14: Змінити add_node_async - delegate при backend
**Файл**: `graph_crawler/domain/entities/graph.py`
**Дія**: Async версія
```python
async def add_node_async(self, node: Node, overwrite: bool = False) -> Node:
    if self._use_backend:
        if overwrite:
            return await self._backend.insert_node_overwrite(node)  # type: ignore
        return await self._backend.insert_node(node)  # type: ignore
    # ... existing code
```
**Тест**: Async test для add_node_async

---

### Крок 15: Змінити get_node_by_url - delegate
**Файл**: `graph_crawler/domain/entities/graph.py`
**Дія**: Lookup делегація
```python
def get_node_by_url(self, url: str, load_from_disk: bool = True) -> Optional[Node]:
    if self._use_backend:
        return self._backend.get_node_by_url_sync(url)  # type: ignore
    # ... existing code
```
**Тест**: Test lookup через backend

---

### Крок 16: Змінити get_node_by_id - delegate
**Файл**: `graph_crawler/domain/entities/graph.py`
**Дія**: ID lookup делегація
```python
def get_node_by_id(self, node_id: str) -> Optional[Node]:
    if self._use_backend:
        return self._backend.get_node_by_id_sync(node_id)  # type: ignore
    # ... existing code
```
**Тест**: Test ID lookup

---

### Крок 17: Змінити __len__ - delegate
**Файл**: `graph_crawler/domain/entities/graph.py`
**Дія**: Count делегація
```python
def __len__(self) -> int:
    if self._use_backend:
        return self._backend.count_nodes_sync()  # type: ignore
    return len(self._nodes)
```
**Тест**: `assert len(graph) == expected_count`

---

### Крок 18: Змінити __iter__ - delegate
**Файл**: `graph_crawler/domain/entities/graph.py`
**Дія**: Iteration делегація
```python
def __iter__(self) -> Iterator[Node]:
    if self._use_backend:
        return self._backend.iter_nodes_sync()  # type: ignore
    return iter(self._nodes.values())
```
**Тест**: `for node in graph: print(node.url)`

---

### Крок 19: Змінити add_edge - delegate
**Файл**: `graph_crawler/domain/entities/graph.py`
**Дія**: Edge делегація
```python
def add_edge(self, edge: Edge, ...) -> Edge:
    if self._use_backend:
        return self._backend.insert_edge(edge)  # sync call needed
    # ... existing code
```
**Тест**: Test edge creation through backend

---

### Крок 20: Integration тест - повний цикл
**Файл**: `tests/integration/test_graph_with_backend.py`
**Дія**: E2E тест
```python
@pytest.mark.asyncio
async def test_full_graph_cycle_with_backend():
    backend = MemoryBackend()
    await backend.open()
    
    graph = Graph(backend=backend)
    
    # Add nodes
    n1 = graph.add_node(Node(url="https://a.com"))
    n2 = graph.add_node(Node(url="https://b.com"))
    
    # Add edge
    graph.add_edge(Edge(source_node_id=n1.node_id, target_node_id=n2.node_id))
    
    # Verify
    assert len(graph) == 2
    assert graph.get_node_by_url("https://a.com") is not None
    
    # Iterate
    urls = [n.url for n in graph]
    assert "https://a.com" in urls
    
    await backend.close()
```
**Тест**: `pytest tests/integration/test_graph_with_backend.py -v`

---

## Phase 3: Property Accessors (Кроки 21-25)

### Крок 21: Додати nodes property з delegation
**Файл**: `graph_crawler/domain/entities/graph.py`
**Дія**: Backward-compatible property
```python
@property
def nodes(self) -> Dict[str, Node]:
    if self._use_backend:
        return self._backend.nodes  # Direct dict access
    return self._nodes
```
**Тест**: `assert "node_id" in graph.nodes`

---

### Крок 22: Додати edges property з delegation
**Файл**: `graph_crawler/domain/entities/graph.py`
**Дія**: Edge list property
```python
@property
def edges(self) -> List[Edge]:
    if self._use_backend:
        return self._backend.edges
    return self._edges
```
**Тест**: `assert len(graph.edges) == expected`

---

### Крок 23: Додати url_to_node property
**Файл**: `graph_crawler/domain/entities/graph.py`
**Дія**: URL index property
```python
@property
def url_to_node(self) -> Dict[str, Node]:
    if self._use_backend:
        return self._backend.url_to_node
    return self._url_to_node
```
**Тест**: `assert "https://a.com" in graph.url_to_node`

---

### Крок 24: Тест backward compatibility - existing code
**Файл**: `tests/integration/test_backward_compat.py`
**Дія**: Перевірка що старий код працює
```python
def test_graph_without_backend_unchanged():
    """Graph без backend працює як раніше."""
    graph = Graph()
    
    node = Node(url="https://example.com")
    graph.add_node(node)
    
    # Прямий доступ до internal attrs
    assert len(graph._nodes) == 1
    assert "https://example.com" in [n.url for n in graph._nodes.values()]
```
**Тест**: `pytest tests/integration/test_backward_compat.py -v`

---

### Крок 25: Тест з обома режимами
**Файл**: `tests/integration/test_both_modes.py`
**Дія**: Параметризований тест
```python
@pytest.mark.parametrize("use_backend", [True, False])
@pytest.mark.asyncio
async def test_graph_operations(use_backend):
    if use_backend:
        backend = MemoryBackend()
        await backend.open()
        graph = Graph(backend=backend)
    else:
        graph = Graph()
    
    # Same operations should work
    node = graph.add_node(Node(url="https://test.com"))
    assert len(graph) == 1
    assert graph.get_node_by_url("https://test.com") is not None
```
**Тест**: `pytest tests/integration/test_both_modes.py -v`

---

## Phase 4: Replace Direct _nodes Access (Кроки 26-35)

### Крок 26: Audit всіх _nodes доступів
**Дія**: Знайти всі файли
```bash
grep -rn "\._nodes\." graph_crawler/ --include="*.py" | grep -v test | grep -v __pycache__
```
**Тест**: Зберегти список файлів для зміни

---

### Крок 27: graph_operations.py - union()
**Файл**: `graph_crawler/domain/entities/graph_operations.py`
**Дія**: Замінити `g1._nodes.values()` на `g1.iter_nodes()`
```python
# BEFORE
for node in g1._nodes.values():
    result.add_node(node)

# AFTER  
for node in g1.iter_nodes():
    result.add_node(node)
```
**Тест**: `pytest tests/unit/test_graph_operations.py::test_union -v`

---

### Крок 28: graph_operations.py - difference()
**Файл**: `graph_crawler/domain/entities/graph_operations.py`
**Дія**: Замінити прямий доступ
```python
# BEFORE
for node in g1._nodes.values():
    if node.url not in other_urls:
        result.add_node(node)

# AFTER
for node in g1.iter_nodes():
    if node.url not in other_urls:
        result.add_node(node)
```
**Тест**: `pytest tests/unit/test_graph_operations.py::test_difference -v`

---

### Крок 29: graph_operations.py - intersection()
**Файл**: `graph_crawler/domain/entities/graph_operations.py`
**Дія**: Замінити intersection
**Тест**: `pytest tests/unit/test_graph_operations.py::test_intersection -v`

---

### Крок 30: graph_operations.py - symmetric_difference()
**Файл**: `graph_crawler/domain/entities/graph_operations.py`
**Дія**: Замінити sym diff
**Тест**: `pytest tests/unit/test_graph_operations.py::test_symmetric_difference -v`

---

### Крок 31: graph_mapper.py - to_dto()
**Файл**: `graph_crawler/application/dto/mappers/graph_mapper.py`
**Дія**: Замінити nodes.values()
```python
# BEFORE
nodes_dto = NodeMapper.to_dto_list(list(graph.nodes.values()))

# AFTER
nodes_dto = NodeMapper.to_dto_list(list(graph.iter_nodes()))
```
**Тест**: `pytest tests/unit/test_graph_mapper.py -v`

---

### Крок 32: graph_statistics.py - перевірка
**Файл**: `graph_crawler/domain/entities/graph_statistics.py`
**Дія**: Перевірити та замінити якщо є прямий доступ
**Тест**: `pytest tests/unit/test_graph_statistics.py -v`

---

### Крок 33: Додати iter_nodes() метод в Graph
**Файл**: `graph_crawler/domain/entities/graph.py`
**Дія**: Публічний метод ітерації
```python
def iter_nodes(self) -> Iterator[Node]:
    """Iterate over all nodes (streaming-safe)."""
    if self._use_backend:
        return self._backend.iter_nodes_sync()
    return iter(self._nodes.values())
```
**Тест**: `for n in graph.iter_nodes(): print(n.url)`

---

### Крок 34: Додати iter_edges() метод в Graph
**Файл**: `graph_crawler/domain/entities/graph.py`
**Дія**: Публічний метод для edges
```python
def iter_edges(self) -> Iterator[Edge]:
    """Iterate over all edges (streaming-safe)."""
    if self._use_backend:
        return self._backend.iter_edges_sync()
    return iter(self._edges)
```
**Тест**: `for e in graph.iter_edges(): print(e)`

---

### Крок 35: Regression тест усіх операцій
**Файл**: `tests/integration/test_regression_all_ops.py`
**Дія**: Масивний regression тест
```python
@pytest.mark.asyncio
async def test_all_operations_with_backend():
    """Всі операції працюють з backend."""
    backend = MemoryBackend()
    await backend.open()
    g1 = Graph(backend=backend)
    g2 = Graph()  # Without backend
    
    # Add same data
    for g in [g1, g2]:
        for i in range(10):
            g.add_node(Node(url=f"https://example.com/{i}"))
    
    # Operations
    assert len(g1) == len(g2)
    assert set(n.url for n in g1) == set(n.url for n in g2)
```
**Тест**: `pytest tests/integration/test_regression_all_ops.py -v`

---

## Phase 5: SQLite Backend Implementation (Кроки 36-45)

### Крок 36: Створити sqlite.py scaffold
**Файл**: `graph_crawler/data/backends/sqlite.py`
**Дія**: Basic structure
```python
"""SQLiteBackend - Persistent storage for large graphs."""

import aiosqlite
from typing import Any, AsyncIterator, Dict, List, Optional, Set

class SQLiteBackend:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn = None
    
    async def open(self) -> None:
        self._conn = await aiosqlite.connect(self.db_path)
        await self._init_schema()
    
    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
```
**Тест**: `python -c "from graph_crawler.data.backends.sqlite import SQLiteBackend; print('OK')"`

---

### Крок 37: SQLiteBackend - schema creation
**Файл**: `graph_crawler/data/backends/sqlite.py`
**Дія**: CREATE TABLE statements
```python
async def _init_schema(self) -> None:
    await self._conn.executescript('''
        CREATE TABLE IF NOT EXISTS nodes (
            node_id TEXT PRIMARY KEY,
            url TEXT NOT NULL UNIQUE,
            depth INTEGER DEFAULT 0,
            scanned INTEGER DEFAULT 0,
            ...
        );
        CREATE TABLE IF NOT EXISTS edges (...);
        CREATE INDEX IF NOT EXISTS idx_nodes_url ON nodes(url);
    ''')
    await self._conn.commit()
```
**Тест**: `pytest tests/unit/test_sqlite_backend.py::test_schema_creation -v`

---

### Крок 38: SQLiteBackend - insert_node
**Файл**: `graph_crawler/data/backends/sqlite.py`
**Дія**: INSERT with UPSERT
```python
async def insert_node(self, node: Any) -> Any:
    await self._conn.execute(
        '''INSERT OR IGNORE INTO nodes (...) VALUES (?, ?, ...)''',
        (node.node_id, node.url, ...)
    )
    await self._conn.commit()
    return node
```
**Тест**: `pytest tests/unit/test_sqlite_backend.py::test_insert_node -v`

---

### Крок 39: SQLiteBackend - get_node_by_url
**Файл**: `graph_crawler/data/backends/sqlite.py`
**Дія**: SELECT by url
```python
async def get_node_by_url(self, url: str) -> Optional[Any]:
    cursor = await self._conn.execute(
        'SELECT * FROM nodes WHERE url = ?', (url,)
    )
    row = await cursor.fetchone()
    if row:
        return self._row_to_node(row)
    return None
```
**Тест**: `pytest tests/unit/test_sqlite_backend.py::test_get_node -v`

---

### Крок 40: SQLiteBackend - iter_nodes (streaming)
**Файл**: `graph_crawler/data/backends/sqlite.py`
**Дія**: LIMIT/OFFSET pagination
```python
async def iter_nodes(self, batch_size: int = 1000) -> AsyncIterator[Any]:
    offset = 0
    while True:
        cursor = await self._conn.execute(
            'SELECT * FROM nodes LIMIT ? OFFSET ?',
            (batch_size, offset)
        )
        rows = await cursor.fetchall()
        if not rows:
            break
        for row in rows:
            yield self._row_to_node(row)
        offset += batch_size
```
**Тест**: `pytest tests/unit/test_sqlite_backend.py::test_streaming -v`

---

### Крок 41: SQLiteBackend - edge operations
**Файл**: `graph_crawler/data/backends/sqlite.py`
**Дія**: insert_edge, edge_exists
**Тест**: `pytest tests/unit/test_sqlite_backend.py::test_edges -v`

---

### Крок 42: SQLiteBackend - count operations
**Файл**: `graph_crawler/data/backends/sqlite.py`
**Дія**: count_nodes, count_edges
```python
async def count_nodes(self) -> int:
    cursor = await self._conn.execute('SELECT COUNT(*) FROM nodes')
    row = await cursor.fetchone()
    return row[0]
```
**Тест**: `pytest tests/unit/test_sqlite_backend.py::test_count -v`

---

### Крок 43: SQLiteBackend - sync wrappers
**Файл**: `graph_crawler/data/backends/sqlite.py`
**Дія**: Sync версії для Graph
**Тест**: `pytest tests/unit/test_sqlite_backend.py::test_sync -v`

---

### Крок 44: Integration тест Graph + SQLiteBackend
**Файл**: `tests/integration/test_graph_sqlite.py`
**Дія**: E2E з SQLite
```python
@pytest.mark.asyncio
async def test_graph_with_sqlite():
    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.db') as f:
        backend = SQLiteBackend(f.name)
        await backend.open()
        
        graph = Graph(backend=backend)
        graph.add_node(Node(url="https://example.com"))
        
        assert len(graph) == 1
        
        await backend.close()
```
**Тест**: `pytest tests/integration/test_graph_sqlite.py -v`

---

### Крок 45: Benchmark Memory vs SQLite
**Файл**: `tests/benchmark/test_backend_perf.py`
**Дія**: Performance comparison
```python
def test_performance_comparison():
    import time
    
    # Memory backend
    start = time.time()
    # ... insert 10000 nodes
    memory_time = time.time() - start
    
    # SQLite backend
    start = time.time()
    # ... insert 10000 nodes  
    sqlite_time = time.time() - start
    
    print(f"Memory: {memory_time:.2f}s, SQLite: {sqlite_time:.2f}s")
    assert sqlite_time < memory_time * 10  # SQLite не більше 10x повільніший
```
**Тест**: `pytest tests/benchmark/test_backend_perf.py -v -s`

---

## Phase 6: Streaming Operations & Final Integration (Кроки 46-50)

### Крок 46: Async iter_nodes_async в Graph
**Файл**: `graph_crawler/domain/entities/graph.py`
**Дія**: Async streaming
```python
async def iter_nodes_async(self) -> AsyncIterator[Node]:
    if self._use_backend:
        async for node in self._backend.iter_nodes():
            yield node
    else:
        for node in self._nodes.values():
            yield node
```
**Тест**: `async for n in graph.iter_nodes_async(): ...`

---

### Крок 47: Streaming union operation
**Файл**: `graph_crawler/domain/entities/graph_operations.py`
**Дія**: union_streaming метод
```python
@staticmethod
async def union_streaming(g1, g2, result_backend):
    """Memory-efficient union for large graphs."""
    result = Graph(backend=result_backend)
    
    async for node in g1.iter_nodes_async():
        await result_backend.insert_node(node)
    
    async for node in g2.iter_nodes_async():
        existing = await result_backend.get_node_by_url(node.url)
        if not existing:
            await result_backend.insert_node(node)
    
    return result
```
**Тест**: `pytest tests/integration/test_streaming_ops.py -v`

---

### Крок 48: Documentation update
**Файл**: `graph_crawler/data/ARCHITECTURE.md`
**Дія**: Оновити документацію з прикладами
**Тест**: Review documentation

---

### Крок 49: Export в __init__.py
**Файл**: `graph_crawler/data/__init__.py`
**Дія**: Додати backends до exports
```python
from graph_crawler.data.backends.memory import MemoryBackend
from graph_crawler.data.backends.sqlite import SQLiteBackend

__all__ = [
    "IGraphBackend",
    "MemoryBackend", 
    "SQLiteBackend",
]
```
**Тест**: `from graph_crawler.data import MemoryBackend, SQLiteBackend`

---

### Крок 50: Full regression test suite
**Файл**: `tests/integration/test_full_regression.py`
**Дія**: Фінальний E2E тест
```python
@pytest.mark.asyncio
async def test_complete_migration():
    """Complete test of all backend functionality."""
    import tempfile
    
    # Test 1: Memory backend
    mb = MemoryBackend()
    await mb.open()
    g1 = Graph(backend=mb)
    
    # Test 2: SQLite backend
    with tempfile.NamedTemporaryFile(suffix='.db') as f:
        sb = SQLiteBackend(f.name)
        await sb.open()
        g2 = Graph(backend=sb)
        
        # Both should work identically
        for g in [g1, g2]:
            for i in range(100):
                g.add_node(Node(url=f"https://test.com/{i}"))
            assert len(g) == 100
        
        # Operations
        urls1 = set(n.url for n in g1)
        urls2 = set(n.url for n in g2)
        assert urls1 == urls2
        
        await sb.close()
    
    await mb.close()
    print("✅ All 50 steps complete!")
```
**Тест**: `pytest tests/integration/test_full_regression.py -v`

---

## Підсумок

| Phase | Кроки | Опис | Estimated Time |
|-------|-------|------|----------------|
| 1 | 1-10 | MemoryBackend тести | 2-3 години |
| 2 | 11-20 | Graph backend параметр | 4-5 годин |
| 3 | 21-25 | Property accessors | 1-2 години |
| 4 | 26-35 | Replace _nodes access | 3-4 години |
| 5 | 36-45 | SQLiteBackend | 6-8 годин |
| 6 | 46-50 | Streaming & final | 2-3 години |

**Загалом**: ~20-25 годин роботи

---

## Команди для швидкого тестування

```bash
# Запуск всіх тестів
pytest tests/ -v

# Тільки backend тести
pytest tests/unit/test_memory_backend.py tests/unit/test_sqlite_backend.py -v

# Integration тести
pytest tests/integration/ -v

# Benchmark
pytest tests/benchmark/ -v -s
```

---

*Version: 1.0*
*Created: 2026-01-20*
