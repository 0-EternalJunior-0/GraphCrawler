"""
============================================================
ТЕСТ 3: КРАУЛІНГ З ПЛАГІНАМИ
============================================================

Показує:
1. Як створити власний плагін
2. Типи плагінів: ON_BEFORE_SCAN, ON_AFTER_SCAN, ON_AFTER_PARSE
3. Як плагіни модифікують контекст
4. Ланцюжок виконання плагінів
"""

import sys
import os
import asyncio
import logging
from datetime import datetime
from typing import Optional, Any, List
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


async def test_with_plugins():
    """
    Тест з кастомними плагінами.
    """
    import graph_crawler as gc
    from graph_crawler import AsyncDriver
    from graph_crawler.plugins.node import BaseNodePlugin, NodePluginType
    from graph_crawler.core.models import EdgeCreationStrategy
    
    print_section("ТЕСТ 3: КРАУЛІНГ З ПЛАГІНАМИ")
    
    # ============================================================
    print_step(1, "ТИПИ ПЛАГІНІВ")
    # ============================================================
    
    print("""
    GraphCrawler підтримує декілька типів плагінів:
    
    NodePluginType:
    - ON_BEFORE_SCAN   - Перед сканування (можна пропустити URL)
    - ON_AFTER_SCAN    - Після сканування (можна фільтрувати links)
    - ON_AFTER_PARSE   - Після парсингу (можна модифікувати node)
    
    EnginePlugin:
    - AntiBotStealthPlugin - Обхід anti-bot захисту
    - CaptchaSolverPlugin  - Розв'язання captcha
    
    DriverPlugin:
    - StealthPlugin, CloudflarePlugin, etc.
    """)
    
    # ============================================================
    print_step(2, "СТВОРЕННЯ КАСТОМНИХ ПЛАГІНІВ")
    # ============================================================
    
    class LoggingPlugin(BaseNodePlugin):
        """
        Плагін для логування кожного кроку.
        Виконується ON_AFTER_SCAN.
        """
        
        @property
        def name(self) -> str:
            return "LoggingPlugin"
        
        @property
        def plugin_type(self) -> NodePluginType:
            return NodePluginType.ON_AFTER_SCAN
        
        def execute(self, context):
            print(f"\n  🔌 LoggingPlugin.execute()")
            print(f"     URL: {context.url}")
            print(f"     Links found: {len(context.extracted_links)}")
            print(f"     Has HTML: {context.html_tree is not None}")
            return context
    
    class LinkFilterPlugin(BaseNodePlugin):
        """
        Плагін для фільтрації посилань.
        Видаляє посилання на зовнішні домени.
        """
        
        def __init__(self, config: dict = None):
            super().__init__(config or {})
            self.allowed_patterns = config.get('allowed_patterns', []) if config else []
        
        @property
        def name(self) -> str:
            return "LinkFilterPlugin"
        
        @property
        def plugin_type(self) -> NodePluginType:
            return NodePluginType.ON_AFTER_SCAN
        
        def execute(self, context):
            original_count = len(context.extracted_links)
            
            # Фільтруємо links
            if self.allowed_patterns:
                filtered = [
                    link for link in context.extracted_links
                    if any(pattern in link for pattern in self.allowed_patterns)
                ]
                context.extracted_links = filtered
            
            print(f"\n  🔌 LinkFilterPlugin.execute()")
            print(f"     Original links: {original_count}")
            print(f"     Filtered links: {len(context.extracted_links)}")
            
            return context
    
    class MetadataPlugin(BaseNodePlugin):
        """
        Плагін для збору метаданих.
        Зберігає custom дані в user_data.
        """
        
        @property
        def name(self) -> str:
            return "MetadataPlugin"
        
        @property
        def plugin_type(self) -> NodePluginType:
            return NodePluginType.ON_AFTER_SCAN
        
        def execute(self, context):
            print(f"\n  🔌 MetadataPlugin.execute()")
            
            # Зберігаємо метадані в user_data
            context.user_data['processed_at'] = datetime.now().isoformat()
            context.user_data['plugin_version'] = '1.0'
            
            # Витягуємо мета-теги якщо є HTML
            if context.html_tree is not None:
                # BeautifulSoup API
                if hasattr(context.html_tree, 'find_all'):
                    meta_tags = context.html_tree.find_all('meta', attrs={'content': True})
                    context.user_data['meta_count'] = len(meta_tags)
                    print(f"     Found {len(meta_tags)} meta tags")
                # Fallback для lxml
                elif hasattr(context.html_tree, 'xpath'):
                    meta_tags = context.html_tree.xpath('//meta/@content')
                    context.user_data['meta_count'] = len(meta_tags)
                    print(f"     Found {len(meta_tags)} meta tags")
            
            print(f"     Added metadata to user_data")
            return context
    
    print("\n  Створено 3 кастомні плагіни:")
    print("  1. LoggingPlugin (ON_AFTER_SCAN) - логування")
    print("  2. LinkFilterPlugin (ON_AFTER_SCAN) - фільтрація посилань")
    print("  3. MetadataPlugin (ON_AFTER_PARSE) - збір метаданих")
    
    # ============================================================
    print_step(3, "ІНІЦІАЛІЗАЦІЯ ПЛАГІНІВ")
    # ============================================================
    
    plugins = [
        LoggingPlugin(config={}),
        LinkFilterPlugin(config={'allowed_patterns': ['httpbin']}),
        MetadataPlugin(config={}),
    ]
    
    print(f"\n  Список плагінів:")
    for i, plugin in enumerate(plugins, 1):
        print(f"    {i}. {type(plugin).__name__} ({plugin.plugin_type.value})")
    
    # ============================================================
    print_step(4, "ЗАПУСК КРАУЛІНГУ")
    # ============================================================
    
    print("\n  >>> graph = await gc.crawl(")
    print("  ...     'https://httpbin.org/html',")
    print("  ...     max_depth=1,")
    print("  ...     max_pages=3,")
    print("  ...     plugins=[LoggingPlugin(), LinkFilterPlugin(), MetadataPlugin()]")
    print("  ... )")
    
    start_time = datetime.now()
    
    graph = await gc.crawl(
        "https://httpbin.org/html",
        max_depth=1,
        max_pages=3,
        plugins=plugins,
        driver=AsyncDriver,
        edge_strategy=EdgeCreationStrategy.NEW_ONLY,
    )
    
    duration = (datetime.now() - start_time).total_seconds()
    
    # ============================================================
    print_step(5, "РЕЗУЛЬТАТИ")
    # ============================================================
    
    print(f"\n  Краулінг завершено за {duration:.2f} секунд!")
    print(f"  Знайдено нод: {len(graph.nodes)}")
    
    print("\n  Перевірка user_data (від MetadataPlugin):")
    for node_id, node in graph.nodes.items():
        print(f"\n  Node: {node.url}")
        if node.user_data:
            for key, value in node.user_data.items():
                print(f"    user_data['{key}'] = {value}")
        else:
            print("    user_data: (empty)")
    
    # ============================================================
    print_step(6, "ПОРЯДОК ВИКОНАННЯ ПЛАГІНІВ")
    # ============================================================
    
    print("""
    Порядок виконання плагінів в NodeScanner:
    
    NodeScanner.scan_node(node):
    │
    ├── 1. ON_BEFORE_SCAN plugins
    │       └── Можуть пропустити сканування (return skip=True)
    │
    ├── 2. driver.fetch(url)
    │       └── HTTP запит до сторінки
    │
    ├── 3. parser.parse(html)
    │       └── Парсинг HTML (lxml/BeautifulSoup)
    │
    ├── 4. ON_AFTER_SCAN plugins   ← LoggingPlugin, LinkFilterPlugin
    │       └── Можуть фільтрувати extracted_links
    │
    └── 5. ON_AFTER_PARSE plugins  ← MetadataPlugin
            └── Можуть модифікувати node, user_data
    
    Потім:
    └── node._update_from_context(context)
        └── Застосовує зміни до Node
    """)
    
    print_section("ТЕСТ 3 ЗАВЕРШЕНО")
    return graph


if __name__ == "__main__":
    print("\n" + "*" * 80)
    print("  GRAPHCRAWLER v3.0 - TRACING TEST 03: PLUGINS")
    print("*" * 80)
    
    graph = asyncio.run(test_with_plugins())
    
    print("\n✅ Тест завершено успішно!")
