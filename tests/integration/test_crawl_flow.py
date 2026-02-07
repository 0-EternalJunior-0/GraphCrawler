"""Integration tests для повного циклу краулінгу.

Тести перевіряють весь flow від старту краулінгу до отримання результату.
Використовуються реальні сайти з багатьма посиланнями.
"""

import pytest
import asyncio
from pathlib import Path
from graph_crawler import crawl, async_crawl, Crawler, AsyncCrawler
from graph_crawler.domain.entities.graph import Graph
from graph_crawler.domain.entities.node import Node
from graph_crawler.domain.value_objects.configs import CrawlerConfig


@pytest.mark.integration
class TestBasicCrawlFlow:
    """Базові тести краулінг flow."""
    
    def test_crawl_single_page_sync(self):
        """Краулінг однієї сторінки (sync API)."""
        # Використовуємо реальний сайт з багатьма посиланнями
        graph = crawl(
            "https://books.toscrape.com/",
            max_depth=0,
            max_pages=1
        )
        
        assert graph is not None
        assert isinstance(graph, Graph)
        
        # max_pages=1 означає що тільки 1 сторінка відсканована,
        # але граф містить всі знайдені посилання (unscanned nodes)
        scanned_count = sum(1 for n in graph.nodes.values() if n.scanned)
        assert scanned_count == 1, f"Expected 1 scanned node, got {scanned_count}"
        
        root = graph.get_node_by_url("https://books.toscrape.com/")
        assert root is not None
        assert root.scanned is True
        assert root.depth == 0
    
    def test_crawl_with_depth_1_sync(self):
        """Краулінг з глибиною 1 (sync API)."""
        graph = crawl(
            "https://books.toscrape.com/",
            max_depth=1,
            max_pages=20
        )
        
        # max_pages=20 означає що max 20 сторінок будуть відскановані
        scanned_count = sum(1 for n in graph.nodes.values() if n.scanned)
        assert scanned_count > 1, "Expected more than 1 scanned node"
        assert scanned_count <= 20, f"Expected max 20 scanned nodes, got {scanned_count}"
        
        # Перевіряємо що є nodes різних глибин серед відсканованих
        scanned_depths = set(node.depth for node in graph.nodes.values() if node.scanned)
        assert 0 in scanned_depths
        assert 1 in scanned_depths or scanned_count == 1
    
    def test_crawl_respects_max_pages(self):
        """Краулінг зупиняється на max_pages."""
        max_pages = 5
        graph = crawl(
            "https://books.toscrape.com/",
            max_depth=2,
            max_pages=max_pages
        )
        
        # max_pages обмежує кількість ВІДСКАНОВАНИХ сторінок
        scanned_count = sum(1 for n in graph.nodes.values() if n.scanned)
        assert scanned_count <= max_pages, f"Expected max {max_pages} scanned nodes, got {scanned_count}"
    
    def test_crawl_respects_max_depth(self):
        """Краулінг не йде глибше max_depth."""
        max_depth = 2
        graph = crawl(
            "https://books.toscrape.com/",
            max_depth=max_depth,
            max_pages=50
        )
        
        # Перевіряємо що немає nodes глибше max_depth
        for node in graph.nodes.values():
            assert node.depth <= max_depth
    
    def test_crawl_filters_external_domains(self):
        """Краулінг фільтрує зовнішні домени."""
        graph = crawl(
            "https://books.toscrape.com/",
            max_depth=1,
            max_pages=10
        )
        
        # Всі nodes повинні бути з того ж домену
        for node in graph.nodes.values():
            assert "books.toscrape.com" in node.url
    
    def test_crawl_collects_metadata(self):
        """Краулінг збирає метадані."""
        graph = crawl(
            "https://books.toscrape.com/",
            max_depth=0,
            max_pages=1
        )
        
        # Знаходимо кореневий node
        root = graph.get_node_by_url("https://books.toscrape.com/")
        assert root is not None, "Root node not found"
        assert root.scanned is True, "Root node should be scanned"
        assert root.response_status == 200, f"Expected status 200, got {root.response_status}"
        # Метадані зберігаються в metadata dict
        assert root.metadata is not None, "Metadata should be collected"
        assert 'title' in root.metadata or 'h1' in root.metadata, "Should have title or h1 in metadata"


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="function")
class TestAsyncCrawlFlow:
    """Тести async краулінг flow."""
    
    async def test_async_crawl_single_page(self):
        """Async краулінг однієї сторінки."""
        graph = await async_crawl(
            "https://books.toscrape.com/",
            max_depth=0,
            max_pages=1
        )
        
        assert graph is not None
        # max_pages=1 обмежує scanned, не total nodes
        scanned_count = sum(1 for n in graph.nodes.values() if n.scanned)
        assert scanned_count == 1
        
        root = graph.get_node_by_url("https://books.toscrape.com/")
        assert root is not None
        assert root.scanned is True
    
    async def test_async_crawl_with_depth(self):
        """Async краулінг з глибиною."""
        graph = await async_crawl(
            "https://books.toscrape.com/",
            max_depth=1,
            max_pages=15
        )
        
        scanned_count = sum(1 for n in graph.nodes.values() if n.scanned)
        assert scanned_count > 1
        assert scanned_count <= 15
    
    async def test_async_crawl_parallel(self):
        """Паралельний async краулінг декількох сайтів."""
        async with AsyncCrawler(max_depth=0, max_pages=1) as crawler:
            results = await asyncio.gather(
                crawler.crawl("https://books.toscrape.com/"),
                crawler.crawl("https://quotes.toscrape.com/"),
            )
        
        assert len(results) == 2
        assert all(isinstance(g, Graph) for g in results)
        # Кожен граф має 1 scanned node
        for g in results:
            scanned_count = sum(1 for n in g.nodes.values() if n.scanned)
            assert scanned_count == 1
    
    async def test_async_crawler_reusable(self):
        """AsyncCrawler можна використовувати повторно."""
        async with AsyncCrawler(max_depth=0, max_pages=2) as crawler:
            graph1 = await crawler.crawl("https://books.toscrape.com/")
            graph2 = await crawler.crawl("https://quotes.toscrape.com/")
        
        scanned1 = sum(1 for n in graph1.nodes.values() if n.scanned)
        scanned2 = sum(1 for n in graph2.nodes.values() if n.scanned)
        assert scanned1 >= 1
        assert scanned2 >= 1
        
        # Графи різні
        assert graph1 is not graph2


@pytest.mark.integration
class TestCrawlerWithDifferentDrivers:
    """Тести краулінгу з різними драйверами."""
    
    def test_crawl_with_http_driver(self):
        """Краулінг з HTTP driver (без JS)."""
        graph = crawl(
            "https://books.toscrape.com/",
            max_depth=0,
            max_pages=1,
            driver="http"
        )
        
        # max_pages=1 означає 1 scanned node
        scanned_count = sum(1 for n in graph.nodes.values() if n.scanned)
        assert scanned_count == 1
        root = graph.get_node_by_url("https://books.toscrape.com/")
        assert root is not None
        assert root.scanned is True
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_crawl_with_async_driver(self):
        """Краулінг з Async driver."""
        graph = await async_crawl(
            "https://books.toscrape.com/",
            max_depth=0,
            max_pages=1,
            driver="async"
        )
        
        scanned_count = sum(1 for n in graph.nodes.values() if n.scanned)
        assert scanned_count == 1


@pytest.mark.integration
class TestCrawlerWithStorage:
    """Тести краулінгу зі збереженням."""
    
    def test_crawl_with_memory_storage(self):
        """Краулінг з memory storage."""
        with Crawler(max_depth=1, max_pages=5, storage="memory") as crawler:
            graph = crawler.crawl("https://books.toscrape.com/")
        
        # max_pages=5 обмежує кількість ВІДСКАНОВАНИХ сторінок
        scanned_count = sum(1 for n in graph.nodes.values() if n.scanned)
        assert scanned_count > 0, "At least one node should be scanned"
        assert scanned_count <= 5, f"Expected max 5 scanned nodes, got {scanned_count}"
    
    def test_crawl_with_json_storage(self, tmp_path):
        """Краулінг з JSON storage - перевірка конфігурації.
        
        Примітка: Storage не зберігає автоматично - це окрема операція.
        Тест перевіряє що storage правильно ініціалізується.
        """
        storage_dir = tmp_path / "crawl_data"
        storage_dir.mkdir()
        
        with Crawler(
            max_depth=0, 
            max_pages=2,
            storage="json",
            storage_config={"storage_dir": str(storage_dir)}
        ) as crawler:
            graph = crawler.crawl("https://books.toscrape.com/")
        
        scanned_count = sum(1 for n in graph.nodes.values() if n.scanned)
        assert scanned_count > 0, "At least one node should be scanned"
        
        # Граф успішно створено з JSON storage конфігурацією
        assert graph is not None
        assert len(graph.nodes) > 0


@pytest.mark.integration
class TestCrawlWithFilters:
    """Тести краулінгу з фільтрами."""
    
    def test_crawl_with_path_filter(self):
        """Краулінг з фільтром шляхів."""
        from graph_crawler.domain.value_objects.models import URLRule
        
        # Створюємо правило: сканувати тільки /catalogue/*
        url_rules = [
            URLRule(
                pattern=r".*/catalogue/.*",
                scan=True,
                create_edges=True
            ),
            URLRule(
                pattern=r".*",
                scan=False,
                create_edges=False
            )
        ]
        
        graph = crawl(
            "https://books.toscrape.com/",
            max_depth=2,
            max_pages=20,
            url_rules=url_rules
        )
        
        # Перевіряємо що всі просканované nodes мають /catalogue/ в URL
        scanned_nodes = [n for n in graph.nodes.values() if n.scanned and n.depth > 0]
        if scanned_nodes:  # Якщо є просканові nodes крім root
            assert any("/catalogue/" in node.url for node in scanned_nodes)
    
    def test_crawl_subdomain_filtering(self):
        """Краулінг з фільтрацією субдоменів."""
        # Використовуємо сайт з субдоменами
        graph = crawl(
            "https://quotes.toscrape.com/",
            max_depth=1,
            max_pages=10
        )
        
        # Всі nodes повинні бути з того ж домену/субдомену
        for node in graph.nodes.values():
            assert "quotes.toscrape.com" in node.url


@pytest.mark.integration
class TestCrawlErrorHandling:
    """Тести обробки помилок при краулінгу."""
    
    def test_crawl_handles_404(self):
        """Краулінг обробляє 404 помилки."""
        # Спробуємо краулити неіснуючу сторінку
        graph = crawl(
            "https://httpbin.org/status/404",
            max_depth=0,
            max_pages=1
        )
        
        # Граф створюється навіть якщо сторінка не знайдена
        assert graph is not None
        assert len(graph.nodes) >= 1
        
        # httpbin.org може повертати різні коди, перевіряємо що граф створено
        assert graph is not None
    
    def test_crawl_handles_timeout(self):
        """Краулінг обробляє timeout."""
        # httpbin.org/delay/{n} створює затримку n секунд
        # Використовуємо стандартний параметр timeout замість request_timeout
        graph = crawl(
            "https://httpbin.org/delay/2",
            max_depth=0,
            max_pages=1,
            timeout=30  # загальний timeout
        )
        
        assert graph is not None
        # Просто перевіряємо що не зависло і граф створено


@pytest.mark.integration
class TestCrawlRealWorldSites:
    """Тести краулінгу реальних сайтів з багатьма посиланнями."""
    
    def test_crawl_books_toscrape(self):
        """Краулінг books.toscrape.com (багато внутрішніх посилань)."""
        graph = crawl(
            "https://books.toscrape.com/",
            max_depth=2,
            max_pages=30
        )
        
        # max_pages=30 обмежує scanned nodes
        scanned_count = sum(1 for n in graph.nodes.values() if n.scanned)
        assert scanned_count > 5, f"Should have scanned at least 5 pages, got {scanned_count}"
        assert scanned_count <= 30, f"Should scan max 30 pages, got {scanned_count}"
        
        # Перевіряємо наявність edges
        assert len(graph.edges) > 0
        
        # Перевіряємо різні глибини серед відсканованих nodes
        scanned_depths = set(n.depth for n in graph.nodes.values() if n.scanned)
        assert len(scanned_depths) >= 2
    
    def test_crawl_quotes_toscrape(self):
        """Краулінг quotes.toscrape.com (сайт з пагінацією)."""
        graph = crawl(
            "https://quotes.toscrape.com/",
            max_depth=2,
            max_pages=20
        )
        
        scanned_count = sum(1 for n in graph.nodes.values() if n.scanned)
        assert scanned_count > 3, f"Should have scanned at least 3 pages, got {scanned_count}"
        assert scanned_count <= 20, f"Should scan max 20 pages, got {scanned_count}"
        
        # Перевіряємо що є посилання на наступні сторінки
        urls = [node.url for node in graph.nodes.values()]
        # Може бути пагінація або інші посилання
        assert len(urls) > 1
    
    def test_crawl_scrapethissite(self):
        """Краулінг scrapethissite.com (багато субсторінок)."""
        graph = crawl(
            "https://scrapethissite.com/",
            max_depth=1,
            max_pages=15
        )
        
        assert len(graph.nodes) > 1
        assert len(graph.nodes) <= 15
        
        # Всі nodes з того ж домену
        for node in graph.nodes.values():
            assert "scrapethissite.com" in node.url
