"""
Тести для Graph entity.

Очікувана кількість: 40+ тестів
"""

import pytest
from graph_crawler.domain.entities.node import Node
from graph_crawler.domain.entities.edge import Edge
from graph_crawler.domain.entities.graph import Graph


class TestGraphCreation:
    """Тести створення Graph."""
    
    def test_creates_empty_graph(self):
        """Створюється порожній граф."""
        graph = Graph()
        
        assert len(graph) == 0
        assert len(graph.nodes) == 0
        assert len(graph.edges) == 0
    
    def test_creates_graph_with_merge_strategy(self):
        """Створюється граф з merge strategy."""
        graph = Graph(default_merge_strategy="merge")
        
        assert graph._default_merge_strategy == "merge"


class TestGraphAddNode:
    """Тести add_node()."""
    
    def test_add_single_node(self):
        """Додається один вузол."""
        graph = Graph()
        node = Node(url="https://example.com", depth=0)
        
        result = graph.add_node(node)
        
        assert len(graph) == 1
        assert result is node
    
    def test_add_multiple_nodes(self):
        """Додаються декілька вузлів."""
        graph = Graph()
        
        for i in range(5):
            node = Node(url=f"https://example.com/{i}", depth=0)
            graph.add_node(node)
        
        assert len(graph) == 5
    
    def test_add_duplicate_url_returns_existing(self):
        """Дублікат URL повертає існуючий вузол."""
        graph = Graph()
        node1 = Node(url="https://example.com", depth=0)
        node2 = Node(url="https://example.com", depth=1)
        
        graph.add_node(node1)
        result = graph.add_node(node2)
        
        assert len(graph) == 1
        assert result is node1
        assert result.depth == 0  # Оригінальний depth
    
    def test_add_duplicate_url_with_overwrite(self):
        """Дублікат URL з overwrite=True перезаписує."""
        graph = Graph()
        node1 = Node(url="https://example.com", depth=0)
        node2 = Node(url="https://example.com", depth=1)
        
        graph.add_node(node1)
        result = graph.add_node(node2, overwrite=True)
        
        assert len(graph) == 1
        assert result is node2
        assert graph.get_node_by_url("https://example.com").depth == 1


class TestGraphGetNode:
    """Тести отримання вузлів."""
    
    def test_get_node_by_url(self):
        """get_node_by_url() працює."""
        graph = Graph()
        node = Node(url="https://example.com", depth=0)
        graph.add_node(node)
        
        result = graph.get_node_by_url("https://example.com")
        
        assert result is node
    
    def test_get_node_by_url_not_found(self):
        """get_node_by_url() повертає None."""
        graph = Graph()
        
        result = graph.get_node_by_url("https://notfound.com")
        
        assert result is None
    
    def test_get_node_by_id(self):
        """get_node_by_id() працює."""
        graph = Graph()
        node = Node(url="https://example.com", depth=0)
        graph.add_node(node)
        
        result = graph.get_node_by_id(node.node_id)
        
        assert result is node
    
    def test_get_node_by_id_not_found(self):
        """get_node_by_id() повертає None."""
        graph = Graph()
        
        result = graph.get_node_by_id("nonexistent-id")
        
        assert result is None


class TestGraphAddEdge:
    """Тести add_edge()."""
    
    def test_add_single_edge(self):
        """Додається одне ребро."""
        graph = Graph()
        edge = Edge(source_node_id="node1", target_node_id="node2")
        
        result = graph.add_edge(edge)
        
        assert len(graph.edges) == 1
        assert result is edge
    
    def test_add_multiple_edges(self):
        """Додаються декілька ребер."""
        graph = Graph()
        
        for i in range(5):
            edge = Edge(source_node_id=f"node{i}", target_node_id=f"node{i+1}")
            graph.add_edge(edge)
        
        assert len(graph.edges) == 5
    
    def test_has_edge(self):
        """has_edge() працює."""
        graph = Graph()
        edge = Edge(source_node_id="node1", target_node_id="node2")
        graph.add_edge(edge)
        
        assert graph.has_edge("node1", "node2") is True
        assert graph.has_edge("node2", "node1") is False
        assert graph.has_edge("node1", "node3") is False


class TestGraphRemoveNode:
    """Тести remove_node()."""
    
    def test_remove_node(self):
        """Видаляється вузол."""
        graph = Graph()
        node = Node(url="https://example.com", depth=0)
        graph.add_node(node)
        
        result = graph.remove_node(node.node_id)
        
        assert result is True
        assert len(graph) == 0
    
    def test_remove_nonexistent_node(self):
        """Видалення неіснуючого вузла повертає False."""
        graph = Graph()
        
        result = graph.remove_node("nonexistent")
        
        assert result is False
    
    def test_remove_node_removes_edges(self):
        """Видалення вузла видаляє пов'язані ребра."""
        graph = Graph()
        node1 = Node(url="https://example.com/1", depth=0)
        node2 = Node(url="https://example.com/2", depth=1)
        graph.add_node(node1)
        graph.add_node(node2)
        
        edge = Edge(source_node_id=node1.node_id, target_node_id=node2.node_id)
        graph.add_edge(edge)
        
        assert len(graph.edges) == 1
        
        graph.remove_node(node1.node_id)
        
        assert len(graph.edges) == 0


class TestGraphCollectionOperations:
    """Тести колекційних операцій."""
    
    def test_len(self):
        """len() працює."""
        graph = Graph()
        assert len(graph) == 0
        
        graph.add_node(Node(url="https://example.com", depth=0))
        assert len(graph) == 1
    
    def test_iter(self):
        """iter() працює."""
        graph = Graph()
        urls = ["https://example.com/1", "https://example.com/2", "https://example.com/3"]
        
        for url in urls:
            graph.add_node(Node(url=url, depth=0))
        
        iterated_urls = [node.url for node in graph]
        
        assert len(iterated_urls) == 3
        for url in urls:
            assert url in iterated_urls
    
    def test_contains_url(self):
        """in оператор з URL."""
        graph = Graph()
        graph.add_node(Node(url="https://example.com", depth=0))
        
        assert "https://example.com" in graph
        assert "https://notfound.com" not in graph
    
    def test_contains_node(self):
        """in оператор з Node."""
        graph = Graph()
        node = Node(url="https://example.com", depth=0)
        graph.add_node(node)
        
        assert node in graph
    
    def test_getitem_by_url(self):
        """[] доступ за URL."""
        graph = Graph()
        node = Node(url="https://example.com", depth=0)
        graph.add_node(node)
        
        result = graph["https://example.com"]
        
        assert result is node
    
    def test_getitem_by_url_raises(self):
        """[] викидає KeyError."""
        graph = Graph()
        
        with pytest.raises(KeyError):
            _ = graph["https://notfound.com"]
    
    def test_getitem_by_index(self):
        """[] доступ за індексом."""
        graph = Graph()
        node = Node(url="https://example.com", depth=0)
        graph.add_node(node)
        
        result = graph[0]
        
        assert result.url == "https://example.com"
    
    def test_getitem_by_index_raises(self):
        """[] викидає IndexError."""
        graph = Graph()
        
        with pytest.raises(IndexError):
            _ = graph[0]


class TestGraphStatistics:
    """Тести статистики."""
    
    def test_get_stats_empty(self):
        """get_stats() для порожнього графа."""
        graph = Graph()
        stats = graph.get_stats()
        
        assert stats["total_nodes"] == 0
        assert stats["total_edges"] == 0
    
    def test_get_stats_with_nodes(self):
        """get_stats() з вузлами."""
        graph = Graph()
        node1 = Node(url="https://example.com/1", depth=0)
        node2 = Node(url="https://example.com/2", depth=1)
        graph.add_node(node1)
        graph.add_node(node2)
        
        edge = Edge(source_node_id=node1.node_id, target_node_id=node2.node_id)
        graph.add_edge(edge)
        
        stats = graph.get_stats()
        
        assert stats["total_nodes"] == 2
        assert stats["total_edges"] == 1
    
    def test_get_unscanned_nodes(self):
        """get_unscanned_nodes() працює."""
        graph = Graph()
        node1 = Node(url="https://example.com/1", depth=0)
        node2 = Node(url="https://example.com/2", depth=1)
        graph.add_node(node1)
        graph.add_node(node2)
        
        node1.mark_as_scanned()
        
        unscanned = graph.get_unscanned_nodes()
        
        assert len(unscanned) == 1
        assert unscanned[0] is node2
    
    def test_get_nodes_by_depth(self):
        """get_nodes_by_depth() працює."""
        graph = Graph()
        graph.add_node(Node(url="https://example.com/1", depth=0))
        graph.add_node(Node(url="https://example.com/2", depth=1))
        graph.add_node(Node(url="https://example.com/3", depth=1))
        graph.add_node(Node(url="https://example.com/4", depth=2))
        
        depth_0 = graph.get_nodes_by_depth(0)
        depth_1 = graph.get_nodes_by_depth(1)
        depth_2 = graph.get_nodes_by_depth(2)
        
        assert len(depth_0) == 1
        assert len(depth_1) == 2
        assert len(depth_2) == 1


class TestGraphSerialization:
    """Тести серіалізації."""
    
    def test_to_dict_empty(self):
        """to_dict() для порожнього графа."""
        graph = Graph()
        data = graph.to_dict()
        
        assert data["nodes"] == []
        assert data["edges"] == []
    
    def test_to_dict_with_data(self):
        """to_dict() з даними."""
        graph = Graph()
        node = Node(url="https://example.com", depth=0)
        graph.add_node(node)
        
        edge = Edge(source_node_id=node.node_id, target_node_id="other")
        graph.add_edge(edge)
        
        data = graph.to_dict()
        
        assert len(data["nodes"]) == 1
        assert len(data["edges"]) == 1
        assert data["nodes"][0]["url"] == "https://example.com"


class TestGraphOperations:
    """Тести арифметичних операцій."""
    
    def test_add_graphs(self):
        """Об'єднання графів (+)."""
        g1 = Graph()
        g1.add_node(Node(url="https://example.com/1", depth=0))
        
        g2 = Graph()
        g2.add_node(Node(url="https://example.com/2", depth=0))
        
        g3 = g1 + g2
        
        assert len(g3) == 2
        assert "https://example.com/1" in g3
        assert "https://example.com/2" in g3
    
    def test_sub_graphs(self):
        """Різниця графів (-)."""
        g1 = Graph()
        g1.add_node(Node(url="https://example.com/1", depth=0))
        g1.add_node(Node(url="https://example.com/2", depth=0))
        
        g2 = Graph()
        g2.add_node(Node(url="https://example.com/2", depth=0))
        
        g3 = g1 - g2
        
        assert len(g3) == 1
        assert "https://example.com/1" in g3
        assert "https://example.com/2" not in g3
    
    def test_and_graphs(self):
        """Перетин графів (&)."""
        g1 = Graph()
        g1.add_node(Node(url="https://example.com/1", depth=0))
        g1.add_node(Node(url="https://example.com/2", depth=0))
        
        g2 = Graph()
        g2.add_node(Node(url="https://example.com/2", depth=0))
        g2.add_node(Node(url="https://example.com/3", depth=0))
        
        g3 = g1 & g2
        
        assert len(g3) == 1
        assert "https://example.com/2" in g3


class TestGraphClear:
    """Тести clear()."""
    
    def test_clear(self):
        """clear() очищає граф."""
        graph = Graph()
        graph.add_node(Node(url="https://example.com/1", depth=0))
        graph.add_node(Node(url="https://example.com/2", depth=0))
        graph.add_edge(Edge(source_node_id="n1", target_node_id="n2"))
        
        graph.clear()
        
        assert len(graph) == 0
        assert len(graph.edges) == 0
        assert len(graph.url_to_node) == 0


class TestGraphCopy:
    """Тести copy()."""
    
    def test_copy(self):
        """copy() створює копію."""
        original = Graph()
        node = Node(url="https://example.com", depth=0)
        original.add_node(node)
        
        copy = original.copy()
        
        assert len(copy) == 1
        assert "https://example.com" in copy
        assert copy is not original


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
