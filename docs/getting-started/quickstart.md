# Quick Start Guide

> **Час читання:** 10 хвилин  
> **Рівень:** Початківець

Цей гайд допоможе вам швидко почати роботу з GraphCrawler.

---

## 🎯 Перший краулінг

### Найпростіший приклад

```python
import graph_crawler as gc

# Краулінг сайту
graph = gc.crawl("https://example.com")

# Результати
print(f"Знайдено {len(graph.nodes)} сторінок")
print(f"Знайдено {len(graph.edges)} посилань")
```

Це все! GraphCrawler автоматично:
- ✅ Обходить сайт до глибини 3
- ✅ Збирає до 100 сторінок
- ✅ Витягує метадані (title, description, h1)
- ✅ Будує граф посилань

---

## 📊 Робота з результатами

### Перегляд нод (сторінок)

```python
# Ітерація по всіх нодах
for node in graph:
    print(f"URL: {node.url}")
    print(f"  Title: {node.get_title()}")
    print(f"  Depth: {node.depth}")
    print(f"  Scanned: {node.scanned}")
    print()
```

### Пошук конкретної сторінки

```python
# За URL
node = graph.get_node_by_url("https://example.com/about")
if node:
    print(f"Found: {node.get_title()}")

# За ID
node = graph.get_node_by_id("some-uuid-here")
```

### Статистика графа

```python
stats = graph.get_stats()
print(stats)
# {
#     'total_nodes': 47,
#     'scanned_nodes': 45,
#     'pending_nodes': 2,
#     'total_edges': 156,
#     'unique_domains': 1,
#     ...
# }
```

### Популярні сторінки

```python
# Топ-10 сторінок за кількістю вхідних посилань
popular = graph.get_popular_nodes(top_n=10, by='in_degree')
for node in popular:
    print(f"{node.url}: {node.metadata.get('in_degree', 0)} incoming links")
```

---

## ⚙️ Налаштування краулінгу

### Основні параметри

```python
graph = gc.crawl(
    "https://example.com",
    
    # Глибина та ліміти
    max_depth=5,          # Максимальна глибина (default: 3)
    max_pages=500,        # Максимум сторінок (default: 100)
    
    # Timing
    timeout=600,          # Таймаут в секундах
    request_delay=0.2,    # Затримка між запитами (default: 0.5)
    
    # Domain filtering
    same_domain=True,     # Тільки поточний домен (default: True)
    
    # Поведінка посилань
    follow_links=True,    # Переходити за посиланнями (default: True)
)
```

### Параметр follow_links

```python
# follow_links=True (default) - краулер переходить за посиланнями
graph = gc.crawl("https://example.com", follow_links=True)

# follow_links=False - сканувати тільки вказані URL
urls = ["https://site.com/page1", "https://site.com/page2"]
graph = gc.crawl(seed_urls=urls, follow_links=False)
```

### Драйвери

```python
# HTTP драйвер (default) - для статичних сайтів
graph = gc.crawl("https://example.com", driver="http")

# Playwright - для JavaScript сайтів (SPA, React, Vue)
graph = gc.crawl("https://spa-app.com", driver="playwright")

# Stealth - для захищених сайтів
graph = gc.crawl("https://protected-site.com", driver="stealth")
```

### Storage

```python
# Memory (default) - для малих краулінгів
graph = gc.crawl(url, storage="memory")

# JSON file - для середніх краулінгів
graph = gc.crawl(
    url,
    storage="json",
    storage_config={"path": "./crawl_data.json"}
)

# SQLite - для великих краулінгів
graph = gc.crawl(
    url,
    storage="sqlite",
    storage_config={"path": "./crawl.db"}
)
```

---

## 🔄 Асинхронний краулінг

Для кращої продуктивності використовуйте async API:

```python
import asyncio
import graph_crawler as gc

async def main():
    # Один сайт
    graph = await gc.async_crawl("https://example.com")
    
    # Паралельний краулінг кількох сайтів
    graphs = await asyncio.gather(
        gc.async_crawl("https://site1.com"),
        gc.async_crawl("https://site2.com"),
        gc.async_crawl("https://site3.com"),
    )
    
    return graphs

results = asyncio.run(main())
```

---

## 🔁 Reusable Crawler

Для краулінгу кількох сайтів з одними налаштуваннями:

```python
# Sync
with gc.Crawler(max_depth=3, request_delay=0.3) as crawler:
    graph1 = crawler.crawl("https://site1.com")
    graph2 = crawler.crawl("https://site2.com")
    graph3 = crawler.crawl("https://site3.com")

# Async
async with gc.AsyncCrawler(max_depth=3) as crawler:
    graphs = await asyncio.gather(
        crawler.crawl("https://site1.com"),
        crawler.crawl("https://site2.com"),
    )
```

---

## 📤 Експорт результатів

### JSON

```python
# Експорт ребер (посилань)
graph.export_edges("edges.json", format="json")
```

**Результат:**
```json
[
  {
    "source": "https://example.com/",
    "target": "https://example.com/about",
    "metadata": {}
  },
  ...
]
```

### CSV

```python
graph.export_edges("edges.csv", format="csv")
```

**Результат:**
```csv
source,target
https://example.com/,https://example.com/about
https://example.com/,https://example.com/contact
...
```

### DOT (Graphviz)

```python
graph.export_edges("graph.dot", format="dot")
```

Можна візуалізувати:
```bash
dot -Tpng graph.dot -o graph.png
```

---

## 🧮 Операції з графами

GraphCrawler підтримує математичні операції над графами:

```python
# Краулінг двох версій сайту
old_graph = gc.crawl("https://example.com", storage="json", 
                     storage_config={"path": "old.json"})
# ... через деякий час ...
new_graph = gc.crawl("https://example.com")

# Знайти нові сторінки
new_pages = new_graph - old_graph
print(f"Нових сторінок: {len(new_pages.nodes)}")

# Знайти видалені сторінки  
removed_pages = old_graph - new_graph
print(f"Видалених сторінок: {len(removed_pages.nodes)}")

# Об'єднати графи
merged = old_graph + new_graph

# Спільні сторінки
common = old_graph & new_graph

# Перевірка підграфа
if old_graph < new_graph:
    print("Всі старі сторінки є в новому графі")
```

---

## 📞 Callbacks для моніторингу

Callbacks отримують словник `data` з відповідними полями:

```python
def on_progress(data):
    """Викликається при оновленні прогресу."""
    current = data.get('current', 0)
    total = data.get('total', 0)
    url = data.get('url', '')
    print(f"Progress: {current}/{total} - {url}")

def on_node_scanned(data):
    """Викликається після сканування кожної ноди."""
    node = data.get('node')
    if node:
        print(f"Scanned: {node.url} - {node.get_title()}")

def on_error(data):
    """Викликається при помилці."""
    url = data.get('url', '')
    error = data.get('error', '')
    print(f"Error on {url}: {error}")

def on_completed(data):
    """Викликається після завершення краулінгу."""
    graph = data.get('graph')
    stats = data.get('stats', {})
    print(f"Done! Total pages: {stats.get('total_nodes', 0)}")

graph = gc.crawl(
    "https://example.com",
    on_progress=on_progress,
    on_node_scanned=on_node_scanned,
    on_error=on_error,
    on_completed=on_completed,
)
```

---

## 🎯 Типові сценарії

### SEO Аудит

```python
graph = gc.crawl(
    "https://mysite.com",
    max_depth=10,
    max_pages=10000,
)

# Знайти сторінки без title
for node in graph:
    if not node.get_title():
        print(f"No title: {node.url}")

# Знайти сторінки без description
for node in graph:
    if not node.get_description():
        print(f"No description: {node.url}")
```

### Sitemap через API

```python
# Краулінг через sitemap.xml
graph = gc.crawl_sitemap("https://example.com")
print(f"URLs in sitemap: {len(graph.nodes)}")
```

### Множинні точки входу

```python
graph = gc.crawl(
    seed_urls=[
        "https://example.com/products/",
        "https://example.com/blog/",
        "https://example.com/about/",
    ],
    max_depth=3
)
```

---

## 🔗 Наступні кроки

- [Приклади коду →](examples.md)
- [Deep Crawling →](../core/deep-crawling.md)
- [URL Rules →](../core/url-rules.md)
- [Plugin System →](../extraction/plugins.md)
- [API Reference →](../api/API.md)

---

**Питання?** Створіть issue на [GitHub](https://github.com/0-EternalJunior-0/GraphCrawler/-/issues)
