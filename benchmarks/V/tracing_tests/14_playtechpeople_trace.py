"""
============================================================
ТРАСУВАННЯ 14: ПОВНИЙ ВИКЛИК ДЛЯ PLAYTECHPEOPLE.COM
============================================================

Цей файл базується на __test_v.py та показує повний процес:
- Як працює краулінг реального сайту
- Як працює AsyncDriver
- Як працюють URLRule
- Як працює EdgeCreationStrategy

Використання:
    python 14_playtechpeople_trace.py
"""

import sys
import os
import asyncio
import logging
from datetime import datetime
from typing import Optional
from pydantic import Field

# Шлях до проекту
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, PROJECT_ROOT)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-7s | %(message)s',
    datefmt='%H:%M:%S'
)

# Вимикаємо зайві логи
for logger_name in ['urllib3', 'asyncio', 'aiohttp', 'charset_normalizer', 'httpx']:
    logging.getLogger(logger_name).setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def print_header(title: str):
    print("\n" + "=" * 100)
    print(f"  {title}")
    print("=" * 100)


def print_section(title: str):
    print(f"\n{'─' * 80}")
    print(f"  📌 {title}")
    print(f"{'─' * 80}")


async def trace_playtechpeople():
    """
    Трасування краулінгу playtechpeople.com.
    """
    print_header("ТРАСУВАННЯ: КРАУЛІНГ PLAYTECHPEOPLE.COM")
    
    import graph_crawler as gc
    from graph_crawler import AsyncDriver, URLRule
    from graph_crawler.core.models import EdgeCreationStrategy
    
    # ============================================================
    print_section("ЕТАП 1: КОНФІГУРАЦІЯ")
    # ============================================================
    
    print("""
    Конфігурація краулінгу:
    
    URL: https://www.playtechpeople.com/
    max_depth: 3  (глибина обходу)
    max_pages: 2  (для швидкого тесту)
    driver: AsyncDriver (aiohttp)
    edge_strategy: NEW_ONLY (тільки нові зв'язки)
    
    URL Rules:
    1. /blog/ - сканувати, але НЕ слідувати посиланням (priority=5)
    2. jobs.smartrecruiters.com - сканувати з HIGH priority (6)
    """)
    
    # ============================================================
    print_section("ЕТАП 2: КАСТОМНА НОДА ДЛЯ ТЕКСТУ")
    # ============================================================
    
    class TextExtractorNode(gc.Node):
        """
        Кастомна нода що витягує текст сторінки.
        Аналог CastomNode з __test_v.py.
        """
        text: Optional[str] = Field(default=None, description="Текст сторінки")
        
        def _update_from_context(self, context):
            """
            Витягує текст з html_tree.
            Викликається ПІСЛЯ парсингу HTML.
            """
            super()._update_from_context(context)
            
            if context.html_tree:
                # BeautifulSoup API - get_text()
                try:
                    raw_text = context.html_tree.get_text(separator=' ', strip=True)
                    # Очищення
                    clean_text = ' '.join(raw_text.split())
                    clean_text = clean_text.replace('\n', ' ').replace('\t', ' ')
                    self.text = clean_text[:5000]  # Обмежуємо розмір
                    
                    print(f"\n  📝 TextExtractorNode._update_from_context()")
                    print(f"     URL: {self.url}")
                    print(f"     Текст: {len(self.text)} символів")
                except Exception as e:
                    logger.warning(f"Error extracting text: {e}")
                    self.text = None
    
    print("""
    TextExtractorNode успадковує gc.Node та додає:
    
    class TextExtractorNode(gc.Node):
        text: Optional[str] = None
        
        def _update_from_context(self, context):
            # Витягуємо текст з html_tree (BeautifulSoup)
            raw_text = context.html_tree.get_text()
            self.text = clean(raw_text)
    """)
    
    # ============================================================
    print_section("ЕТАП 3: URL RULES")
    # ============================================================
    
    url_rules = [
        URLRule(
            pattern="/blog/",
            should_follow_links=False,  # Не слідувати посиланням з блогу
            should_scan=True,           # Але сканувати
            priority=5
        ),
        URLRule(
            pattern="jobs.smartrecruiters.com",
            should_follow_links=False,
            should_scan=True,
            priority=6  # Вищий пріоритет для job сторінок
        ),
    ]
    
    print("""
    URL Rules визначені:
    
    Rule 1: Blog pages
    ├── pattern: "/blog/"
    ├── should_scan: True (сканувати)
    ├── should_follow_links: False (не слідувати)
    └── priority: 5 (default)
    
    Rule 2: Job pages (external)
    ├── pattern: "jobs.smartrecruiters.com"
    ├── should_scan: True
    ├── should_follow_links: False
    └── priority: 6 (вищий)
    
    Ефект:
    - Blog сторінки скануються, але їх посилання ігноруються
    - Job сторінки скануються з вищим пріоритетом
    """)
    
    # ============================================================
    print_section("ЕТАП 4: EDGE CREATION STRATEGY")
    # ============================================================
    
    print("""
    EdgeCreationStrategy визначає як створюються зв'язки:
    
    1. ALL (default):
       - Створює edge для КОЖНОГО посилання
       - A → B, A → C, B → A (навіть якщо A вже є)
       - Більше edges, повна картина зв'язків
    
    2. NEW_ONLY (використовуємо тут):
       - Edge тільки для НОВИХ нод
       - A → B (new), A → C (new), B → A (skip, A вже є)
       - Менше edges, краща продуктивність
    
    3. Вибір:
       - ALL: для аналізу структури сайту
       - NEW_ONLY: для краулінгу великих сайтів
    """)
    
    # ============================================================
    print_section("ЕТАП 5: ЗАПУСК КРАУЛІНГУ")
    # ============================================================
    
    print("\n  🚀 Запуск краулінгу playtechpeople.com...")
    print("     (max_pages=2 для швидкого тесту)\n")
    
    start_time = datetime.now()
    
    try:
        graph = await gc.crawl(
            "https://www.playtechpeople.com/",
            max_depth=3,
            max_pages=2,  # Обмежуємо для тесту
            node_class=TextExtractorNode,
            driver=AsyncDriver,
            url_rules=url_rules,
            edge_strategy=EdgeCreationStrategy.NEW_ONLY,
        )
        
        duration = (datetime.now() - start_time).total_seconds()
        
        # ============================================================
        print_section("ЕТАП 6: РЕЗУЛЬТАТИ")
        # ============================================================
        
        print(f"\n  ⏱️ Час виконання: {duration:.2f} секунд")
        print(f"  📊 Знайдено нод: {len(graph.nodes)}")
        print(f"  🔗 Знайдено edges: {len(graph.edges)}")
        
        print("\n  📋 Деталі нод:")
        for node_id, node in graph.nodes.items():
            print(f"\n      Node: {node.url[:60]}...")
            print(f"      ├── depth: {node.depth}")
            print(f"      ├── scanned: {node.scanned}")
            print(f"      ├── should_scan: {node.should_scan}")
            print(f"      ├── can_create_edges: {node.can_create_edges}")
            
            if isinstance(node, TextExtractorNode) and node.text:
                preview = node.text[:150] + '...' if len(node.text) > 150 else node.text
                print(f"      └── text preview: '{preview}'")
            
            # Metadata
            if node.metadata:
                title = node.metadata.get('title', 'N/A')
                print(f"      └── title: {title}")
        
    except Exception as e:
        print(f"\n  ❌ Помилка: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    # ============================================================
    print_section("ЕТАП 7: АРХІТЕКТУРА ПРОЦЕСУ")
    # ============================================================
    
    print("""
    Повний ланцюжок викликів для цього краулінгу:
    
    gc.crawl("https://www.playtechpeople.com/", ...)
    │
    ├── api/simple.py::crawl()
    │   ├── ApplicationContainer()
    │   ├── CrawlerConfig(url, max_depth=3, max_pages=2, ...)
    │   ├── create_driver(AsyncDriver) → aiohttp driver
    │   └── GraphCrawlerClient()
    │
    ├── client.crawl()
    │   ├── CrawlerConfig з url_rules
    │   └── GraphSpider(config, driver, ...)
    │
    └── spider.crawl()
        │
        ├── root_node = TextExtractorNode(url, depth=0)
        ├── graph.add_node(root_node)
        ├── scheduler.add_node(root_node)
        │
        └── coordinator.coordinate()
            │
            ├── [LOOP] while scheduler not empty & pages < max_pages:
            │   │
            │   ├── node = scheduler.get_next()  # heapq за priority
            │   │
            │   ├── scanner.scan_node(node)
            │   │   ├── html = await driver.fetch(url)  # aiohttp GET
            │   │   ├── node.process_html(html)
            │   │   │   ├── BeautifulSoup.parse(html)
            │   │   │   ├── ON_HTML_PARSED plugins
            │   │   │   ├── node._update_from_context()  ← TextExtractorNode!
            │   │   │   └── ON_AFTER_SCAN plugins
            │   │   └── return extracted_links
            │   │
            │   └── processor.process_links(node, links)
            │       ├── for link in links:
            │       │   ├── URLRule matching → priority, should_scan
            │       │   ├── if should_scan:
            │       │   │   ├── child = TextExtractorNode(link, depth+1)
            │       │   │   ├── graph.add_node(child)
            │       │   │   └── scheduler.add_node(child)  # heapq
            │       │   └── if edge_strategy == NEW_ONLY:
            │       │       └── graph.add_edge(node, child)  # тільки нові
            │       └── continue loop
            │
            └── return graph
    """)
    
    print_header("ТРАСУВАННЯ ЗАВЕРШЕНО")
    return graph


if __name__ == "__main__":
    print("\n" + "*" * 100)
    print("  GRAPHCRAWLER v3.0 - ТРАСУВАННЯ PLAYTECHPEOPLE.COM")
    print("*" * 100)
    
    graph = asyncio.run(trace_playtechpeople())
    print("\n✅ Трасування завершено успішно!")
