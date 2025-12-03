"""
============================================================
ТРАСУВАННЯ 12: ПОВНИЙ ВИКЛИК З КАСТОМНОЮ НОДОЮ
============================================================

Цей файл показує як працюють кастомні Node класи:
- Як успадкувати Node
- Як додати кастомні поля
- Як перевизначити _update_from_context
- Як це впливає на процес

Використання:
    python 12_full_trace_custom_node.py
"""

import sys
import os
import asyncio
import logging
from datetime import datetime
from typing import Optional, List
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


async def trace_custom_node():
    """
    Трасування з кастомною нодою.
    """
    print_header("ТРАСУВАННЯ: ВИКЛИК З КАСТОМНОЮ НОДОЮ")
    
    import graph_crawler as gc
    from graph_crawler import AsyncDriver
    from graph_crawler.core.models import EdgeCreationStrategy
    
    # ============================================================
    print_section("ЕТАП 1: БАЗОВИЙ КЛАС NODE")
    # ============================================================
    
    print("""
    Базовий Node (graph_crawler/core/node.py) - Pydantic модель:
    
    class Node(BaseModel):
        # Базові поля (завжди є)
        url: str
        node_id: str = Field(default_factory=uuid4)
        depth: int = 0
        should_scan: bool = True
        can_create_edges: bool = True
        created_at: datetime = Field(default_factory=now)
        
        # Після сканування
        metadata: Dict = Field(default_factory=dict)
        user_data: Dict = Field(default_factory=dict)
        scanned: bool = False
        response_status: Optional[int] = None
        content_hash: Optional[str] = None
        
        # v3.0: Динамічний пріоритет
        priority: Optional[int] = Field(default=None, ge=1, le=10)
        
        # Життєвий цикл
        lifecycle_stage: NodeLifecycle = NodeLifecycle.URL_STAGE
    """)
    
    # ============================================================
    print_section("ЕТАП 2: СТВОРЕННЯ КАСТОМНОЇ НОДИ")
    # ============================================================
    
    class TextNode(gc.Node):
        """
        Кастомна нода що витягує текст сторінки.
        
        Успадковує всі поля Node та додає:
        - text: очищений текст сторінки
        - word_count: кількість слів
        """
        
        # Кастомні поля (Pydantic Fields)
        text: Optional[str] = Field(default=None, description="Текст сторінки")
        word_count: int = Field(default=0, description="Кількість слів")
        
        def _update_from_context(self, context):
            """
            Цей метод викликається ПІСЛЯ ON_HTML_PARSED плагінів,
            ПЕРЕД ON_AFTER_SCAN плагінами.
            
            Тут можна витягнути дані з html_tree.
            """
            # Спочатку викликаємо батьківський метод
            super()._update_from_context(context)
            
            print(f"\n  🔧 TextNode._update_from_context()")
            print(f"     ├── URL: {self.url}")
            print(f"     ├── html_tree присутній: {context.html_tree is not None}")
            
            # Витягуємо текст якщо є html_tree
            if context.html_tree:
                # BeautifulSoup API
                raw_text = context.html_tree.get_text(separator=' ', strip=True)
                # Очищення
                self.text = ' '.join(raw_text.split())
                self.word_count = len(self.text.split())
                
                print(f"     ├── Текст витягнуто: {len(self.text)} символів")
                print(f"     └── Слів: {self.word_count}")
    
    print("""
    TextNode успадковує gc.Node та додає:
    
    class TextNode(gc.Node):
        text: Optional[str] = None       # Текст сторінки
        word_count: int = 0              # Кількість слів
        
        def _update_from_context(self, context):
            # Витягуємо текст з html_tree
            ...
    
    Коли викликається _update_from_context:
    
    node.process_html(html)
    ├── parse(html) → html_tree
    ├── ON_BEFORE_SCAN плагіни
    ├── ON_HTML_PARSED плагіни
    ├── _update_from_context(context)  ← ТУТ!
    └── ON_AFTER_SCAN плагіни
    """)
    
    # ============================================================
    print_section("ЕТАП 3: ЗАПУСК КРАУЛІНГУ")
    # ============================================================
    
    print("\n  🚀 Запуск краулінгу з TextNode...\n")
    
    start_time = datetime.now()
    
    graph = await gc.crawl(
        "https://httpbin.org/html",
        max_depth=1,
        max_pages=2,
        driver=AsyncDriver,
        node_class=TextNode,  # ← Кастомна нода!
        edge_strategy=EdgeCreationStrategy.NEW_ONLY,
    )
    
    duration = (datetime.now() - start_time).total_seconds()
    
    # ============================================================
    print_section("ЕТАП 4: ВНУТРІШНІЙ ПРОЦЕС СТВОРЕННЯ НОДИ")
    # ============================================================
    
    print("""
    Коли вказано node_class=TextNode:
    
    1. GraphSpider отримує node_class з config:
       self.config.custom_node_class = TextNode
    
    2. При створенні root_node:
       node_class = self.config.custom_node_class or Node
       root_node = node_class(url=url, depth=0)
       
    3. При створенні child nodes в LinkProcessor:
       node_class = self.custom_node_class or Node
       child_node = node_class(url=url, depth=parent_depth+1)
    
    4. Pydantic автоматично:
       - Валідує всі поля (базові + кастомні)
       - Встановлює defaults
       - Викликає model_post_init()
    
    5. При скануванні:
       node.process_html(html)
       └── _update_from_context()  ← Кастомна логіка тут!
    """)
    
    # ============================================================
    print_section("ЕТАП 5: РЕЗУЛЬТАТИ")
    # ============================================================
    
    print(f"\n  ⏱️ Час виконання: {duration:.2f} секунд")
    print(f"  📊 Знайдено нод: {len(graph.nodes)}")
    
    print("\n  📋 Кастомні поля TextNode:")
    for node_id, node in graph.nodes.items():
        print(f"\n      Node: {node.url}")
        print(f"      ├── Тип: {type(node).__name__}")
        print(f"      ├── scanned: {node.scanned}")
        
        # Перевіряємо кастомні поля
        if isinstance(node, TextNode):
            print(f"      ├── word_count: {node.word_count}")
            if node.text:
                preview = node.text[:100] + '...' if len(node.text) > 100 else node.text
                print(f"      └── text preview: '{preview}'")
        else:
            print(f"      └── ⚠️ Не TextNode!")
    
    print_header("ТРАСУВАННЯ ЗАВЕРШЕНО")
    return graph


if __name__ == "__main__":
    print("\n" + "*" * 100)
    print("  GRAPHCRAWLER v3.0 - ТРАСУВАННЯ З КАСТОМНОЮ НОДОЮ")
    print("*" * 100)
    
    graph = asyncio.run(trace_custom_node())
    print("\n✅ Трасування завершено успішно!")
