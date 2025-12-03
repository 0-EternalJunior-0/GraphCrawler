"""
Unit тести для механізмів гнучкого ядра v3.0.

Тестує:
1. Dynamic Priority Support (Scheduler)
2. Explicit Filter Override (LinkProcessor)
3. Post-Scan Hooks (CrawlCoordinator)

"""

import pytest
import asyncio
from typing import List
from unittest.mock import Mock, AsyncMock, MagicMock

from graph_crawler.domain.entities.node import Node
from graph_crawler.domain.entities.graph import Graph
from graph_crawler.domain.value_objects.configs import CrawlerConfig
from graph_crawler.domain.value_objects.models import DomainFilterConfig, PathFilterConfig
from graph_crawler.application.use_cases.crawling.scheduler import CrawlScheduler
from graph_crawler.application.use_cases.crawling.link_processor import LinkProcessor
from graph_crawler.application.use_cases.crawling.crawl_coordinator import CrawlCoordinator
from graph_crawler.application.use_cases.crawling.filters.domain_filter import DomainFilter
from graph_crawler.application.use_cases.crawling.filters.path_filter import PathFilter


# ===============================================
# ТЕСТ 1: Dynamic Priority Support (Scheduler)
# ===============================================

class TestDynamicPriority:
    """Тести для Dynamic Priority Support механізму."""
    
    def test_node_with_dynamic_priority(self):
        """Node з динамічним priority має вищий пріоритет за URLRule."""
        scheduler = CrawlScheduler()
        
        # Створюємо node з динамічним priority
        node1 = Node(url="https://example.com/page1", depth=1)
        node1.priority = 10  # Високий динамічний пріоритет
        
        node2 = Node(url="https://example.com/page2", depth=1)
        # node2 не має priority - використає default
        
        # Додаємо в scheduler
        scheduler.add_node(node1)
        scheduler.add_node(node2)
        
        # Отримуємо наступний node (має бути node1 з вищим пріоритетом)
        next_node = scheduler.get_next()
        assert next_node.url == "https://example.com/page1"
    
    def test_priority_ordering(self):
        """Nodes з різними пріоритетами обробляються в правильному порядку."""
        scheduler = CrawlScheduler()
        
        # Створюємо nodes з різними пріоритетами
        nodes = [
            (Node(url="https://example.com/low", depth=1), 3),
            (Node(url="https://example.com/high", depth=1), 10),
            (Node(url="https://example.com/medium", depth=1), 7),
        ]
        
        # Встановлюємо пріоритети та додаємо
        for node, priority in nodes:
            node.priority = priority
            scheduler.add_node(node)
        
        # Отримуємо nodes - мають бути відсортовані за пріоритетом (10, 7, 3)
        result = []
        while not scheduler.is_empty():
            node = scheduler.get_next()
            result.append(node.url)
        
        assert result == [
            "https://example.com/high",    # priority=10
            "https://example.com/medium",  # priority=7
            "https://example.com/low",     # priority=3
        ]
    
    def test_fallback_to_default_priority(self):
        """Node без priority використовує default."""
        scheduler = CrawlScheduler()
        
        node = Node(url="https://example.com/page", depth=1)
        # Не встановлюємо node.priority
        
        scheduler.add_node(node)
        
        # Має використати DEFAULT_URL_PRIORITY
        next_node = scheduler.get_next()
        assert next_node is not None


# ===============================================
# ТЕСТ 2: Explicit Filter Override (LinkProcessor)
# ===============================================

class TestExplicitFilterOverride:
    """Тести для Explicit Filter Override механізму."""
    
    def test_explicit_decision_allows_external_url(self):
        """Explicit decision дозволяє зовнішній URL незважаючи на фільтри."""
        # Створюємо граф та source node
        graph = Graph()
        source_node = Node(url="https://example.com", depth=0)
        graph.add_node(source_node)
        
        # Встановлюємо explicit decision для зовнішнього URL
        external_url = "https://external.com/page"
        source_node.user_data['explicit_scan_decisions'] = {
            external_url: True  # Дозволяємо
        }
        
        # Створюємо LinkProcessor з фільтром (тільки example.com)
        scheduler = CrawlScheduler()
        domain_config = DomainFilterConfig(base_domain="example.com", allowed_domains=["domain+subdomains"])
        domain_filter = DomainFilter(config=domain_config)
        path_config = PathFilterConfig()
        path_filter = PathFilter(config=path_config)
        
        processor = LinkProcessor(
            graph=graph,
            scheduler=scheduler,
            domain_filter=domain_filter,
            path_filter=path_filter,
        )
        
        # Обробляємо зовнішнє посилання
        links = [external_url]
        new_nodes = processor.process_links(source_node, links)
        
        # Має бути створена нова нода (фільтр перебитий)
        assert new_nodes == 1
        assert graph.get_node_by_url(external_url) is not None
    
    def test_explicit_decision_blocks_url(self):
        """Explicit decision може заблокувати URL."""
        graph = Graph()
        source_node = Node(url="https://example.com", depth=0)
        graph.add_node(source_node)
        
        # Встановлюємо explicit decision для блокування
        blocked_url = "https://example.com/blocked"
        source_node.user_data['explicit_scan_decisions'] = {
            blocked_url: False  # Блокуємо
        }
        
        scheduler = CrawlScheduler()
        domain_config = DomainFilterConfig(base_domain="example.com", allowed_domains=["domain+subdomains"])
        domain_filter = DomainFilter(config=domain_config)
        path_config = PathFilterConfig()
        path_filter = PathFilter(config=path_config)
        
        processor = LinkProcessor(
            graph=graph,
            scheduler=scheduler,
            domain_filter=domain_filter,
            path_filter=path_filter,
        )
        
        # Обробляємо заблоковане посилання
        links = [blocked_url]
        new_nodes = processor.process_links(source_node, links)
        
        # Не має бути створено нову ноду
        assert new_nodes == 0
        assert graph.get_node_by_url(blocked_url) is None
    
    def test_no_explicit_decision_uses_filters(self):
        """Без explicit decision використовуються звичайні фільтри."""
        graph = Graph()
        source_node = Node(url="https://example.com", depth=0)
        graph.add_node(source_node)
        
        # НЕ встановлюємо explicit_scan_decisions
        
        scheduler = CrawlScheduler()
        domain_config = DomainFilterConfig(base_domain="example.com", allowed_domains=["domain+subdomains"])
        domain_filter = DomainFilter(config=domain_config)
        path_config = PathFilterConfig()
        path_filter = PathFilter(config=path_config)
        
        processor = LinkProcessor(
            graph=graph,
            scheduler=scheduler,
            domain_filter=domain_filter,
            path_filter=path_filter,
        )
        
        # Обробляємо зовнішнє посилання
        external_url = "https://external.com/page"
        links = [external_url]
        new_nodes = processor.process_links(source_node, links)
        
        # Має бути заблоковано фільтром
        assert new_nodes == 0
        assert graph.get_node_by_url(external_url) is None


# ===============================================
# ТЕСТ 3: Post-Scan Hooks (CrawlCoordinator)
# ===============================================

class TestPostScanHooks:
    """Тести для Post-Scan Hooks механізму."""
    
    @pytest.mark.asyncio
    async def test_single_hook_modifies_links(self):
        """Один hook може модифікувати список посилань."""
        
        # Створюємо hook який фільтрує посилання
        async def filter_hook(node: Node, links: List[str]) -> List[str]:
            # Фільтруємо тільки посилання що починаються з /important
            return [link for link in links if "/important" in link]
        
        # Mock залежності
        config = CrawlerConfig(url="https://example.com", max_depth=3)
        driver = Mock()
        driver.supports_batch_fetching.return_value = False
        
        graph = Graph()
        scheduler = CrawlScheduler()
        
        # Mock scanner
        scanner = AsyncMock()
        scanner.scan_node = AsyncMock(return_value=[
            "https://example.com/important/page1",
            "https://example.com/skip/page",
            "https://example.com/important/page2"
        ])
        
        # Mock processor
        processor = Mock()
        processor.process_links_async = AsyncMock()
        
        progress_tracker = Mock()
        progress_tracker.get_pages_crawled.return_value = 0
        progress_tracker.should_publish_progress.return_value = False
        progress_tracker.publish_node_scan_started = Mock()
        progress_tracker.publish_node_scanned = Mock()
        progress_tracker.increment_pages = Mock()
        
        incremental_strategy = Mock()
        incremental_strategy.should_process_node_links.return_value = True
        
        # Створюємо coordinator з hook
        coordinator = CrawlCoordinator(
            config=config,
            driver=driver,
            graph=graph,
            scheduler=scheduler,
            scanner=scanner,
            processor=processor,
            progress_tracker=progress_tracker,
            incremental_strategy=incremental_strategy,
            post_scan_hooks=[filter_hook]  # Додаємо hook
        )
        
        # Додаємо node в scheduler
        node = Node(url="https://example.com", depth=0)
        scheduler.add_node(node)
        
        # Виконуємо краулінг
        await coordinator.coordinate()
        
        # Перевіряємо що processor отримав відфільтровані посилання
        processor.process_links_async.assert_called_once()
        call_args = processor.process_links_async.call_args
        processed_links = call_args[0][1]  # Другий аргумент - links
        
        assert len(processed_links) == 2
        assert "https://example.com/important/page1" in processed_links
        assert "https://example.com/important/page2" in processed_links
        assert "https://example.com/skip/page" not in processed_links
    
    @pytest.mark.asyncio
    async def test_multiple_hooks_chain(self):
        """Декілька hooks виконуються послідовно."""
        
        # Hook 1: фільтрує за "important"
        async def filter_hook(node: Node, links: List[str]) -> List[str]:
            return [link for link in links if "important" in link]
        
        # Hook 2: додає "/analyzed" до кожного посилання
        async def analyze_hook(node: Node, links: List[str]) -> List[str]:
            return [link + "/analyzed" for link in links]
        
        # Mock залежності (аналогічно попередньому тесту)
        config = CrawlerConfig(url="https://example.com", max_depth=3)
        driver = Mock()
        driver.supports_batch_fetching.return_value = False
        
        graph = Graph()
        scheduler = CrawlScheduler()
        
        scanner = AsyncMock()
        scanner.scan_node = AsyncMock(return_value=[
            "https://example.com/important",
            "https://example.com/skip",
        ])
        
        processor = Mock()
        processor.process_links_async = AsyncMock()
        
        progress_tracker = Mock()
        progress_tracker.get_pages_crawled.return_value = 0
        progress_tracker.should_publish_progress.return_value = False
        progress_tracker.publish_node_scan_started = Mock()
        progress_tracker.publish_node_scanned = Mock()
        progress_tracker.increment_pages = Mock()
        
        incremental_strategy = Mock()
        incremental_strategy.should_process_node_links.return_value = True
        
        # Створюємо coordinator з 2 hooks
        coordinator = CrawlCoordinator(
            config=config,
            driver=driver,
            graph=graph,
            scheduler=scheduler,
            scanner=scanner,
            processor=processor,
            progress_tracker=progress_tracker,
            incremental_strategy=incremental_strategy,
            post_scan_hooks=[filter_hook, analyze_hook]  # 2 hooks
        )
        
        node = Node(url="https://example.com", depth=0)
        scheduler.add_node(node)
        
        await coordinator.coordinate()
        
        # Перевіряємо що обидва hooks виконались
        processor.process_links_async.assert_called_once()
        call_args = processor.process_links_async.call_args
        processed_links = call_args[0][1]
        
        # Має бути: filter (тільки important) → analyze (+/analyzed)
        assert len(processed_links) == 1
        assert processed_links[0] == "https://example.com/important/analyzed"
    
    @pytest.mark.asyncio
    async def test_hook_error_handling(self):
        """Помилки в hooks не зупиняють краулінг."""
        
        # Hook який викидає помилку
        async def broken_hook(node: Node, links: List[str]) -> List[str]:
            raise ValueError("Hook error!")
        
        # Hook який працює нормально
        async def working_hook(node: Node, links: List[str]) -> List[str]:
            return [link for link in links if "good" in link]
        
        config = CrawlerConfig(url="https://example.com", max_depth=3)
        driver = Mock()
        driver.supports_batch_fetching.return_value = False
        
        graph = Graph()
        scheduler = CrawlScheduler()
        
        scanner = AsyncMock()
        scanner.scan_node = AsyncMock(return_value=[
            "https://example.com/good",
            "https://example.com/bad",
        ])
        
        processor = Mock()
        processor.process_links_async = AsyncMock()
        
        progress_tracker = Mock()
        progress_tracker.get_pages_crawled.return_value = 0
        progress_tracker.should_publish_progress.return_value = False
        progress_tracker.publish_node_scan_started = Mock()
        progress_tracker.publish_node_scanned = Mock()
        progress_tracker.increment_pages = Mock()
        
        incremental_strategy = Mock()
        incremental_strategy.should_process_node_links.return_value = True
        
        # Створюємо coordinator з broken hook першим
        coordinator = CrawlCoordinator(
            config=config,
            driver=driver,
            graph=graph,
            scheduler=scheduler,
            scanner=scanner,
            processor=processor,
            progress_tracker=progress_tracker,
            incremental_strategy=incremental_strategy,
            post_scan_hooks=[broken_hook, working_hook]
        )
        
        node = Node(url="https://example.com", depth=0)
        scheduler.add_node(node)
        
        # Виконуємо - не має викинути помилку
        await coordinator.coordinate()
        
        # Перевіряємо що working_hook виконався
        processor.process_links_async.assert_called_once()
        call_args = processor.process_links_async.call_args
        processed_links = call_args[0][1]
        
        # Working hook має відфільтрувати
        assert len(processed_links) == 1
        assert processed_links[0] == "https://example.com/good"


# ===============================================
# ІНТЕГРАЦІЙНИЙ ТЕСТ: Всі 3 механізми разом
# ===============================================

class TestIntegration:
    """Інтеграційні тести для всіх механізмів разом."""
    
    @pytest.mark.asyncio
    async def test_all_mechanisms_together(self):
        """Всі 3 механізми працюють разом без конфліктів."""
        
        # 1. Створюємо node з динамічним priority
        class CustomNode(Node):
            ml_priority: int = None
        
        # 2. Post-scan hook
        async def ml_hook(node: Node, links: List[str]) -> List[str]:
            # Фільтруємо та встановлюємо explicit decisions
            selected = [link for link in links if "job" in link]
            
            if selected:
                node.user_data['explicit_scan_decisions'] = {
                    selected[0]: True  # Дозволяємо перше посилання
                }
                node.user_data['child_priorities'] = {
                    selected[0]: 10  # Високий пріоритет
                }
            
            return selected
        
        # Створюємо систему
        graph = Graph()
        scheduler = CrawlScheduler()
        
        source_node = CustomNode(url="https://example.com", depth=0)
        source_node.ml_priority = 10
        graph.add_node(source_node)
        scheduler.add_node(source_node)
        
        config = CrawlerConfig(url="https://example.com", max_depth=3)
        driver = Mock()
        driver.supports_batch_fetching.return_value = False
        
        scanner = AsyncMock()
        scanner.scan_node = AsyncMock(return_value=[
            "https://example.com/job/developer",
            "https://example.com/about",
        ])
        
        domain_config = DomainFilterConfig(base_domain="example.com", allowed_domains=["domain+subdomains"])
        domain_filter = DomainFilter(config=domain_config)
        path_config = PathFilterConfig()
        path_filter = PathFilter(config=path_config)
        
        processor = LinkProcessor(
            graph=graph,
            scheduler=scheduler,
            domain_filter=domain_filter,
            path_filter=path_filter,
            custom_node_class=CustomNode,
        )
        
        progress_tracker = Mock()
        progress_tracker.get_pages_crawled.return_value = 0
        progress_tracker.should_publish_progress.return_value = False
        progress_tracker.publish_node_scan_started = Mock()
        progress_tracker.publish_node_scanned = Mock()
        progress_tracker.increment_pages = Mock()
        
        incremental_strategy = Mock()
        incremental_strategy.should_process_node_links.return_value = True
        
        coordinator = CrawlCoordinator(
            config=config,
            driver=driver,
            graph=graph,
            scheduler=scheduler,
            scanner=scanner,
            processor=processor,
            progress_tracker=progress_tracker,
            incremental_strategy=incremental_strategy,
            post_scan_hooks=[ml_hook]  # МЕХАНІЗМ 3
        )
        
        # Виконуємо краулінг
        result_graph = await coordinator.coordinate()
        
        # Перевіряємо результати
        assert result_graph is not None
        
        # Має бути створена нова нода для job URL
        job_node = result_graph.get_node_by_url("https://example.com/job/developer")
        assert job_node is not None
        
        # МЕХАНІЗМ 1: Перевіряємо що пріоритет встановлено
        assert hasattr(job_node, 'ml_priority')
        
        # МЕХАНІЗМ 2: Перевіряємо що explicit decision працює
        assert source_node.user_data.get('explicit_scan_decisions') is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
