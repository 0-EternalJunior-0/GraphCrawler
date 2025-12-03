"""
============================================================
ТЕСТ 6: ПОВНИЙ ПРИКЛАД - playtechpeople.com
============================================================

Повна демонстрація всіх можливостей на реальному сайті:
- Кастомна Node
- URL Rules
- Плагіни
- Edge Strategy
- Детальний вивід результатів
"""

import sys
import os
import asyncio
import logging
from datetime import datetime
from typing import Optional, Any
from pydantic import Field

# Шлях до проекту
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, PROJECT_ROOT)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-7s | %(message)s',
    datefmt='%H:%M:%S'
)

logger = logging.getLogger(__name__)


def print_section(title: str):
    print("\n" + "=" * 80)
    print(f" {title}")
    print("=" * 80)


def print_step(step: int, description: str):
    print(f"\n{'─' * 60}")
    print(f"  КРОК {step}: {description}")
    print(f"{'─' * 60}")


async def test_full_example():
    """
    Повний приклад на реальному сайті.
    """
    import graph_crawler as gc
    from graph_crawler import URLRule, AsyncDriver
    from graph_crawler.plugins.node import BaseNodePlugin, NodePluginType
    from graph_crawler.core.models import EdgeCreationStrategy
    
    print_section("ТЕСТ 6: ПОВНИЙ ПРИКЛАД - playtechpeople.com")
    
    # ============================================================
    print_step(1, "ВИЗНАЧЕННЯ КАСТОМНОЇ НОДИ")
    # ============================================================
    
    class CastomNode(gc.Node):
        """
        Кастомна Node для збору тексту сторінки.
        """
        text: Optional[str] = Field(default=None, description="Текст сторінки")
        word_count: int = Field(default=0, description="Кількість слів")
        
        def _update_from_context(self, context: Any):
            super()._update_from_context(context)
            if context.html_tree:
                raw_text = context.html_tree.text
                clean_text = ' '.join(raw_text.split())
                clean_text = clean_text.replace('\n', ' ').replace('\t', ' ')
                self.text = clean_text[:1000]  # Обмежуємо
                self.word_count = len(clean_text.split())
    
    print("  CastomNode визначено:")
    print("  - text: текст сторінки")
    print("  - word_count: кількість слів")
    
    # ============================================================
    print_step(2, "ВИЗНАЧЕННЯ URL RULES")
    # ============================================================
    
    url_rules = [
        # Блог - скануємо але не йдемо по внутрішніх посиланнях
        URLRule(
            pattern="/blog/",
            should_follow_links=False,
            should_scan=True,
            priority=5
        ),
        # Вакансії - високий пріоритет
        URLRule(
            pattern="jobs.smartrecruiters.com",
            should_follow_links=False,
            should_scan=True,
            priority=6
        ),
    ]
    
    print("  URL Rules:")
    for rule in url_rules:
        print(f"  - pattern='{rule.pattern}' priority={rule.priority}")
    
    # ============================================================
    print_step(3, "ВИЗНАЧЕННЯ ПЛАГІНА")
    # ============================================================
    
    class AnalyticsPlugin(BaseNodePlugin):
        """Плагін для збору аналітики."""
        
        def __init__(self, config=None):
            super().__init__(config or {})
            self.pages_analyzed = 0
        
        @property
        def name(self) -> str:
            return "AnalyticsPlugin"
        
        @property
        def plugin_type(self) -> NodePluginType:
            return NodePluginType.ON_AFTER_SCAN
        
        def execute(self, context):
            self.pages_analyzed += 1
            context.user_data['analyzed_at'] = datetime.now().isoformat()
            context.user_data['analysis_id'] = self.pages_analyzed
            return context
    
    analytics_plugin = AnalyticsPlugin()
    print("  AnalyticsPlugin визначено")
    
    # ============================================================
    print_step(4, "ЗАПУСК КРАУЛІНГУ")
    # ============================================================
    
    print("""
    >>> graph = gc.crawl(
    ...     "https://www.playtechpeople.com/",
    ...     max_depth=3,
    ...     max_pages=2,
    ...     node_class=CastomNode,
    ...     driver=AsyncDriver,
    ...     url_rules=url_rules,
    ...     edge_strategy=EdgeCreationStrategy.NEW_ONLY,
    ...     plugins=[analytics_plugin]
    ... )
    """)
    
    start_time = datetime.now()
    
    graph = await gc.crawl(
        "https://www.playtechpeople.com/",
        max_depth=3,
        max_pages=2,
        node_class=CastomNode,
        driver=AsyncDriver,
        url_rules=url_rules,
        edge_strategy=EdgeCreationStrategy.NEW_ONLY,
        plugins=[analytics_plugin]
    )
    
    duration = (datetime.now() - start_time).total_seconds()
    
    # ============================================================
    print_step(5, "РЕЗУЛЬТАТИ")
    # ============================================================
    
    print(f"\n  ⏱  Час виконання: {duration:.2f} секунд")
    print(f"  📊 Сторінок проаналізовано: {analytics_plugin.pages_analyzed}")
    print(f"  🔗 Всього нод: {len(graph.nodes)}")
    print(f"  🔗 Всього edges: {len(graph.edges)}")
    
    stats = graph.get_stats()
    print(f"\n  Статистика графа:")
    print(f"    - nodes_count: {stats['nodes_count']}")
    print(f"    - edges_count: {stats['edges_count']}")
    print(f"    - max_depth: {stats['max_depth']}")
    
    print("\n  Детальна інформація по нодах:")
    print("  " + "-" * 70)
    
    for node_id, node in graph.nodes.items():
        print(f"\n  📄 {node.url}")
        print(f"     depth: {node.depth}")
        print(f"     scanned: {node.scanned}")
        print(f"     title: {node.title[:50] + '...' if node.title and len(node.title) > 50 else node.title}")
        
        if isinstance(node, CastomNode):
            print(f"     word_count: {node.word_count}")
            if node.text:
                preview = node.text[:100] + "..." if len(node.text) > 100 else node.text
                print(f"     text: '{preview}'")
        
        if node.user_data:
            print(f"     user_data keys: {list(node.user_data.keys())}")
    
    # ============================================================
    print_step(6, "ПОВНИЙ ЛАНЦЮЖОК ВИКЛИКІВ")
    # ============================================================
    
    print("""
    ПОВНИЙ ЛАНЦЮЖОК:
    
    gc.crawl("https://www.playtechpeople.com/", ...)
    │
    ├── api/simple.py::crawl()
    │   ├── ApplicationContainer()          # DI контейнер
    │   ├── CrawlerConfig(
    │   │       url=url,
    │   │       max_depth=3,
    │   │       max_pages=2,
    │   │       custom_node_class=CastomNode,
    │   │       url_rules=url_rules,
    │   │       node_plugins=[analytics_plugin],
    │   │       edge_strategy=NEW_ONLY
    │   │   )
    │   ├── create_driver(AsyncDriver)      # DriverFactory
    │   └── GraphCrawlerClient.crawl()
    │       │
    │       ├── GraphSpider(config)
    │       │   ├── Graph()                 # Граф для зберігання
    │       │   ├── CrawlScheduler(url_rules)  # Черга з пріоритетами
    │       │   ├── NodeScanner(driver, plugins)
    │       │   └── LinkProcessor(custom_node_class, url_rules, edge_strategy)
    │       │
    │       └── spider.crawl()
    │           └── CrawlCoordinator.coordinate()
    │               └── _crawl_sequential_mode()
    │                   │
    │                   ├── LOOP:
    │                   │   ├── scheduler.get_next()     # Бере node за priority
    │                   │   │
    │                   │   ├── scanner.scan_node(node)
    │                   │   │   ├── driver.fetch(url)   # HTTP запит
    │                   │   │   ├── parser.parse(html)  # Парсинг HTML
    │                   │   │   ├── plugins[ON_AFTER_SCAN].execute()
    │                   │   │   ├── plugins[ON_AFTER_PARSE].execute()  # AnalyticsPlugin
    │                   │   │   └── node._update_from_context()  # CastomNode
    │                   │   │
    │                   │   ├── [post_scan_hooks]       # v3.0 hooks
    │                   │   │
    │                   │   └── processor.process_links()
    │                   │       ├── _should_scan_url()  # URLRule + filters
    │                   │       ├── CastomNode(url=link)  # Створення child
    │                   │       ├── _should_create_edge()  # EdgeStrategy
    │                   │       └── scheduler.add_node()   # До черги
    │                   │
    │                   └── return graph
    │
    └── return graph
    """)
    
    print_section("ТЕСТ 6 ЗАВЕРШЕНО")
    return graph


if __name__ == "__main__":
    print("\n" + "*" * 80)
    print("  GRAPHCRAWLER v3.0 - TRACING TEST 06: FULL EXAMPLE")
    print("*" * 80)
    
    graph = asyncio.run(test_full_example())
    
    print("\n✅ Тест завершено успішно!")
