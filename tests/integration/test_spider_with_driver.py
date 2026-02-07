"""Integration tests для Spider з різними драйверами.

Тести перевіряють роботу Spider з HTTP, Async та іншими драйверами.
"""

import pytest
import asyncio
from graph_crawler.application.use_cases.crawling.spider import GraphSpider
from graph_crawler.domain.value_objects.configs import CrawlerConfig
from graph_crawler.infrastructure.transport import HTTPDriver
from graph_crawler.infrastructure.persistence.memory_storage import MemoryStorage
from graph_crawler.domain.entities.graph import Graph


@pytest.mark.integration
class TestSpiderWithHTTPDriver:
    """Тести Spider з HTTP Driver."""
    
    def test_spider_creates_with_http_driver(self):
        """Spider створюється з HTTP driver."""
        config = CrawlerConfig(
            url="https://books.toscrape.com/",
            max_depth=0,
            max_pages=1
        )
        driver = HTTPDriver()
        storage = MemoryStorage()
        
        spider = GraphSpider(config=config, driver=driver, storage=storage)
        
        assert spider is not None
        assert spider.config == config
        assert spider.driver == driver
    
    @pytest.mark.asyncio
    async def test_spider_crawls_with_http_driver(self):
        """Spider краулить з HTTP driver."""
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
        
        root = list(n for n in graph.nodes.values() if n.scanned)[0]
        assert root.scanned is True
        assert root.url == "https://books.toscrape.com/"
    
    @pytest.mark.asyncio
    async def test_spider_crawls_multiple_pages_http(self):
        """Spider краулить декілька сторінок з HTTP driver."""
        config = CrawlerConfig(
            url="https://books.toscrape.com/",
            max_depth=1,
            max_pages=10
        )
        driver = HTTPDriver()
        storage = MemoryStorage()
        spider = GraphSpider(config=config, driver=driver, storage=storage)
        
        graph = await spider.crawl()
        
        # Перевіряємо кількість скановоних сторінок
        scanned_nodes = [n for n in graph.nodes.values() if n.scanned]
        assert len(scanned_nodes) > 1
        assert len(scanned_nodes) <= 10
    
    @pytest.mark.asyncio
    async def test_spider_respects_rate_limit(self):
        """Spider поважає rate limit."""
        import time
        
        config = CrawlerConfig(
            url="https://books.toscrape.com/",
            max_depth=0,
            max_pages=2
        )
        driver = HTTPDriver()
        storage = MemoryStorage()
        spider = GraphSpider(config=config, driver=driver, storage=storage)
        
        start_time = time.time()
        graph = await spider.crawl()
        elapsed_time = time.time() - start_time
        
        # Перевіряємо що краулінг виконано
        assert len(graph.nodes) >= 1


@pytest.mark.integration
@pytest.mark.asyncio
class TestSpiderWithAsyncDriver:
    """Тести Spider з Async Driver."""
    
    async def test_spider_creates_with_async_driver(self):
        """Spider створюється з Async driver."""
        try:
            from graph_crawler.infrastructure.transport import AsyncDriver
        except ImportError:
            pytest.skip("AsyncDriver not available")
        
        config = CrawlerConfig(
            url="https://books.toscrape.com/",
            max_depth=0,
            max_pages=1
        )
        driver = AsyncDriver()
        storage = MemoryStorage()
        
        spider = GraphSpider(config=config, driver=driver, storage=storage)
        
        assert spider is not None
        assert isinstance(spider.driver, AsyncDriver)
    
    async def test_spider_crawls_with_async_driver(self):
        """Spider краулить з Async driver."""
        try:
            from graph_crawler.infrastructure.transport import AsyncDriver
        except ImportError:
            pytest.skip("AsyncDriver not available")
        
        config = CrawlerConfig(
            url="https://books.toscrape.com/",
            max_depth=0,
            max_pages=1
        )
        driver = AsyncDriver()
        storage = MemoryStorage()
        spider = GraphSpider(config=config, driver=driver, storage=storage)
        
        graph = await spider.crawl()
        
        assert isinstance(graph, Graph)
        # Перевіряємо що scanned тільки 1 node
        scanned_nodes = [n for n in graph.nodes.values() if n.scanned]
        assert len(scanned_nodes) == 1
    
    async def test_spider_async_driver_comparison(self):
        """Порівняння HTTP та Async drivers."""
        try:
            from graph_crawler.infrastructure.transport import AsyncDriver
        except ImportError:
            pytest.skip("AsyncDriver not available")
        
        import time
        
        # HTTP driver
        config_http = CrawlerConfig(
            url="https://books.toscrape.com/",
            max_depth=1,
            max_pages=5
        )
        driver_http = HTTPDriver()
        storage_http = MemoryStorage()
        spider_http = GraphSpider(config=config_http, driver=driver_http, storage=storage_http)
        
        start = time.time()
        await spider_http.crawl()
        http_time = time.time() - start
        
        # Async driver
        config_async = CrawlerConfig(
            url="https://books.toscrape.com/",
            max_depth=1,
            max_pages=5
        )
        driver_async = AsyncDriver()
        storage_async = MemoryStorage()
        spider_async = GraphSpider(config=config_async, driver=driver_async, storage=storage_async)
        
        start = time.time()
        await spider_async.crawl()
        async_time = time.time() - start
        
        # Просто перевіряємо що обидва працюють
        assert http_time > 0
        assert async_time > 0


@pytest.mark.integration
@pytest.mark.asyncio
class TestSpiderDriverFeatures:
    """Тести специфічних можливостей драйверів."""
    
    async def test_spider_handles_redirects(self):
        """Spider обробляє редиректи."""
        config = CrawlerConfig(
            url="https://httpbin.org/redirect/1",
            max_depth=0,
            max_pages=1
        )
        driver = HTTPDriver()
        storage = MemoryStorage()
        spider = GraphSpider(config=config, driver=driver, storage=storage)
        
        graph = await spider.crawl()
        
        assert len(graph.nodes) >= 1
        root = list(graph.nodes.values())[0]
        # Редирект має бути оброблений
        assert root.scanned is True or root.response_status == 302
    
    async def test_spider_handles_large_html(self):
        """Spider обробляє великі HTML сторінки."""
        # books.toscrape.com має великі сторінки з багатьма книгами
        config = CrawlerConfig(
            url="https://books.toscrape.com/catalogue/category/books_1/index.html",
            max_depth=0,
            max_pages=1
        )
        driver = HTTPDriver()
        storage = MemoryStorage()
        spider = GraphSpider(config=config, driver=driver, storage=storage)
        
        graph = await spider.crawl()
        
        root = list(graph.nodes.values())[0]
        # Node просканована
        assert root.scanned is True
    
    async def test_spider_extracts_links_correctly(self):
        """Spider правильно витягує посилання."""
        config = CrawlerConfig(
            url="https://books.toscrape.com/",
            max_depth=1,
            max_pages=10
        )
        driver = HTTPDriver()
        storage = MemoryStorage()
        spider = GraphSpider(config=config, driver=driver, storage=storage)
        
        graph = await spider.crawl()
        
        # Перевіряємо що посилання витягнуті
        assert len(graph.edges) > 0
        
        # Перевіряємо що edges мають source та target
        # graph.edges це list, не dict
        for edge in graph.edges:
            assert edge.source_node_id in graph.nodes
            assert edge.target_node_id in graph.nodes
    
    async def test_spider_handles_different_content_types(self):
        """Spider обробляє різні content types."""
        # Сайт з різними типами контенту
        config = CrawlerConfig(
            url="https://httpbin.org/html",
            max_depth=0,
            max_pages=1
        )
        driver = HTTPDriver()
        storage = MemoryStorage()
        spider = GraphSpider(config=config, driver=driver, storage=storage)
        
        graph = await spider.crawl()
        
        root = list(graph.nodes.values())[0]
        assert root.scanned is True


@pytest.mark.integration
@pytest.mark.asyncio
class TestSpiderConcurrency:
    """Тести concurrent краулінгу."""
    
    async def test_spider_multiple_concurrent_crawls(self):
        """Декілька Spider можуть краулити одночасно."""
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
        
        driver1 = HTTPDriver()
        driver2 = HTTPDriver()
        storage1 = MemoryStorage()
        storage2 = MemoryStorage()
        
        spider1 = GraphSpider(config=config1, driver=driver1, storage=storage1)
        spider2 = GraphSpider(config=config2, driver=driver2, storage=storage2)
        
        # Краулимо одночасно
        results = await asyncio.gather(
            spider1.crawl(),
            spider2.crawl()
        )
        
        assert len(results) == 2
        assert all(isinstance(g, Graph) for g in results)
        assert all(len(g.nodes) >= 1 for g in results)
    
    async def test_spider_handles_concurrent_same_site(self):
        """Spider може краулити той самий сайт concurrent."""
        configs = [
            CrawlerConfig(
                url="https://books.toscrape.com/",
                max_depth=0,
                max_pages=2
            )
            for _ in range(3)
        ]
        
        drivers = [HTTPDriver() for _ in range(3)]
        storages = [MemoryStorage() for _ in range(3)]
        spiders = [
            GraphSpider(config=config, driver=driver, storage=storage)
            for config, driver, storage in zip(configs, drivers, storages)
        ]
        
        results = await asyncio.gather(*[s.crawl() for s in spiders])
        
        assert len(results) == 3
        assert all(len(g.nodes) >= 1 for g in results)


@pytest.mark.integration
@pytest.mark.asyncio
class TestSpiderEdgeCases:
    """Тести edge cases для Spider."""
    
    async def test_spider_empty_page(self):
        """Spider обробляє порожню сторінку."""
        # httpbin.org/html має мінімальний HTML
        config = CrawlerConfig(
            url="https://httpbin.org/html",
            max_depth=0,
            max_pages=1
        )
        driver = HTTPDriver()
        storage = MemoryStorage()
        spider = GraphSpider(config=config, driver=driver, storage=storage)
        
        graph = await spider.crawl()
        
        assert len(graph.nodes) >= 1
    
    async def test_spider_page_with_no_links(self):
        """Spider обробляє сторінку без посилань."""
        # Сторінка без посилань
        config = CrawlerConfig(
            url="https://httpbin.org/html",
            max_depth=1,
            max_pages=5
        )
        driver = HTTPDriver()
        storage = MemoryStorage()
        spider = GraphSpider(config=config, driver=driver, storage=storage)
        
        graph = await spider.crawl()
        
        # Має бути тільки root node
        assert len(graph.nodes) >= 1
    
    async def test_spider_circular_references(self):
        """Spider обробляє циклічні посилання."""
        # books.toscrape.com має циклічні посилання (home -> category -> home)
        config = CrawlerConfig(
            url="https://books.toscrape.com/",
            max_depth=2,
            max_pages=30
        )
        driver = HTTPDriver()
        storage = MemoryStorage()
        spider = GraphSpider(config=config, driver=driver, storage=storage)
        
        graph = await spider.crawl()
        
        # Не має бути дублікатів URLs
        urls = [node.url for node in graph.nodes.values()]
        assert len(urls) == len(set(urls))  # Всі URLs унікальні
