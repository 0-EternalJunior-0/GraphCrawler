"""
============================================================
ТЕСТ 1: ДЕФОЛТНИЙ ВИКЛИК - Мінімальна конфігурація
============================================================

Показує весь ланцюжок викликів для найпростішого краулінгу:
1. gc.crawl() -> API entry point
2. ApplicationContainer -> створення залежностей  
3. GraphCrawlerClient -> координація краулінгу
4. GraphSpider -> логіка краулінгу
5. CrawlCoordinator -> режим краулінгу
6. NodeScanner -> сканування сторінок
7. LinkProcessor -> обробка посилань
8. Scheduler -> черга URL
9. Driver -> HTTP запити
"""

import sys
import os
import asyncio
import logging
from datetime import datetime

# Шлях до проекту
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, PROJECT_ROOT)

# Налаштування логування
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s.%(msecs)03d | %(levelname)-7s | %(name)-40s | %(message)s',
    datefmt='%H:%M:%S'
)

# Вимикаємо зайві логи
for logger_name in ['urllib3', 'asyncio', 'aiohttp', 'charset_normalizer']:
    logging.getLogger(logger_name).setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def print_section(title: str, char: str = "="):
    """Друкує секцію."""
    width = 80
    print("\n" + char * width)
    print(f" {title}")
    print(char * width)


def print_step(step: int, description: str):
    """Друкує крок."""
    print(f"\n{'─' * 60}")
    print(f"  КРОК {step}: {description}")
    print(f"{'─' * 60}")


async def test_default_crawl():
    """
    Тест дефолтного виклику без будь-яких параметрів.
    """
    print_section("ТЕСТ 1: ДЕФОЛТНИЙ ВИКЛИК gc.crawl()")
    
    print("""
    Конфігурація:
    - URL: https://httpbin.org/html (проста тестова сторінка)
    - max_depth: 1 (тільки стартова)
    - max_pages: 2
    - driver: AsyncDriver (за замовчуванням)
    - plugins: немає
    - node_class: стандартний Node
    """)
    
    # ============================================================
    print_step(1, "ІМПОРТ БІБЛІОТЕКИ")
    # ============================================================
    print("  >>> import graph_crawler as gc")
    import graph_crawler as gc
    print(f"  ✓ Версія: {gc.__version__}")
    print(f"  ✓ Модуль: {gc.__file__}")
    
    # ============================================================
    print_step(2, "ВИКЛИК gc.crawl() - ENTRY POINT")
    # ============================================================
    print("""
    Що відбувається всередині gc.crawl():
    
    1. graph_crawler/__init__.py експортує crawl з api/simple.py
    2. crawl() - це async функція
    3. Створює ApplicationContainer (DI контейнер)
    4. Створює CrawlerConfig з параметрами
    5. Створює Driver через DriverFactory
    6. Створює GraphCrawlerClient
    7. Викликає client.crawl()
    """)
    
    from graph_crawler.api.simple import crawl
    print(f"  >>> crawl = {crawl}")
    print(f"  >>> crawl.__module__ = '{crawl.__module__}'")
    
    # ============================================================
    print_step(3, "ІНІЦІАЛІЗАЦІЯ КОНТЕЙНЕРА")
    # ============================================================
    print("""
    ApplicationContainer створює:
    - CoreContainer: EventBus, Configs
    - DriverContainer: HTTP/Async/Playwright drivers
    - StorageContainer: Memory/JSON/SQLite storage
    - FilterContainer: Domain/Path filters
    - CrawlerContainer: Spider, Scheduler, Processor
    """)
    
    from graph_crawler.containers import ApplicationContainer
    container = ApplicationContainer()
    print(f"  ✓ Container: {container}")
    
    # ============================================================
    print_step(4, "СТВОРЕННЯ DRIVER")
    # ============================================================
    print("""
    За замовчуванням використовується AsyncDriver:
    - Асинхронні HTTP запити через aiohttp
    - Підтримка batch fetching
    - Connection pooling
    """)
    
    from graph_crawler.drivers import AsyncDriver
    print(f"  >>> AsyncDriver = {AsyncDriver}")
    print(f"  >>> AsyncDriver.__module__ = '{AsyncDriver.__module__}'")
    
    # ============================================================
    print_step(5, "ЗАПУСК КРАУЛІНГУ")
    # ============================================================
    print("\n  >>> graph = await gc.crawl('https://httpbin.org/html', max_depth=1, max_pages=2)")
    print("\n  Очікуйте... (виконується async краулінг)\n")
    
    start_time = datetime.now()
    
    # Виконуємо краулінг
    graph = await gc.crawl(
        "https://httpbin.org/html",
        max_depth=1,
        max_pages=2,
        driver=AsyncDriver,
    )
    
    duration = (datetime.now() - start_time).total_seconds()
    
    # ============================================================
    print_step(6, "РЕЗУЛЬТАТИ")
    # ============================================================
    print(f"""
    Краулінг завершено за {duration:.2f} секунд!
    
    Результати:
    - Знайдено нод: {len(graph.nodes)}
    - Знайдено edges: {len(graph.edges)}
    """)
    
    print("\n  Ноди:")
    for node_id, node in graph.nodes.items():
        print(f"    - {node.url}")
        print(f"      depth={node.depth}, scanned={node.scanned}")
        # title знаходиться в metadata
        if node.metadata and 'h1' in node.metadata:
            title = node.metadata.get('h1', [''])[0] if isinstance(node.metadata.get('h1'), list) else node.metadata.get('h1')
            if title:
                print(f"      title='{title[:50]}...' " if len(str(title)) > 50 else f"      title='{title}'")
    
    # ============================================================
    print_step(7, "ВНУТРІШНЯ СТРУКТУРА")
    # ============================================================
    print("""
    Ланцюжок викликів (спрощено):
    
    gc.crawl(url)
    └── api/simple.py::crawl()
        ├── ApplicationContainer()  # DI
        ├── CrawlerConfig()         # Конфігурація
        ├── create_driver()         # Фабрика драйверів
        │   └── AsyncDriver()       # aiohttp-based
        └── GraphCrawlerClient()
            └── client.crawl()
                └── GraphSpider()
                    ├── CrawlScheduler      # Черга URL
                    ├── NodeScanner         # Сканування
                    ├── LinkProcessor       # Обробка посилань
                    └── CrawlCoordinator    # Координація
                        └── _crawl_sequential_mode()
                            ├── scheduler.get_next()
                            ├── scanner.scan_node()
                            └── processor.process_links()
    """)
    
    print_section("ТЕСТ 1 ЗАВЕРШЕНО", "=")
    return graph


if __name__ == "__main__":
    print("\n" + "*" * 80)
    print("  GRAPHCRAWLER v3.0 - TRACING TEST 01: DEFAULT CRAWL")
    print("*" * 80)
    
    graph = asyncio.run(test_default_crawl())
    
    print("\n✅ Тест завершено успішно!")
