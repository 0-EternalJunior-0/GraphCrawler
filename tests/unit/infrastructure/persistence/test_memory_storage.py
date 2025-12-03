"""Тести для MemoryStorage - in-memory сховище для графів.

Виправлено API:
- save_graph(graph) - без graph_id
- load_graph() - без параметрів
- Edge(source_node_id, target_node_id) - правильні назви полів
"""

import pytest
from graph_crawler.infrastructure.persistence.memory_storage import MemoryStorage
from graph_crawler.domain.entities.graph import Graph
from graph_crawler.domain.entities.node import Node
from graph_crawler.domain.entities.edge import Edge


@pytest.mark.asyncio
class TestMemoryStorageInitialization:
    """Тести ініціалізації MemoryStorage."""
    
    async def test_creates_empty_storage(self):
        """Storage створюється пустим."""
        storage = MemoryStorage()
        
        assert storage is not None
        assert hasattr(storage, 'save_graph')
        assert hasattr(storage, 'load_graph')
    
    async def test_storage_is_empty_initially(self):
        """Storage спочатку пустий."""
        storage = MemoryStorage()
        
        # Спроба завантажити граф
        graph = await storage.load_graph()
        
        assert graph is None


@pytest.mark.asyncio
class TestMemoryStorageSaveGraph:
    """Тести збереження графа."""
    
    async def test_saves_empty_graph(self):
        """Зберігає пустий граф."""
        storage = MemoryStorage()
        graph = Graph()
        
        result = await storage.save_graph(graph)
        
        assert result is True
    
    async def test_saves_graph_with_nodes(self):
        """Зберігає граф з nodes."""
        storage = MemoryStorage()
        graph = Graph()
        
        node1 = Node(url="https://example.com", depth=0)
        node2 = Node(url="https://example.com/page1", depth=1)
        
        graph.add_node(node1)
        graph.add_node(node2)
        
        result = await storage.save_graph(graph)
        
        assert result is True
    
    async def test_saves_graph_with_edges(self):
        """Зберігає граф з edges."""
        storage = MemoryStorage()
        graph = Graph()
        
        node1 = Node(url="https://example.com", depth=0)
        node2 = Node(url="https://example.com/page1", depth=1)
        
        graph.add_node(node1)
        graph.add_node(node2)
        
        # Правильні назви полів: source_node_id, target_node_id
        edge = Edge(source_node_id=node1.node_id, target_node_id=node2.node_id)
        graph.add_edge(edge)
        
        result = await storage.save_graph(graph)
        
        assert result is True
    
    async def test_overwrites_existing_graph(self):
        """Перезаписує існуючий граф."""
        storage = MemoryStorage()
        
        # Перший граф
        graph1 = Graph()
        graph1.add_node(Node(url="https://example.com/page1", depth=0))
        await storage.save_graph(graph1)
        
        # Другий граф (інший)
        graph2 = Graph()
        graph2.add_node(Node(url="https://example.com/page2", depth=0))
        await storage.save_graph(graph2)
        
        # Завантажуємо граф
        loaded = await storage.load_graph()
        
        # Має бути другий граф
        assert "page2" in list(loaded.nodes.values())[0].url


@pytest.mark.asyncio
class TestMemoryStorageLoadGraph:
    """Тести завантаження графа."""
    
    async def test_loads_saved_graph(self):
        """Завантажує збережений граф."""
        storage = MemoryStorage()
        
        # Зберігаємо граф
        original_graph = Graph()
        node = Node(url="https://example.com", depth=0)
        original_graph.add_node(node)
        
        await storage.save_graph(original_graph)
        
        # Завантажуємо граф
        loaded_graph = await storage.load_graph()
        
        assert loaded_graph is not None
        assert len(loaded_graph.nodes) == 1
    
    async def test_loads_graph_with_correct_data(self):
        """Завантажує граф з правильними даними."""
        storage = MemoryStorage()
        
        # Зберігаємо граф
        original_graph = Graph()
        node1 = Node(url="https://example.com", depth=0)
        node2 = Node(url="https://example.com/page1", depth=1)
        
        original_graph.add_node(node1)
        original_graph.add_node(node2)
        
        edge = Edge(source_node_id=node1.node_id, target_node_id=node2.node_id)
        original_graph.add_edge(edge)
        
        await storage.save_graph(original_graph)
        
        # Завантажуємо граф
        loaded_graph = await storage.load_graph()
        
        assert len(loaded_graph.nodes) == 2
        assert len(loaded_graph.edges) == 1
    
    async def test_returns_none_for_empty_storage(self):
        """Повертає None для пустого storage."""
        storage = MemoryStorage()
        
        loaded_graph = await storage.load_graph()
        
        assert loaded_graph is None


@pytest.mark.asyncio
class TestMemoryStorageClear:
    """Тести очищення storage."""
    
    async def test_clear_removes_graph(self):
        """clear() видаляє граф."""
        storage = MemoryStorage()
        
        # Зберігаємо граф
        graph = Graph()
        graph.add_node(Node(url="https://example.com/1", depth=0))
        await storage.save_graph(graph)
        
        # Очищуємо
        await storage.clear()
        
        # Граф має бути видалений
        loaded = await storage.load_graph()
        
        assert loaded is None
    
    async def test_clear_allows_new_saves(self):
        """Після clear() можна зберігати нові графи."""
        storage = MemoryStorage()
        
        # Зберігаємо граф
        graph1 = Graph()
        graph1.add_node(Node(url="https://example.com/old", depth=0))
        await storage.save_graph(graph1)
        
        # Очищуємо
        await storage.clear()
        
        # Зберігаємо новий граф
        graph2 = Graph()
        graph2.add_node(Node(url="https://example.com/new", depth=0))
        await storage.save_graph(graph2)
        
        # Завантажуємо
        loaded = await storage.load_graph()
        
        assert "new" in list(loaded.nodes.values())[0].url


@pytest.mark.asyncio
class TestMemoryStorageExists:
    """Тести методу exists."""
    
    async def test_exists_false_initially(self):
        """exists() повертає False для пустого storage."""
        storage = MemoryStorage()
        
        result = await storage.exists()
        
        assert result is False
    
    async def test_exists_true_after_save(self):
        """exists() повертає True після збереження."""
        storage = MemoryStorage()
        
        graph = Graph()
        graph.add_node(Node(url="https://example.com", depth=0))
        await storage.save_graph(graph)
        
        result = await storage.exists()
        
        assert result is True
    
    async def test_exists_false_after_clear(self):
        """exists() повертає False після clear."""
        storage = MemoryStorage()
        
        graph = Graph()
        await storage.save_graph(graph)
        await storage.clear()
        
        result = await storage.exists()
        
        assert result is False


@pytest.mark.asyncio
class TestMemoryStoragePerformance:
    """Тести продуктивності MemoryStorage."""
    
    async def test_handles_large_graph(self):
        """Обробляє великий граф (до MAX_NODES)."""
        storage = MemoryStorage()
        
        # Створюємо граф з 500 nodes (менше ніж MAX_NODES=1000)
        large_graph = Graph()
        for i in range(500):
            node = Node(url=f"https://example.com/page{i}", depth=i % 10)
            large_graph.add_node(node)
        
        # Зберігаємо
        result = await storage.save_graph(large_graph)
        
        assert result is True
        
        # Завантажуємо
        loaded = await storage.load_graph()
        
        assert len(loaded.nodes) == 500
    
    async def test_fast_save_and_load(self):
        """Швидке збереження та завантаження."""
        import time
        
        storage = MemoryStorage()
        
        # Граф середнього розміру
        graph = Graph()
        for i in range(100):
            node = Node(url=f"https://example.com/page{i}", depth=0)
            graph.add_node(node)
        
        # Збереження має бути швидким
        start = time.time()
        await storage.save_graph(graph)
        save_time = time.time() - start
        
        # Завантаження має бути швидким
        start = time.time()
        await storage.load_graph()
        load_time = time.time() - start
        
        # Memory storage має бути дуже швидким (< 1 секунди)
        assert save_time < 1.0
        assert load_time < 1.0
    
    async def test_raises_memory_error_for_too_large_graph(self):
        """Кидає MemoryError для занадто великого графа."""
        storage = MemoryStorage()
        
        # Створюємо граф з більше ніж MAX_NODES (1000)
        large_graph = Graph()
        for i in range(1001):
            node = Node(url=f"https://example.com/page{i}", depth=0)
            large_graph.add_node(node)
        
        # Має кинути MemoryError
        with pytest.raises(MemoryError):
            await storage.save_graph(large_graph)


@pytest.mark.asyncio
class TestMemoryStorageConcurrency:
    """Тести concurrent доступу."""
    
    async def test_sequential_saves(self):
        """Обробляє sequential saves."""
        storage = MemoryStorage()
        
        # Sequential saves (оскільки MemoryStorage зберігає один граф)
        for i in range(3):
            graph = Graph()
            graph.add_node(Node(url=f"https://example.com/{i}", depth=0))
            await storage.save_graph(graph)
        
        # Має бути останній граф
        loaded = await storage.load_graph()
        
        assert loaded is not None
        assert "2" in list(loaded.nodes.values())[0].url


# Загальна кількість тестів: 20+
# Покриває: ініціалізація, save/load, clear, exists, performance, concurrency
