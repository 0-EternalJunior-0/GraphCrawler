"""
Unit tests для Low-Memory Graph режиму (eviction policy).

Тестує:
1. Ініціалізацію Graph з low_memory_mode
2. Автоматичний eviction при перевищенні threshold
3. Lazy loading при get_node_by_url()
4. Коректність даних після eviction/load
"""

import tempfile
import pytest
from pathlib import Path

from graph_crawler.domain.entities.graph import Graph
from graph_crawler.domain.entities.node import Node

class TestLowMemoryGraph:
    """Тести для low-memory режиму Graph."""

    def test_init_low_memory_mode(self, tmp_path):
        """Тест ініціалізації Graph з low_memory_mode."""
        from graph_crawler.infrastructure.persistence.sqlite_eviction_storage import (
            SQLiteEvictionStorage
        )
        eviction_storage = SQLiteEvictionStorage(str(tmp_path / "eviction"))

        graph = Graph(
            low_memory_mode=True,
            evict_threshold=100,
            eviction_storage=eviction_storage
        )

        assert graph._low_memory_mode is True
        assert graph._evict_threshold == 100
        assert graph._eviction_storage is not None
        assert graph.get_evicted_urls_count() == 0

        graph.close_eviction_storage()

    def test_init_without_storage_path_raises(self):
        """Тест що без storage_path виникає помилка."""
        with pytest.raises(ValueError, match="eviction_storage"):
            Graph(low_memory_mode=True)

    def test_add_nodes_triggers_eviction(self, tmp_path):
        """Тест що eviction спрацьовує при виклику _maybe_evict()."""
        from graph_crawler.infrastructure.persistence.sqlite_eviction_storage import (
            SQLiteEvictionStorage
        )

        threshold = 50
        eviction_storage = SQLiteEvictionStorage(str(tmp_path / "eviction"))

        graph = Graph(
            low_memory_mode=True,
            evict_threshold=threshold,
            evict_batch_size=20,
            eviction_storage=eviction_storage
        )

        # Додаємо більше ніж threshold * 2 нод (trigger для eviction)
        num_nodes = threshold * 3  # 150 нод
        for i in range(num_nodes):
            node = Node(
                url=f"https://example.com/page{i}",
                depth=0,
            )
            node.scanned = True  # Робимо scanned щоб могли evict
            graph.add_node(node)

        # Викликаємо eviction вручну (імітуємо виклик з CrawlCoordinator)
        graph._maybe_evict()

        # Перевіряємо що eviction відбувся
        ram_nodes = len(graph._nodes)
        disk_nodes = graph.get_evicted_urls_count()
        total_nodes = graph.get_total_nodes_count()

        print(f"RAM: {ram_nodes}, Disk: {disk_nodes}, Total: {total_nodes}")

        # Має бути eviction - не всі ноди в RAM
        assert total_nodes == num_nodes
        assert disk_nodes > 0, "Eviction should have happened"
        # Після eviction RAM має бути значно менше ніж всього нод
        assert ram_nodes < num_nodes, f"RAM {ram_nodes} should be < total {num_nodes}"

        graph.close_eviction_storage()

    def test_lazy_loading_from_disk(self, tmp_path):
        """Тест lazy loading - завантаження ноди з диска."""
        from graph_crawler.infrastructure.persistence.sqlite_eviction_storage import (
            SQLiteEvictionStorage
        )

        eviction_storage = SQLiteEvictionStorage(str(tmp_path / "eviction"))
        graph = Graph(
            low_memory_mode=True,
            evict_threshold=10,
            evict_batch_size=5,
            eviction_storage=eviction_storage
        )

        test_url = "https://example.com/test-page"

        # Створюємо ноду і примусово evict
        node = Node(
            url=test_url,
            depth=0,
        )
        node.scanned = True
        node.metadata = {"title": "Test Page"}
        node.user_data = {"custom": "data"}

        # Спочатку додаємо щоб отримати node_id
        graph.add_node(node)
        node_id = node.node_id

        # Примусово evict - зберігаємо на диск і видаляємо з RAM
        graph._eviction_storage.save_nodes_sync([node])
        del graph._nodes[node_id]
        del graph._url_to_node[test_url]
        graph._evicted_url_hashes.add(hash(test_url))

        # Перевіряємо що ноди немає в RAM
        assert test_url not in graph._url_to_node
        assert graph._is_url_evicted(test_url)

        # Lazy loading через get_node_by_url
        loaded_node = graph.get_node_by_url(test_url)

        assert loaded_node is not None, f"Node should be loaded from disk for URL: {test_url}"
        assert loaded_node.url == test_url
        assert loaded_node.scanned is True
        assert loaded_node.metadata.get("title") == "Test Page"
        assert loaded_node.user_data.get("custom") == "data"

        # Тепер нода має бути в RAM
        assert test_url in graph._url_to_node
        assert not graph._is_url_evicted(test_url)

        graph.close_eviction_storage()

    def test_is_url_known(self, tmp_path):
        """Тест перевірки is_url_known для RAM та disk."""
        from graph_crawler.infrastructure.persistence.sqlite_eviction_storage import (
            SQLiteEvictionStorage
        )

        eviction_storage = SQLiteEvictionStorage(str(tmp_path / "eviction"))
        graph = Graph(
            low_memory_mode=True,
            evict_threshold=100,
            eviction_storage=eviction_storage
        )

        # Ноді в RAM
        node_ram = Node(url="https://example.com/ram-page", depth=0)
        graph.add_node(node_ram)

        # Симулюємо ноду на диску
        graph._evicted_url_hashes.add(hash("https://example.com/disk-page"))

        # Перевірки
        assert graph.is_url_known("https://example.com/ram-page") is True
        assert graph.is_url_known("https://example.com/disk-page") is True
        assert graph.is_url_known("https://example.com/unknown") is False

        graph.close_eviction_storage()

    def test_get_total_nodes_count(self, tmp_path):
        """Тест підрахунку загальної кількості нод."""
        from graph_crawler.infrastructure.persistence.sqlite_eviction_storage import (
            SQLiteEvictionStorage
        )

        eviction_storage = SQLiteEvictionStorage(str(tmp_path / "eviction"))
        graph = Graph(
            low_memory_mode=True,
            evict_threshold=100,
            eviction_storage=eviction_storage
        )

        # Додаємо ноди в RAM
        for i in range(5):
            graph.add_node(Node(url=f"https://example.com/ram{i}", depth=0))

        # Симулюємо ноди на диску
        for i in range(3):
            graph._evicted_url_hashes.add(hash(f"https://example.com/disk{i}"))

        assert graph.get_total_nodes_count() == 8
        assert len(graph._nodes) == 5
        assert graph.get_evicted_urls_count() == 3

        graph.close_eviction_storage()

    def test_load_all_from_disk(self, tmp_path):
        """Тест завантаження всіх нод з диска."""
        from graph_crawler.infrastructure.persistence.sqlite_eviction_storage import (
            SQLiteEvictionStorage
        )

        eviction_storage = SQLiteEvictionStorage(str(tmp_path / "eviction"))
        graph = Graph(
            low_memory_mode=True,
            evict_threshold=100,
            eviction_storage=eviction_storage
        )

        # Створюємо та evict ноди
        for i in range(5):
            node = Node(url=f"https://example.com/page{i}", depth=0)
            node.scanned = True
            graph._eviction_storage.save_nodes_sync([node])
            graph._evicted_url_hashes.add(hash(node.url))

        assert graph.get_evicted_urls_count() == 5
        assert len(graph._nodes) == 0

        # Завантажуємо всі з диска
        loaded = graph.load_all_from_disk()

        assert loaded == 5
        assert graph.get_evicted_urls_count() == 0
        assert len(graph._nodes) == 5

        graph.close_eviction_storage()

    def test_stats_include_eviction_info(self, tmp_path):
        """Тест що статистика включає інформацію про eviction."""
        from graph_crawler.infrastructure.persistence.sqlite_eviction_storage import (
            SQLiteEvictionStorage
        )

        eviction_storage = SQLiteEvictionStorage(str(tmp_path / "eviction"))
        graph = Graph(
            low_memory_mode=True,
            evict_threshold=100,
            eviction_storage=eviction_storage
        )

        # Додаємо ноди
        for i in range(10):
            graph.add_node(Node(url=f"https://example.com/page{i}", depth=0))

        # Симулюємо eviction
        graph._evicted_url_hashes.add(hash("https://example.com/evicted1"))
        graph._evicted_url_hashes.add(hash("https://example.com/evicted2"))

        stats = graph.get_stats()

        assert "evicted_to_disk" in stats
        assert stats["evicted_to_disk"] == 2
        assert "total_nodes_including_evicted" in stats
        assert stats["total_nodes_including_evicted"] == 12

        graph.close_eviction_storage()

    def test_backward_compatibility(self):
        """Тест що Graph без low_memory_mode працює як раніше."""
        graph = Graph()

        assert graph._low_memory_mode is False
        assert graph._eviction_storage is None

        # Додаємо ноди
        for i in range(100):
            graph.add_node(Node(url=f"https://example.com/page{i}", depth=0))

        # Всі ноди мають бути в RAM
        assert len(graph._nodes) == 100
        assert graph.get_evicted_urls_count() == 0

        # get_node_by_url працює
        node = graph.get_node_by_url("https://example.com/page50")
        assert node is not None

class TestSQLiteEvictionStorage:
    """Тести для SQLiteEvictionStorage."""

    def test_save_and_load_node(self, tmp_path):
        """Тест збереження та завантаження ноди."""
        from graph_crawler.infrastructure.persistence.sqlite_eviction_storage import (
            SQLiteEvictionStorage
        )

        storage = SQLiteEvictionStorage(str(tmp_path / "eviction"))

        node = Node(
            url="https://example.com/test",
            depth=2,
        )
        node.scanned = True
        node.response_status = 200
        node.metadata = {"title": "Test"}
        node.user_data = {"key": "value"}

        # Save
        storage.save_nodes_sync([node])

        # Load
        loaded = storage.load_node_sync("https://example.com/test")

        assert loaded is not None
        assert loaded["url"] == "https://example.com/test"
        assert loaded["depth"] == 2
        assert loaded["scanned"] is True
        assert loaded["response_status"] == 200
        assert loaded["metadata"]["title"] == "Test"
        assert loaded["user_data"]["key"] == "value"

        storage.close()

    def test_batch_operations(self, tmp_path):
        """Тест batch операцій."""
        from graph_crawler.infrastructure.persistence.sqlite_eviction_storage import (
            SQLiteEvictionStorage
        )

        storage = SQLiteEvictionStorage(str(tmp_path / "eviction"))

        # Batch save
        nodes = [
            Node(url=f"https://example.com/page{i}", depth=i % 3)
            for i in range(100)
        ]
        for n in nodes:
            n.scanned = True

        saved = storage.save_nodes_sync(nodes)
        assert saved == 100

        # Batch load
        urls = [f"https://example.com/page{i}" for i in range(50)]
        loaded = storage.load_nodes_batch_sync(urls)
        assert len(loaded) == 50

        # Stats
        stats = storage.get_stats()
        assert stats["evicted_nodes"] == 100

        storage.close()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
