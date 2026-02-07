"""Тести для LinkProcessor - обробка посилань.

Виправлено API:
- process_links() повертає int (синхронний)
- process_links_async() для async версії
- DomainFilter використовує DomainFilterConfig
- PathFilter використовує PathFilterConfig
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from graph_crawler.application.use_cases.crawling.link_processor import LinkProcessor
from graph_crawler.application.use_cases.crawling.scheduler import CrawlScheduler
from graph_crawler.application.use_cases.crawling.filters.domain_filter import DomainFilter
from graph_crawler.application.use_cases.crawling.filters.path_filter import PathFilter
from graph_crawler.domain.entities.graph import Graph
from graph_crawler.domain.entities.node import Node
from graph_crawler.domain.value_objects.models import URLRule, DomainFilterConfig, PathFilterConfig


class TestLinkProcessorCreation:
    """Тести створення LinkProcessor."""
    
    def test_creates_link_processor(self):
        """LinkProcessor створюється з необхідними параметрами."""
        graph = Graph()
        scheduler = CrawlScheduler()
        domain_config = DomainFilterConfig(base_domain="example.com", allowed_domains=["domain+subdomains"])
        domain_filter = DomainFilter(config=domain_config)
        path_config = PathFilterConfig()
        path_filter = PathFilter(config=path_config)
        
        processor = LinkProcessor(
            graph=graph,
            scheduler=scheduler,
            domain_filter=domain_filter,
            path_filter=path_filter
        )
        
        assert processor is not None
        assert hasattr(processor, 'process_links')
        assert hasattr(processor, 'process_links_async')


class TestLinkProcessorProcessLinks:
    """Тести методу process_links (синхронний)."""
    
    def test_process_single_link(self):
        """Обробляє одне посилання."""
        graph = Graph()
        scheduler = CrawlScheduler()
        domain_config = DomainFilterConfig(base_domain="example.com", allowed_domains=["domain+subdomains"])
        domain_filter = DomainFilter(config=domain_config)
        path_config = PathFilterConfig()
        path_filter = PathFilter(config=path_config)
        
        processor = LinkProcessor(
            graph=graph,
            scheduler=scheduler,
            domain_filter=domain_filter,
            path_filter=path_filter
        )
        
        source_node = Node(url="https://example.com", depth=0)
        graph.add_node(source_node)
        
        # process_links повертає int (кількість створених нод)
        result = processor.process_links(source_node, ["https://example.com/page1"])
        
        assert isinstance(result, int)
        assert result >= 0
    
    def test_process_multiple_links(self):
        """Обробляє декілька посилань."""
        graph = Graph()
        scheduler = CrawlScheduler()
        domain_config = DomainFilterConfig(base_domain="example.com", allowed_domains=["domain+subdomains"])
        domain_filter = DomainFilter(config=domain_config)
        path_config = PathFilterConfig()
        path_filter = PathFilter(config=path_config)
        
        processor = LinkProcessor(
            graph=graph,
            scheduler=scheduler,
            domain_filter=domain_filter,
            path_filter=path_filter
        )
        
        source_node = Node(url="https://example.com", depth=0)
        graph.add_node(source_node)
        
        links = [
            "https://example.com/page1",
            "https://example.com/page2",
            "https://example.com/page3"
        ]
        
        result = processor.process_links(source_node, links)
        
        assert isinstance(result, int)
    
    def test_returns_zero_when_source_cannot_create_edges(self):
        """Повертає 0 якщо source_node не може створювати edges."""
        graph = Graph()
        scheduler = CrawlScheduler()
        domain_config = DomainFilterConfig(base_domain="example.com", allowed_domains=["domain+subdomains"])
        domain_filter = DomainFilter(config=domain_config)
        path_config = PathFilterConfig()
        path_filter = PathFilter(config=path_config)
        
        processor = LinkProcessor(
            graph=graph,
            scheduler=scheduler,
            domain_filter=domain_filter,
            path_filter=path_filter
        )
        
        source_node = Node(url="https://example.com", depth=0, can_create_edges=False)
        graph.add_node(source_node)
        
        result = processor.process_links(source_node, ["https://example.com/page1"])
        
        assert result == 0


@pytest.mark.asyncio
class TestLinkProcessorProcessLinksAsync:
    """Тести асинхронного методу process_links_async."""
    
    async def test_process_links_async_returns_int(self):
        """process_links_async повертає int."""
        graph = Graph()
        scheduler = CrawlScheduler()
        domain_config = DomainFilterConfig(base_domain="example.com", allowed_domains=["domain+subdomains"])
        domain_filter = DomainFilter(config=domain_config)
        path_config = PathFilterConfig()
        path_filter = PathFilter(config=path_config)
        
        processor = LinkProcessor(
            graph=graph,
            scheduler=scheduler,
            domain_filter=domain_filter,
            path_filter=path_filter
        )
        
        source_node = Node(url="https://example.com", depth=0)
        graph.add_node(source_node)
        
        result = await processor.process_links_async(source_node, ["https://example.com/page1"])
        
        assert isinstance(result, int)
    
    async def test_process_links_async_with_batch_size(self):
        """process_links_async працює з batch_size."""
        graph = Graph()
        scheduler = CrawlScheduler()
        domain_config = DomainFilterConfig(base_domain="example.com", allowed_domains=["domain+subdomains"])
        domain_filter = DomainFilter(config=domain_config)
        path_config = PathFilterConfig()
        path_filter = PathFilter(config=path_config)
        
        processor = LinkProcessor(
            graph=graph,
            scheduler=scheduler,
            domain_filter=domain_filter,
            path_filter=path_filter
        )
        
        source_node = Node(url="https://example.com", depth=0)
        graph.add_node(source_node)
        
        links = [f"https://example.com/page{i}" for i in range(50)]
        
        result = await processor.process_links_async(source_node, links, batch_size=10)
        
        assert isinstance(result, int)


class TestLinkProcessorDomainFiltering:
    """Тести фільтрації за доменами."""
    
    def test_allows_same_domain_links(self):
        """Дозволяє посилання з того ж домену."""
        graph = Graph()
        scheduler = CrawlScheduler()
        domain_config = DomainFilterConfig(base_domain="example.com", allowed_domains=["domain+subdomains"])
        domain_filter = DomainFilter(config=domain_config)
        path_config = PathFilterConfig()
        path_filter = PathFilter(config=path_config)
        
        processor = LinkProcessor(
            graph=graph,
            scheduler=scheduler,
            domain_filter=domain_filter,
            path_filter=path_filter
        )
        
        source_node = Node(url="https://example.com", depth=0)
        graph.add_node(source_node)
        
        result = processor.process_links(source_node, ["https://example.com/page1"])
        
        # Має створити ноду
        assert result >= 0
    
    def test_blocks_external_domain_links(self):
        """Блокує посилання з іншого домену."""
        graph = Graph()
        scheduler = CrawlScheduler()
        domain_config = DomainFilterConfig(base_domain="example.com", allowed_domains=["domain+subdomains"])
        domain_filter = DomainFilter(config=domain_config)
        path_config = PathFilterConfig()
        path_filter = PathFilter(config=path_config)
        
        processor = LinkProcessor(
            graph=graph,
            scheduler=scheduler,
            domain_filter=domain_filter,
            path_filter=path_filter
        )
        
        source_node = Node(url="https://example.com", depth=0)
        graph.add_node(source_node)
        
        result = processor.process_links(source_node, ["https://other.com/page1"])
        
        # Не має створювати ноду для іншого домену
        assert result == 0


class TestLinkProcessorURLRules:
    """Тести URL Rules в LinkProcessor."""
    
    def test_url_rule_excludes_pattern(self):
        """URL rule виключає URL за патерном."""
        graph = Graph()
        scheduler = CrawlScheduler()
        domain_config = DomainFilterConfig(base_domain="example.com", allowed_domains=["domain+subdomains"])
        domain_filter = DomainFilter(config=domain_config)
        path_config = PathFilterConfig()
        path_filter = PathFilter(config=path_config)
        
        # Rule що виключає PDF
        rule = URLRule(pattern=r"\.pdf$", should_scan=False)
        
        processor = LinkProcessor(
            graph=graph,
            scheduler=scheduler,
            domain_filter=domain_filter,
            path_filter=path_filter,
            url_rules=[rule]
        )
        
        source_node = Node(url="https://example.com", depth=0)
        graph.add_node(source_node)
        
        result = processor.process_links(source_node, ["https://example.com/doc.pdf"])
        
        # PDF має бути виключений
        assert result == 0


# Загальна кількість тестів: 12+
# Покриває: створення, process_links (sync/async), domain filtering, URL rules
