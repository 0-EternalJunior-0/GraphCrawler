"""
============================================================
ТЕСТ 5: ДЕМОНСТРАЦІЯ ГНУЧКОГО ЯДРА v3.0
============================================================

Показує 3 нові механізми гнучкості:
1. Dynamic Priority Support - плагіни встановлюють пріоритети
2. Explicit Filter Override - плагіни перебивають фільтри
3. Post-Scan Hooks - async hooks між scan та process
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


def print_section(title: str):
    print("\n" + "=" * 80)
    print(f" {title}")
    print("=" * 80)


def print_step(step: int, description: str):
    print(f"\n{'─' * 60}")
    print(f"  КРОК {step}: {description}")
    print(f"{'─' * 60}")


async def test_flexible_core():
    """
    Демонстрація гнучкого ядра v3.0.
    """
    import graph_crawler as gc
    from graph_crawler import AsyncDriver
    from graph_crawler.plugins.node import BaseNodePlugin, NodePluginType
    from graph_crawler.core.models import EdgeCreationStrategy
    
    print_section("ТЕСТ 5: ГНУЧКЕ ЯДРО v3.0")
    
    # ============================================================
    print_step(1, "ОГЛЯД 3 МЕХАНІЗМІВ ГНУЧКОСТІ")
    # ============================================================
    
    print("""
    v3.0 додає 3 механізми для повного контролю краулінгу:
    
    1. DYNAMIC PRIORITY SUPPORT (Scheduler)
       - Плагін може встановити node.priority
       - node.priority > URLRule.priority > default
       - Приклад: ML плагін пріоритизує релевантні сторінки
    
    2. EXPLICIT FILTER OVERRIDE (LinkProcessor)
       - node.user_data['explicit_scan_decisions'] = {url: True/False}
       - Перебиває ВСІ фільтри (Domain, Path, URLRule)
       - Приклад: ML плагін дозволяє важливі зовнішні URL
    
    3. POST-SCAN HOOKS (CrawlCoordinator)
       - async функції між scan та process_links
       - Можуть фільтрувати/модифікувати links
       - Приклад: ML API фільтрує посилання
    """)
    
    # ============================================================
    print_step(2, "КАСТОМНА НОДА З ПРІОРИТЕТОМ")
    # ============================================================
    
    class MLNode(gc.Node):
        """Node з підтримкою ML пріоритетів."""
        ml_priority: Optional[int] = Field(default=None, description="ML-assigned priority")
        ml_score: Optional[float] = Field(default=None, description="ML relevance score")
        
        @property
        def priority(self) -> Optional[int]:
            """Повертає ml_priority для Scheduler."""
            return self.ml_priority
    
    print("  MLNode клас:")
    print("  >>> class MLNode(gc.Node):")
    print("  >>>     ml_priority: Optional[int]  # Для Dynamic Priority")
    print("  >>>     ml_score: Optional[float]   # ML relevance")
    
    # ============================================================
    print_step(3, "ML DECISION PLUGIN")
    # ============================================================
    
    class MLDecisionPlugin(BaseNodePlugin):
        """
        Демо ML плагін що використовує всі 3 механізми v3.0.
        """
        
        @property
        def name(self) -> str:
            return "MLDecisionPlugin"
        
        @property
        def plugin_type(self) -> NodePluginType:
            return NodePluginType.ON_AFTER_SCAN
        
        def execute(self, context):
            print(f"\n  🤖 MLDecisionPlugin.execute()")
            print(f"     URL: {context.url}")
            print(f"     Links: {len(context.extracted_links)}")
            
            # Симулюємо ML аналіз
            priorities = {}
            explicit_decisions = {}
            
            for link in context.extracted_links:
                # Симуляція ML score
                if 'links' in link:
                    score = 0.9  # Високий score
                    priorities[link] = 10  # Високий пріоритет
                    print(f"     ⭐ High priority: {link} (score={score})")
                elif 'html' in link:
                    score = 0.7
                    priorities[link] = 7
                else:
                    score = 0.3
                    priorities[link] = 3
            
            # МЕХАНІЗМ 1: Dynamic Priority
            context.user_data['child_priorities'] = priorities
            print(f"     Set {len(priorities)} child priorities")
            
            # МЕХАНІЗМ 2: Explicit Filter Override (якщо потрібно)
            # Наприклад, дозволити зовнішній URL:
            # explicit_decisions['https://external.com'] = True
            context.user_data['explicit_scan_decisions'] = explicit_decisions
            
            return context
    
    print("\n  MLDecisionPlugin:")
    print("  - Аналізує посилання")
    print("  - Встановлює child_priorities (Dynamic Priority)")
    print("  - Може встановити explicit_scan_decisions (Filter Override)")
    
    # ============================================================
    print_step(4, "POST-SCAN HOOK")
    # ============================================================
    
    async def ml_filter_hook(node, links: List[str]) -> List[str]:
        """
        Async hook для фільтрації посилань.
        Виконується ПІСЛЯ scan, ПЕРЕД process_links.
        """
        print(f"\n  🔗 ml_filter_hook()")
        print(f"     Node: {node.url}")
        print(f"     Links before: {len(links)}")
        
        # Симуляція ML фільтрації
        # await ml_api.analyze(links)  # В реальності - async API call
        await asyncio.sleep(0.01)  # Симуляція async
        
        # Фільтруємо (залишаємо всі для демо)
        filtered = links
        
        print(f"     Links after: {len(filtered)}")
        return filtered
    
    print("\n  ml_filter_hook:")
    print("  - async функція")
    print("  - Приймає (node, links)")
    print("  - Повертає відфільтровані links")
    print("  - Може робити async ML API calls")
    
    # ============================================================
    print_step(5, "ЗАПУСК КРАУЛІНГУ")
    # ============================================================
    
    print("\n  >>> graph = await gc.crawl(")
    print("  ...     'https://httpbin.org/links/3/0',")
    print("  ...     max_depth=2,")
    print("  ...     max_pages=5,")
    print("  ...     node_class=MLNode,")
    print("  ...     plugins=[MLDecisionPlugin()],")
    print("  ...     # post_scan_hooks=[ml_filter_hook],  # TODO: expose in API")
    print("  ... )")
    
    start_time = datetime.now()
    
    graph = await gc.crawl(
        "https://httpbin.org/links/3/0",
        max_depth=2,
        max_pages=5,
        node_class=MLNode,
        plugins=[MLDecisionPlugin()],
        driver=AsyncDriver,
        edge_strategy=EdgeCreationStrategy.NEW_ONLY,
    )
    
    duration = (datetime.now() - start_time).total_seconds()
    
    # ============================================================
    print_step(6, "РЕЗУЛЬТАТИ")
    # ============================================================
    
    print(f"\n  Краулінг завершено за {duration:.2f} секунд!")
    print(f"  Знайдено нод: {len(graph.nodes)}")
    
    print("\n  Перевірка user_data (ML priorities):")
    for node_id, node in graph.nodes.items():
        print(f"\n  Node: {node.url}")
        if 'child_priorities' in node.user_data:
            print(f"    child_priorities: {len(node.user_data['child_priorities'])} entries")
        if isinstance(node, MLNode) and node.ml_priority:
            print(f"    ml_priority: {node.ml_priority}")
    
    # ============================================================
    print_step(7, "АРХІТЕКТУРА ГНУЧКОГО ЯДРА")
    # ============================================================
    
    print("""
    Як 3 механізми працюють разом:
    
    CrawlCoordinator._crawl_sequential_mode():
    │
    ├── scheduler.get_next()           # Вибирає node за priority
    │   └── MECHANISM 1: node.priority (від плагіна)
    │
    ├── scanner.scan_node(node)
    │   └── plugin.execute()           # ML плагін
    │       └── Sets child_priorities
    │       └── Sets explicit_scan_decisions
    │
    ├── POST-SCAN HOOKS                # MECHANISM 3
    │   └── links = await hook(node, links)
    │
    └── processor.process_links(node, links)
        └── _should_scan_url()
            └── MECHANISM 2: explicit_scan_decisions
        └── Creates child nodes
            └── Uses child_priorities
    
    Результат: ML/Plugin має повний контроль над:
    - Порядком сканування (priority)
    - Які URL сканувати (explicit decisions)
    - Фільтрація посилань (hooks)
    """)
    
    print_section("ТЕСТ 5 ЗАВЕРШЕНО")
    return graph


if __name__ == "__main__":
    print("\n" + "*" * 80)
    print("  GRAPHCRAWLER v3.0 - TRACING TEST 05: FLEXIBLE CORE")
    print("*" * 80)
    
    graph = asyncio.run(test_flexible_core())
    
    print("\n✅ Тест завершено успішно!")
