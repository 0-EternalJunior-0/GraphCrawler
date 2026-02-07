# Simple Crawling

> **Час читання:** 8 хвилин  
> **Рівень:** Початківець

Основні методи краулінгу з GraphCrawler.

---

## Огляд

GraphCrawler пропонує декілька способів краулінгу:

| Метод | Тип | Опис |
|-------|-----|------|
| `crawl()` | Sync | Найпростіший спосіб, блокуючий виклик |
| `async_crawl()` | Async | Для async/await контексту |
| `Crawler` | Sync | Reusable краулер з context manager |
| `AsyncCrawler` | Async | Async reusable краулер |
| `crawl_sitemap()` | Sync | Краулінг через sitemap.xml |

---

## Функція crawl()

### Базове використання

```python
import graph_crawler as gc

# Найпростіший виклик
graph = gc.crawl("https://example.com")
```

### Параметри

```python
graph = gc.crawl(
    url="https://example.com",    # Початковий URL
    
    # Ліміти
    max_depth=3,                  # Максимальна глибина (default: 3)
    max_pages=100,                # Максимум сторінок (default: 100)
    
    # Швидкість
    timeout=300,                  # Таймаут в секундах
    request_delay=0.5,            # Затримка між запитами (default: 0.5)
    
    # Фільтрація
    same_domain=True,             # Тільки поточний домен (default: True)
    
    # Поведінка посилань
    follow_links=True,            # Переходити за посиланнями (default: True)
    
    # Компоненти
    driver="http",                # "http", "playwright", "stealth"
    storage="memory",             # "memory", "json", "sqlite"
)
```

### Параметр follow_links

Контролює чи краулер переходить за знайденими посиланнями:

```python
# follow_links=True (default)
# Краулер знаходить посилання на сторінках і переходить за ними
graph = gc.crawl("https://example.com", follow_links=True)

# follow_links=False
# Краулер сканує ТІЛЬКИ вказані URL, не переходячи за посиланнями
graph = gc.crawl("https://example.com", follow_links=False)
```

#### Use Case: Сканування списку URL

```python
import graph_crawler as gc

# Маємо конкретний список URL для сканування
urls_to_scan = [
    "https://example.com/page1",
    "https://example.com/page2",
    "https://example.com/page3",
]

# Скануємо тільки ці URL, не переходячи за посиланнями на сторінках
graph = gc.crawl(
    seed_urls=urls_to_scan,
    follow_links=False,  # Не переходити за посиланнями
)

print(f"Scanned exactly {len(graph.nodes)} pages")  # 3 сторінки
```

#### Use Case: Перевірка доступності сторінок

```python
# Перевірка HTTP статусів для списку URL
urls = ["https://site.com/page1", "https://site.com/page2"]

graph = gc.crawl(
    seed_urls=urls,
    follow_links=False,
)

for node in graph:
    print(f"{node.url}: {node.response_status}")
```

**Примітка:** `URLRule.should_follow_links` має вищий пріоритет за глобальний `follow_links` параметр для конкретних URL патернів.

### Приклади

#### Швидкий краулінг (без затримок)

```python
graph = gc.crawl(
    "https://example.com",
    request_delay=0,  # Без затримок
    max_pages=50,
)
```

#### Глибокий краулінг

```python
graph = gc.crawl(
    "https://example.com",
    max_depth=10,
    max_pages=10000,
    timeout=3600,  # 1 година
)
```

#### Краулінг зовнішніх посилань

```python
graph = gc.crawl(
    "https://example.com",
    same_domain=False,  # Дозволити зовнішні домени
    max_depth=2,
)
```

---

## Функція async_crawl()

### Базове використання

```python
import asyncio
import graph_crawler as gc

async def main():
    graph = await gc.async_crawl("https://example.com")
    return graph

graph = asyncio.run(main())
```

### Паралельний краулінг

```python
import asyncio
import graph_crawler as gc

async def crawl_many(urls):
    graphs = await asyncio.gather(
        *[gc.async_crawl(url, max_depth=2) for url in urls]
    )
    return graphs

urls = [
    "https://site1.com",
    "https://site2.com",
    "https://site3.com",
]

results = asyncio.run(crawl_many(urls))
```

---

## Клас Crawler

Reusable синхронний краулер з context manager.

### Використання

```python
import graph_crawler as gc

# Context manager (рекомендовано)
with gc.Crawler(max_depth=3, request_delay=0.3) as crawler:
    graph1 = crawler.crawl("https://site1.com")
    graph2 = crawler.crawl("https://site2.com")
    graph3 = crawler.crawl("https://site3.com")

# Ручне управління
crawler = gc.Crawler(max_depth=3)
try:
    graph = crawler.crawl("https://example.com")
finally:
    crawler.close()
```

### Переваги

- **Перевикористання ресурсів** - одне HTTP з'єднання
- **Спільні налаштування** - не треба дублювати параметри
- **Session sharing** - cookies, headers зберігаються

---

## Клас AsyncCrawler

Async версія Crawler.

```python
import asyncio
import graph_crawler as gc

async def main():
    async with gc.AsyncCrawler(max_depth=3) as crawler:
        # Послідовний краулінг
        graph1 = await crawler.crawl("https://site1.com")
        
        # Паралельний краулінг
        graphs = await asyncio.gather(
            crawler.crawl("https://site2.com"),
            crawler.crawl("https://site3.com"),
        )
    
    return graph1, graphs

result = asyncio.run(main())
```

---

## Функція crawl_sitemap()

Краулінг через sitemap.xml замість обходу посилань.

### Базове використання

```python
import graph_crawler as gc

# Автоматично знаходить sitemap.xml через robots.txt
graph = gc.crawl_sitemap("https://example.com")
```

### Параметри

```python
graph = gc.crawl_sitemap(
    "https://example.com",
    max_urls=1000,           # Максимум URL з sitemap
    include_urls=True,       # Сканувати кінцеві URL (default: True)
    timeout=600,
)
```

### Тільки структура (без сканування)

```python
# Тільки парсинг sitemap без завантаження сторінок
graph = gc.crawl_sitemap(
    "https://example.com",
    include_urls=False,
)

# Отримаємо граф з URL, але без контенту
for node in graph:
    print(f"{node.url} (not scanned)")
```

---

## Результат: Graph

Всі методи краулінгу повертають об'єкт `Graph`.

### Основні властивості

```python
graph = gc.crawl("https://example.com")

# Колекції
print(f"Nodes: {len(graph.nodes)}")
print(f"Edges: {len(graph.edges)}")

# Ітерація
for node in graph:
    print(node.url)

# Перевірка наявності
if "https://example.com/about" in graph:
    print("Found!")

# Доступ за індексом
first_node = graph[0]
```

### Статистика

```python
stats = graph.get_stats()
print(stats)
# {
#     'total_nodes': 47,
#     'scanned_nodes': 45,
#     'pending_nodes': 2,
#     'total_edges': 156,
#     'unique_domains': 1,
# }
```

### Пошук

```python
# За URL
node = graph.get_node_by_url("https://example.com/about")

# За ID
node = graph.get_node_by_id("some-uuid")
```

### Експорт

```python
# JSON
graph.export_edges("edges.json", format="json")

# CSV
graph.export_edges("edges.csv", format="csv")

# DOT (Graphviz)
graph.export_edges("graph.dot", format="dot")
```

---

## Node (Вузол)

Кожна сторінка представлена об'єктом `Node`.

### Властивості

```python
for node in graph:
    # Основне
    print(f"URL: {node.url}")
    print(f"ID: {node.node_id}")
    print(f"Depth: {node.depth}")
    print(f"Scanned: {node.scanned}")
    
    # Метадані
    print(f"Title: {node.get_title()}")
    print(f"H1: {node.get_h1()}")
    print(f"Description: {node.get_description()}")
    
    # HTTP
    print(f"Status: {node.response_status}")
    
    # Часові мітки
    print(f"Created: {node.created_at}")
```

### User Data

Плагіни зберігають дані в `user_data`:

```python
for node in graph:
    # Дані від плагінів
    phones = node.user_data.get('phones', [])
    emails = node.user_data.get('emails', [])
    prices = node.user_data.get('prices', [])
    embedding = node.user_data.get('embedding')
```

---

## Edge (Ребро)

Посилання між сторінками.

```python
for edge in graph.edges:
    print(f"From: {edge.source_node_id}")
    print(f"To: {edge.target_node_id}")
    print(f"Metadata: {edge.metadata}")
```

---

## Наступні кроки

- [Deep Crawling →](deep-crawling.md)
- [URL Rules →](url-rules.md)
- [Graph Operations →](graph-operations.md)
- [API Reference →](../api/API.md)
