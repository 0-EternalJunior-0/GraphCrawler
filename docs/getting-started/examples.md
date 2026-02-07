# Code Examples

> **Час читання:** 15 хвилин  
> **Рівень:** Початківець - Середній

Практичні приклади використання GraphCrawler для різних задач.

---

## 📋 Зміст

1. [Базові приклади](#базові-приклади)
2. [SEO та аналітика](#seo-та-аналітика)
3. [Екстракція даних](#екстракція-даних)
4. [Порівняння сайтів](#порівняння-сайтів)
5. [E-commerce](#e-commerce)
6. [AI/ML Pipeline](#aiml-pipeline)

---

## Базові приклади

### Простий краулінг

```python
import graph_crawler as gc

# Мінімальний приклад
graph = gc.crawl("https://example.com")
print(f"Pages: {len(graph.nodes)}, Links: {len(graph.edges)}")
```

### Краулінг з параметрами

```python
import graph_crawler as gc

graph = gc.crawl(
    "https://example.com",
    max_depth=5,
    max_pages=1000,
    request_delay=0.2,
    timeout=3600,  # 1 hour
)

# Вивід статистики
stats = graph.get_stats()
for key, value in stats.items():
    print(f"{key}: {value}")
```

### Краулінг JavaScript сайту

```python
import graph_crawler as gc

# React/Vue/Angular SPA
graph = gc.crawl(
    "https://spa-app.com",
    driver="playwright",
    driver_config={
        "headless": True,
        "wait_for": "networkidle",  # Wait for JS to load
    }
)
```

### Асинхронний паралельний краулінг

```python
import asyncio
import graph_crawler as gc

async def crawl_multiple():
    urls = [
        "https://site1.com",
        "https://site2.com",
        "https://site3.com",
        "https://site4.com",
    ]
    
    async with gc.AsyncCrawler(max_depth=3) as crawler:
        graphs = await asyncio.gather(
            *[crawler.crawl(url) for url in urls]
        )
    
    # Об'єднати всі графи
    combined = graphs[0]
    for g in graphs[1:]:
        combined = combined + g
    
    return combined

result = asyncio.run(crawl_multiple())
print(f"Total pages from all sites: {len(result.nodes)}")
```

---

## SEO та аналітика

### Знайти сторінки без мета-тегів

```python
import graph_crawler as gc

graph = gc.crawl("https://mysite.com", max_depth=5)

# Сторінки без title
no_title = [n for n in graph if not n.get_title()]
print(f"Pages without title: {len(no_title)}")
for node in no_title[:10]:
    print(f"  - {node.url}")

# Сторінки без description
no_desc = [n for n in graph if not n.get_description()]
print(f"\nPages without description: {len(no_desc)}")
for node in no_desc[:10]:
    print(f"  - {node.url}")

# Сторінки з занадто довгим title
long_title = [n for n in graph if len(n.get_title() or '') > 60]
print(f"\nPages with title > 60 chars: {len(long_title)}")
```

### Знайти orphan pages (без вхідних посилань)

```python
import graph_crawler as gc
from collections import defaultdict

graph = gc.crawl("https://mysite.com", max_depth=10)

# Підрахувати вхідні посилання
in_degree = defaultdict(int)
for edge in graph.edges:
    in_degree[edge.target_node_id] += 1

# Знайти orphan pages (крім головної)
orphans = []
for node in graph:
    if node.depth > 0 and in_degree[node.node_id] == 0:
        orphans.append(node)

print(f"Orphan pages: {len(orphans)}")
for node in orphans:
    print(f"  - {node.url}")
```

### Аналіз глибини сайту

```python
import graph_crawler as gc
from collections import Counter

graph = gc.crawl("https://mysite.com", max_depth=10)

# Розподіл сторінок по глибині
depth_distribution = Counter(node.depth for node in graph)

print("Page distribution by depth:")
for depth in sorted(depth_distribution.keys()):
    count = depth_distribution[depth]
    bar = "█" * (count // 5)
    print(f"  Depth {depth}: {count:4} {bar}")
```

### Експорт для візуалізації

```python
import graph_crawler as gc

graph = gc.crawl("https://mysite.com", max_depth=3)

# Експорт в різних форматах
graph.export_edges("site_map.json", format="json")
graph.export_edges("site_map.csv", format="csv")
graph.export_edges("site_map.dot", format="dot")

# Візуалізація через Graphviz
import os
os.system("dot -Tpng site_map.dot -o site_map.png")
os.system("dot -Tsvg site_map.dot -o site_map.svg")
```

---

## Екстракція даних

### Витягти контактні дані

```python
import graph_crawler as gc
from graph_crawler.extensions.plugins.node import (
    PhoneExtractorPlugin,
    EmailExtractorPlugin,
)

graph = gc.crawl(
    "https://company.com",
    max_depth=3,
    plugins=[
        PhoneExtractorPlugin(),
        EmailExtractorPlugin(),
    ]
)

# Зібрати всі контакти
all_phones = set()
all_emails = set()

for node in graph:
    phones = node.user_data.get('phones', [])
    emails = node.user_data.get('emails', [])
    
    all_phones.update(phones)
    all_emails.update(emails)
    
    if phones or emails:
        print(f"\n{node.url}:")
        if phones:
            print(f"  Phones: {phones}")
        if emails:
            print(f"  Emails: {emails}")

print(f"\n\nTotal unique phones: {len(all_phones)}")
print(f"Total unique emails: {len(all_emails)}")
```

### Витягти структуровані дані (Schema.org)

```python
import graph_crawler as gc
from graph_crawler.extensions.plugins.node.structured_data import (
    StructuredDataPlugin,
    StructuredDataOptions,
)

# Налаштування для e-commerce
options = StructuredDataOptions(
    allowed_types=['Product', 'Offer', 'Organization'],
)

graph = gc.crawl(
    "https://shop.com",
    plugins=[StructuredDataPlugin(options)]
)

for node in graph:
    sd = node.user_data.get('structured_data')
    if sd and sd.has_data:
        print(f"\n{node.url}:")
        print(f"  Type: {sd.get_type()}")
        print(f"  Name: {sd.get_property('name')}")
        
        # Для продуктів
        for product in sd.get_all_of_type('Product'):
            print(f"  Product: {product.get('name')}")
            offers = product.get('offers', {})
            if offers:
                print(f"    Price: {offers.get('price')} {offers.get('priceCurrency')}")
```

### Кастомний плагін для екстракції

```python
import graph_crawler as gc
from graph_crawler import BaseNodePlugin, NodePluginType
import re

class SocialLinksPlugin(BaseNodePlugin):
    """Витягує посилання на соціальні мережі."""
    
    SOCIAL_PATTERNS = {
        'facebook': r'facebook\.com/[\w.]+',
        'twitter': r'twitter\.com/[\w]+',
        'instagram': r'instagram\.com/[\w.]+',
        'linkedin': r'linkedin\.com/(in|company)/[\w-]+',
        'youtube': r'youtube\.com/(c|channel|user)/[\w-]+',
    }
    
    @property
    def name(self):
        return "social_links"
    
    @property
    def plugin_type(self):
        return NodePluginType.ON_HTML_PARSED
    
    def execute(self, context):
        html = context.html or ''
        social = {}
        
        for platform, pattern in self.SOCIAL_PATTERNS.items():
            matches = re.findall(pattern, html, re.IGNORECASE)
            if matches:
                social[platform] = list(set(matches))
        
        context.user_data['social_links'] = social
        return context

# Використання
graph = gc.crawl(
    "https://company.com",
    plugins=[SocialLinksPlugin()]
)

for node in graph:
    social = node.user_data.get('social_links', {})
    if social:
        print(f"\n{node.url}:")
        for platform, links in social.items():
            print(f"  {platform}: {links}")
```

---

## Порівняння сайтів

### Моніторинг змін

```python
import graph_crawler as gc
import json
from datetime import datetime

def save_snapshot(graph, filename):
    """Зберегти снапшот сайту."""
    data = {
        'timestamp': datetime.now().isoformat(),
        'urls': [node.url for node in graph],
        'stats': graph.get_stats(),
    }
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)

def load_snapshot(filename):
    """Завантажити попередній снапшот."""
    with open(filename) as f:
        return json.load(f)

# Поточний краулінг
current = gc.crawl("https://example.com", max_depth=5)
current_urls = set(node.url for node in current)

# Порівняти з попереднім (якщо є)
try:
    previous = load_snapshot('snapshot.json')
    previous_urls = set(previous['urls'])
    
    # Аналіз змін
    new_pages = current_urls - previous_urls
    removed_pages = previous_urls - current_urls
    
    print(f"New pages: {len(new_pages)}")
    for url in list(new_pages)[:10]:
        print(f"  + {url}")
    
    print(f"\nRemoved pages: {len(removed_pages)}")
    for url in list(removed_pages)[:10]:
        print(f"  - {url}")
        
except FileNotFoundError:
    print("No previous snapshot found")

# Зберегти поточний снапшот
save_snapshot(current, 'snapshot.json')
print(f"\nSnapshot saved with {len(current.nodes)} pages")
```

### Порівняння конкурентів

```python
import asyncio
import graph_crawler as gc

async def compare_competitors():
    competitors = [
        "https://competitor1.com",
        "https://competitor2.com",
        "https://competitor3.com",
    ]
    
    async with gc.AsyncCrawler(max_depth=3, max_pages=500) as crawler:
        graphs = await asyncio.gather(
            *[crawler.crawl(url) for url in competitors]
        )
    
    # Порівняння
    print("\nCompetitor Analysis:")
    print(f"{'Site':<30} {'Pages':>8} {'Links':>8} {'Avg Depth':>10}")
    print("-" * 60)
    
    for url, graph in zip(competitors, graphs):
        avg_depth = sum(n.depth for n in graph) / max(len(graph.nodes), 1)
        print(f"{url:<30} {len(graph.nodes):>8} {len(graph.edges):>8} {avg_depth:>10.2f}")

asyncio.run(compare_competitors())
```

---

## E-commerce

### Краулінг каталогу товарів

```python
import graph_crawler as gc
from graph_crawler import URLRule
from graph_crawler.extensions.plugins.node import PriceExtractorPlugin

# URL правила для e-commerce
rules = [
    URLRule(pattern=r"/product/", priority=10),      # Високий пріоритет для товарів
    URLRule(pattern=r"/category/", priority=8),      # Категорії
    URLRule(pattern=r"/cart", should_scan=False),    # Ігнорувати кошик
    URLRule(pattern=r"/checkout", should_scan=False),# Ігнорувати оплату
    URLRule(pattern=r"\.pdf$", should_scan=False),   # Ігнорувати PDF
]

graph = gc.crawl(
    "https://shop.com",
    max_depth=5,
    max_pages=5000,
    url_rules=rules,
    plugins=[PriceExtractorPlugin()],
)

# Аналіз товарів
products = []
for node in graph:
    if '/product/' in node.url:
        prices = node.user_data.get('prices', [])
        products.append({
            'url': node.url,
            'title': node.get_title(),
            'prices': prices,
        })

print(f"Found {len(products)} products")
for p in products[:10]:
    print(f"  {p['title']}: {p['prices']}")
```

### Моніторинг цін

```python
import graph_crawler as gc
from graph_crawler.extensions.plugins.node import PriceExtractorPlugin
import json

def monitor_prices(url, history_file='price_history.json'):
    graph = gc.crawl(
        url,
        max_depth=3,
        plugins=[PriceExtractorPlugin()],
    )
    
    # Збір цін
    current_prices = {}
    for node in graph:
        prices = node.user_data.get('prices', [])
        if prices:
            current_prices[node.url] = {
                'title': node.get_title(),
                'prices': prices,
            }
    
    # Порівняння з історією
    try:
        with open(history_file) as f:
            history = json.load(f)
    except FileNotFoundError:
        history = {}
    
    # Знайти зміни цін
    changes = []
    for url, data in current_prices.items():
        if url in history:
            old_prices = history[url]['prices']
            new_prices = data['prices']
            if old_prices != new_prices:
                changes.append({
                    'url': url,
                    'title': data['title'],
                    'old': old_prices,
                    'new': new_prices,
                })
    
    # Зберегти нову історію
    with open(history_file, 'w') as f:
        json.dump(current_prices, f, indent=2)
    
    return changes

# Використання
changes = monitor_prices("https://shop.com")
for change in changes:
    print(f"Price changed: {change['title']}")
    print(f"  Old: {change['old']}")
    print(f"  New: {change['new']}")
```

---

## AI/ML Pipeline

### Підготовка даних для RAG

```python
import graph_crawler as gc
from graph_crawler.extensions.plugins.node import TextExtractorPlugin
from graph_crawler.extensions.plugins.node.vectorization import RealTimeVectorizerPlugin

# Краулінг документації
graph = gc.crawl(
    "https://docs.example.com",
    max_depth=5,
    plugins=[
        TextExtractorPlugin(),
        RealTimeVectorizerPlugin(),
    ]
)

# Підготовка для vector database
documents = []
for node in graph:
    text = node.user_data.get('text_content', '')
    embedding = node.user_data.get('embedding')
    
    if text and embedding:
        documents.append({
            'id': node.node_id,
            'url': node.url,
            'title': node.get_title(),
            'text': text,
            'embedding': embedding,
            'metadata': {
                'depth': node.depth,
                'h1': node.get_h1(),
            }
        })

print(f"Prepared {len(documents)} documents for vector DB")

# Приклад збереження в Chroma
try:
    import chromadb
    
    client = chromadb.Client()
    collection = client.create_collection("docs")
    
    collection.add(
        ids=[d['id'] for d in documents],
        embeddings=[d['embedding'] for d in documents],
        documents=[d['text'] for d in documents],
        metadatas=[d['metadata'] for d in documents],
    )
    print(f"Stored in ChromaDB")
except ImportError:
    print("ChromaDB not installed")
```

### Класифікація контенту

```python
import graph_crawler as gc
from graph_crawler import BaseNodePlugin, NodePluginType

class ContentClassifierPlugin(BaseNodePlugin):
    """Класифікує контент сторінки."""
    
    CATEGORIES = {
        'product': ['buy', 'price', 'cart', 'shop', 'product'],
        'blog': ['blog', 'article', 'post', 'news', 'read'],
        'docs': ['documentation', 'guide', 'tutorial', 'api', 'reference'],
        'about': ['about', 'team', 'contact', 'company', 'careers'],
    }
    
    @property
    def name(self):
        return "content_classifier"
    
    @property
    def plugin_type(self):
        return NodePluginType.ON_AFTER_SCAN
    
    def execute(self, context):
        text = (context.user_data.get('text_content', '') + 
                context.url + 
                (context.metadata.get('title') or '')).lower()
        
        scores = {}
        for category, keywords in self.CATEGORIES.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                scores[category] = score
        
        if scores:
            best = max(scores, key=scores.get)
            context.user_data['category'] = best
            context.user_data['category_scores'] = scores
        
        return context

# Використання
graph = gc.crawl(
    "https://example.com",
    plugins=[ContentClassifierPlugin()]
)

# Групування по категоріях
from collections import defaultdict
categories = defaultdict(list)

for node in graph:
    cat = node.user_data.get('category', 'other')
    categories[cat].append(node.url)

for cat, urls in categories.items():
    print(f"\n{cat.upper()} ({len(urls)} pages):")
    for url in urls[:5]:
        print(f"  - {url}")
```

---

## 🔗 Наступні кроки

- [Deep Crawling →](../core/deep-crawling.md)
- [URL Rules →](../core/url-rules.md)
- [Plugin System →](../extraction/plugins.md)
- [Distributed Crawling →](../advanced/distributed-crawling.md)

---

**Маєте приклад для додавання?** Створіть PR на [GitHub](https://github.com/0-EternalJunior-0/GraphCrawler)
