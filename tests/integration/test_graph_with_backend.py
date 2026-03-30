"""
Integration тести для Graph з Backend.

Крок 20: Повний цикл тестування Graph + MemoryBackend
"""

import pytest
from graph_crawler.data.backends.memory import MemoryBackend
from graph_crawler.domain.entities.graph import Graph
from graph_crawler.domain.entities.node import Node
from graph_crawler.domain.entities.edge import Edge

@pytest.mark.asyncio
async def test_full_graph_cycle_with_backend():
    """Крок 20: E2E тест Graph з MemoryBackend."""
    backend = MemoryBackend()
    await backend.open()

    graph = Graph(backend=backend)

    # Add nodes
    n1 = graph.add_node(Node(url="https://a.com"))
    n2 = graph.add_node(Node(url="https://b.com"))

    # Verify nodes added
    assert len(graph) == 2
    assert graph.get_node_by_url("https://a.com") is not None
    assert graph.get_node_by_url("https://b.com") is not None
    assert graph.get_node_by_url("https://c.com") is None

    # Add edge
    edge = Edge(source_node_id=n1.node_id, target_node_id=n2.node_id)
    graph.add_edge(edge)

    # Verify via backend
    assert await backend.count_edges() == 1
    assert await backend.edge_exists(n1.node_id, n2.node_id)

    # Iterate
    urls = [n.url for n in graph]
    assert "https://a.com" in urls
    assert "https://b.com" in urls

    await backend.close()
    print("✅ test_full_graph_cycle_with_backend passed!")

@pytest.mark.asyncio
async def test_graph_async_operations_with_backend():
    """Тест async методів з backend."""
    backend = MemoryBackend()
    await backend.open()

    graph = Graph(backend=backend)

    # Async add node
    n1 = await graph.add_node_async(Node(url="https://async1.com"))
    n2 = await graph.add_node_async(Node(url="https://async2.com"))

    assert len(graph) == 2

    # Async add edge
    edge = Edge(source_node_id=n1.node_id, target_node_id=n2.node_id)
    await graph.add_edge_async(edge)

    assert await backend.count_edges() == 1

    await backend.close()
    print("✅ test_graph_async_operations_with_backend passed!")

@pytest.mark.asyncio
async def test_graph_node_lookup_with_backend():
    """Тест lookup операцій."""
    backend = MemoryBackend()
    await backend.open()

    graph = Graph(backend=backend)

    node = Node(url="https://lookup-test.com")
    added = graph.add_node(node)

    # By URL
    found_by_url = graph.get_node_by_url("https://lookup-test.com")
    assert found_by_url is not None
    assert found_by_url.url == "https://lookup-test.com"

    # By ID
    found_by_id = graph.get_node_by_id(added.node_id)
    assert found_by_id is not None
    assert found_by_id.node_id == added.node_id

    await backend.close()
    print("✅ test_graph_node_lookup_with_backend passed!")

def test_graph_without_backend_unchanged():
    """Backward compatibility: Graph без backend працює як раніше."""
    graph = Graph()

    node = Node(url="https://example.com")
    graph.add_node(node)

    # Перевіряємо що внутрішні структури заповнені
    assert len(graph._nodes) == 1
    assert "https://example.com" in [n.url for n in graph._nodes.values()]
    assert graph._use_backend is False

    print("✅ test_graph_without_backend_unchanged passed!")

@pytest.mark.asyncio
async def test_graph_url_normalization_with_backend():
    """URL нормалізація працює з backend."""
    backend = MemoryBackend()
    await backend.open()

    graph = Graph(backend=backend)

    # Add with trailing slash
    graph.add_node(Node(url="https://example.com/"))

    # Try to add without - should return same node (result assigned to _ as unused)
    _ = graph.add_node(Node(url="https://example.com"))

    assert len(graph) == 1

    # Lookup should work both ways
    assert graph.get_node_by_url("https://example.com/") is not None
    assert graph.get_node_by_url("https://example.com") is not None

    await backend.close()
    print("✅ test_graph_url_normalization_with_backend passed!")

@pytest.mark.asyncio
async def test_graph_iteration_with_backend():
    """Ітерація по графу з backend."""
    backend = MemoryBackend()
    await backend.open()

    graph = Graph(backend=backend)

    # Add multiple nodes
    for i in range(10):
        graph.add_node(Node(url=f"https://example.com/{i}"))

    # Iterate and count
    count = 0
    urls = set()
    for node in graph:
        count += 1
        urls.add(node.url)

    assert count == 10
    assert len(urls) == 10

    await backend.close()
    print("✅ test_graph_iteration_with_backend passed!")
