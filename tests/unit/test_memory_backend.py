"""
Unit тести для MemoryBackend.

Кроки 2-10 з MIGRATION_50_STEPS.md
"""

import pytest
from graph_crawler.data.backends.memory import MemoryBackend
from graph_crawler.domain.entities.node import Node
from graph_crawler.domain.entities.edge import Edge

# ═══════════════════════════════════════════════════════════════════════════
# Крок 2: Lifecycle тести
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_memory_backend_lifecycle():
    """Крок 2: open/close lifecycle."""
    backend = MemoryBackend()

    # Initially closed
    assert not backend._is_open

    # Open
    await backend.open()
    assert backend._is_open

    # Close
    await backend.close()
    assert not backend._is_open

# ═══════════════════════════════════════════════════════════════════════════
# Крок 3: Insert node
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_insert_node():
    """Крок 3: Базовий insert node."""
    backend = MemoryBackend()
    await backend.open()

    node = Node(url="https://example.com")
    result = await backend.insert_node(node)

    assert result.url == "https://example.com"
    assert await backend.count_nodes() == 1

    await backend.close()

# ═══════════════════════════════════════════════════════════════════════════
# Крок 4: URL normalization
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_url_normalization():
    """Крок 4: URL нормалізація - trailing slash."""
    backend = MemoryBackend()
    await backend.open()

    # З trailing slash
    node1 = Node(url="https://example.com/")
    result1 = await backend.insert_node(node1)

    # Без trailing slash - має бути та сама нода
    node2 = Node(url="https://example.com")
    result2 = await backend.insert_node(node2)

    # Перевіряємо що це одна і та сама нода
    assert result1.node_id == result2.node_id
    assert await backend.count_nodes() == 1

    await backend.close()

@pytest.mark.asyncio
async def test_url_normalization_case():
    """Крок 4: URL нормалізація - case sensitivity."""
    backend = MemoryBackend()
    await backend.open()

    # Uppercase domain
    node1 = Node(url="https://EXAMPLE.COM/page")
    await backend.insert_node(node1)

    # Lowercase domain - має бути та сама нода
    node2 = Node(url="https://example.com/page")
    await backend.insert_node(node2)

    assert await backend.count_nodes() == 1

    await backend.close()

# ═══════════════════════════════════════════════════════════════════════════
# Крок 5: Get node by URL
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_node_by_url():
    """Крок 5: Отримання ноди за URL."""
    backend = MemoryBackend()
    await backend.open()

    node = Node(url="https://example.com/page")
    await backend.insert_node(node)

    # Знайти існуючу
    found = await backend.get_node_by_url("https://example.com/page")
    assert found is not None
    assert found.url == "https://example.com/page"

    # Не знайти неіснуючу
    not_found = await backend.get_node_by_url("https://other.com")
    assert not_found is None

    await backend.close()

@pytest.mark.asyncio
async def test_get_node_by_id():
    """Крок 5: Отримання ноди за ID."""
    backend = MemoryBackend()
    await backend.open()

    node = Node(url="https://example.com")
    inserted = await backend.insert_node(node)

    # Знайти за ID
    found = await backend.get_node_by_id(inserted.node_id)
    assert found is not None
    assert found.url == "https://example.com"

    # Не знайти неіснуючий ID
    not_found = await backend.get_node_by_id("fake-id-12345")
    assert not_found is None

    await backend.close()

# ═══════════════════════════════════════════════════════════════════════════
# Крок 6: Insert edge
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_insert_edge():
    """Крок 6: Додавання ребра."""
    backend = MemoryBackend()
    await backend.open()

    # Створити дві ноди
    node1 = Node(url="https://a.com")
    node2 = Node(url="https://b.com")
    n1 = await backend.insert_node(node1)
    n2 = await backend.insert_node(node2)

    # Додати ребро
    edge = Edge(source_node_id=n1.node_id, target_node_id=n2.node_id)
    await backend.insert_edge(edge)

    assert await backend.count_edges() == 1
    assert await backend.edge_exists(n1.node_id, n2.node_id)
    assert not await backend.edge_exists(n2.node_id, n1.node_id)  # Направлене

    await backend.close()

# ═══════════════════════════════════════════════════════════════════════════
# Крок 7: Iter nodes
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_iter_nodes():
    """Крок 7: Streaming ітерація по нодах."""
    backend = MemoryBackend()
    await backend.open()

    # Додати 100 нод
    for i in range(100):
        node = Node(url=f"https://example.com/page{i}")
        await backend.insert_node(node)

    # Ітерувати з batch_size=10
    count = 0
    urls = set()
    async for node in backend.iter_nodes(batch_size=10):
        count += 1
        urls.add(node.url)

    assert count == 100
    assert len(urls) == 100

    await backend.close()

@pytest.mark.asyncio
async def test_iter_edges():
    """Крок 7: Streaming ітерація по ребрах."""
    backend = MemoryBackend()
    await backend.open()

    # Створити ноди
    nodes = []
    for i in range(10):
        node = Node(url=f"https://example.com/{i}")
        nodes.append(await backend.insert_node(node))

    # Створити ребра (chain)
    for i in range(9):
        edge = Edge(source_node_id=nodes[i].node_id, target_node_id=nodes[i+1].node_id)
        await backend.insert_edge(edge)

    # Ітерувати
    count = 0
    async for edge in backend.iter_edges():
        count += 1

    assert count == 9

    await backend.close()

# ═══════════════════════════════════════════════════════════════════════════
# Крок 8: Delete node
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_delete_node():
    """Крок 8: Видалення ноди з каскадом ребер."""
    backend = MemoryBackend()
    await backend.open()

    # Створити дві ноди
    node1 = Node(url="https://a.com")
    node2 = Node(url="https://b.com")
    n1 = await backend.insert_node(node1)
    n2 = await backend.insert_node(node2)

    # Додати ребро
    edge = Edge(source_node_id=n1.node_id, target_node_id=n2.node_id)
    await backend.insert_edge(edge)

    assert await backend.count_nodes() == 2
    assert await backend.count_edges() == 1

    # Видалити node1 - ребро має видалитись автоматично
    deleted = await backend.delete_node(n1.node_id)
    assert deleted
    assert await backend.count_nodes() == 1
    assert await backend.count_edges() == 0

    # Спроба видалити неіснуючу ноду
    deleted_fake = await backend.delete_node("fake-id")
    assert not deleted_fake

    await backend.close()

# ═══════════════════════════════════════════════════════════════════════════
# Крок 9: Batch operations
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_batch_insert_nodes():
    """Крок 9: Batch insert нод."""
    backend = MemoryBackend()
    await backend.open()

    nodes = [Node(url=f"https://example.com/{i}") for i in range(50)]
    count = await backend.insert_nodes_batch(nodes)

    assert count == 50
    assert await backend.count_nodes() == 50

    await backend.close()

@pytest.mark.asyncio
async def test_batch_insert_edges():
    """Крок 9: Batch insert ребер."""
    backend = MemoryBackend()
    await backend.open()

    # Створити ноди
    nodes = []
    for i in range(10):
        nodes.append(await backend.insert_node(Node(url=f"https://example.com/{i}")))

    # Batch insert edges
    edges = [
        Edge(source_node_id=nodes[i].node_id, target_node_id=nodes[i+1].node_id)
        for i in range(9)
    ]
    count = await backend.insert_edges_batch(edges)

    assert count == 9
    assert await backend.count_edges() == 9

    await backend.close()

@pytest.mark.asyncio
async def test_batch_get_nodes():
    """Крок 9: Batch отримання нод."""
    backend = MemoryBackend()
    await backend.open()

    # Додати ноди
    for i in range(10):
        await backend.insert_node(Node(url=f"https://example.com/{i}"))

    # Batch get
    urls = [f"https://example.com/{i}" for i in range(5)]
    urls.append("https://nonexistent.com")  # Неіснуючий URL

    result = await backend.get_nodes_batch(urls)

    assert len(result) == 5  # Тільки існуючі

    await backend.close()

# ═══════════════════════════════════════════════════════════════════════════
# Крок 10: Sync wrappers
# ═══════════════════════════════════════════════════════════════════════════

def test_sync_insert_node():
    """Крок 10: Sync версія insert_node."""
    backend = MemoryBackend()

    node = Node(url="https://example.com")
    result = backend.insert_node_sync(node)

    assert result.url == "https://example.com"
    assert backend.count_nodes_sync() == 1

def test_sync_get_node():
    """Крок 10: Sync версія get_node_by_url."""
    backend = MemoryBackend()

    node = Node(url="https://example.com")
    backend.insert_node_sync(node)

    found = backend.get_node_by_url_sync("https://example.com")
    assert found is not None
    assert found.url == "https://example.com"

    not_found = backend.get_node_by_url_sync("https://other.com")
    assert not_found is None

def test_sync_iter_nodes():
    """Крок 10: Sync версія iter_nodes."""
    backend = MemoryBackend()

    for i in range(10):
        backend.insert_node_sync(Node(url=f"https://example.com/{i}"))

    count = 0
    for node in backend.iter_nodes_sync():
        count += 1

    assert count == 10

def test_sync_url_exists():
    """Крок 10: Sync версія url_exists."""
    backend = MemoryBackend()

    backend.insert_node_sync(Node(url="https://example.com"))

    assert backend.url_exists_sync("https://example.com")
    assert not backend.url_exists_sync("https://other.com")

# ═══════════════════════════════════════════════════════════════════════════
# Додаткові тести
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_stats():
    """Тест статистики."""
    backend = MemoryBackend()
    await backend.open()

    # Додати ноди (частина scanned)
    for i in range(10):
        node = Node(url=f"https://example.com/{i}")
        if i < 5:
            node.scanned = True
        await backend.insert_node(node)

    stats = await backend.get_stats()

    assert stats["total_nodes"] == 10
    assert stats["scanned_nodes"] == 5
    assert stats["unscanned_nodes"] == 5
    assert stats["backend_type"] == "memory"

    await backend.close()

@pytest.mark.asyncio
async def test_iter_unscanned_nodes():
    """Тест ітерації по unscanned нодах."""
    backend = MemoryBackend()
    await backend.open()

    for i in range(10):
        node = Node(url=f"https://example.com/{i}")
        node.scanned = (i % 2 == 0)  # Парні - scanned
        await backend.insert_node(node)

    unscanned_count = 0
    async for node in backend.iter_unscanned_nodes():
        assert not node.scanned
        unscanned_count += 1

    assert unscanned_count == 5

    await backend.close()

@pytest.mark.asyncio
async def test_transaction_context():
    """Тест transaction context manager."""
    backend = MemoryBackend()
    await backend.open()

    async with backend.transaction():
        await backend.insert_node(Node(url="https://example.com"))

    assert await backend.count_nodes() == 1

    await backend.close()
