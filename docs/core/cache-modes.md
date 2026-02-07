# Cache Modes

> **Час читання:** 5 хвилин  
> **Рівень:** Середній

Режими кешування для оптимізації краулінгу.

---

## Огляд

GraphCrawler підтримує кешування на рівні HTTP та Storage.

---

## HTTP Cache

### Middleware-based caching

```python
from graph_crawler.extensions.middleware import CacheMiddleware

cache_middleware = CacheMiddleware(
    ttl=3600,              # Час життя кешу (секунди)
    max_size=10000,        # Максимум записів
    cache_dir="./cache",   # Директорія кешу
)

graph = gc.crawl(
    "https://example.com",
    driver_config={
        "middleware": [cache_middleware]
    }
)
```

### File-based cache

```python
graph = gc.crawl(
    "https://example.com",
    driver_config={
        "cache_enabled": True,
        "cache_dir": "./http_cache",
        "cache_ttl": 86400,  # 24 години
    }
)
```

---

## Storage Persistence

### Збереження в JSON

```python
# Перший краулінг
graph = gc.crawl(
    "https://example.com",
    storage="json",
    storage_config={
        "path": "./crawl_cache.json"
    }
)

# Наступний краулінг - продовжує з існуючого стану
graph2 = gc.crawl(
    base_graph=graph,
    max_pages=200  # Додаткові сторінки
)
```

### Збереження в SQLite

```python
# Довготривале зберігання
graph = gc.crawl(
    "https://example.com",
    storage="sqlite",
    storage_config={
        "path": "./persistent_cache.db"
    }
)
```

---

## Content Hash

GraphCrawler автоматично обчислює hash контенту:

```python
for node in graph:
    print(f"{node.url}: {node.content_hash}")
```

Це дозволяє:
- Виявляти зміни контенту
- Уникати дублювання
- Оптимізувати повторний краулінг

### Приклад: Виявлення змін

```python
import json

def detect_changes(url, cache_file='content_hashes.json'):
    """Виявляє сторінки зі зміненим контентом."""
    
    # Поточний краулінг
    graph = gc.crawl(url, max_depth=3)
    
    # Завантажити попередні хеші
    try:
        with open(cache_file) as f:
            old_hashes = json.load(f)
    except FileNotFoundError:
        old_hashes = {}
    
    # Знайти зміни
    changed = []
    for node in graph:
        old_hash = old_hashes.get(node.url)
        if old_hash and old_hash != node.content_hash:
            changed.append(node.url)
    
    # Зберегти нові хеші
    new_hashes = {n.url: n.content_hash for n in graph}
    with open(cache_file, 'w') as f:
        json.dump(new_hashes, f)
    
    return changed

changed_pages = detect_changes("https://example.com")
print(f"Changed pages: {len(changed_pages)}")
```

---

## Наступні кроки

- [Deep Crawling →](deep-crawling.md)
- [Proxy & Security →](../advanced/proxy-security.md)
