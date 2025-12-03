"""
============================================================
ТЕСТ 2: КРАУЛІНГ З КАСТОМНОЮ НОДОЮ
============================================================

Показує:
1. Як створити власний клас Node
2. Як Node отримує дані з context
3. Lifecycle Node: URL_STAGE -> BEFORE_FETCH -> AFTER_FETCH -> AFTER_PARSE
4. Як user_data зберігає custom поля
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


async def test_custom_node():
    """
    Тест з кастомною Node.
    """
    import graph_crawler as gc
    from graph_crawler import AsyncDriver
    from graph_crawler.core.models import EdgeCreationStrategy
    
    print_section("ТЕСТ 2: КАСТОМНА НОДА (CustomNode)")
    
    # ============================================================
    print_step(1, "ВИЗНАЧЕННЯ КАСТОМНОГО КЛАСУ NODE")
    # ============================================================
    
    print("""
    Кастомна Node дозволяє:
    - Додати власні поля (text, keywords, sentiment, etc)
    - Перевизначити _update_from_context() для custom logic
    - Зберігати ML features прямо в ноді
    """)
    
    # Визначаємо кастомну ноду
    class CustomNode(gc.Node):
        """
        Кастомна Node з додатковими полями.
        
        Поля:
        - text: Очищений текст сторінки
        - word_count: Кількість слів
        - has_forms: Чи є форми на сторінці
        """
        text: Optional[str] = Field(default=None, description="Очищений текст")
        word_count: int = Field(default=0, description="Кількість слів")
        has_forms: bool = Field(default=False, description="Чи є форми")
        
        def _update_from_context(self, context: Any):
            """
            Викликається ПІСЛЯ парсингу HTML.
            
            context містить:
            - context.url: URL сторінки
            - context.html_tree: Parsed HTML (lxml/BeautifulSoup)
            - context.parser: Парсер з методами
            - context.response_data: Raw response
            """
            # Спочатку викликаємо батьківський метод
            super()._update_from_context(context)
            
            print(f"\n  📝 CustomNode._update_from_context() called for {self.url}")
            
            if context.html_tree:
                # Витягуємо текст
                raw_text = context.html_tree.text
                clean_text = ' '.join(raw_text.split())
                self.text = clean_text[:500]  # Обмежуємо довжину
                
                # Рахуємо слова
                self.word_count = len(clean_text.split())
                
                # Перевіряємо наявність форм
                # BeautifulSoup API (замість xpath)
                if hasattr(context.html_tree, 'find_all'):
                    forms = context.html_tree.find_all('form')
                    self.has_forms = len(forms) > 0
                elif hasattr(context.html_tree, 'xpath'):
                    # Fallback для lxml якщо хтось використовує LxmlAdapter
                    forms = context.html_tree.xpath('//form')
                    self.has_forms = len(forms) > 0
                
                print(f"    ✓ text length: {len(self.text or '')} chars")
                print(f"    ✓ word_count: {self.word_count}")
                print(f"    ✓ has_forms: {self.has_forms}")
    
    print("\n  CustomNode клас визначено:")
    print(f"  >>> class CustomNode(gc.Node):")
    print(f"  >>>     text: Optional[str]")
    print(f"  >>>     word_count: int")
    print(f"  >>>     has_forms: bool")
    print(f"  >>>     def _update_from_context(self, context): ...")
    
    # ============================================================
    print_step(2, "LIFECYCLE НОДИ")
    # ============================================================
    
    print("""
    Node проходить через стадії (NodeLifecycle):
    
    1. URL_STAGE       - Node створена з URL (ще не fetched)
    2. BEFORE_FETCH    - Перед HTTP запитом
    3. AFTER_FETCH     - Після отримання response
    4. AFTER_PARSE     - Після парсингу HTML ← _update_from_context()
    
    Плагіни можуть виконуватись на кожній стадії!
    """)
    
    # ============================================================
    print_step(3, "ЗАПУСК КРАУЛІНГУ З КАСТОМНОЮ НОДОЮ")
    # ============================================================
    
    print("\n  >>> graph = await gc.crawl(")
    print("  ...     'https://httpbin.org/forms/post',")
    print("  ...     max_depth=1,")
    print("  ...     max_pages=2,")
    print("  ...     node_class=CustomNode,  # <-- Кастомна Node!")
    print("  ...     driver=AsyncDriver,")
    print("  ... )")
    
    start_time = datetime.now()
    
    graph = await gc.crawl(
        "https://httpbin.org/forms/post",
        max_depth=1,
        max_pages=2,
        node_class=CustomNode,
        driver=AsyncDriver,
        edge_strategy=EdgeCreationStrategy.NEW_ONLY,
    )
    
    duration = (datetime.now() - start_time).total_seconds()
    
    # ============================================================
    print_step(4, "РЕЗУЛЬТАТИ")
    # ============================================================
    
    print(f"\n  Краулінг завершено за {duration:.2f} секунд!")
    print(f"  Знайдено нод: {len(graph.nodes)}")
    
    print("\n  Детальна інформація по нодах:")
    for node_id, node in graph.nodes.items():
        print(f"\n  Node: {node.url}")
        print(f"    - type: {type(node).__name__}")
        print(f"    - depth: {node.depth}")
        print(f"    - scanned: {node.scanned}")
        
        # Кастомні поля
        if isinstance(node, CustomNode):
            print(f"    - word_count: {node.word_count}")
            print(f"    - has_forms: {node.has_forms}")
            if node.text:
                preview = node.text[:100] + "..." if len(node.text) > 100 else node.text
                print(f"    - text preview: '{preview}'")
    
    # ============================================================
    print_step(5, "ВНУТРІШНЯ СТРУКТУРА")
    # ============================================================
    
    print("""
    Як node_class передається через систему:
    
    gc.crawl(node_class=CustomNode)
    └── api/simple.py::crawl()
        └── CrawlerConfig(custom_node_class=CustomNode)
            └── GraphCrawlerClient.crawl()
                └── GraphSpider(config)
                    └── LinkProcessor(custom_node_class=CustomNode)
                        └── process_links()
                            └── target_node = CustomNode(url=link, ...)
                                └── NodeScanner.scan_node(node)
                                    └── node._update_from_context(context)
    
    Тобто:
    1. CustomNode передається в config
    2. LinkProcessor використовує його для створення нових нод
    3. Після парсингу викликається _update_from_context()
    """)
    
    print_section("ТЕСТ 2 ЗАВЕРШЕНО")
    return graph


if __name__ == "__main__":
    print("\n" + "*" * 80)
    print("  GRAPHCRAWLER v3.0 - TRACING TEST 02: CUSTOM NODE")
    print("*" * 80)
    
    graph = asyncio.run(test_custom_node())
    
    print("\n✅ Тест завершено успішно!")
