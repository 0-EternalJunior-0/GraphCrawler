# GraphCrawler

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-4.0.0-green.svg)](CHANGELOG.md)
[![Performance](https://img.shields.io/badge/speedup-3.2x-brightgreen.svg)]()

Python бібліотека для сканування веб-сайтів та побудови графу їх структури.

## 🚀 Python 3.14 Optimizations

GraphCrawler 4.0 оптимізований для Python 3.14 з підтримкою **free-threading**:

- ⚡ **2-4x швидше** HTML парсинг (free-threading)
- 🚀 **3.2x швидше** end-to-end crawling
- 📉 **16% менше** memory usage
- ⏱️ **30% швидший** startup

### Free-threading Mode (рекомендовано)

```bash
# Увімкнути free-threading для максимальної швидкості
export PYTHON_GIL=0
python your_script.py
```

## Встановлення

```bash
pip install -e .
```

### Optional dependencies

```bash
# Playwright driver (для JavaScript сайтів)
pip install -e ".[playwright]"

# Векторизація тексту (плагін)
pip install -e ".[embeddings]"

# Content extractors (плагіни)
pip install -e ".[articles]"

# MongoDB/PostgreSQL storage
pip install -e ".[mongodb,postgresql]"

# Все разом
pip install -e ".[all]"
```

## Швидкий старт

```python
import graph_crawler as gc

# Синхронний API (рекомендовано)
graph = gc.crawl("https://example.com")

print(f"Знайдено {len(graph.nodes)} сторінок")
print(f"Знайдено {len(graph.edges)} посилань")
```

## API

### Sync API

```python
import graph_crawler as gc

# Функція crawl()
graph = gc.crawl(
    "https://example.com",
    max_depth=3,        # Максимальна глибина (default: 3)
    max_pages=100,      # Максимум сторінок (default: 100)
    same_domain=True,   # Тільки поточний домен (default: True)
    timeout=300,        # Таймаут в секундах
    request_delay=0.5,  # Затримка між запитами (default: 0.5)
    follow_links=True,  # Переходити за посиланнями (default: True)
    driver="http",      # "http", "async", "playwright"
)

# Клас Crawler (reusable)
with gc.Crawler(max_depth=3) as crawler:
    graph1 = crawler.crawl("https://site1.com")
    graph2 = crawler.crawl("https://site2.com")
```

### Параметр follow_links

```python
# follow_links=False - сканувати тільки вказані URL
urls = ["https://site.com/page1", "https://site.com/page2"]
graph = gc.crawl(seed_urls=urls, follow_links=False)
```

### Async API

```python
import asyncio
import graph_crawler as gc

async def main():
    # Функція async_crawl()
    graph = await gc.async_crawl("https://example.com")
    
    # Клас AsyncCrawler (паралельний краулінг)
    async with gc.AsyncCrawler() as crawler:
        graphs = await asyncio.gather(
            crawler.crawl("https://site1.com"),
            crawler.crawl("https://site2.com"),
        )
    return graphs

graphs = asyncio.run(main())
```

### Операції з графом

```python
# Статистика
stats = graph.get_stats()
# {'total_nodes': 47, 'scanned_nodes': 45, 'total_edges': 156, ...}

# Пошук вузла
node = graph.get_node_by_url("https://example.com/page")

# Операції над графами
merged = graph1 + graph2      # Об'єднання
diff = graph2 - graph1        # Різниця
common = graph1 & graph2      # Перетин

# Порівняння
if graph1 < graph2:
    print("graph1 є підграфом graph2")

# Експорт
graph.export_edges("edges.json", format="json")
graph.export_edges("edges.csv", format="csv")
graph.export_edges("graph.dot", format="dot")
```

### URL Rules

```python
from graph_crawler import crawl, URLRule

rules = [
    URLRule(pattern=r".*\.pdf$", should_scan=False),     # Ігнорувати PDF
    URLRule(pattern=r"/products/", priority=10),         # Високий пріоритет
    URLRule(pattern=r"/admin/", should_scan=False),      # Ігнорувати admin
    
    # should_follow_links - контроль переходу за посиланнями
    URLRule(
        pattern=r'external\.com',
        should_scan=True,           # Сканувати сторінку
        should_follow_links=False   # Не переходити за посиланнями
    ),
]

graph = crawl("https://example.com", url_rules=rules)
```

### Edge Rules (контроль ребер)

```python
from graph_crawler import crawl, EdgeRule

edge_rules = [
    # Не створювати edges при різниці глибини > 2
    EdgeRule(max_depth_diff=2, action='skip'),
    
    # Не створювати edges з blog на products
    EdgeRule(
        source_pattern=r'.*/blog/.*',
        target_pattern=r'.*/products/.*',
        action='skip'
    ),
]

graph = crawl("https://example.com", edge_rules=edge_rules)
```

### ContentType (тип контенту)

```python
from graph_crawler import ContentType

# Детекція типу контенту
content_type = ContentType.from_content_type_header("text/html; charset=utf-8")
# ContentType.HTML

content_type = ContentType.from_url("https://api.example.com/data.json")
# ContentType.JSON

# Фільтрація nodes по типу
html_nodes = [n for n in graph if n.content_type == ContentType.HTML]

# Перевірки
if content_type.is_text_based():
    print("Text content")
if content_type.is_scannable():
    print("Can scan for links")
```

### Плагіни

```python
from graph_crawler import crawl, BaseNodePlugin, NodePluginType

class CustomPlugin(BaseNodePlugin):
    @property
    def name(self):
        return "custom_plugin"
    
    @property
    def plugin_type(self):
        return NodePluginType.ON_HTML_PARSED
    
    def execute(self, context):
        # context.html_tree - BeautifulSoup об'єкт
        # context.extracted_links - список посилань
        # context.user_data - словник для даних
        images = context.html_tree.find_all('img')
        context.user_data['image_count'] = len(images)
        return context

graph = crawl("https://example.com", plugins=[CustomPlugin()])
```

## Драйвери

| Драйвер | Опис | Використання |
|---------|------|-------------|
| `http` | Async HTTP (aiohttp) | Статичні сайти (default) |
| `async` | Alias для http | Зворотня сумісність |
| `playwright` | Браузер з JS рендерингом | JavaScript сайти |

```python
# HTTP драйвер (default)
graph = gc.crawl("https://example.com", driver="http")

# Playwright для JavaScript сайтів
graph = gc.crawl("https://spa-example.com", driver="playwright")
```

## Storage

| Storage | Опис | Рекомендовано для |
|---------|------|------------------|
| `memory` | В пам'яті | < 1,000 сторінок |
| `json` | JSON файл | 1,000 - 20,000 сторінок |
| `sqlite` | SQLite база | 20,000+ сторінок |
| `postgresql` | PostgreSQL | Великі проекти |
| `mongodb` | MongoDB | Великі проекти |

## Структура проекту

```
graph_crawler/
├── api/              # Simple API (crawl, Crawler, async_crawl)
├── client/           # GraphCrawlerClient
├── core/             # Node, Edge, Graph, Events, Models
├── crawler/          # Spider, Scheduler, LinkProcessor, Filters
├── drivers/          # HTTP, Playwright драйвери
├── storage/          # Memory, JSON, SQLite, PostgreSQL, MongoDB
├── plugins/          # Node плагіни (vectorization, content_extractors)
├── middleware/       # Rate limiting, Retry, Robots.txt, Proxy
├── factories/        # Driver, Storage factories
├── containers/       # Dependency Injection containers
├── adapters/         # BeautifulSoup adapter
├── exporters/        # JSON, CSV, DOT exporters
└── utils/            # URL utils, DNS cache, Bloom filter
```

## Тестування

```bash
pytest
pytest --cov=package_crawler
```

## Вимоги

- **Python 3.11+** (мінімальна версія)
- Залежності: див. [requirements.txt](requirements.txt)

### Яку версію Python обрати?

| Версія | Рекомендовано для | Примітки |
|--------|-------------------|----------|
| **3.14** | Максимальна швидкість | Free-threading (GIL=0), ~3.2x швидше |
| **3.12-3.13** | Візуалізація з коробки | Стабільні залежності (pyvis, networkx) |
| **3.11** | Сумісність | Всі функції працюють |

### Рекомендації для Python 3.14

```bash
# Free-threading для максимальної швидкості (рекомендовано)
export PYTHON_GIL=0

# JIT compiler (увімкнено за замовчуванням)
export PYTHON_JIT=1

# Запуск
python your_crawler.py
```


