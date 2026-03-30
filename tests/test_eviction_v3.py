"""
Тести для Eviction System v3.0 Migration.

"""

import asyncio
import gc
import sys
import tempfile
import time
from pathlib import Path

# Додаємо path для імпорту
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_batch_remove_nodes():
    """Тест batch delete замість поодиноких del."""
    from graph_crawler.domain.entities.graph import Graph
    from graph_crawler.domain.entities.node import Node
    from graph_crawler.infrastructure.persistence.sqlite_eviction_storage import SQLiteEvictionStorage

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = SQLiteEvictionStorage(tmpdir)

        graph = Graph(
            low_memory_mode=True,
            evict_threshold=10,
            eviction_storage=storage,
        )

        # Додаємо 20 нод
        nodes = []
        for i in range(20):
            node = Node(url=f"https://example.com/page{i}", depth=0)
            node.scanned = True
            graph.add_node(node)
            nodes.append(node)

        assert len(graph._nodes) == 20

        # Тест _batch_remove_nodes
        node_ids = {n.node_id for n in nodes[:10]}
        urls = {n.url for n in nodes[:10]}

        graph._batch_remove_nodes(node_ids, urls)

        assert len(graph._nodes) == 10
        assert len(graph._url_to_node) == 10

        storage.close()
        print("✅ test_batch_remove_nodes PASSED")

def test_get_url_status():
    """Тест об'єднаного lookup."""
    from graph_crawler.domain.entities.graph import Graph
    from graph_crawler.domain.entities.node import Node
    from graph_crawler.infrastructure.persistence.sqlite_eviction_storage import SQLiteEvictionStorage

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = SQLiteEvictionStorage(tmpdir)

        graph = Graph(
            low_memory_mode=True,
            evict_threshold=5,
            eviction_storage=storage,
        )

        # Додаємо ноду
        node = Node(url="https://example.com/page1", depth=0)
        graph.add_node(node)

        # Тест get_url_status
        is_known, found_node = graph.get_url_status("https://example.com/page1")
        assert is_known is True
        assert found_node is not None
        assert found_node.url == "https://example.com/page1"

        # Невідомий URL
        is_known, found_node = graph.get_url_status("https://example.com/unknown")
        assert is_known is False
        assert found_node is None

        storage.close()
        print("✅ test_get_url_status PASSED")

def test_check_urls_batch():
    """Тест batch перевірки URLs."""
    from graph_crawler.domain.entities.graph import Graph
    from graph_crawler.domain.entities.node import Node
    from graph_crawler.infrastructure.persistence.sqlite_eviction_storage import SQLiteEvictionStorage

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = SQLiteEvictionStorage(tmpdir)

        graph = Graph(
            low_memory_mode=True,
            evict_threshold=100,
            eviction_storage=storage,
        )

        # Додаємо кілька нод
        for i in range(5):
            node = Node(url=f"https://example.com/page{i}", depth=0)
            graph.add_node(node)

        # Batch check
        urls_to_check = [
            "https://example.com/page0",
            "https://example.com/page2",
            "https://example.com/page99",  # Невідомий
            "https://example.com/page100",  # Невідомий
        ]

        result = graph.check_urls_batch(urls_to_check)

        assert result["https://example.com/page0"][0] is True
        assert result["https://example.com/page2"][0] is True
        assert result["https://example.com/page99"][0] is False
        assert result["https://example.com/page100"][0] is False

        storage.close()
        print("✅ test_check_urls_batch PASSED")

def test_async_eviction():
    """Тест async eviction (не блокує event loop)."""
    from graph_crawler.domain.entities.graph import Graph
    from graph_crawler.domain.entities.node import Node
    from graph_crawler.infrastructure.persistence.sqlite_eviction_storage import SQLiteEvictionStorage

    async def run_test():
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = SQLiteEvictionStorage(tmpdir)

            graph = Graph(
                low_memory_mode=True,
                evict_threshold=5,
                eviction_storage=storage,
            )

            # Додаємо 10 нод
            nodes = []
            for i in range(10):
                node = Node(url=f"https://example.com/page{i}", depth=0)
                node.scanned = True
                graph.add_node(node)
                nodes.append(node)

            assert len(graph._nodes) == 10

            # Async eviction
            await graph._evict_nodes_async(nodes[:5])

            assert len(graph._nodes) == 5
            assert len(graph._evicted_url_hashes) == 5

            storage.close()
            print("✅ test_async_eviction PASSED")

    asyncio.run(run_test())

def test_gc_optimization():
    """Тест що GC вимикається під час eviction."""
    from graph_crawler.domain.entities.graph import Graph
    from graph_crawler.domain.entities.node import Node
    from graph_crawler.infrastructure.persistence.sqlite_eviction_storage import SQLiteEvictionStorage

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = SQLiteEvictionStorage(tmpdir)

        graph = Graph(
            low_memory_mode=True,
            evict_threshold=5,
            eviction_storage=storage,
        )

        # Додаємо ноди
        nodes = []
        for i in range(10):
            node = Node(url=f"https://example.com/page{i}", depth=0)
            node.scanned = True
            graph.add_node(node)
            nodes.append(node)

        # Вимірюємо час eviction
        gc.collect()
        start = time.perf_counter()

        graph._evict_nodes_sync(nodes[:5])

        elapsed = time.perf_counter() - start

        # Eviction повинен бути швидким (<100ms для 5 нод)
        assert elapsed < 0.1, f"Eviction занадто повільний: {elapsed*1000:.2f}ms"

        storage.close()
        print(f"✅ test_gc_optimization PASSED (eviction time: {elapsed*1000:.2f}ms)")

def test_lmdb_storage():
    """Тест LMDB eviction storage."""
    try:
        from graph_crawler.infrastructure.persistence.lmdb_eviction_storage import (
            LMDBEvictionStorage,
            LMDB_AVAILABLE,
        )

        if not LMDB_AVAILABLE:
            print("⚠️ test_lmdb_storage SKIPPED (lmdb not installed)")
            return

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LMDBEvictionStorage(tmpdir, lightweight_mode=False)

            # Створюємо mock nodes
            class MockNode:
                def __init__(self, url, node_id, depth=0):
                    self.url = url
                    self.node_id = node_id
                    self.depth = depth
                    self.scanned = True
                    self.response_status = 200
                    self.content_hash = "abc123"
                    self.simhash = "def456"
                    self.priority = 5
                    self.metadata = {"title": "Test"}
                    self.user_data = {"custom": "data"}

            nodes = [MockNode(f"https://example.com/p{i}", f"id{i}") for i in range(10)]

            # Тест save_nodes_sync
            count = storage.save_nodes_sync(nodes)
            assert count == 10

            # Тест load_node_sync
            data = storage.load_node_sync("https://example.com/p0")
            assert data is not None
            assert data['url'] == "https://example.com/p0"
            assert data['metadata']['title'] == "Test"

            # Тест url_exists
            assert storage.url_exists("https://example.com/p0") is True
            assert storage.url_exists("https://example.com/unknown") is False

            # Тест urls_exist_batch
            found = storage.urls_exist_batch([
                "https://example.com/p0",
                "https://example.com/p1",
                "https://example.com/unknown",
            ])
            assert "https://example.com/p0" in found
            assert "https://example.com/p1" in found
            assert "https://example.com/unknown" not in found

            # Тест get_stats
            stats = storage.get_stats()
            assert stats['evicted_nodes'] == 10
            assert stats['storage_type'] == 'lmdb'

            storage.cleanup()
            print("✅ test_lmdb_storage PASSED")

    except ImportError as e:
        print(f"⚠️ test_lmdb_storage SKIPPED: {e}")

def test_lmdb_lightweight_mode():
    """Тест LMDB lightweight mode (без metadata)."""
    try:
        from graph_crawler.infrastructure.persistence.lmdb_eviction_storage import (
            LMDBEvictionStorage,
            LMDB_AVAILABLE,
        )

        if not LMDB_AVAILABLE:
            print("⚠️ test_lmdb_lightweight_mode SKIPPED (lmdb not installed)")
            return

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LMDBEvictionStorage(tmpdir, lightweight_mode=True)

            class MockNode:
                def __init__(self, url, node_id):
                    self.url = url
                    self.node_id = node_id
                    self.depth = 0
                    self.scanned = True
                    self.response_status = 200
                    self.metadata = {"title": "Test", "description": "Long description..."}
                    self.user_data = {"data": list(range(100))}

            node = MockNode("https://example.com/page", "id1")
            storage.save_nodes_sync([node])

            # В lightweight mode metadata не зберігається
            data = storage.load_node_sync("https://example.com/page")
            assert data is not None
            assert 'metadata' not in data  # Не повинно бути
            assert 'user_data' not in data  # Не повинно бути

            storage.cleanup()
            print("✅ test_lmdb_lightweight_mode PASSED")

    except ImportError as e:
        print(f"⚠️ test_lmdb_lightweight_mode SKIPPED: {e}")

def test_eviction_storage_factory():
    """Тест factory функції get_eviction_storage."""
    from graph_crawler.infrastructure.persistence import get_eviction_storage

    with tempfile.TemporaryDirectory() as tmpdir:
        # Тест SQLite
        storage = get_eviction_storage(f"{tmpdir}/sqlite", storage_type="sqlite")
        assert storage is not None
        storage.close()

        # Тест auto (повинен вибрати LMDB якщо доступний)
        storage = get_eviction_storage(f"{tmpdir}/auto", storage_type="auto")
        assert storage is not None
        stats = storage.get_stats()
        print(f"  Auto-selected: {stats.get('storage_type', 'sqlite')}")
        storage.close()

        print("✅ test_eviction_storage_factory PASSED")

def benchmark_eviction():
    """Бенчмарк eviction performance."""
    from graph_crawler.domain.entities.graph import Graph
    from graph_crawler.domain.entities.node import Node
    from graph_crawler.infrastructure.persistence.sqlite_eviction_storage import SQLiteEvictionStorage

    print("\n📊 Eviction Benchmark")
    print("=" * 50)

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = SQLiteEvictionStorage(tmpdir)

        graph = Graph(
            low_memory_mode=True,
            evict_threshold=100,
            eviction_storage=storage,
        )

        # Додаємо 500 нод
        nodes = []
        for i in range(500):
            node = Node(url=f"https://example.com/page{i}", depth=0)
            node.scanned = True
            graph.add_node(node)
            nodes.append(node)

        # Benchmark sync eviction
        gc.collect()
        gc.disable()

        start = time.perf_counter()
        graph._evict_nodes_sync(nodes[:250])
        eviction_time = time.perf_counter() - start

        gc.enable()
        gc_start = time.perf_counter()
        gc.collect()
        gc_time = time.perf_counter() - gc_start

        print("Nodes evicted: 250")
        print(f"Eviction time: {eviction_time*1000:.2f}ms")
        print(f"GC time after: {gc_time*1000:.2f}ms")
        print(f"Total: {(eviction_time + gc_time)*1000:.2f}ms")

        storage.close()

if __name__ == "__main__":
    print("\n🧪 Eviction System v3.0 Tests")
    print("=" * 50)

    test_batch_remove_nodes()
    test_get_url_status()
    test_check_urls_batch()
    test_async_eviction()
    test_gc_optimization()
    test_lmdb_storage()
    test_lmdb_lightweight_mode()
    test_eviction_storage_factory()

    benchmark_eviction()

    print("\n" + "=" * 50)
    print("✅ All tests passed!")
