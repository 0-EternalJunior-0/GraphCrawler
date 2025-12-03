"""Модуль CRAWLER - Логіка краулінгу веб-сайту.

Цей модуль реалізує головну бізнес-логіку обходу веб-сайту:

**Основні компоненти (модульна архітектура):**

1. **GraphSpider** (crawler/spider.py)
   - Головний краулер-координатор
   - Реалізує BFS (Breadth-First Search) алгоритм
   - Координує роботу NodeScanner та LinkProcessor
   - Управляє життєвим циклом краулінгу
   - Перевіряє ліміти (max_pages, max_depth)

2. **NodeScanner** (crawler/node_scanner.py)
   - Відповідає ТІЛЬКИ за сканування окремих сторінок
   - Завантаження HTML через Driver
   - Обробка HTML через плагіни (process_html)
   - Підтримка batch режиму для AsyncDriver

3. **LinkProcessor** (crawler/link_processor.py)
   - Відповідає ТІЛЬКИ за обробку знайдених посилань
   - Фільтрація URL через DomainFilter та PathFilter
   - Створення нових Node та Edge
   - Додавання в Scheduler та Graph

4. **CrawlScheduler** (crawler/scheduler.py)
   - Черга непросканованих URL
   - BFS порядок обходу
   - Дедуплікація URL (set())
   - Пріоритезація за depth

5. **URL Filters** (crawler/filters/)
   - Strategy Pattern для різних фільтрів:
     * DomainFilter - фільтр за доменом
     * PathFilter - фільтр за шляхом (regex)
   - Валідація через Pydantic моделі

6. **HTML Parsers** (crawler/parsers/)
   - Парсинг HTML контенту через BeautifulSoup
   - Інтегровано в плагінну систему Node

**Алгоритм краулінгу:**

```
1. Створити початковий Node з start_url (depth=0)
2. Додати в Scheduler
3. LOOP while є непроскановані nodes:
   a) node = scheduler.get_next()
   b) Middleware PRE_REQUEST
   c) html = driver.fetch(node.url)
   d) Middleware POST_REQUEST
   e) links = parser.extract_links(html)
   f) Фільтрувати links через URLFilter
   g) Створити нові Nodes для дозволених URL
   h) Створити Edges (node → new_nodes)
   i) graph.add_nodes(), graph.add_edges()
   j) storage.save_partial()
   k) Event: NODE_SCANNED
   l) Перевірка: max_pages <= 20k, max_depth
4. storage.save_graph()
5. return graph
```

**Рекомендації:**
- Попередження при 20,000+ сторінок (жорсткого ліміту немає)
- Один домен на процес (рекомендовано)
- allowed_domains = ["domain+subdomains"] за замовчуванням

**Приклад використання (Alpha 2.0):**

```python
from graph_crawler.application.use_cases.crawling import GraphSpider
from graph_crawler.domain.entities import CrawlerConfig
from graph_crawler.infrastructure.transport.http import HTTPDriver
from graph_crawler.infrastructure.persistence.json_storage import JSONStorage

# Конфігурація
config = CrawlerConfig(
    start_url="https://example.com",
    max_depth=3,
    max_pages=100,
    allowed_domains=["domain+subdomains"]  # або "*" для всіх
)

# Створити компоненти (Alpha 2.0: прямі імпорти)
driver = HTTPDriver({})
storage = JSONStorage("./graphs_storage")

# Запустити краулінг
spider = GraphSpider(config, driver, storage)
graph = spider.crawl()

print(f"Просканованих: {len(graph.nodes)}")

# Очистити
driver.close()
storage.clear()
```

**Підмодулі:**
- crawler/spider.py - Головний Spider (координатор)
- crawler/node_scanner.py - Сканер окремих сторінок
- crawler/link_processor.py - Обробник посилань
- crawler/scheduler.py - Черга URL для сканування
- crawler/filters/ - URL фільтри (Domain, Path)
- crawler/parsers/ - HTML парсери (інтегровано в плагіни)
"""

from graph_crawler.application.use_cases.crawling.crawl_coordinator import (
    CrawlCoordinator,
)
from graph_crawler.application.use_cases.crawling.filters.base import BaseURLFilter
from graph_crawler.application.use_cases.crawling.filters.domain_filter import (
    DomainFilter,
)
from graph_crawler.application.use_cases.crawling.filters.path_filter import PathFilter
from graph_crawler.application.use_cases.crawling.incremental_strategy import (
    IncrementalCrawlStrategy,
)
from graph_crawler.application.use_cases.crawling.link_processor import LinkProcessor
from graph_crawler.application.use_cases.crawling.multiprocess_spider import (
    MultiprocessSpider,
)
from graph_crawler.application.use_cases.crawling.node_scanner import NodeScanner
from graph_crawler.application.use_cases.crawling.progress_tracker import (
    CrawlProgressTracker,
)
from graph_crawler.application.use_cases.crawling.scheduler import CrawlScheduler
from graph_crawler.application.use_cases.crawling.spider import GraphSpider

# Нові компоненти (SRP Refactoring 2.1)
from graph_crawler.application.use_cases.crawling.spider_lifecycle import (
    SpiderLifecycleManager,
)

# Try to import optional spiders
try:
    from graph_crawler.application.use_cases.crawling.celery_batch_spider import (  # RECOMMENDED
        CeleryBatchSpider,
    )
    from graph_crawler.application.use_cases.crawling.celery_spider import (  # DEPRECATED
        CelerySpider,
    )
    from graph_crawler.application.use_cases.crawling.serialization_mixin import (
        ConfigSerializationMixin,
        create_instance_from_path,
        import_class_from_path,
    )

    __all__ = [
        "GraphSpider",
        "MultiprocessSpider",
        "CelerySpider",  # DEPRECATED - use CeleryBatchSpider
        "CeleryBatchSpider",  # RECOMMENDED - 24x faster
        "ConfigSerializationMixin",  # Serialization Mixin
        "import_class_from_path",
        "create_instance_from_path",
        "NodeScanner",
        "LinkProcessor",
        "CrawlScheduler",
        "BaseURLFilter",
        "DomainFilter",
        "PathFilter",
        "SpiderLifecycleManager",
        "IncrementalCrawlStrategy",
        "CrawlProgressTracker",
        "CrawlCoordinator",
    ]
except ImportError:
    CelerySpider = None
    CeleryBatchSpider = None
    ConfigSerializationMixin = None
    __all__ = [
        "GraphSpider",
        "MultiprocessSpider",
        "NodeScanner",
        "LinkProcessor",
        "CrawlScheduler",
        "BaseURLFilter",
        "DomainFilter",
        "PathFilter",
        "SpiderLifecycleManager",
        "IncrementalCrawlStrategy",
        "CrawlProgressTracker",
        "CrawlCoordinator",
    ]
