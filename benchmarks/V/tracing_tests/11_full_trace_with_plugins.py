"""
============================================================
ТРАСУВАННЯ 11: ПОВНИЙ ВИКЛИК З ПЛАГІНАМИ
============================================================

Цей файл показує як плагіни впливають на процес краулінгу:
- Коли викликаються плагіни
- Як плагіни модифікують контекст
- Як плагіни впливають на ноди

Використання:
    python 11_full_trace_with_plugins.py
"""

import sys
import os
import asyncio
import logging
from datetime import datetime
from typing import Optional, List, Any
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


def print_header(title: str):
    print("\n" + "=" * 100)
    print(f"  {title}")
    print("=" * 100)


def print_section(title: str):
    print(f"\n{'─' * 80}")
    print(f"  📌 {title}")
    print(f"{'─' * 80}")


async def trace_with_plugins():
    """
    Трасування з плагінами.
    """
    print_header("ТРАСУВАННЯ: ВИКЛИК З ПЛАГІНАМИ")
    
    import graph_crawler as gc
    from graph_crawler import AsyncDriver
    from graph_crawler.plugins.node import BaseNodePlugin, NodePluginType, NodePluginContext
    from graph_crawler.core.models import EdgeCreationStrategy
    
    # ============================================================
    print_section("ЕТАП 1: СИСТЕМА ПЛАГІНІВ")
    # ============================================================
    
    print("""
    GraphCrawler v3.0 має 4 типи плагінів для нод:
    
    1. ON_NODE_CREATED - при створенні ноди (тільки URL)
       └── Використання: аналіз URL, встановлення should_scan
    
    2. ON_BEFORE_SCAN - перед скануванням
       └── Використання: підготовка до сканування
    
    3. ON_HTML_PARSED - після парсингу HTML
       └── Використання: витягування даних з HTML
    
    4. ON_AFTER_SCAN - після сканування
       └── Використання: пост-обробка, встановлення пріоритетів
    
    Порядок виконання:
    Node created → ON_NODE_CREATED
    Scanner starts → ON_BEFORE_SCAN
    HTML parsed → ON_HTML_PARSED
    Scanner ends → ON_AFTER_SCAN
    """)
    
    # ============================================================
    print_section("ЕТАП 2: СТВОРЕННЯ КАСТОМНОГО ПЛАГІНА")
    # ============================================================
    
    class TracingPlugin(BaseNodePlugin):
        """
        Плагін для трасування всіх викликів.
        """
        
        def __init__(self):
            super().__init__()
            self.call_count = 0
        
        @property
        def name(self) -> str:
            return "TracingPlugin"
        
        @property
        def plugin_type(self) -> NodePluginType:
            # Реєструємо для ON_AFTER_SCAN (найчастіший варіант)
            return NodePluginType.ON_AFTER_SCAN
        
        def execute(self, context: NodePluginContext) -> NodePluginContext:
            self.call_count += 1
            
            print(f"\n  🔌 TracingPlugin.execute() - Виклик #{self.call_count}")
            print(f"     ├── URL: {context.url}")
            print(f"     ├── Depth: {context.depth}")
            print(f"     ├── Links знайдено: {len(context.extracted_links)}")
            print(f"     ├── Metadata keys: {list(context.metadata.keys())}")
            print(f"     └── HTML присутній: {context.html is not None}")
            
            # Плагін може модифікувати user_data
            context.user_data['traced'] = True
            context.user_data['trace_time'] = datetime.now().isoformat()
            
            return context
    
    tracing_plugin = TracingPlugin()
    
    print("""
    TracingPlugin створено:
    - Тип: ON_AFTER_SCAN
    - Логує кожен виклик
    - Додає 'traced' та 'trace_time' в user_data
    """)
    
    # ============================================================
    print_section("ЕТАП 3: СТРУКТУРА КОНТЕКСТУ ПЛАГІНА")
    # ============================================================
    
    print("""
    NodePluginContext (передається в плагін):
    
    @dataclass
    class NodePluginContext:
        # Базові дані (завжди доступні)
        node: Node
        url: str
        depth: int
        should_scan: bool
        can_create_edges: bool
        
        # HTML дані (тільки на HTML_STAGE)
        html: Optional[str] = None
        html_tree: Optional[Any] = None  # BeautifulSoup
        parser: Optional[Any] = None
        
        # Результати обробки
        metadata: Dict = field(default_factory=dict)
        user_data: Dict = field(default_factory=dict)
        extracted_links: List[str] = field(default_factory=list)
    
    Плагін МОЖЕ:
    - Читати всі поля
    - Модифікувати metadata, user_data
    - Модифікувати extracted_links (фільтрувати, додавати)
    - Встановлювати should_scan, can_create_edges
    
    Плагін НЕ МОЖЕ:
    - Змінювати url, depth (read-only)
    - Зберігати html після виконання (очищується)
    """)
    
    # ============================================================
    print_section("ЕТАП 4: ЗАПУСК КРАУЛІНГУ З ПЛАГІНОМ")
    # ============================================================
    
    print("\n  🚀 Запуск краулінгу з TracingPlugin...\n")
    
    start_time = datetime.now()
    
    graph = await gc.crawl(
        "https://httpbin.org/links/2/0",
        max_depth=1,
        max_pages=3,
        driver=AsyncDriver,
        plugins=[tracing_plugin],
        edge_strategy=EdgeCreationStrategy.NEW_ONLY,
    )
    
    duration = (datetime.now() - start_time).total_seconds()
    
    # ============================================================
    print_section("ЕТАП 5: ПОСЛІДОВНІСТЬ ВИКЛИКІВ ПЛАГІНА")
    # ============================================================
    
    print("""
    Для кожної сторінки плагіни викликаються в такій послідовності:
    
    1. Node створено → graph.add_node()
       │
       └── NodePluginManager.execute_sync(ON_NODE_CREATED, context)
           └── Всі плагіни типу ON_NODE_CREATED
    
    2. Scanner.scan_node(node)
       │
       ├── NodePluginManager.execute_sync(ON_BEFORE_SCAN, context)
       │   └── Всі плагіни типу ON_BEFORE_SCAN
       │
       ├── driver.fetch(url) → HTML
       │
       ├── node.process_html(html)
       │   │
       │   ├── BeautifulSoup.parse(html)
       │   │
       │   ├── NodePluginManager.execute_sync(ON_HTML_PARSED, context)
       │   │   └── Всі плагіни типу ON_HTML_PARSED
       │   │   └── MetadataExtractorPlugin (default)
       │   │   └── LinkExtractorPlugin (default)
       │   │
       │   └── NodePluginManager.execute_sync(ON_AFTER_SCAN, context)
       │       └── Всі плагіни типу ON_AFTER_SCAN
       │       └── TracingPlugin ← НАШ ПЛАГІН ТУТ!
       │
       └── return extracted_links
    """)
    
    # ============================================================
    print_section("ЕТАП 6: РЕЗУЛЬТАТИ")
    # ============================================================
    
    print(f"\n  ⏱️ Час виконання: {duration:.2f} секунд")
    print(f"  📊 Знайдено нод: {len(graph.nodes)}")
    print(f"  🔌 TracingPlugin викликано: {tracing_plugin.call_count} раз(ів)")
    
    print("\n  📋 Перевірка user_data (від плагіна):")
    for node_id, node in graph.nodes.items():
        print(f"\n      Node: {node.url}")
        if node.user_data.get('traced'):
            print(f"      ├── traced: ✅")
            print(f"      └── trace_time: {node.user_data.get('trace_time')}")
        else:
            print(f"      └── traced: ❌ (не просканована)")
    
    print_header("ТРАСУВАННЯ ЗАВЕРШЕНО")
    return graph


if __name__ == "__main__":
    print("\n" + "*" * 100)
    print("  GRAPHCRAWLER v3.0 - ТРАСУВАННЯ З ПЛАГІНАМИ")
    print("*" * 100)
    
    graph = asyncio.run(trace_with_plugins())
    print("\n✅ Трасування завершено успішно!")
