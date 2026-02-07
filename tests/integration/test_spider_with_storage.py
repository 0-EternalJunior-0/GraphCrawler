"""Integration tests для Spider зі storage.

Тести перевіряють роботу Spider з різними типами storage (memory, JSON, SQLite).
"""

import pytest
import asyncio
from pathlib import Path
from graph_crawler.application.use_cases.crawling.spider import GraphSpider
from graph_crawler.domain.value_objects.configs import CrawlerConfig
from graph_crawler.infrastructure.transport import HTTPDriver
from graph_crawler.infrastructure.persistence import (
    MemoryStorage, JSONStorage, SQLiteStorage
)
from graph_crawler.domain.entities.graph import Graph


@pytest.mark.integration
@pytest.mark.asyncio
class TestSpiderWithMemoryStorage:
    """Тести Spider з Memory Storage."""
    
    async def test_spider_with_memory_storage_basic(self):
        """Spider працює з memory storage."""
        config = CrawlerConfig(
            url="https://books.toscrape.com/",
            max_depth=0,
            max_pages=1
        )
        driver = HTTPDriver()
        storage = MemoryStorage()
        spider = GraphSpider(config=config, driver=driver, storage=storage)
        
        graph = await spider.crawl()
        
        assert isinstance(graph, Graph)
        # Перевіряємо що scanned тільки 1 node (root)
        scanned_nodes = [n for n in graph.nodes.values() if n.scanned]
        assert len(scanned_nodes) == 1
    
    async def test_spider_saves_to_memory_storage(self):
        """Spider зберігає дані в memory storage."""
        config = CrawlerConfig(
            url="https://books.toscrape.com/",
            max_depth=1,
            max_pages=5
        )
        driver = HTTPDriver()
        storage = MemoryStorage()
        spider = GraphSpider(config=config, driver=driver, storage=storage)
        
        graph = await spider.crawl()
        
        # Зберігаємо граф
        await storage.save_graph(graph)
        
        # Завантажуємо назад
        loaded_graph = await storage.load_graph()
        
        assert loaded_graph is not None
        assert len(loaded_graph.nodes) == len(graph.nodes)
    
    async def test_spider_memory_storage_isolated(self):
        """Memory storage ізольовані між Spider."""
        config1 = CrawlerConfig(
            url="https://books.toscrape.com/",
            max_depth=0,
            max_pages=1
        )
        config2 = CrawlerConfig(
            url="https://quotes.toscrape.com/",
            max_depth=0,
            max_pages=1
        )
        
        storage1 = MemoryStorage()
        storage2 = MemoryStorage()
        
        spider1 = GraphSpider(config=config1, driver=HTTPDriver(), storage=storage1)
        spider2 = GraphSpider(config=config2, driver=HTTPDriver(), storage=storage2)
        
        graph1 = await spider1.crawl()
        graph2 = await spider2.crawl()
        
        await storage1.save_graph(graph1)
        await storage2.save_graph(graph2)
        
        # Кожен storage містить свої дані
        loaded1 = await storage1.load_graph()
        loaded2 = await storage2.load_graph()
        
        urls1 = [n.url for n in loaded1.nodes.values()]
        urls2 = [n.url for n in loaded2.nodes.values()]
        
        assert urls1 != urls2


@pytest.mark.integration
@pytest.mark.asyncio
class TestSpiderWithJSONStorage:
    """Тести Spider з JSON Storage."""
    
    async def test_spider_with_json_storage_basic(self, tmp_path):
        """Spider працює з JSON storage."""
        storage_dir = tmp_path / "json_storage"
        storage_dir.mkdir()
        
        config = CrawlerConfig(
            url="https://books.toscrape.com/",
            max_depth=0,
            max_pages=1
        )
        driver = HTTPDriver()
        storage = JSONStorage(storage_dir=str(storage_dir))
        spider = GraphSpider(config=config, driver=driver, storage=storage)
        
        graph = await spider.crawl()
        
        # Перевіряємо що scanned тільки 1 node
        scanned_nodes = [n for n in graph.nodes.values() if n.scanned]
        assert len(scanned_nodes) == 1
    
    async def test_spider_saves_to_json_storage(self, tmp_path):
        """Spider зберігає дані в JSON файли."""
        storage_dir = tmp_path / "json_storage"
        storage_dir.mkdir()
        
        config = CrawlerConfig(
            url="https://books.toscrape.com/",
            max_depth=1,
            max_pages=5
        )
        driver = HTTPDriver()
        storage = JSONStorage(storage_dir=str(storage_dir))
        spider = GraphSpider(config=config, driver=driver, storage=storage)
        
        graph = await spider.crawl()
        await storage.save_graph(graph)
        
        # Перевіряємо що JSON файли створені
        json_files = list(storage_dir.glob("*.json"))
        assert len(json_files) > 0
    
    async def test_spider_loads_from_json_storage(self, tmp_path):
        """Spider завантажує дані з JSON storage."""
        storage_dir = tmp_path / "json_storage"
        storage_dir.mkdir()
        
        config = CrawlerConfig(
            url="https://books.toscrape.com/",
            max_depth=1,
            max_pages=5
        )
        driver = HTTPDriver()
        storage = JSONStorage(storage_dir=str(storage_dir))
        spider = GraphSpider(config=config, driver=driver, storage=storage)
        
        # Краулимо та зберігаємо
        graph = await spider.crawl()
        await storage.save_graph(graph)
        
        # Створюємо новий storage і завантажуємо
        storage2 = JSONStorage(storage_dir=str(storage_dir))
        loaded_graph = await storage2.load_graph()
        
        assert loaded_graph is not None
        assert len(loaded_graph.nodes) == len(graph.nodes)
        
        # Порівнюємо URLs
        original_urls = set(n.url for n in graph.nodes.values())
        loaded_urls = set(n.url for n in loaded_graph.nodes.values())
        assert original_urls == loaded_urls
    
    async def test_spider_json_storage_persistence(self, tmp_path):
        """JSON storage зберігає дані між запусками."""
        storage_dir = tmp_path / "json_storage"
        storage_dir.mkdir()
        
        # Перший crawl
        config1 = CrawlerConfig(
            url="https://books.toscrape.com/",
            max_depth=0,
            max_pages=1
        )
        storage1 = JSONStorage(storage_dir=str(storage_dir))
        spider1 = GraphSpider(config=config1, driver=HTTPDriver(), storage=storage1)
        graph1 = await spider1.crawl()
        await storage1.save_graph(graph1)
        
        # Другий crawl (інший Spider, але той самий storage_dir)
        storage2 = JSONStorage(storage_dir=str(storage_dir))
        loaded = await storage2.load_graph()
        
        assert loaded is not None
        assert len(loaded.nodes) > 0


@pytest.mark.integration
@pytest.mark.asyncio
class TestSpiderWithSQLiteStorage:
    """Тести Spider з SQLite Storage."""
    
    async def test_spider_with_sqlite_storage_basic(self, tmp_path):
        """Spider працює з SQLite storage."""
        storage_dir = tmp_path / "sqlite_storage"
        storage_dir.mkdir()
        
        config = CrawlerConfig(
            url="https://books.toscrape.com/",
            max_depth=0,
            max_pages=1
        )
        driver = HTTPDriver()
        storage = SQLiteStorage(storage_dir=str(storage_dir))
        spider = GraphSpider(config=config, driver=driver, storage=storage)
        
        graph = await spider.crawl()
        
        # Перевіряємо що scanned тільки 1 node
        scanned_nodes = [n for n in graph.nodes.values() if n.scanned]
        assert len(scanned_nodes) == 1
        
        # Перевіряємо що DB файл створений
        assert (storage_dir / "graph.db").exists()
    
    async def test_spider_saves_to_sqlite(self, tmp_path):
        """Spider зберігає дані в SQLite."""
        storage_dir = tmp_path / "sqlite_storage"
        storage_dir.mkdir()
        
        config = CrawlerConfig(
            url="https://books.toscrape.com/",
            max_depth=1,
            max_pages=10
        )
        driver = HTTPDriver()
        storage = SQLiteStorage(storage_dir=str(storage_dir))
        spider = GraphSpider(config=config, driver=driver, storage=storage)
        
        graph = await spider.crawl()
        await storage.save_graph(graph)
        
        # Завантажуємо назад
        loaded_graph = await storage.load_graph()
        
        assert loaded_graph is not None
        assert len(loaded_graph.nodes) > 0
    
    async def test_spider_sqlite_handles_multiple_crawls(self, tmp_path):
        """SQLite storage обробляє декілька crawls."""
        storage_dir = tmp_path / "sqlite_storage"
        storage_dir.mkdir()
        
        # Перший crawl
        config1 = CrawlerConfig(
            url="https://books.toscrape.com/",
            max_depth=0,
            max_pages=2
        )
        storage1 = SQLiteStorage(storage_dir=str(storage_dir))
        spider1 = GraphSpider(config=config1, driver=HTTPDriver(), storage=storage1)
        graph1 = await spider1.crawl()
        await storage1.save_graph(graph1)
        
        # Другий crawl (інший сайт)
        config2 = CrawlerConfig(
            url="https://quotes.toscrape.com/",
            max_depth=0,
            max_pages=2
        )
        storage2 = SQLiteStorage(storage_dir=str(storage_dir))
        spider2 = GraphSpider(config=config2, driver=HTTPDriver(), storage=storage2)
        graph2 = await spider2.crawl()
        await storage2.save_graph(graph2)
        
        # Завантажуємо останній граф
        loaded = await storage2.load_graph()
        
        assert loaded is not None
        # Має бути граф з quotes.toscrape.com
        urls = [n.url for n in loaded.nodes.values()]
        assert any("quotes.toscrape.com" in url for url in urls)


@pytest.mark.integration
@pytest.mark.asyncio
class TestSpiderStorageComparison:
    """Порівняння різних storage типів."""
    
    async def test_storage_types_produce_same_graph(self, tmp_path):
        """Різні storage типи зберігають однакові дані."""
        config = CrawlerConfig(
            url="https://books.toscrape.com/",
            max_depth=0,
            max_pages=3
        )
        
        # Memory storage
        storage_mem = MemoryStorage()
        spider_mem = GraphSpider(config=config, driver=HTTPDriver(), storage=storage_mem)
        graph_mem = await spider_mem.crawl()
        await storage_mem.save_graph(graph_mem)
        
        # JSON storage
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        storage_json = JSONStorage(storage_dir=str(json_dir))
        await storage_json.save_graph(graph_mem)  # Зберігаємо той самий граф
        
        # SQLite storage
        storage_dir = tmp_path / "sqlite"
        storage_dir.mkdir()
        storage_sqlite = SQLiteStorage(storage_dir=str(storage_dir))
        await storage_sqlite.save_graph(graph_mem)  # Зберігаємо той самий граф
        
        # Завантажуємо з кожного storage
        loaded_mem = await storage_mem.load_graph()
        loaded_json = await storage_json.load_graph()
        loaded_sqlite = await storage_sqlite.load_graph()
        
        # Перевіряємо що всі мають однакову кількість nodes
        assert len(loaded_mem.nodes) == len(loaded_json.nodes) == len(loaded_sqlite.nodes)
        
        # Перевіряємо що URLs однакові
        urls_mem = set(n.url for n in loaded_mem.nodes.values())
        urls_json = set(n.url for n in loaded_json.nodes.values())
        urls_sqlite = set(n.url for n in loaded_sqlite.nodes.values())
        
        assert urls_mem == urls_json == urls_sqlite


@pytest.mark.integration
@pytest.mark.asyncio
class TestSpiderStoragePerformance:
    """Тести продуктивності storage."""
    
    async def test_storage_save_performance(self, tmp_path):
        """Storage зберігає дані швидко."""
        import time
        
        config = CrawlerConfig(
            url="https://books.toscrape.com/",
            max_depth=1,
            max_pages=10
        )
        
        # Memory storage
        storage_mem = MemoryStorage()
        spider_mem = GraphSpider(config=config, driver=HTTPDriver(), storage=storage_mem)
        
        graph = await spider_mem.crawl()
        
        start = time.time()
        await storage_mem.save_graph(graph)
        mem_time = time.time() - start
        
        # JSON storage
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        storage_json = JSONStorage(storage_dir=str(json_dir))
        
        start = time.time()
        await storage_json.save_graph(graph)
        json_time = time.time() - start
        
        # Обидва мають бути швидкими
        assert mem_time < 5  # Менше 5 секунд
        assert json_time < 5  # Менше 5 секунд


@pytest.mark.integration
@pytest.mark.asyncio
class TestSpiderStorageEdgeCases:
    """Тести edge cases для storage."""
    
    async def test_storage_handles_empty_graph(self, tmp_path):
        """Storage обробляє порожній граф."""
        from graph_crawler.domain.entities.graph import Graph
        
        empty_graph = Graph()
        
        # Memory
        storage_mem = MemoryStorage()
        await storage_mem.save_graph(empty_graph)
        loaded = await storage_mem.load_graph()
        assert len(loaded.nodes) == 0
        
        # JSON
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        storage_json = JSONStorage(storage_dir=str(json_dir))
        await storage_json.save_graph(empty_graph)
        loaded = await storage_json.load_graph()
        assert len(loaded.nodes) == 0
    
    async def test_storage_handles_large_graph(self, tmp_path):
        """Storage обробляє великий граф."""
        config = CrawlerConfig(
            url="https://books.toscrape.com/",
            max_depth=2,
            max_pages=50
        )
        driver = HTTPDriver()
        
        # JSON storage
        json_dir = tmp_path / "json"
        json_dir.mkdir()
        storage = JSONStorage(storage_dir=str(json_dir))
        spider = GraphSpider(config=config, driver=driver, storage=storage)
        
        graph = await spider.crawl()
        await storage.save_graph(graph)
        
        # Завантажуємо назад
        loaded = await storage.load_graph()
        
        assert len(loaded.nodes) == len(graph.nodes)
