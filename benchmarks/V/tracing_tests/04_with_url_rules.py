"""
============================================================
ТЕСТ 4: КРАУЛІНГ З URL RULES
============================================================

Показує:
1. Як URLRule контролює пріоритет сканування
2. Як URLRule фільтрує посилання
3. Як EdgeCreationStrategy контролює граф
4. Dynamic Priority від плагінів (v3.0)
"""

import sys
import os
import asyncio
import logging
from datetime import datetime

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


async def test_url_rules():
    """
    Тест з URL Rules та Edge Strategy.
    """
    import graph_crawler as gc
    from graph_crawler import URLRule, AsyncDriver
    from graph_crawler.core.models import EdgeCreationStrategy
    
    print_section("ТЕСТ 4: URL RULES ТА EDGE STRATEGY")
    
    # ============================================================
    print_step(1, "URL RULE ПОЯСНЕННЯ")
    # ============================================================
    
    print("""
    URLRule дозволяє контролювати поведінку для URL за regex патерном:
    
    URLRule(
        pattern="/blog/",          # Regex патерн для URL
        should_scan=True,           # Чи сканувати сторінку
        should_follow_links=False,  # Чи йти по посиланнях
        priority=6,                 # Пріоритет (1-10, вище = важливіше)
        create_edge=True,           # Чи створювати edge
    )
    
    Приклади:
    - should_scan=False: Сторінка не буде завантажена взагалі
    - should_follow_links=False: Посилання зі сторінки ігноруються
    - priority=10: Сторінка буде оброблена першою
    """)
    
    # ============================================================
    print_step(2, "EDGE CREATION STRATEGY")
    # ============================================================
    
    print("""
    EdgeCreationStrategy контролює коли створюються edges:
    
    - ALL (default): Створювати всі edges
    - NEW_ONLY: Edge тільки для нових нод (перше знаходження)
    - MAX_IN_DEGREE: Ліміт на incoming edges
    - SAME_DEPTH_ONLY: Тільки nodes тієї ж глибини
    - DEEPER_ONLY: Тільки на глибші рівні
    - FIRST_ENCOUNTER_ONLY: Тільки перший edge на кожен URL
    """)
    
    print(f"  Доступні стратегії:")
    for strategy in EdgeCreationStrategy:
        print(f"    - {strategy.value}")
    
    # ============================================================
    print_step(3, "ВИЗНАЧЕННЯ URL RULES")
    # ============================================================
    
    url_rules = [
        # Сторінки /html скануємо але не йдемо по посиланнях
        URLRule(
            pattern="/html",
            should_scan=True,
            should_follow_links=False,
            priority=8
        ),
        # Сторінки /links скануємо з високим пріоритетом
        URLRule(
            pattern="/links",
            should_scan=True,
            should_follow_links=True,
            priority=10
        ),
        # Виключаємо /image
        URLRule(
            pattern="/image",
            should_scan=False,
            priority=1
        ),
    ]
    
    print("\n  URL Rules:")
    for i, rule in enumerate(url_rules, 1):
        print(f"  {i}. pattern='{rule.pattern}'")
        print(f"      should_scan={rule.should_scan}")
        print(f"      should_follow_links={rule.should_follow_links}")
        print(f"      priority={rule.priority}")
    
    # ============================================================
    print_step(4, "ЗАПУСК КРАУЛІНГУ")
    # ============================================================
    
    print("\n  >>> graph = await gc.crawl(")
    print("  ...     'https://httpbin.org/links/5/0',")
    print("  ...     max_depth=2,")
    print("  ...     max_pages=10,")
    print("  ...     url_rules=url_rules,")
    print("  ...     edge_strategy=EdgeCreationStrategy.NEW_ONLY,")
    print("  ... )")
    
    start_time = datetime.now()
    
    graph = await gc.crawl(
        "https://httpbin.org/links/5/0",
        max_depth=2,
        max_pages=10,
        url_rules=url_rules,
        driver=AsyncDriver,
        edge_strategy=EdgeCreationStrategy.NEW_ONLY,
    )
    
    duration = (datetime.now() - start_time).total_seconds()
    
    # ============================================================
    print_step(5, "РЕЗУЛЬТАТИ")
    # ============================================================
    
    print(f"\n  Краулінг завершено за {duration:.2f} секунд!")
    print(f"  Знайдено нод: {len(graph.nodes)}")
    print(f"  Знайдено edges: {len(graph.edges)}")
    
    print("\n  Ноди по depth:")
    depth_counts = {}
    for node in graph.nodes.values():
        d = node.depth
        depth_counts[d] = depth_counts.get(d, 0) + 1
    for depth in sorted(depth_counts.keys()):
        print(f"    depth={depth}: {depth_counts[depth]} нод")
    
    print("\n  Список нод:")
    for node_id, node in graph.nodes.items():
        status = "✓" if node.scanned else "✗"
        print(f"    [{status}] depth={node.depth} {node.url}")
    
    # ============================================================
    print_step(6, "МЕХАНІЗМ РОБОТИ URL RULES")
    # ============================================================
    
    print("""
    Як URL Rules застосовуються:
    
    1. Scheduler.add_node(node):
       ├── _match_rule(node.url)     # Знаходить перший rule що матчить
       ├── _calculate_priority()     # v3.0: node.priority > URLRule > default
       └── _apply_rule_to_node()     # Встановлює should_scan, can_create_edges
    
    2. LinkProcessor._should_scan_url(url, source_url):
       ├── Check explicit_scan_decisions (v3.0 - від плагінів)
       ├── Check URLRule.should_scan
       ├── Check DomainFilter
       └── Check PathFilter
    
    3. LinkProcessor._should_create_edge():
       ├── Check URLRule.create_edge
       ├── Check EdgeRule
       └── Apply EdgeCreationStrategy
    
    Пріоритет перевірки:
    explicit_scan_decisions > URLRule > DomainFilter > PathFilter
    """)
    
    print_section("ТЕСТ 4 ЗАВЕРШЕНО")
    return graph


if __name__ == "__main__":
    print("\n" + "*" * 80)
    print("  GRAPHCRAWLER v3.0 - TRACING TEST 04: URL RULES")
    print("*" * 80)
    
    graph = asyncio.run(test_url_rules())
    
    print("\n✅ Тест завершено успішно!")
