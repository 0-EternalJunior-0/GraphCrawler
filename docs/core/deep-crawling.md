# Deep Crawling

> **Час читання:** 10 хвилин  
> **Рівень:** Середній

Просунуті техніки краулінгу для складних та великих сайтів.

---

## Множинні точки входу (Seed URLs)

### Базове використання

```python
import graph_crawler as gc

graph = gc.crawl(
    seed_urls=[
        "https://example.com/products/",
        "https://example.com/blog/",
        "https://example.com/docs/",
    ],
    max_depth=3
)
```

### Use Cases

- **E-commerce:** Краулінг різних категорій товарів
- **Документація:** Різні версії документів
- **Мультимовність:** Версії сайту різними мовами

---

## Інкрементальний краулінг

### Продовження краулінгу

```python
import graph_crawler as gc

# Перший краулінг
graph1 = gc.crawl(
    "https://example.com",
    max_pages=100,
    storage="json",
    storage_config={"path": "./crawl1.json"}
)

print(f"First crawl: {len(graph1.nodes)} pages")

# Продовження краулінгу
graph2 = gc.crawl(
    base_graph=graph1,
    max_pages=200,  # Додатково ще 100 сторінок
)

print(f"After continuation: {len(graph2.nodes)} pages")
```

### Комбінація з seed_urls

```python
# Початковий краулінг sitemap
sitemap_graph = gc.crawl_sitemap("https://example.com")

# Фільтрація - тільки продукти
product_urls = [n.url for n in sitemap_graph if '/product/' in n.url]

# Детальний краулінг з нових точок
graph = gc.crawl(
    base_graph=sitemap_graph,
    seed_urls=product_urls[:100],
    max_depth=2
)
```

---

## Драйвери для різних сценаріїв

### HTTP Driver (Default)

Найшвидший, для статичних сайтів:

```python
graph = gc.crawl(
    "https://example.com",
    driver="http",
    driver_config={
        "max_connections": 100,    # Паралельні з'єднання
        "timeout": 30,             # Таймаут запиту
        "ssl_verify": True,        # Перевірка SSL
        "follow_redirects": True,
    }
)
```

### Playwright Driver

Для JavaScript-heavy сайтів (React, Vue, Angular):

```python
graph = gc.crawl(
    "https://spa-app.com",
    driver="playwright",
    driver_config={
        "headless": True,                    # Без UI
        "browser": "chromium",               # chromium/firefox/webkit
        "wait_for": "networkidle",           # Чекати на завершення JS
        "timeout": 60000,                    # ms
        "viewport": {"width": 1920, "height": 1080},
    }
)
```

### Stealth Driver

Для обходу антибот-захисту:

```python
graph = gc.crawl(
    "https://protected-site.com",
    driver="stealth",
    driver_config={
        "fingerprint": "random",    # Випадковий fingerprint
        "proxy_rotation": True,
    }
)
```

---

## Storage для великих краулінгів

### Memory (< 1K pages)

```python
graph = gc.crawl(url, storage="memory")
```

### JSON (1K - 20K pages)

```python
graph = gc.crawl(
    url,
    storage="json",
    storage_config={
        "path": "./crawl_data.json",
        "indent": 2,  # Pretty print
    }
)
```

### SQLite (20K+ pages)

```python
graph = gc.crawl(
    url,
    max_pages=100000,
    storage="sqlite",
    storage_config={
        "path": "./crawl.db",
        "journal_mode": "WAL",  # Write-Ahead Logging
    }
)
```

### PostgreSQL (Production)

```python
graph = gc.crawl(
    url,
    storage="postgresql",
    storage_config={
        "host": "localhost",
        "port": 5432,
        "database": "crawler",
        "user": "crawler_user",
        "password": "secret",
    }
)
```

### MongoDB (Production)

```python
graph = gc.crawl(
    url,
    storage="mongodb",
    storage_config={
        "host": "localhost",
        "port": 27017,
        "database": "crawler",
        "collection": "crawl_results",
    }
)
```

---

## Callbacks та моніторинг

Всі callbacks отримують словник `data` з відповідними полями.

### Progress Callback

```python
def on_progress(data):
    current = data.get('current', 0)
    total = data.get('total', 0)
    url = data.get('url', '')
    percent = (current / total) * 100 if total else 0
    print(f"[{percent:.1f}%] {current}/{total} - {url[:50]}...")

graph = gc.crawl(
    "https://example.com",
    on_progress=on_progress,
)
```

### Node Scanned Callback

```python
def on_node_scanned(data):
    node = data.get('node')
    if node:
        title = node.get_title() or 'No title'
        status = node.response_status
        print(f"[{status}] {title[:40]}... - {node.url}")

graph = gc.crawl(
    "https://example.com",
    on_node_scanned=on_node_scanned,
)
```

### Error Callback

```python
def on_error(data):
    url = data.get('url', '')
    error = data.get('error', '')
    print(f"ERROR: {url}")
    print(f"  Reason: {error}")
    # Можна логувати в файл
    with open('errors.log', 'a') as f:
        f.write(f"{url}\t{error}\n")

graph = gc.crawl(
    "https://example.com",
    on_error=on_error,
)
```

### Completed Callback

```python
def on_completed(data):
    graph = data.get('graph')
    stats = data.get('stats', {})
    print(f"\n\nCrawl completed!")
    print(f"  Total pages: {stats.get('total_nodes', 0)}")
    print(f"  Scanned: {stats.get('scanned_nodes', 0)}")
    print(f"  Links: {stats.get('total_edges', 0)}")
    
    # Зберегти результати
    if graph:
        graph.export_edges('final_result.json', format='json')

graph = gc.crawl(
    "https://example.com",
    on_completed=on_completed,
)
```

---

## Edge Strategy

Контроль створення ребер (посилань) в графі.

### All (Default)

Створювати всі знайдені ребра:

```python
graph = gc.crawl(url, edge_strategy="all")
```

### New Only

Тільки нові посилання (уникати дублікатів):

```python
graph = gc.crawl(url, edge_strategy="new_only")
```

### Deeper Only

Тільки посилання на глибші рівні:

```python
graph = gc.crawl(url, edge_strategy="deeper_only")
```

### Max In-Degree

Обмежити кількість вхідних посилань на вузол:

```python
graph = gc.crawl(url, edge_strategy="max_in_degree")
```

---

## Performance Tips

### 1. Використовуйте Free-Threading (Python 3.14)

```bash
export PYTHON_GIL=0
```

### 2. Налаштуйте паралельність

```python
graph = gc.crawl(
    url,
    driver_config={
        "max_connections": 50,  # Більше паралельних запитів
    },
    request_delay=0.1,  # Менша затримка
)
```

### 3. Фільтруйте непотрібні URL

```python
from graph_crawler import URLRule

rules = [
    URLRule(pattern=r"\.pdf$", should_scan=False),
    URLRule(pattern=r"\.zip$", should_scan=False),
    URLRule(pattern=r"/cdn/", should_scan=False),
]

graph = gc.crawl(url, url_rules=rules)
```

### 4. Обмежте плагіни

```python
from graph_crawler.extensions.plugins.node import (
    MetadataExtractorPlugin,
    LinkExtractorPlugin,
)

# Тільки необхідні плагіни
graph = gc.crawl(
    url,
    plugins=[
        MetadataExtractorPlugin(),
        LinkExtractorPlugin(),
    ]
)
```

### 5. Використовуйте правильний storage

| Сторінок | Storage | Причина |
|----------|---------|---------|  
| < 1K | memory | Найшвидший |
| 1K-20K | json | Простий, portable |
| 20K+ | sqlite | Швидкий для великих об'ємів |
| 100K+ | postgresql | Production-ready |

---

## Приклад: Повний краулінг e-commerce

```python
import graph_crawler as gc
from graph_crawler import URLRule
from graph_crawler.extensions.plugins.node import (
    MetadataExtractorPlugin,
    LinkExtractorPlugin,
)
from graph_crawler.extensions.plugins.node.extractors import PriceExtractorPlugin

def progress(data):
    current = data.get('current', 0)
    total = data.get('total', 0)
    if current % 100 == 0:
        print(f"Progress: {current}/{total}")

def error(data):
    url = data.get('url', '')
    err = data.get('error', '')
    print(f"Failed: {url} - {err}")

def completed(data):
    graph = data.get('graph')
    stats = data.get('stats', {})
    print(f"\nDone! {stats.get('scanned_nodes', 0)} pages crawled")
    if graph:
        graph.export_edges('ecommerce.json', format='json')

rules = [
    URLRule(pattern=r"/product/", priority=10),
    URLRule(pattern=r"/category/", priority=8),
    URLRule(pattern=r"/cart", should_scan=False),
    URLRule(pattern=r"/account", should_scan=False),
    URLRule(pattern=r"\.pdf$", should_scan=False),
]

graph = gc.crawl(
    "https://shop.example.com",
    
    # Масштаб
    max_depth=6,
    max_pages=50000,
    timeout=7200,  # 2 години
    
    # Швидкість
    request_delay=0.1,
    driver_config={"max_connections": 50},
    
    # Storage
    storage="sqlite",
    storage_config={"path": "./ecommerce.db"},
    
    # Плагіни
    plugins=[
        MetadataExtractorPlugin(),
        LinkExtractorPlugin(),
        PriceExtractorPlugin(),
    ],
    
    # URL правила
    url_rules=rules,
    
    # Callbacks
    on_progress=progress,
    on_error=error,
    on_completed=completed,
)
```

---

## Наступні кроки

- [URL Rules →](url-rules.md)
- [Graph Operations →](graph-operations.md)
- [Distributed Crawling →](../advanced/distributed-crawling.md)
