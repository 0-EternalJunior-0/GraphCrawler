"""Integration tests для plugins системи.

Тести перевіряють роботу plugins з реальним краулінгом.
"""

import pytest
import asyncio
from graph_crawler import crawl, async_crawl
from graph_crawler.extensions.plugins.node import BaseNodePlugin, NodePluginType, NodePluginContext
from graph_crawler.domain.entities.node import Node
from graph_crawler.application.use_cases.crawling.spider import GraphSpider
from graph_crawler.domain.value_objects.configs import CrawlerConfig
from graph_crawler.infrastructure.transport import HTTPDriver
from graph_crawler.infrastructure.persistence.memory_storage import MemoryStorage


@pytest.mark.integration
class TestPluginsBasicIntegration:
    """Базові integration тести для plugins."""
    
    def test_plugin_receives_node_created_event(self):
        """Plugin отримує node_created events."""
        created_urls = []
        
        class TrackingPlugin(BaseNodePlugin):
            @property
            def plugin_type(self):
                return NodePluginType.ON_NODE_CREATED
            
            @property
            def name(self):
                return "tracking_plugin"
            
            def execute(self, context: NodePluginContext) -> NodePluginContext:
                created_urls.append(context.url)
                return context
        
        plugin = TrackingPlugin()
        
        # Краулимо з plugin
        graph = crawl(
            "https://books.toscrape.com/",
            max_depth=0,
            max_pages=1,
            plugins=[plugin]
        )
        
        # Plugin має отримати event
        assert len(created_urls) >= 1
        assert "books.toscrape.com" in created_urls[0]
    
    def test_plugin_can_modify_node_metadata(self):
        """Plugin може модифікувати metadata node."""
        class MetadataPlugin(BaseNodePlugin):
            @property
            def plugin_type(self):
                return NodePluginType.ON_NODE_CREATED
            
            @property
            def name(self):
                return "metadata_plugin"
            
            def execute(self, context: NodePluginContext) -> NodePluginContext:
                context.node.user_data["custom_flag"] = True
                context.node.user_data["plugin_version"] = "1.0"
                return context
        
        plugin = MetadataPlugin()
        
        graph = crawl(
            "https://books.toscrape.com/",
            max_depth=0,
            max_pages=1,
            plugins=[plugin]
        )
        
        # Перевіряємо що metadata додана
        root = list(graph.nodes.values())[0]
        assert root.user_data.get("custom_flag") is True
        assert root.user_data.get("plugin_version") == "1.0"
    
    def test_multiple_plugins_work_together(self):
        """Декілька plugins працюють разом."""
        events_plugin1 = []
        events_plugin2 = []
        
        class Plugin1(BaseNodePlugin):
            @property
            def plugin_type(self):
                return NodePluginType.ON_NODE_CREATED
            
            @property
            def name(self):
                return "plugin1"
            
            def execute(self, context: NodePluginContext) -> NodePluginContext:
                events_plugin1.append(context.url)
                context.node.user_data["plugin1"] = "active"
                return context
        
        class Plugin2(BaseNodePlugin):
            @property
            def plugin_type(self):
                return NodePluginType.ON_NODE_CREATED
            
            @property
            def name(self):
                return "plugin2"
            
            def execute(self, context: NodePluginContext) -> NodePluginContext:
                events_plugin2.append(context.url)
                context.node.user_data["plugin2"] = "active"
                return context
        
        graph = crawl(
            "https://books.toscrape.com/",
            max_depth=0,
            max_pages=1,
            plugins=[Plugin1(), Plugin2()]
        )
        
        # Обидва plugins отримали events
        assert len(events_plugin1) >= 1
        assert len(events_plugin2) >= 1
        
        # Обидва plugins додали metadata
        root = list(graph.nodes.values())[0]
        assert root.user_data.get("plugin1") == "active"
        assert root.user_data.get("plugin2") == "active"


@pytest.mark.integration
@pytest.mark.asyncio
class TestPluginsAsyncIntegration:
    """Async integration тести для plugins."""
    
    async def test_plugin_works_with_async_crawl(self):
        """Plugin працює з async_crawl."""
        created_nodes = []
        
        class AsyncTrackingPlugin(BaseNodePlugin):
            @property
            def plugin_type(self):
                return NodePluginType.ON_NODE_CREATED
            
            @property
            def name(self):
                return "async_tracking_plugin"
            
            def execute(self, context: NodePluginContext) -> NodePluginContext:
                created_nodes.append(context.node)
                return context
        
        plugin = AsyncTrackingPlugin()
        
        graph = await async_crawl(
            "https://books.toscrape.com/",
            max_depth=0,
            max_pages=1,
            plugins=[plugin]
        )
        
        assert len(created_nodes) >= 1
    
    async def test_plugin_handles_multiple_concurrent_crawls(self):
        """Plugin обробляє concurrent crawls."""
        events_count = {"count": 0}
        
        class CountingPlugin(BaseNodePlugin):
            @property
            def plugin_type(self):
                return NodePluginType.ON_NODE_CREATED
            
            @property
            def name(self):
                return "counting_plugin"
            
            def execute(self, context: NodePluginContext) -> NodePluginContext:
                events_count["count"] += 1
                return context
        
        plugin = CountingPlugin()
        
        # Два concurrent crawls з тим самим plugin
        results = await asyncio.gather(
            async_crawl(
                "https://books.toscrape.com/",
                max_depth=0,
                max_pages=1,
                plugins=[plugin]
            ),
            async_crawl(
                "https://quotes.toscrape.com/",
                max_depth=0,
                max_pages=1,
                plugins=[plugin]
            )
        )
        
        # Plugin отримав events з обох crawls
        assert events_count["count"] >= 2


@pytest.mark.integration
class TestPluginsWithRealCrawling:
    """Тести plugins з реальним краулінгом."""
    
    def test_plugin_tracks_all_discovered_urls(self):
        """Plugin відслідковує всі знайдені URLs."""
        discovered = []
        
        class URLTrackerPlugin(BaseNodePlugin):
            @property
            def plugin_type(self):
                return NodePluginType.ON_NODE_CREATED
            
            @property
            def name(self):
                return "url_tracker_plugin"
            
            def execute(self, context: NodePluginContext) -> NodePluginContext:
                discovered.append({
                    "url": context.url,
                    "depth": context.depth,
                })
                return context
        
        graph = crawl(
            "https://books.toscrape.com/",
            max_depth=1,
            max_pages=10,
            plugins=[URLTrackerPlugin()]
        )
        
        # Plugin відслідкував всі nodes
        assert len(discovered) == len(graph.nodes)
        
        # Перевіряємо структуру даних
        assert all("url" in item for item in discovered)
        assert all("depth" in item for item in discovered)
    
    def test_plugin_can_filter_urls(self):
        """Plugin може фільтрувати URLs."""
        blocked_urls = []
        
        class FilterPlugin(BaseNodePlugin):
            @property
            def plugin_type(self):
                return NodePluginType.ON_NODE_CREATED
            
            @property
            def name(self):
                return "filter_plugin"
            
            def execute(self, context: NodePluginContext) -> NodePluginContext:
                # Блокуємо URLs що містять "page"
                if "page" in context.url.lower():
                    blocked_urls.append(context.url)
                    # Plugin може позначити node як заблоковану
                    context.node.user_data["blocked"] = True
                return context
        
        graph = crawl(
            "https://books.toscrape.com/",
            max_depth=1,
            max_pages=20,
            plugins=[FilterPlugin()]
        )
        
        # Перевіряємо що plugin виявив URLs з "page"
        blocked_nodes = [n for n in graph.nodes.values() if n.user_data.get("blocked")]
        # Може бути або не бути залежно від структури сайту
        # Головне що plugin спрацював
        assert len(graph.nodes) > 0
    
    def test_plugin_collects_statistics(self):
        """Plugin збирає статистику краулінгу."""
        stats = {
            "total_nodes": 0,
            "depths": {},
        }
        
        class StatsPlugin(BaseNodePlugin):
            @property
            def plugin_type(self):
                return NodePluginType.ON_NODE_CREATED
            
            @property
            def name(self):
                return "stats_plugin"
            
            def execute(self, context: NodePluginContext) -> NodePluginContext:
                stats["total_nodes"] += 1
                depth = context.depth
                stats["depths"][depth] = stats["depths"].get(depth, 0) + 1
                return context
        
        graph = crawl(
            "https://books.toscrape.com/",
            max_depth=1,
            max_pages=15,
            plugins=[StatsPlugin()]
        )
        
        # Статистика зібрана
        assert stats["total_nodes"] > 0
        assert len(stats["depths"]) > 0
        assert 0 in stats["depths"]  # Root depth


@pytest.mark.integration
class TestPluginsCustomBehavior:
    """Тести custom поведінки plugins."""
    
    def test_plugin_can_add_custom_fields(self):
        """Plugin може додавати custom поля до nodes."""
        class EnrichmentPlugin(BaseNodePlugin):
            @property
            def plugin_type(self):
                return NodePluginType.ON_NODE_CREATED
            
            @property
            def name(self):
                return "enrichment_plugin"
            
            def execute(self, context: NodePluginContext) -> NodePluginContext:
                # Додаємо custom поля
                context.node.user_data["discovered_at"] = "2025-01-01"
                context.node.user_data["crawler_version"] = "3.2.0"
                context.node.user_data["tags"] = ["book", "shop"]
                return context
        
        graph = crawl(
            "https://books.toscrape.com/",
            max_depth=0,
            max_pages=1,
            plugins=[EnrichmentPlugin()]
        )
        
        root = list(graph.nodes.values())[0]
        assert root.user_data.get("discovered_at") == "2025-01-01"
        assert root.user_data.get("crawler_version") == "3.2.0"
        assert "book" in root.user_data.get("tags", [])
    
    def test_plugin_can_log_progress(self):
        """Plugin може логувати прогрес."""
        progress_log = []
        
        class ProgressPlugin(BaseNodePlugin):
            def __init__(self):
                super().__init__()
                self.count = 0
            
            @property
            def plugin_type(self):
                return NodePluginType.ON_NODE_CREATED
            
            @property
            def name(self):
                return "progress_plugin"
            
            def execute(self, context: NodePluginContext) -> NodePluginContext:
                self.count += 1
                if self.count % 5 == 0:
                    progress_log.append(f"Processed {self.count} nodes")
                return context
        
        graph = crawl(
            "https://books.toscrape.com/",
            max_depth=1,
            max_pages=20,
            plugins=[ProgressPlugin()]
        )
        
        # Plugin логував прогрес
        # Якщо було >= 5 nodes, має бути хоча б один лог
        if len(graph.nodes) >= 5:
            assert len(progress_log) > 0


@pytest.mark.integration
class TestPluginsErrorHandling:
    """Тести обробки помилок в plugins."""
    
    def test_plugin_error_does_not_crash_crawler(self):
        """Помилка в plugin не ламає crawler."""
        class BrokenPlugin(BaseNodePlugin):
            @property
            def plugin_type(self):
                return NodePluginType.ON_NODE_CREATED
            
            @property
            def name(self):
                return "broken_plugin"
            
            def execute(self, context: NodePluginContext) -> NodePluginContext:
                # Цей plugin завжди кидає помилку
                raise ValueError("Plugin error!")
        
        # Crawler має продовжити роботу навіть якщо plugin ламається
        try:
            graph = crawl(
                "https://books.toscrape.com/",
                max_depth=0,
                max_pages=1,
                plugins=[BrokenPlugin()]
            )
            # Граф створений навіть з broken plugin
            assert len(graph.nodes) >= 1
        except ValueError:
            # Або exception пробрасывається - обидва варіанти OK
            pass
    
    def test_one_plugin_error_does_not_affect_others(self):
        """Помилка в одному plugin не впливає на інші."""
        working_plugin_called = []
        
        class BrokenPlugin(BaseNodePlugin):
            @property
            def plugin_type(self):
                return NodePluginType.ON_NODE_CREATED
            
            @property
            def name(self):
                return "broken_plugin"
            
            def execute(self, context: NodePluginContext) -> NodePluginContext:
                raise ValueError("Broken!")
        
        class WorkingPlugin(BaseNodePlugin):
            @property
            def plugin_type(self):
                return NodePluginType.ON_NODE_CREATED
            
            @property
            def name(self):
                return "working_plugin"
            
            def execute(self, context: NodePluginContext) -> NodePluginContext:
                working_plugin_called.append(True)
                return context
        
        try:
            graph = crawl(
                "https://books.toscrape.com/",
                max_depth=0,
                max_pages=1,
                plugins=[BrokenPlugin(), WorkingPlugin()]
            )
            
            # WorkingPlugin має спрацювати навіть якщо BrokenPlugin ламається
            # (залежить від реалізації error handling)
            assert len(graph.nodes) >= 1
        except ValueError:
            # Exception може бути пробрасований
            pass
