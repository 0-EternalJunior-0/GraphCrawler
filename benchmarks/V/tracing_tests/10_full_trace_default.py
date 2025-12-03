"""
============================================================
ТРАСУВАННЯ 10: ПОВНИЙ ВИКЛИК - ДЕФОЛТНА КОНФІГУРАЦІЯ
============================================================

Цей файл показує ПОВНИЙ ланцюжок викликів для дефолтного краулінгу:
- Звідки беруться дані
- Як ініціалізуються класи
- Як створюються ноди
- Як знаходяться нові URL
- Як працює граф

Використання:
    python 10_full_trace_default.py
"""

import sys
import os
import asyncio
import logging
from datetime import datetime
from typing import Optional, List, Any

# Шлях до проекту
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, PROJECT_ROOT)

# Детальне логування
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)-7s | %(name)-50s | %(message)s',
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


def print_code(code: str):
    """Друкує код з підсвіткою."""
    print(f"\n  >>> {code}")


def print_trace(source: str, action: str, details: str = ""):
    """Друкує трасування виклику."""
    print(f"  📍 [{source}] {action}")
    if details:
        print(f"      └─ {details}")


async def trace_default_crawl():
    """
    Детальне трасування дефолтного виклику gc.crawl().
    """
    print_header("ТРАСУВАННЯ: ДЕФОЛТНИЙ ВИКЛИК gc.crawl()")
    
    # ============================================================
    print_section("ЕТАП 1: ІМПОРТ БІБЛІОТЕКИ")
    # ============================================================
    
    print_code("import graph_crawler as gc")
    print("""
    Що відбувається при імпорті:
    
    1. Python завантажує graph_crawler/__init__.py
    2. __init__.py імпортує:
       - crawl з api/simple.py (головна функція)
       - Node, Edge, Graph з core/
       - AsyncDriver, PlaywrightDriver з drivers/
       - URLRule з core/models.py
    """)
    
    import graph_crawler as gc
    print(f"\n  ✅ Імпорт успішний")
    print(f"     Версія: {gc.__version__}")
    print(f"     Шлях: {gc.__file__}")
    
    # ============================================================
    print_section("ЕТАП 2: ВИКЛИК gc.crawl() - API ENTRY POINT")
    # ============================================================
    
    print_code("graph = await gc.crawl('https://httpbin.org/html', max_depth=1, max_pages=2)")
    print("""
    gc.crawl() знаходиться в graph_crawler/api/simple.py
    
    Параметри що передаються:
    - url: 'https://httpbin.org/html'
    - max_depth: 1
    - max_pages: 2
    - driver: None (буде створено AsyncDriver)
    - plugins: None (буде використано дефолтні)
    """)
    
    # ============================================================
    print_section("ЕТАП 3: ВСЕРЕДИНІ crawl() - СТВОРЕННЯ КОНТЕЙНЕРА")
    # ============================================================
    
    print("""
    В api/simple.py::crawl():
    
    1. from graph_crawler.containers import ApplicationContainer
    2. container = ApplicationContainer()
    
    ApplicationContainer (DI контейнер) створює:
    ├── CoreContainer
    │   ├── EventBus - система подій
    │   └── Configs - конфігурації
    ├── DriverContainer  
    │   ├── http_driver - синхронний requests
    │   ├── async_driver - aiohttp (DEFAULT)
    │   └── playwright_driver - для JS сторінок
    ├── StorageContainer
    │   ├── memory_storage - в RAM (DEFAULT)
    │   ├── json_storage - в JSON файл
    │   └── sqlite_storage - в SQLite
    ├── FilterContainer
    │   ├── domain_filter - фільтр доменів
    │   └── path_filter - фільтр шляхів
    └── CrawlerContainer
        ├── scheduler - черга URL
        ├── scanner - сканер сторінок
        └── processor - обробник посилань
    """)
    
    from graph_crawler.containers import ApplicationContainer
    container = ApplicationContainer()
    print(f"  ✅ ApplicationContainer створено: {container}")
    
    # ============================================================
    print_section("ЕТАП 4: СТВОРЕННЯ CRAWLER CONFIG")
    # ============================================================
    
    print("""
    CrawlerConfig створюється з параметрів:
    
    config = CrawlerConfig(
        url='https://httpbin.org/html',
        max_depth=1,
        max_pages=2,
        allowed_domains=['*'],  # default
        url_rules=[],
        node_plugins=[],
        custom_node_class=None,  # використовуємо базовий Node
        edge_strategy='all'
    )
    """)
    
    from graph_crawler.core.configs import CrawlerConfig, DriverConfig
    driver_cfg = DriverConfig(request_delay=0.5)
    config = CrawlerConfig(
        url='https://httpbin.org/html',
        max_depth=1,
        max_pages=2,
        driver=driver_cfg,
    )
    print(f"  ✅ CrawlerConfig: max_depth={config.max_depth}, max_pages={config.max_pages}")
    
    # ============================================================
    print_section("ЕТАП 5: СТВОРЕННЯ DRIVER")
    # ============================================================
    
    print("""
    Driver створюється через DriverFactory:
    
    from graph_crawler.factories.driver_factory import create_driver
    driver = create_driver(AsyncDriver, {})
    
    AsyncDriver (graph_crawler/drivers/async_http/driver.py):
    - Використовує aiohttp для HTTP запитів
    - Підтримує batch fetching (паралельні запити)
    - max_concurrent_requests=24 за замовчуванням
    """)
    
    from graph_crawler.drivers import AsyncDriver
    from graph_crawler.factories.driver_factory import create_driver
    driver = create_driver(AsyncDriver, {})
    print(f"  ✅ Driver створено: {type(driver).__name__}")
    
    # ============================================================
    print_section("ЕТАП 6: СТВОРЕННЯ CLIENT")
    # ============================================================
    
    print("""
    GraphCrawlerClient - координатор краулінгу:
    
    client = GraphCrawlerClient(
        driver=driver,
        storage=MemoryStorage(),
        event_bus=EventBus(),
        repository=GraphRepository()
    )
    
    Відповідальності:
    - Створення GraphSpider
    - Координація краулінгу
    - Збереження графу
    """)
    
    from graph_crawler.client.client import GraphCrawlerClient
    event_bus = container.core.event_bus()
    storage_instance = container.storage.memory_storage()
    repository = container.repository()
    
    client = GraphCrawlerClient(
        driver=driver,
        storage=storage_instance,
        event_bus=event_bus,
        repository=repository,
    )
    print(f"  ✅ Client створено: {client}")
    
    # ============================================================
    print_section("ЕТАП 7: ВИКЛИК client.crawl() → СТВОРЕННЯ SPIDER")
    # ============================================================
    
    print("""
    Всередині client.crawl():
    
    1. Створюється CrawlerConfig
    2. Створюється GraphSpider
    3. Spider.crawl() запускається асинхронно
    
    GraphSpider (graph_crawler/crawler/spider.py) містить:
    ├── graph: Graph - граф результатів
    ├── scheduler: CrawlScheduler - черга URL з пріоритетами
    ├── domain_filter: DomainFilter - фільтрація по домену
    ├── path_filter: PathFilter - фільтрація по шляху
    ├── scanner: NodeScanner - сканування сторінок
    ├── processor: LinkProcessor - обробка посилань
    └── coordinator: CrawlCoordinator - координація процесу
    """)
    
    # ============================================================
    print_section("ЕТАП 8: ЗАПУСК КРАУЛІНГУ")
    # ============================================================
    
    print("""
    Spider.crawl() виконує:
    
    1. Створює root_node (стартова сторінка)
       node = Node(url='https://httpbin.org/html', depth=0)
    
    2. Додає в граф:
       graph.add_node(root_node)
    
    3. Додає в scheduler:
       scheduler.add_node(root_node)
    
    4. Делегує координатору:
       await coordinator.coordinate()
    """)
    
    print("\n  🚀 Запуск краулінгу...\n")
    
    start_time = datetime.now()
    graph = await client.crawl(
        url='https://httpbin.org/html',
        max_depth=1,
        max_pages=2,
    )
    duration = (datetime.now() - start_time).total_seconds()
    
    # ============================================================
    print_section("ЕТАП 9: КООРДИНАТОР - ГОЛОВНИЙ ЦИКЛ")
    # ============================================================
    
    print("""
    CrawlCoordinator.coordinate() виконує головний цикл:
    
    while not scheduler.is_empty() and pages_crawled < max_pages:
        │
        ├── 1. Отримати наступну ноду:
        │      node = scheduler.get_next()  # heapq за пріоритетом
        │
        ├── 2. Перевірити глибину:
        │      if node.depth > max_depth: skip
        │
        ├── 3. Сканувати сторінку:
        │      links = await scanner.scan_node(node)
        │      │
        │      ├── HTTP запит через driver.fetch(url)
        │      ├── Парсинг HTML (BeautifulSoup)
        │      ├── node.process_html(html)
        │      │   ├── Витягує metadata (title, h1, description)
        │      │   ├── Витягує посилання <a href>
        │      │   ├── Виконує плагіни
        │      │   └── Очищує HTML з пам'яті
        │      └── Повертає список посилань
        │
        └── 4. Обробити посилання:
               processor.process_links(node, links)
               │
               ├── Для кожного link:
               │   ├── Нормалізація URL
               │   ├── domain_filter.should_scan(url) → bool
               │   ├── path_filter.should_scan(url) → bool
               │   ├── Створення child_node
               │   ├── graph.add_node(child_node)
               │   ├── graph.add_edge(parent, child)
               │   └── scheduler.add_node(child_node)
               └── Повторити цикл
    """)
    
    # ============================================================
    print_section("ЕТАП 10: РЕЗУЛЬТАТИ")
    # ============================================================
    
    print(f"\n  ⏱️ Час виконання: {duration:.2f} секунд")
    print(f"  📊 Знайдено нод: {len(graph.nodes)}")
    print(f"  🔗 Знайдено edges: {len(graph.edges)}")
    
    print("\n  📋 Деталі нод:")
    for node_id, node in graph.nodes.items():
        print(f"\n      Node: {node.url}")
        print(f"      ├── depth: {node.depth}")
        print(f"      ├── scanned: {node.scanned}")
        print(f"      ├── should_scan: {node.should_scan}")
        print(f"      ├── lifecycle: {node.lifecycle_stage.value}")
        if node.metadata:
            print(f"      └── metadata:")
            for key, value in node.metadata.items():
                val_str = str(value)[:50] + '...' if len(str(value)) > 50 else str(value)
                print(f"          ├── {key}: {val_str}")
    
    # Закриваємо driver
    await driver.close()
    
    print_header("ТРАСУВАННЯ ЗАВЕРШЕНО")
    return graph


if __name__ == "__main__":
    print("\n" + "*" * 100)
    print("  GRAPHCRAWLER v3.0 - ПОВНЕ ТРАСУВАННЯ ДЕФОЛТНОГО ВИКЛИКУ")
    print("*" * 100)
    
    graph = asyncio.run(trace_default_crawl())
    print("\n✅ Трасування завершено успішно!")
