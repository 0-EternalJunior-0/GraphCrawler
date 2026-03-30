"""
Тести для перевірки concurrency fixes в Graph.
"""

import asyncio

import pytest

from graph_crawler.domain.entities.edge import Edge
from graph_crawler.domain.entities.graph import Graph
from graph_crawler.domain.entities.node import Node

class TestGraphShardedLock:
    """Тести для шардованого Lock."""

    def test_graph_has_sharded_locks(self):
        """Перевірка що граф має шардовані locks."""
        graph = Graph()

        # Перевіряємо наявність шардованих locks
        assert hasattr(graph, '_num_shards')
        assert hasattr(graph, '_locks')
        assert len(graph._locks) == graph._num_shards
        assert graph._num_shards == 16  # default

    def test_graph_has_global_lock(self):
        """Перевірка наявності глобального lock."""
        graph = Graph()
        assert hasattr(graph, '_global_lock')

    def test_get_shard_index_deterministic(self):
        """Перевірка що shard index детерміністичний."""
        graph = Graph()
        url = "https://example.com/page1"

        idx1 = graph._get_shard_index(url)
        idx2 = graph._get_shard_index(url)

        assert idx1 == idx2
        assert 0 <= idx1 < graph._num_shards

    def test_get_shard_index_distributes_urls(self):
        """Перевірка що URLs розподіляються по шардах."""
        graph = Graph()

        # Генеруємо багато URLs
        shard_counts = dict.fromkeys(range(graph._num_shards), 0)

        for i in range(1000):
            url = f"https://example.com/page{i}"
            shard_idx = graph._get_shard_index(url)
            shard_counts[shard_idx] += 1

        # Перевіряємо що URLs розподілені (не всі в одному шарді)
        non_empty_shards = sum(1 for c in shard_counts.values() if c > 0)
        assert non_empty_shards > 10  # Більшість шардів використовуються

class TestGraphAsyncOperations:
    """Тести для async операцій."""

    @pytest.mark.asyncio
    async def test_add_node_async_thread_safe(self):
        """Перевірка thread-safety add_node_async."""
        graph = Graph()

        async def add_nodes(prefix: str, count: int):
            for i in range(count):
                node = Node(url=f"https://{prefix}.com/page{i}")
                await graph.add_node_async(node)

        # Запускаємо паралельно кілька корутин
        await asyncio.gather(
            add_nodes("site1", 100),
            add_nodes("site2", 100),
            add_nodes("site3", 100),
        )

        # Всі ноди повинні бути додані
        assert len(graph) == 300

    @pytest.mark.asyncio
    async def test_add_edge_async_thread_safe(self):
        """Перевірка thread-safety add_edge_async."""
        graph = Graph()

        # Створюємо ноди
        nodes = []
        for i in range(10):
            node = Node(url=f"https://example.com/page{i}")
            graph.add_node(node)
            nodes.append(node)

        async def add_edges(start_idx: int, count: int):
            for i in range(count):
                source = nodes[start_idx]
                target = nodes[(start_idx + i + 1) % len(nodes)]
                edge = Edge(
                    source_node_id=source.node_id,
                    target_node_id=target.node_id
                )
                await graph.add_edge_async(edge)

        # Запускаємо паралельно
        await asyncio.gather(
            add_edges(0, 5),
            add_edges(2, 5),
            add_edges(5, 5),
        )

        # Перевіряємо що edges додані
        assert len(graph.edges) == 15

    @pytest.mark.asyncio
    async def test_concurrent_add_same_url(self):
        """Перевірка що duplicate URLs обробляються коректно при concurrency."""
        graph = Graph()
        url = "https://example.com/same-page"

        async def try_add_node():
            node = Node(url=url)
            return await graph.add_node_async(node)

        # Спробуємо додати ту саму URL паралельно
        results = await asyncio.gather(*[try_add_node() for _ in range(100)])

        # Повинна бути тільки одна нода
        assert len(graph) == 1

        # Всі результати повинні повернути ту саму ноду
        first_node_id = results[0].node_id
        assert all(r.node_id == first_node_id for r in results)

class TestFindDuplicatesLSH:
    """Тести для LSH-оптимізованого find_duplicates."""

    def test_find_duplicates_performance(self):
        """Перевірка що LSH працює швидко на великих даних."""
        import time

        graph = Graph()

        # Створюємо 1000 нод з simhash
        for i in range(1000):
            node = Node(url=f"https://example.com/page{i}")
            # Симулюємо simhash - деякі схожі
            base_hash = (i // 10) * 0x1000000000000000  # Групуємо по 10
            node.simhash = format(base_hash + i, '016x')
            graph.add_node(node)

        # Вимірюємо час
        start = time.time()
        graph.find_duplicates(max_distance=3)
        elapsed = time.time() - start

        # LSH повинен працювати швидко (< 5 секунд для 1000 нод на будь-якій системі)
        # Це все одно значно краще ніж O(n²) який займав би > 30 секунд
        assert elapsed < 5.0, f"find_duplicates took {elapsed:.2f}s, expected < 5s"

    def test_find_duplicates_handles_string_simhash(self):
        """Перевірка що find_duplicates працює з string simhash."""
        graph = Graph()

        node1 = Node(url="https://example.com/page1")
        node1.simhash = "0000000000000001"  # string hex

        node2 = Node(url="https://example.com/page2")
        node2.simhash = "0000000000000002"  # близький до node1

        graph.add_node(node1)
        graph.add_node(node2)

        duplicates = graph.find_duplicates(max_distance=3)

        # Повинні бути знайдені як дублікати
        assert len(duplicates) == 1
        assert len(duplicates[0]) == 2

class TestSchedulerAsyncOperations:
    """Тести для async операцій Scheduler."""

    @pytest.mark.asyncio
    async def test_scheduler_has_async_lock(self):
        """Перевірка що scheduler має async lock."""
        from graph_crawler.application.use_cases.crawling.scheduler import CrawlScheduler

        scheduler = CrawlScheduler()
        assert hasattr(scheduler, '_seen_urls_lock')

    @pytest.mark.asyncio
    async def test_add_node_async_thread_safe(self):
        """Перевірка thread-safety add_node_async в scheduler."""
        from graph_crawler.application.use_cases.crawling.scheduler import CrawlScheduler

        scheduler = CrawlScheduler()

        async def add_nodes(prefix: str, count: int):
            for i in range(count):
                node = Node(url=f"https://{prefix}.com/page{i}")
                await scheduler.add_node_async(node)

        # Запускаємо паралельно
        await asyncio.gather(
            add_nodes("site1", 50),
            add_nodes("site2", 50),
        )

        # Всі ноди повинні бути додані
        assert scheduler.size() == 100

class TestLinkProcessorAsync:
    """Тести для async операцій LinkProcessor."""

    def test_link_processor_has_async_method(self):
        """Перевірка наявності async методу."""
        from graph_crawler.application.use_cases.crawling.link_processor import LinkProcessor

        # Перевіряємо що метод існує
        assert hasattr(LinkProcessor, '_process_single_link_async')

        import inspect
        method = LinkProcessor._process_single_link_async
        assert inspect.iscoroutinefunction(method)
