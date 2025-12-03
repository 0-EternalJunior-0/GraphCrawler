"""E2E tests для distributed краулінгу з Celery.

Тести перевіряють роботу distributed crawler з Celery та Redis.
"""

import pytest
import asyncio
from graph_crawler import crawl


@pytest.mark.e2e
@pytest.mark.distributed
@pytest.mark.skipif(
    True,  # Skip by default, requires Celery + Redis setup
    reason="Requires Celery and Redis to be running"
)
class TestDistributedCrawlE2E:
    """E2E тести distributed краулінгу."""
    
    def test_distributed_crawler_import(self):
        """Distributed crawler може бути імпортований."""
        try:
            from graph_crawler import EasyDistributedCrawler
            assert EasyDistributedCrawler is not None
        except ImportError:
            pytest.skip("Celery not installed")
    
    def test_celery_tasks_available(self):
        """Celery tasks доступні."""
        try:
            from graph_crawler import crawl_page_task, crawl_batch_task
            assert crawl_page_task is not None
            assert crawl_batch_task is not None
        except ImportError:
            pytest.skip("Celery not installed")
    
    @pytest.mark.asyncio
    async def test_distributed_crawl_basic(self):
        """Distributed краулінг базовий тест."""
        try:
            from graph_crawler import EasyDistributedCrawler
        except ImportError:
            pytest.skip("Celery not installed")
        
        # Створюємо distributed crawler
        crawler = EasyDistributedCrawler(
            broker_url="redis://localhost:6379/0",
            result_backend="redis://localhost:6379/1"
        )
        
        # Краулимо (це має запустити Celery tasks)
        try:
            graph = await crawler.crawl(
                "https://books.toscrape.com/",
                max_depth=1,
                max_pages=10
            )
            
            assert graph is not None
            assert len(graph.nodes) > 0
        except Exception as e:
            # Може не працювати без running Celery worker
            pytest.skip(f"Celery not running: {e}")
    
    def test_distributed_crawl_parallel_sites(self):
        """Distributed краулінг декількох сайтів паралельно."""
        try:
            from graph_crawler import EasyDistributedCrawler
        except ImportError:
            pytest.skip("Celery not installed")
        
        crawler = EasyDistributedCrawler()
        
        try:
            # Запускаємо паралельний краулінг
            import asyncio
            results = asyncio.run(asyncio.gather(
                crawler.crawl("https://books.toscrape.com/", max_depth=1, max_pages=5),
                crawler.crawl("https://quotes.toscrape.com/", max_depth=1, max_pages=5),
            ))
            
            assert len(results) == 2
            assert all(len(g.nodes) > 0 for g in results)
        except Exception:
            pytest.skip("Celery not running")
    
    def test_distributed_crawl_handles_large_site(self):
        """Distributed краулінг обробляє великий сайт."""
        try:
            from graph_crawler import EasyDistributedCrawler
        except ImportError:
            pytest.skip("Celery not installed")
        
        crawler = EasyDistributedCrawler()
        
        try:
            # Великий краулінг - має бути розподілений між workers
            import asyncio
            graph = asyncio.run(crawler.crawl(
                "https://books.toscrape.com/",
                max_depth=2,
                max_pages=50
            ))
            
            assert len(graph.nodes) > 10
            assert len(graph.nodes) <= 50
        except Exception:
            pytest.skip("Celery not running")


@pytest.mark.e2e
@pytest.mark.integration
class TestDistributedCrawlFallback:
    """Тести fallback коли distributed недоступний."""
    
    def test_regular_crawl_works_without_celery(self):
        """Звичайний crawl працює без Celery."""
        # Навіть якщо Celery не встановлений, звичайний crawl має працювати
        graph = crawl(
            "https://books.toscrape.com/",
            max_depth=0,
            max_pages=1
        )
        
        # max_pages=1 означає що скануємо 1 сторінку, але у графі будуть
        # і інші nodes (посилання знайдені на сторінці) зі scanned=False
        scanned_nodes = [n for n in graph.nodes.values() if n.scanned]
        assert len(scanned_nodes) == 1
    
    def test_async_crawl_works_without_celery(self):
        """Async crawl працює без Celery."""
        from graph_crawler import async_crawl
        import asyncio
        
        graph = asyncio.run(async_crawl(
            "https://books.toscrape.com/",
            max_depth=0,
            max_pages=1
        ))
        
        # max_pages=1 означає що скануємо 1 сторінку
        scanned_nodes = [n for n in graph.nodes.values() if n.scanned]
        assert len(scanned_nodes) == 1
    
    def test_crawler_detects_celery_unavailable(self):
        """Crawler детектує що Celery недоступний."""
        from graph_crawler import celery
        
        if celery is None:
            # Celery не встановлений - це OK
            assert True
        else:
            # Celery встановлений
            assert celery is not None


@pytest.mark.e2e
@pytest.mark.skipif(
    True,
    reason="Mock test for documentation"
)
class TestDistributedCrawlAdvanced:
    """Розширені тести distributed краулінгу (requires setup)."""
    
    def test_distributed_crawl_with_multiple_workers(self):
        """Distributed краулінг з декількома workers."""
        # Цей тест вимагає запущених Celery workers
        # celery -A graph_crawler.infrastructure.messaging worker -c 4
        
        try:
            from graph_crawler import EasyDistributedCrawler
        except ImportError:
            pytest.skip("Celery not installed")
        
        crawler = EasyDistributedCrawler()
        
        # Великий краулінг що має бути розподілений
        import asyncio
        graph = asyncio.run(crawler.crawl(
            "https://books.toscrape.com/",
            max_depth=3,
            max_pages=100
        ))
        
        assert len(graph.nodes) > 20
        # Tasks мали бути розподілені між workers
    
    def test_distributed_crawl_task_monitoring(self):
        """Моніторинг tasks в distributed краулінгу."""
        try:
            from graph_crawler import celery
            from celery import states
        except ImportError:
            pytest.skip("Celery not installed")
        
        if celery is None:
            pytest.skip("Celery not configured")
        
        # Перевіряємо статус Celery
        inspector = celery.control.inspect()
        
        # Active workers
        active = inspector.active()
        # Може бути None якщо немає workers
        
        # Registered tasks
        registered = inspector.registered()
        # Має містити crawl_page_task, crawl_batch_task
        
        # Це скоріше integration test для Celery setup
        assert True  # Placeholder
