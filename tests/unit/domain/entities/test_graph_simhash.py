"""
Тести для SimHash функціональності в Graph (пошук подібних/дублюючих нод).
"""

import pytest

from graph_crawler.domain.entities.graph import Graph
from graph_crawler.domain.entities.node import Node
from graph_crawler.domain.value_objects.lifecycle import NodeLifecycle

def create_node_with_simhash(url: str, simhash: str, depth: int = 0) -> Node:
    """Helper для створення ноди з simhash."""
    node = Node(url=url, depth=depth)
    node.lifecycle_stage = NodeLifecycle.HTML_STAGE
    node.simhash = simhash
    return node

class TestFindSimilarNodes:
    """Тести для find_similar_nodes()."""

    def test_find_similar_nodes_returns_similar(self):
        """find_similar_nodes() знаходить схожі ноди."""
        graph = Graph()

        # Додаємо ноди зі схожими simhash
        node1 = create_node_with_simhash("https://example.com/1", "0000000000000000")
        node2 = create_node_with_simhash("https://example.com/2", "0000000000000001")  # distance=1
        node3 = create_node_with_simhash("https://example.com/3", "0000000000000003")  # distance=2
        node4 = create_node_with_simhash("https://example.com/4", "ffffffffffffffff")  # distance=64

        graph.add_node(node1)
        graph.add_node(node2)
        graph.add_node(node3)
        graph.add_node(node4)

        # Шукаємо схожі до node1
        similar = graph.find_similar_nodes(node1, max_distance=5)

        assert len(similar) == 2  # node2 і node3, але не node4
        assert similar[0][0].url == "https://example.com/2"  # distance=1
        assert similar[0][1] == 1
        assert similar[1][0].url == "https://example.com/3"  # distance=2
        assert similar[1][1] == 2

    def test_find_similar_nodes_excludes_self(self):
        """find_similar_nodes() не включає саму ноду."""
        graph = Graph()

        node1 = create_node_with_simhash("https://example.com/1", "abc123def456789a")
        graph.add_node(node1)

        similar = graph.find_similar_nodes(node1, max_distance=100)

        assert len(similar) == 0

    def test_find_similar_nodes_no_simhash_warning(self):
        """find_similar_nodes() повертає пустий список для ноди без simhash."""
        graph = Graph()

        node1 = Node(url="https://example.com/1", depth=0)  # без simhash
        graph.add_node(node1)

        similar = graph.find_similar_nodes(node1)

        assert similar == []

    def test_find_similar_nodes_with_limit(self):
        """find_similar_nodes() обмежує кількість результатів."""
        graph = Graph()

        node1 = create_node_with_simhash("https://example.com/1", "0000000000000000")

        for i in range(10):
            node = create_node_with_simhash(f"https://example.com/{i+2}", f"000000000000000{i}")
            graph.add_node(node)

        graph.add_node(node1)

        similar = graph.find_similar_nodes(node1, max_distance=100, limit=3)

        assert len(similar) == 3

    def test_find_similar_nodes_sorted_by_distance(self):
        """find_similar_nodes() сортує за distance."""
        graph = Graph()

        node1 = create_node_with_simhash("https://example.com/1", "0000000000000000")
        node2 = create_node_with_simhash("https://example.com/2", "000000000000000f")  # distance=4
        node3 = create_node_with_simhash("https://example.com/3", "0000000000000001")  # distance=1
        node4 = create_node_with_simhash("https://example.com/4", "0000000000000007")  # distance=3

        graph.add_node(node1)
        graph.add_node(node2)
        graph.add_node(node3)
        graph.add_node(node4)

        similar = graph.find_similar_nodes(node1, max_distance=10)

        # Перевіряємо порядок
        assert similar[0][1] == 1  # node3
        assert similar[1][1] == 3  # node4
        assert similar[2][1] == 4  # node2

class TestFindDuplicates:
    """Тести для find_duplicates()."""

    def test_find_duplicates_groups_similar(self):
        """find_duplicates() групує схожі ноди."""
        graph = Graph()

        # Група 1: дуже схожі
        node1 = create_node_with_simhash("https://example.com/1", "0000000000000000")
        node2 = create_node_with_simhash("https://example.com/2", "0000000000000001")

        # Група 2: інші схожі між собою
        node3 = create_node_with_simhash("https://example.com/3", "ffffffffffffffff")
        node4 = create_node_with_simhash("https://example.com/4", "fffffffffffffffe")

        # Унікальна нода (не в групі)
        node5 = create_node_with_simhash("https://example.com/5", "5555555555555555")

        for node in [node1, node2, node3, node4, node5]:
            graph.add_node(node)

        duplicates = graph.find_duplicates(max_distance=3)

        assert len(duplicates) == 2  # 2 групи

    def test_find_duplicates_no_duplicates(self):
        """find_duplicates() повертає пустий список якщо немає дублікатів."""
        graph = Graph()

        # Всі ноди дуже різні
        node1 = create_node_with_simhash("https://example.com/1", "0000000000000000")
        node2 = create_node_with_simhash("https://example.com/2", "ffffffffffffffff")
        node3 = create_node_with_simhash("https://example.com/3", "5555555555555555")

        for node in [node1, node2, node3]:
            graph.add_node(node)

        duplicates = graph.find_duplicates(max_distance=3)

        assert len(duplicates) == 0

    def test_find_duplicates_sorted_by_size(self):
        """find_duplicates() сортує групи за розміром."""
        graph = Graph()

        # Маленька група (2 ноди)
        node1 = create_node_with_simhash("https://example.com/1", "aaaaaaaaaaaaaaaa")
        node2 = create_node_with_simhash("https://example.com/2", "aaaaaaaaaaaaaaab")

        # Велика група (3 ноди)
        node3 = create_node_with_simhash("https://example.com/3", "0000000000000000")
        node4 = create_node_with_simhash("https://example.com/4", "0000000000000001")
        node5 = create_node_with_simhash("https://example.com/5", "0000000000000002")

        for node in [node1, node2, node3, node4, node5]:
            graph.add_node(node)

        duplicates = graph.find_duplicates(max_distance=3)

        # Велика група повинна бути першою
        assert len(duplicates[0]) >= len(duplicates[1])

    def test_find_duplicates_empty_graph(self):
        """find_duplicates() працює з порожнім графом."""
        graph = Graph()

        duplicates = graph.find_duplicates()

        assert duplicates == []

    def test_find_duplicates_nodes_without_simhash(self):
        """find_duplicates() ігнорує ноди без simhash."""
        graph = Graph()

        node1 = Node(url="https://example.com/1", depth=0)  # без simhash
        node2 = Node(url="https://example.com/2", depth=0)  # без simhash

        graph.add_node(node1)
        graph.add_node(node2)

        duplicates = graph.find_duplicates()

        assert duplicates == []

class TestGetDuplicateStats:
    """Тести для get_duplicate_stats()."""

    def test_get_duplicate_stats_returns_dict(self):
        """get_duplicate_stats() повертає словник зі статистикою."""
        graph = Graph()

        node1 = create_node_with_simhash("https://example.com/1", "0000000000000000")
        node2 = create_node_with_simhash("https://example.com/2", "0000000000000001")
        node3 = create_node_with_simhash("https://example.com/3", "ffffffffffffffff")

        for node in [node1, node2, node3]:
            graph.add_node(node)

        stats = graph.get_duplicate_stats(max_distance=3)

        assert "total_nodes" in stats
        assert "nodes_with_simhash" in stats
        assert "duplicate_groups" in stats
        assert "total_duplicates" in stats
        assert "largest_group_size" in stats
        assert "duplicate_rate" in stats

    def test_get_duplicate_stats_correct_values(self):
        """get_duplicate_stats() повертає правильні значення."""
        graph = Graph()

        # 2 дублікати
        node1 = create_node_with_simhash("https://example.com/1", "0000000000000000")
        node2 = create_node_with_simhash("https://example.com/2", "0000000000000001")
        # 1 унікальна
        node3 = create_node_with_simhash("https://example.com/3", "ffffffffffffffff")

        for node in [node1, node2, node3]:
            graph.add_node(node)

        stats = graph.get_duplicate_stats(max_distance=3)

        assert stats["total_nodes"] == 3
        assert stats["nodes_with_simhash"] == 3
        assert stats["duplicate_groups"] == 1
        assert stats["total_duplicates"] == 2
        assert stats["largest_group_size"] == 2
        # 2/3 = 66.67%
        assert stats["duplicate_rate"] == pytest.approx(66.67, rel=0.1)

    def test_get_duplicate_stats_empty_graph(self):
        """get_duplicate_stats() працює з порожнім графом."""
        graph = Graph()

        stats = graph.get_duplicate_stats()

        assert stats["total_nodes"] == 0
        assert stats["duplicate_groups"] == 0
        assert stats["duplicate_rate"] == 0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
