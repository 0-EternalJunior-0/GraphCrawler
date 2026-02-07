# Session Management

> **Час читання:** 8 хвилин  
> **Рівень:** Senior

Управління сесіями та станом краулера.

---

## Reusable Crawler

### Sync

```python
import graph_crawler as gc

# Одна сесія для багатьох краулінгів
with gc.Crawler(
    max_depth=3,
    driver_config={"timeout": 30},
) as crawler:
    # Cookies та headers зберігаються
    graph1 = crawler.crawl("https://site1.com")
    graph2 = crawler.crawl("https://site2.com")
```

### Async

```python
import asyncio
import graph_crawler as gc

async def main():
    async with gc.AsyncCrawler(max_depth=3) as crawler:
        graphs = await asyncio.gather(
            crawler.crawl("https://site1.com"),
            crawler.crawl("https://site2.com"),
        )
    return graphs

results = asyncio.run(main())
```

---

## Cookies

### Встановлення cookies

```python
graph = gc.crawl(
    "https://example.com",
    driver_config={
        "cookies": {
            "session_id": "abc123",
            "auth_token": "xyz789",
        }
    }
)
```

### Cookies з файлу

```python
import json

# Завантажити cookies з браузера
with open('cookies.json') as f:
    cookies = json.load(f)

graph = gc.crawl(
    "https://example.com",
    driver_config={"cookies": cookies}
)
```

---

## Headers

### Кастомні заголовки

```python
graph = gc.crawl(
    "https://api.example.com",
    driver_config={
        "headers": {
            "Authorization": "Bearer token123",
            "X-Custom-Header": "value",
            "Accept-Language": "uk-UA,uk;q=0.9",
        }
    }
)
```

---

## Browser State (Playwright)

### Збереження стану

```python
graph = gc.crawl(
    "https://example.com",
    driver="playwright",
    driver_config={
        "storage_state": "./browser_state.json",
        "save_state": True,
    }
)
```

### Відновлення стану

```python
# Використати збережений стан
graph = gc.crawl(
    "https://example.com",
    driver="playwright",
    driver_config={
        "storage_state": "./browser_state.json",
    }
)
```

---

## Наступні кроки

- [Hooks & Auth →](hooks-auth.md)
- [Proxy & Security →](proxy-security.md)
