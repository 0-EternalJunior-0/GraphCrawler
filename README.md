# GraphCrawler

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![PyPI](https://img.shields.io/badge/pypi-v4.0.13-green.svg)](https://pypi.org/project/graph-crawler/)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

Бібліотека для побудови графу структури веб-сайтів.

## Встановлення

```bash
pip install graph-crawler
```

Додаткові залежності:

```bash
pip install graph-crawler[playwright]    # JavaScript сайти
pip install graph-crawler[embeddings]    # Векторизація
pip install graph-crawler[mongodb]       # MongoDB storage
pip install graph-crawler[all]           # Все
```

## Використання

```python
import graph_crawler as gc

# Базове сканування
graph = gc.crawl("https://example.com", max_depth=2, max_pages=50)

print(f"Сторінок: {len(graph.nodes)}")
print(f"Посилань: {len(graph.edges)}")

# Збереження
gc.save_graph(graph, "site.json")
```

### Async API

```python
import asyncio
import graph_crawler as gc

async def main():
    graph = await gc.async_crawl("https://example.com")
    return graph

graph = asyncio.run(main())
```

### Параметри crawl()

| Параметр | Default | Опис |
|----------|---------|------|
| `max_depth` | 3 | Глибина сканування |
| `max_pages` | 100 | Ліміт сторінок |
| `same_domain` | True | Тільки поточний домен |
| `request_delay` | 0.5 | Затримка між запитами (сек) |
| `timeout` | 300 | Загальний таймаут (сек) |
| `driver` | "http" | Драйвер: `http`, `playwright` |

### URL Rules

```python
from graph_crawler import crawl, URLRule

rules = [
    URLRule(pattern=r"\.pdf$", should_scan=False),
    URLRule(pattern=r"/admin/", should_scan=False),
    URLRule(pattern=r"/products/", priority=10),
]

graph = crawl("https://example.com", url_rules=rules)
```

### Операції з графом

```python
# Статистика
stats = graph.get_stats()

# Пошук
node = graph.get_node_by_url("https://example.com/page")

# Об'єднання графів
merged = graph1 + graph2

# Експорт
graph.export_edges("edges.csv", format="csv")
graph.export_edges("graph.dot", format="dot")
```

## Драйвери

| Драйвер | Призначення |
|---------|-------------|
| `http` | Статичні сайти (default) |
| `playwright` | JavaScript/SPA сайти |

```python
# Playwright для JS сайтів
graph = gc.crawl("https://spa-site.com", driver="playwright")
```

## Storage

| Тип | Рекомендовано |
|-----|---------------|
| `memory` | < 1K сторінок |
| `json` | 1K - 20K сторінок |
| `sqlite` | 20K+ сторінок |
| `mongodb` | Великі проекти |

## CLI

```bash
graph-crawler crawl https://example.com --max-depth 2
graph-crawler list
graph-crawler info graph_name
```

## Вимоги

- Python 3.11+

## Ліцензія

MIT
