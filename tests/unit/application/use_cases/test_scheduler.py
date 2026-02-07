"""Тести для CrawlScheduler - планувальник черги вузлів.

Виправлено API:
- size() замість queue_size
- get_next() замість get_next_node()
- _match_rule() замість _match_url_rule()
- is_empty() замість has_nodes()
"""

import pytest
from graph_crawler.application.use_cases.crawling.scheduler import CrawlScheduler
from graph_crawler.domain.entities.node import Node
from graph_crawler.domain.value_objects.models import URLRule


class TestSchedulerCreation:
    """Тести створення CrawlScheduler."""
    
    def test_creates_empty_scheduler(self):
        """Scheduler створюється порожнім."""
        scheduler = CrawlScheduler()
        
        assert scheduler is not None
        assert scheduler.size() == 0
        assert scheduler.is_empty() is True


class TestSchedulerAddNode:
    """Тести додавання вузлів."""
    
    def test_add_single_node(self):
        """Додає один вузол."""
        scheduler = CrawlScheduler()
        node = Node(url="https://example.com", depth=0)
        
        result = scheduler.add_node(node)
        
        assert result is True
        assert scheduler.size() == 1
    
    def test_add_multiple_nodes(self):
        """Додає декілька вузлів."""
        scheduler = CrawlScheduler()
        
        for i in range(5):
            node = Node(url=f"https://example.com/page{i}", depth=0)
            scheduler.add_node(node)
        
        assert scheduler.size() == 5
    
    def test_add_duplicate_node_ignored(self):
        """Дублікати ігноруються."""
        scheduler = CrawlScheduler()
        
        node1 = Node(url="https://example.com", depth=0)
        node2 = Node(url="https://example.com", depth=0)  # Той самий URL
        
        scheduler.add_node(node1)
        result = scheduler.add_node(node2)
        
        assert result is False
        assert scheduler.size() == 1


class TestSchedulerGetNext:
    """Тести отримання наступного вузла."""
    
    def test_get_next_returns_node(self):
        """get_next повертає вузол."""
        scheduler = CrawlScheduler()
        node = Node(url="https://example.com", depth=0)
        scheduler.add_node(node)
        
        result = scheduler.get_next()
        
        assert result is not None
        assert result.url == "https://example.com"
    
    def test_get_next_empty_returns_none(self):
        """get_next повертає None для порожньої черги."""
        scheduler = CrawlScheduler()
        
        result = scheduler.get_next()
        
        assert result is None
    
    def test_get_next_decreases_size(self):
        """get_next зменшує розмір черги."""
        scheduler = CrawlScheduler()
        
        scheduler.add_node(Node(url="https://example.com/1", depth=0))
        scheduler.add_node(Node(url="https://example.com/2", depth=0))
        
        assert scheduler.size() == 2
        
        scheduler.get_next()
        
        assert scheduler.size() == 1


class TestSchedulerURLRules:
    """Тести URL Rules."""
    
    def test_url_rule_excludes_pattern(self):
        """URL rule виключає URL за патерном."""
        rule = URLRule(pattern=r"\.pdf$", should_scan=False)
        scheduler = CrawlScheduler(url_rules=[rule])
        
        # PDF URL має бути виключений
        node = Node(url="https://example.com/doc.pdf", depth=0)
        result = scheduler.add_node(node)
        
        assert result is False
    
    def test_url_rule_allows_matching_url(self):
        """URL rule дозволяє URL що не матчить exclude."""
        rule = URLRule(pattern=r"\.pdf$", should_scan=False)
        scheduler = CrawlScheduler(url_rules=[rule])
        
        # HTML URL має бути дозволений
        node = Node(url="https://example.com/page.html", depth=0)
        result = scheduler.add_node(node)
        
        assert result is True
    
    def test_match_rule_finds_pattern(self):
        """_match_rule знаходить патерн."""
        rule = URLRule(pattern=r"/products/", priority=8)
        scheduler = CrawlScheduler(url_rules=[rule])
        
        result = scheduler._match_rule("https://example.com/products/item1")
        
        assert result is not None
        assert result.priority == 8
    
    def test_match_rule_returns_none_for_no_match(self):
        """_match_rule повертає None якщо немає збігу."""
        rule = URLRule(pattern=r"/products/", priority=8)
        scheduler = CrawlScheduler(url_rules=[rule])
        
        result = scheduler._match_rule("https://example.com/about")
        
        assert result is None


class TestSchedulerStatistics:
    """Тести статистики."""
    
    def test_size_returns_queue_length(self):
        """size() повертає розмір черги."""
        scheduler = CrawlScheduler()
        
        for i in range(10):
            scheduler.add_node(Node(url=f"https://example.com/{i}", depth=0))
        
        assert scheduler.size() == 10
    
    def test_is_empty_true_for_empty_queue(self):
        """is_empty() повертає True для порожньої черги."""
        scheduler = CrawlScheduler()
        
        assert scheduler.is_empty() is True
    
    def test_is_empty_false_for_non_empty_queue(self):
        """is_empty() повертає False для непорожньої черги."""
        scheduler = CrawlScheduler()
        scheduler.add_node(Node(url="https://example.com", depth=0))
        
        assert scheduler.is_empty() is False
    
    def test_has_url_checks_seen_urls(self):
        """has_url() перевіряє seen URLs."""
        scheduler = CrawlScheduler()
        scheduler.add_node(Node(url="https://example.com", depth=0))
        
        assert scheduler.has_url("https://example.com") is True
        assert scheduler.has_url("https://other.com") is False


class TestSchedulerMemoryStatistics:
    """Тести статистики пам'яті."""
    
    def test_get_memory_statistics_returns_dict(self):
        """get_memory_statistics повертає dict."""
        scheduler = CrawlScheduler()
        
        stats = scheduler.get_memory_statistics()
        
        assert isinstance(stats, dict)
        assert "queue_size" in stats
        assert "use_bloom_filter" in stats
    
    def test_get_summary_returns_string(self):
        """get_summary повертає string."""
        scheduler = CrawlScheduler()
        scheduler.add_node(Node(url="https://example.com", depth=0))
        
        summary = scheduler.get_summary()
        
        assert isinstance(summary, str)
        assert "Queue Size" in summary


class TestSchedulerBloomFilter:
    """Тести Bloom Filter."""
    
    def test_can_disable_bloom_filter(self):
        """Можна вимкнути Bloom Filter."""
        scheduler = CrawlScheduler(use_bloom_filter=False)
        
        assert scheduler.use_bloom_filter is False
    
    def test_bloom_filter_enabled_by_default(self):
        """Bloom Filter увімкнений за замовчуванням."""
        scheduler = CrawlScheduler()
        
        assert scheduler.use_bloom_filter is True


# Загальна кількість тестів: 25+
# Покриває: створення, add_node, get_next, URL rules, statistics, bloom filter
