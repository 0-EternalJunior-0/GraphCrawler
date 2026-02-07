# Graph Operations

> **Час читання:** 8 хвилин  
> **Рівень:** Середній

Математичні операції над графами та аналіз структури.

---

## Огляд

GraphCrawler підтримує повний набір операцій над графами:

| Операція | Оператор | Метод |
|----------|----------|-------|
| Об'єднання | `+`, `\|` | `union()` |
| Різниця | `-` | `difference()` |
| Перетин | `&` | `intersection()` |
| Симетрична різниця | `^` | `symmetric_difference()` |
| Підграф | `<`, `<=` | `is_subgraph()` |
| Надграф | `>`, `>=` | `is_supergraph()` |

---

## Об'єднання графів (Union)

### Оператор `+`

```python
import graph_crawler as gc

graph1 = gc.crawl("https://site1.com", max_depth=2)
graph2 = gc.crawl("https://site2.com", max_depth=2)

# Об'єднання
merged = graph1 + graph2

print(f"Graph1: {len(graph1.nodes)} nodes")
print(f"Graph2: {len(graph2.nodes)} nodes")
print(f"Merged: {len(merged.nodes)} nodes")
```

### Оператор `|`

```python
# Еквівалентно
merged = graph1 | graph2
```

### Use Case: Моніторинг змін

```python
# Краулінг різних розділів сайту
products = gc.crawl("https://shop.com/products", max_depth=3)
blog = gc.crawl("https://shop.com/blog", max_depth=3)
docs = gc.crawl("https://shop.com/docs", max_depth=3)

# Повна карта сайту
full_site = products + blog + docs
print(f"Total site structure: {len(full_site.nodes)} pages")
```

---

## Різниця графів (Difference)

### Оператор `-`

```python
# Знайти нові сторінки
old_graph = gc.crawl("https://example.com")  # Вчора
# ... час проходить ...
new_graph = gc.crawl("https://example.com")  # Сьогодні

# Нові сторінки (є в new, немає в old)
new_pages = new_graph - old_graph
print(f"New pages: {len(new_pages.nodes)}")
for node in new_pages:
    print(f"  + {node.url}")

# Видалені сторінки (є в old, немає в new)
removed_pages = old_graph - new_graph
print(f"Removed pages: {len(removed_pages.nodes)}")
for node in removed_pages:
    print(f"  - {node.url}")
```

### Use Case: Аудит контенту

```python
import graph_crawler as gc
import json
from datetime import datetime

def audit_site(url, history_file='audit_history.json'):
    """Аудит змін на сайті."""
    current = gc.crawl(url, max_depth=5)
    
    # Завантажити попередній стан
    try:
        with open(history_file) as f:
            history = json.load(f)
            previous_urls = set(history['urls'])
    except FileNotFoundError:
        previous_urls = set()
    
    current_urls = set(n.url for n in current)
    
    report = {
        'date': datetime.now().isoformat(),
        'total_pages': len(current_urls),
        'new_pages': list(current_urls - previous_urls),
        'removed_pages': list(previous_urls - current_urls),
    }
    
    # Зберегти поточний стан
    with open(history_file, 'w') as f:
        json.dump({'urls': list(current_urls)}, f)
    
    return report

report = audit_site("https://example.com")
print(f"New: {len(report['new_pages'])}")
print(f"Removed: {len(report['removed_pages'])}")
```

---

## Перетин графів (Intersection)

### Оператор `&`

```python
# Спільні сторінки
common = graph1 & graph2
print(f"Common pages: {len(common.nodes)}")
```

### Use Case: Аналіз конкурентів

```python
import asyncio
import graph_crawler as gc

async def analyze_competitors(urls):
    async with gc.AsyncCrawler(max_depth=2) as crawler:
        graphs = await asyncio.gather(
            *[crawler.crawl(url) for url in urls]
        )
    
    # Знайти спільні патерни URL
    url_patterns = []
    for g in graphs:
        patterns = set()
        for node in g:
            # Витягти патерн (без домену)
            path = node.url.split('/')[-1] if '/' in node.url else ''
            patterns.add(path)
        url_patterns.append(patterns)
    
    # Спільні патерни у всіх конкурентів
    common_patterns = url_patterns[0]
    for p in url_patterns[1:]:
        common_patterns &= p
    
    return common_patterns

competitors = [
    "https://shop1.com",
    "https://shop2.com",
    "https://shop3.com",
]

common = asyncio.run(analyze_competitors(competitors))
print(f"Common URL patterns: {common}")
```

---

## Симетрична різниця (XOR)

### Оператор `^`

```python
# Сторінки, які є тільки в одному з графів
unique = graph1 ^ graph2
print(f"Unique to either graph: {len(unique.nodes)}")
```

---

## Порівняння графів

### Підграф `<`, `<=`

```python
# Перевірка чи graph1 є підграфом graph2
if graph1 < graph2:
    print("graph1 is a strict subgraph of graph2")

if graph1 <= graph2:
    print("graph1 is a subgraph of graph2 (or equal)")
```

### Надграф `>`, `>=`

```python
if graph1 > graph2:
    print("graph1 is a strict supergraph of graph2")

if graph1 >= graph2:
    print("graph1 is a supergraph of graph2 (or equal)")
```

### Рівність `==`

```python
if graph1 == graph2:
    print("Graphs are equal")
```

### Use Case: Перевірка повноти краулінгу

```python
# Краулінг sitemap
sitemap_graph = gc.crawl_sitemap("https://example.com")

# Краулінг через посилання
link_graph = gc.crawl("https://example.com", max_depth=10)

# Перевірка чи всі URL з sitemap знайдені
if sitemap_graph <= link_graph:
    print("All sitemap URLs found via links!")
else:
    missing = sitemap_graph - link_graph
    print(f"Missing {len(missing.nodes)} URLs from sitemap:")
    for node in missing:
        print(f"  - {node.url}")
```

---

## Статистика графа

### get_stats()

```python
stats = graph.get_stats()
print(stats)
# {
#     'total_nodes': 150,
#     'scanned_nodes': 145,
#     'pending_nodes': 5,
#     'failed_nodes': 0,
#     'total_edges': 487,
#     'unique_domains': 1,
#     'avg_depth': 2.3,
#     'max_depth': 5,
# }
```

### get_popular_nodes()

```python
# Топ сторінок за вхідними посиланнями
popular = graph.get_popular_nodes(top_n=10, by='in_degree')
for node in popular:
    print(f"{node.url}: {node.metadata.get('in_degree', 0)} incoming links")
```

### get_edge_statistics()

```python
edge_stats = graph.get_edge_statistics()
print(edge_stats)
# {
#     'total_edges': 487,
#     'internal_edges': 450,
#     'external_edges': 37,
#     'avg_out_degree': 3.2,
#     'avg_in_degree': 3.2,
#     'max_out_degree': 15,
#     'max_in_degree': 25,
# }
```

### find_cycles()

```python
# Знайти цикли в графі
cycles = graph.find_cycles(max_cycles=10)
print(f"Found {len(cycles)} cycles:")
for cycle in cycles:
    print(f"  {' -> '.join(cycle[:5])}...")
```

---

## Аналіз структури

### Orphan Pages (без вхідних посилань)

```python
from collections import defaultdict

def find_orphans(graph):
    """Знайти сторінки без вхідних посилань."""
    in_degree = defaultdict(int)
    for edge in graph.edges:
        in_degree[edge.target_node_id] += 1
    
    orphans = []
    for node in graph:
        if node.depth > 0 and in_degree[node.node_id] == 0:
            orphans.append(node)
    
    return orphans

orphans = find_orphans(graph)
print(f"Orphan pages: {len(orphans)}")
```

### Dead Ends (без вихідних посилань)

```python
def find_dead_ends(graph):
    """Знайти сторінки без вихідних посилань."""
    out_degree = defaultdict(int)
    for edge in graph.edges:
        out_degree[edge.source_node_id] += 1
    
    dead_ends = []
    for node in graph:
        if node.scanned and out_degree[node.node_id] == 0:
            dead_ends.append(node)
    
    return dead_ends

dead_ends = find_dead_ends(graph)
print(f"Dead ends: {len(dead_ends)}")
```

### Глибина сайту

```python
from collections import Counter

def analyze_depth(graph):
    """Аналіз розподілу сторінок по глибині."""
    distribution = Counter(node.depth for node in graph)
    
    print("Depth distribution:")
    for depth in sorted(distribution.keys()):
        count = distribution[depth]
        bar = '█' * (count // 5)
        print(f"  Level {depth}: {count:4} {bar}")
    
    return distribution

analyze_depth(graph)
```

---

## Експорт для візуалізації

### Graphviz (DOT)

```python
graph.export_edges("site.dot", format="dot")

# Візуалізація
import os
os.system("dot -Tpng site.dot -o site.png")
os.system("dot -Tsvg site.dot -o site.svg")
```

### NetworkX (Python)

```python
import networkx as nx
import matplotlib.pyplot as plt

def to_networkx(graph):
    """Конвертація в NetworkX граф."""
    G = nx.DiGraph()
    
    for node in graph:
        G.add_node(node.node_id, url=node.url, title=node.get_title())
    
    for edge in graph.edges:
        G.add_edge(edge.source_node_id, edge.target_node_id)
    
    return G

G = to_networkx(graph)

# Візуалізація
plt.figure(figsize=(20, 20))
nx.draw(G, with_labels=False, node_size=50, alpha=0.7)
plt.savefig("graph.png", dpi=150)
```

---

## Наступні кроки

- [URL Rules →](url-rules.md)
- [Cache Modes →](cache-modes.md)
- [API Reference →](../api/API.md)
