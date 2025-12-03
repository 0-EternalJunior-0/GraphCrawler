# GraphCrawler

[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-3.2.0-green.svg)](CHANGELOG.md)

Python бібліотека для сканування веб-сайтів та побудови графу їх структури.

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
    driver="http",      # "http", "async", "playwright"
)

# Клас Crawler (reusable)
with gc.Crawler(max_depth=3) as crawler:
    graph1 = crawler.crawl("https://site1.com")
    graph2 = crawler.crawl("https://site2.com")
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
]

graph = crawl("https://example.com", url_rules=rules)
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
pytest --cov=graph_crawler
```

## Вимоги

- Python 3.9+
- Залежності: див. [requirements.txt](requirements.txt)

## Ліцензія

[MIT](LICENSE)

## Автор

0-EternalJunior-0
