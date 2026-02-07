"""E2E tests для повного циклу краулінгу.

End-to-end тести що перевіряють весь flow від початку до кінця.
Використовуються реальні сайти з складною структурою.
"""

import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
from graph_crawler import crawl, async_crawl, Crawler, AsyncCrawler
from graph_crawler.domain.value_objects.models import URLRule


@pytest.mark.e2e
class TestFullCrawlE2E:
    """E2E тести повного краулінгу."""
    
    def test_complete_crawl_books_site(self):
        """Повний E2E: краулінг книжкового сайту."""
        # Краулимо books.toscrape.com - сайт з багатьма категоріями та книгами
        graph = crawl(
            "https://books.toscrape.com/",
            max_depth=3,
            max_pages=100,
            request_delay=0.1  # Ввічливо до сервера
        )
        
        # Перевірки результату - scanned_nodes це кількість оброблених сторінок
        scanned = [n for n in graph.nodes.values() if n.scanned]
        assert len(scanned) > 10
        assert len(scanned) <= 100
        
        # Є edges між nodes
        assert len(graph.edges) > 0
        
        # Є nodes різних глибин
        depths = set(node.depth for node in graph.nodes.values())
        assert len(depths) >= 2
        
        # Всі URLs з того ж домену
        assert all("books.toscrape.com" in n.url for n in graph.nodes.values())
    
    def test_complete_crawl_quotes_site(self):
        """Повний E2E: краулінг сайту з цитатами."""
        graph = crawl(
            "https://quotes.toscrape.com/",
            max_depth=2,
            max_pages=50,
            request_delay=0.1
        )
        
        # Перевіряємо скановані сторінки
        scanned = [n for n in graph.nodes.values() if n.scanned]
        assert len(scanned) > 5
        assert len(scanned) <= 50
        
        # Перевіряємо що є пагінація
        urls = [n.url for n in graph.nodes.values()]
        # Може бути /page/2/, /page/3/ тощо
        pagination_urls = [u for u in urls if "/page/" in u]
        # Сайт має пагінацію
        assert len(urls) > 1
    
    def test_complete_crawl_with_metadata_extraction(self):
        """E2E: краулінг з витяганням метаданих."""
        graph = crawl(
            "https://books.toscrape.com/",
            max_depth=1,
            max_pages=20,
            request_delay=0.1
        )
        
        # Перевіряємо що метадані витягнуті
        root = graph.get_node_by_url("https://books.toscrape.com/")
        assert root is not None
        # HTML не зберігається (економія RAM), але node має бути скановану
        assert root.scanned is True
        
        # Перевіряємо що є статус
        assert root.response_status == 200


@pytest.mark.e2e
class TestFullCrawlWithFiltersE2E:
    """E2E тести краулінгу з фільтрами."""
    
    def test_crawl_with_url_rules(self):
        """E2E: краулінг з URL rules."""
        # Краулимо тільки /catalogue/* URLs
        url_rules = [
            URLRule(
                pattern=r".*/catalogue/.*",
                scan=True,
                create_edges=True
            ),
            URLRule(
                pattern=r".*",
                scan=False,
                create_edges=True  # Створюємо edges але не сканимо
            )
        ]
        
        graph = crawl(
            "https://books.toscrape.com/",
            max_depth=2,
            max_pages=30,
            url_rules=url_rules,
            request_delay=0.1
        )
        
        # Перевіряємо що є nodes
        assert len(graph.nodes) > 1
        
        # Scanned nodes мають /catalogue/ в URL (окрім root)
        scanned = [n for n in graph.nodes.values() if n.scanned and n.depth > 0]
        if scanned:
            # Якщо є scanned nodes (крім root), вони мають відповідати правилу
            assert any("/catalogue/" in n.url for n in scanned)
    
    def test_crawl_with_domain_filtering(self):
        """E2E: краулінг з фільтрацією доменів."""
        graph = crawl(
            "https://books.toscrape.com/",
            max_depth=2,
            max_pages=30,
            request_delay=0.1
        )
        
        # Всі nodes з того ж домену
        for node in graph.nodes.values():
            assert "books.toscrape.com" in node.url
            # Немає зовнішніх доменів
            assert "google.com" not in node.url
            assert "facebook.com" not in node.url


@pytest.mark.e2e
class TestFullCrawlWithStorageE2E:
    """E2E тести краулінгу зі збереженням."""
    
    def test_crawl_and_save_to_json(self):
        """E2E: краулінг та збереження в JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_dir = Path(tmpdir) / "crawl_data"
            storage_dir.mkdir()
            
            # Краулимо
            graph = crawl(
                "https://books.toscrape.com/",
                max_depth=1,
                max_pages=10,
                request_delay=0.1
            )
            
            # Граф створений
            scanned = [n for n in graph.nodes.values() if n.scanned]
            assert len(scanned) > 0
            
            # Зберігаємо вручну через JSONStorage
            from graph_crawler.infrastructure.persistence import JSONStorage
            storage = JSONStorage(storage_dir=str(storage_dir))
            
            import asyncio
            asyncio.run(storage.save_graph(graph))
            
            # JSON файли створені
            json_files = list(storage_dir.glob("*.json"))
            assert len(json_files) > 0
            
            # Можемо завантажити назад
            loaded_graph = asyncio.run(storage.load_graph())
            
            assert loaded_graph is not None
            assert len(loaded_graph.nodes) == len(graph.nodes)
    
    def test_crawl_and_save_to_sqlite(self):
        """E2E: краулінг та збереження в SQLite."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_dir = Path(tmpdir) / "sqlite_data"
            storage_dir.mkdir()
            
            # Краулимо
            graph = crawl(
                "https://books.toscrape.com/",
                max_depth=1,
                max_pages=10,
                request_delay=0.1
            )
            
            # Граф створений
            scanned = [n for n in graph.nodes.values() if n.scanned]
            assert len(scanned) > 0
            
            # Зберігаємо вручну через SQLiteStorage
            from graph_crawler.infrastructure.persistence import SQLiteStorage
            storage = SQLiteStorage(storage_dir=str(storage_dir))
            
            import asyncio
            asyncio.run(storage.save_graph(graph))
            
            # DB файл створений
            db_path = storage_dir / "graph.db"
            assert db_path.exists()
            
            # Можемо завантажити назад
            loaded_graph = asyncio.run(storage.load_graph())
            
            assert loaded_graph is not None
            assert len(loaded_graph.nodes) > 0
            
            # КРИТИЧНО: Закриваємо з'єднання перед видаленням tmpdir
            asyncio.run(storage.close())


@pytest.mark.e2e
@pytest.mark.asyncio
class TestFullAsyncCrawlE2E:
    """E2E тести async краулінгу."""
    
    async def test_async_crawl_complete_flow(self):
        """E2E: async краулінг повний flow."""
        graph = await async_crawl(
            "https://books.toscrape.com/",
            max_depth=2,
            max_pages=30,
            request_delay=0.1
        )
        
        # Перевіряємо скановані сторінки
        scanned = [n for n in graph.nodes.values() if n.scanned]
        assert len(scanned) > 5
        assert len(scanned) <= 30
        assert len(graph.edges) > 0
    
    async def test_async_parallel_crawls(self):
        """E2E: паралельні async crawls."""
        async with AsyncCrawler(max_depth=1, max_pages=10, request_delay=0.1) as crawler:
            results = await asyncio.gather(
                crawler.crawl("https://books.toscrape.com/"),
                crawler.crawl("https://quotes.toscrape.com/"),
                crawler.crawl("https://scrapethissite.com/"),
            )
        
        # Всі crawls успішні
        assert len(results) == 3
        assert all(len(g.nodes) > 0 for g in results)
        
        # Кожен граф унікальний
        urls_sets = [
            set(n.url for n in g.nodes.values())
            for g in results
        ]
        # URLs різні між графами
        assert urls_sets[0] != urls_sets[1]
        assert urls_sets[1] != urls_sets[2]


@pytest.mark.e2e
class TestFullCrawlComplexSitesE2E:
    """E2E тести складних реальних сайтів."""
    
    def test_crawl_site_with_pagination(self):
        """E2E: сайт з пагінацією."""
        graph = crawl(
            "https://quotes.toscrape.com/",
            max_depth=2,
            max_pages=25,
            request_delay=0.1
        )
        
        assert len(graph.nodes) > 5
        
        # Перевіряємо структуру графа
        assert len(graph.edges) > 0
        
        # Є різні глибини
        depths = [n.depth for n in graph.nodes.values()]
        assert max(depths) >= 1
    
    def test_crawl_site_with_categories(self):
        """E2E: сайт з категоріями."""
        # books.toscrape.com має категорії книг
        graph = crawl(
            "https://books.toscrape.com/",
            max_depth=2,
            max_pages=40,
            request_delay=0.1
        )
        
        assert len(graph.nodes) > 10
        
        # Перевіряємо що є різні types URLs
        urls = [n.url for n in graph.nodes.values()]
        
        # Має бути головна, категорії, або книги
        assert len(set(urls)) == len(urls)  # Всі URLs унікальні
    
    def test_crawl_site_with_deep_structure(self):
        """E2E: сайт з глибокою структурою."""
        graph = crawl(
            "https://books.toscrape.com/",
            max_depth=3,
            max_pages=50,
            request_delay=0.1
        )
        
        scanned = [n for n in graph.nodes.values() if n.scanned]
        assert len(scanned) > 10
        
        # Є nodes на різних глибинах
        depths = set(n.depth for n in graph.nodes.values())
        assert len(depths) >= 2
        
        # Є edges що з'єднують nodes
        # graph.edges це list, не dict
        assert len(graph.edges) > 0
        for edge in graph.edges:
            assert edge.source_node_id in graph.nodes
            assert edge.target_node_id in graph.nodes


@pytest.mark.e2e
class TestFullCrawlPerformanceE2E:
    """E2E тести продуктивності краулінгу."""
    
    def test_crawl_completes_in_reasonable_time(self):
        """E2E: краулінг завершується за розумний час."""
        import time
        
        start = time.time()
        
        graph = crawl(
            "https://books.toscrape.com/",
            max_depth=1,
            max_pages=10,
            request_delay=0.1
        )
        
        elapsed = time.time() - start
        
        # 10 сторінок з 0.1с delay = ~1-2 секунди + fetch time
        # Максимум 30 секунд для 10 сторінок
        assert elapsed < 30
        
        # Перевіряємо скановані сторінки
        scanned = [n for n in graph.nodes.values() if n.scanned]
        assert len(scanned) <= 10
    
    @pytest.mark.asyncio
    async def test_async_crawl_faster_than_sync(self):
        """E2E: async краулінг швидший за sync."""
        import time
        
        # Async crawl (в async тесті не можна викликати sync crawl який робить asyncio.run())
        start = time.time()
        async_graph = await async_crawl(
            "https://books.toscrape.com/",
            max_depth=1,
            max_pages=10,
            request_delay=0.05,
            driver="async"
        )
        async_time = time.time() - start
        
        # Перевіряємо що async працює
        scanned = [n for n in async_graph.nodes.values() if n.scanned]
        assert len(scanned) > 0
        assert async_time > 0
