"""
============================================================
ТРАСУВАННЯ 13: ПОВНИЙ ВИКЛИК З URL RULES
============================================================

Цей файл показує як URLRule впливають на краулінг:
- Як визначаються правила
- Як вони матчаться
- Як вони впливають на пріоритет та сканування

Використання:
    python 13_full_trace_url_rules.py
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


def print_header(title: str):
    print("\n" + "=" * 100)
    print(f"  {title}")
    print("=" * 100)


def print_section(title: str):
    print(f"\n{'─' * 80}")
    print(f"  📌 {title}")
    print(f"{'─' * 80}")


async def trace_url_rules():
    """
    Трасування з URL Rules.
    """
    print_header("ТРАСУВАННЯ: ВИКЛИК З URL RULES")
    
    import graph_crawler as gc
    from graph_crawler import AsyncDriver, URLRule
    from graph_crawler.core.models import EdgeCreationStrategy
    
    # ============================================================
    print_section("ЕТАП 1: СТРУКТУРА URLRule")
    # ============================================================
    
    print("""
    URLRule (graph_crawler/core/models.py) - правило для URL:
    
    class URLRule(BaseModel):
        pattern: str              # Regex або substring для матчингу
        should_scan: bool = True  # Чи сканувати сторінку
        should_follow_links: bool = True  # Чи слідувати посиланням
        priority: int = 5         # Пріоритет 1-10 (10 = найвищий)
    
    Приклади:
    
    # Виключити /blog/ зі сканування
    URLRule(pattern="/blog/", should_scan=False)
    
    # Сканувати /api/ з високим пріоритетом
    URLRule(pattern="/api/", priority=10)
    
    # Сканувати jobs.site.com але не слідувати посиланням
    URLRule(pattern="jobs.site.com", should_follow_links=False, priority=8)
    """)
    
    # ============================================================
    print_section("ЕТАП 2: ВИЗНАЧЕННЯ ПРАВИЛ")
    # ============================================================
    
    rules = [
        # Високий пріоритет для /links/2
        URLRule(pattern="/links/2", priority=10),
        # Середній пріоритет для /links/1
        URLRule(pattern="/links/1", priority=7),
        # Низький пріоритет для решти
        URLRule(pattern="/links/0", priority=3),
    ]
    
    print("\n  Визначені правила:")
    for i, rule in enumerate(rules, 1):
        print(f"\n      Rule #{i}:")
        print(f"      ├── pattern: '{rule.pattern}'")
        print(f"      ├── should_scan: {rule.should_scan}")
        print(f"      ├── should_follow_links: {rule.should_follow_links}")
        print(f"      └── priority: {rule.priority}")
    
    # ============================================================
    print_section("ЕТАП 3: ЯК ПРАВИЛА ЗАСТОСОВУЮТЬСЯ")
    # ============================================================
    
    print("""
    Правила застосовуються в CrawlScheduler.add_node():
    
    def add_node(self, node: Node) -> bool:
        # 1. Пошук правила що матчить URL
        matched_rule = self._match_rule(node.url)
        
        # 2. Перевірка should_scan
        if matched_rule and matched_rule.should_scan is False:
            logger.debug(f"Excluded by rule: {node.url}")
            return False  # Не додаємо в чергу!
        
        # 3. Обчислення пріоритету
        priority = self._calculate_priority(url, matched_rule, node)
        # Порядок: node.priority > URLRule.priority > default(5)
        
        # 4. Застосування правила до ноди
        matched_rule.apply_to_node(node)
        # Встановлює should_scan, should_follow_links
        
        # 5. Додавання в priority queue
        heapq.heappush(self.queue, (-priority, self.counter, node))
    
    _match_rule() використовує regex.search():
    - pattern="/blog/" матчить "example.com/blog/post1"
    - pattern="jobs." матчить "jobs.example.com/vacancy"
    """)
    
    # ============================================================
    print_section("ЕТАП 4: ЗАПУСК КРАУЛІНГУ")
    # ============================================================
    
    print("\n  🚀 Запуск краулінгу з URL Rules...\n")
    
    start_time = datetime.now()
    
    graph = await gc.crawl(
        "https://httpbin.org/links/3/0",
        max_depth=2,
        max_pages=5,
        driver=AsyncDriver,
        url_rules=rules,
        edge_strategy=EdgeCreationStrategy.NEW_ONLY,
    )
    
    duration = (datetime.now() - start_time).total_seconds()
    
    # ============================================================
    print_section("ЕТАП 5: ВПЛИВ НА ПОРЯДОК СКАНУВАННЯ")
    # ============================================================
    
    print("""
    URL Rules впливають на:
    
    1. ПОРЯДОК сканування (через priority):
       - priority=10 сканується ПЕРШИМ
       - priority=1 сканується ОСТАННІМ
       - Scheduler використовує heapq (мін-купа)
       - Зберігаємо як -priority для max-heap поведінки
    
    2. ЧИ сканувати (should_scan):
       - should_scan=False → URL ігнорується
       - Не додається в чергу взагалі
    
    3. ЧИ слідувати посиланням (should_follow_links):
       - should_follow_links=False → посилання з цієї сторінки НЕ обробляються
       - Корисно для leaf pages (jobs, forms)
    
    Черга (simplified):
    
    heapq: [(-10, counter1, high_priority_node),
            (-7, counter2, medium_priority_node),
            (-3, counter3, low_priority_node)]
    
    get_next() → high_priority_node (priority=10)
    """)
    
    # ============================================================
    print_section("ЕТАП 6: РЕЗУЛЬТАТИ")
    # ============================================================
    
    print(f"\n  ⏱️ Час виконання: {duration:.2f} секунд")
    print(f"  📊 Знайдено нод: {len(graph.nodes)}")
    
    print("\n  📋 Ноди та їх пріоритети:")
    for node_id, node in graph.nodes.items():
        # Визначаємо який rule матчнув
        matched = None
        for rule in rules:
            if rule.pattern in node.url:
                matched = rule
                break
        
        print(f"\n      Node: {node.url}")
        print(f"      ├── depth: {node.depth}")
        print(f"      ├── scanned: {node.scanned}")
        if matched:
            print(f"      └── matched rule: pattern='{matched.pattern}', priority={matched.priority}")
        else:
            print(f"      └── matched rule: None (default priority)")
    
    print_header("ТРАСУВАННЯ ЗАВЕРШЕНО")
    return graph


if __name__ == "__main__":
    print("\n" + "*" * 100)
    print("  GRAPHCRAWLER v3.0 - ТРАСУВАННЯ З URL RULES")
    print("*" * 100)
    
    graph = asyncio.run(trace_url_rules())
    print("\n✅ Трасування завершено успішно!")
