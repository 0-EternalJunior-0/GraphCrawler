# 🕸️🐍 GraphCrawler: Open-Source Graph-Based Web Crawler & Scraper

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-4.0.19-green.svg)](CHANGELOG.md)
[![Performance](https://img.shields.io/badge/speedup-3.2x-brightgreen.svg)]()
[![PyPI Downloads](https://img.shields.io/badge/downloads-10k%2B-orange.svg)]()

---

## 🎯 Build Powerful Web Graphs in Minutes

GraphCrawler is a feature-rich, production-ready Python library for web crawling that builds a **graph representation** of website structures. Perfect for SEO analysis, link auditing, content extraction, and AI pipelines.

> **Python 3.14 Optimized** — With free-threading support, GraphCrawler achieves **3.2x faster** crawling speeds!

---

## ⚡ Quick Start

Get started with just 3 lines of code:

```python
import graph_crawler as gc

# Crawl and build a graph
graph = gc.crawl("https://example.com")

print(f"Found {len(graph.nodes)} pages")
print(f"Found {len(graph.edges)} links")
```

**Async? No problem:**

```python
import asyncio
import graph_crawler as gc

async def main():
    graph = await gc.async_crawl("https://example.com")
    return graph

graph = asyncio.run(main())
```

[📚 Full Quick Start Guide →](getting-started/quickstart.md)

---

## 🆕 What's New in v4.0

### 🚀 Python 3.14 Free-Threading

GraphCrawler 4.0 is optimized for Python 3.14's free-threading mode:

```bash
# Enable free-threading for maximum speed
export PYTHON_GIL=0
python your_script.py
```

**Performance Results:**

- ⚡ **2-4x faster** HTML parsing
- 🚀 **3.2x faster** end-to-end crawling
- 📉 **16% less** memory usage
- ⏱️ **30% faster** startup

### 🌱 Multiple Seed URLs

```python
graph = gc.crawl(
    seed_urls=[
        "https://example.com/products/",
        "https://example.com/blog/",
        "https://example.com/docs/",
    ],
    max_depth=3
)
```

### 🔄 Incremental Crawling

```python
# Start with initial crawl
graph1 = gc.crawl("https://example.com", max_pages=50)

# Later, continue from where you left off
graph2 = gc.crawl(base_graph=graph1, max_pages=100)
```

[📖 View Full Changelog →](changelog.md)

---

## ✨ Key Features

### 🕸️ Graph-Based Architecture

Unlike traditional crawlers, GraphCrawler builds a **complete graph structure** of your website:

```python
# Graph operations
merged = graph1 + graph2      # Union
diff = graph2 - graph1        # Difference
common = graph1 & graph2      # Intersection

# Subgraph detection
if graph1 < graph2:
    print("graph1 is a subgraph of graph2")

# Find popular pages
popular = graph.get_popular_nodes(top_n=10, by='in_degree')
```

### 🔌 Plugin Architecture

Extend functionality with powerful plugins:

```python
from graph_crawler import crawl, BaseNodePlugin, NodePluginType

class SEOPlugin(BaseNodePlugin):
    @property
    def name(self):
        return "seo_analyzer"

    @property
    def plugin_type(self):
        return NodePluginType.ON_HTML_PARSED

    def execute(self, context):
        # Your custom logic here
        context.user_data['seo_score'] = calculate_seo(context.html_tree)
        return context

graph = crawl("https://example.com", plugins=[SEOPlugin()])
```

### 🎭 Multiple Drivers

| Driver       | Description            | Best For               |
| ------------ | ---------------------- | ---------------------- |
| `http`       | Async HTTP (aiohttp)   | Static sites (default) |
| `playwright` | Full browser rendering | JavaScript SPAs        |
| `stealth`    | Anti-detection mode    | Protected sites        |

### 💾 Flexible Storage

| Storage      | Scale          | Best For        |
| ------------ | -------------- | --------------- |
| `memory`     | < 1K pages     | Quick tests     |
| `json`       | 1K - 20K pages | Medium projects |
| `sqlite`     | 20K+ pages     | Large crawls    |
| `postgresql` | 100K+ pages    | Production      |
| `mongodb`    | 100K+ pages    | Production      |

### 📊 Rich Data Extraction

Built-in extractors for:

- 📝 **Metadata** (title, description, h1, canonical)
- 🔗 **Links** (internal, external, nofollow)
- 📞 **Phones** (UA, US, RU formats)
- 📧 **Emails** (RFC 5322 compliant)
- 💰 **Prices** (USD, EUR, UAH with ranges)
- 🏷️ **Structured Data** (JSON-LD, Open Graph, Microdata)

---

## 📚 Documentation Structure

| Section                                                   | Description                         | Audience       |
| --------------------------------------------------------- | ----------------------------------- | -------------- |
| [**Getting Started**](getting-started/installation.md)    | Installation & Quick Start          | Everyone       |
| [**Core Concepts**](core/simple-crawling.md)              | Crawling modes, URL rules, caching  | All developers |
| [**Advanced**](advanced/distributed-crawling.md)          | Distributed crawling, proxies, auth | Senior devs    |
| [**Extraction**](extraction/plugins.md)                   | Plugins & data extraction           | All developers |
| [**API Reference**](api/API.md)                           | Complete API documentation          | All developers |
| [**Architecture**](architecture/ARCHITECTURE_OVERVIEW.md) | System internals                    | Architects     |

---

## 🛠️ Installation

### Basic Installation

```bash
pip install graph-crawler
```

### With Optional Features

```bash
# JavaScript rendering (Playwright)
pip install graph-crawler[playwright]

# ML/AI features (embeddings)
pip install graph-crawler[embeddings]

# Database backends
pip install graph-crawler[mongodb,postgresql]

# Everything
pip install graph-crawler[all]
```

[📖 Detailed Installation Guide →](getting-started/installation.md)

---

## 🎓 Learning Paths

### 🌱 Beginner Path (Week 1)

1. [Installation](getting-started/installation.md)
2. [Quick Start](getting-started/quickstart.md)
3. [Simple Crawling](core/simple-crawling.md)
4. [Code Examples](getting-started/examples.md)

### 🚀 Intermediate Path (Week 2-3)

1. [Deep Crawling](core/deep-crawling.md)
2. [URL Rules](core/url-rules.md)
3. [Plugin System](extraction/plugins.md)
4. [Structured Data](extraction/structured-data.md)

### 🏆 Advanced Path (Month 2+)

1. [Distributed Crawling](advanced/distributed-crawling.md)
2. [Proxy & Security](advanced/proxy-security.md)
3. [Architecture Overview](architecture/ARCHITECTURE_OVERVIEW.md)
4. [Custom Extractors](extraction/custom-extractors.md)

---

## 💡 Use Cases

### SEO Analysis

```python
graph = gc.crawl("https://yoursite.com", max_depth=5)

# Find orphan pages (no incoming links)
for node in graph:
    in_degree = len([e for e in graph.edges if e.target_node_id == node.node_id])
    if in_degree == 0 and node.depth > 0:
        print(f"Orphan: {node.url}")

# Export for visualization
graph.export_edges("site_structure.dot", format="dot")
```

### Content Extraction

```python
from graph_crawler.extensions.plugins.node.extractors import (
    PhoneExtractorPlugin,
    EmailExtractorPlugin,
    PriceExtractorPlugin,
)

graph = gc.crawl(
    "https://shop.com",
    plugins=[
        PhoneExtractorPlugin(),
        EmailExtractorPlugin(),
        PriceExtractorPlugin(),
    ]
)

for node in graph:
    print(f"Page: {node.url}")
    print(f"  Phones: {node.user_data.get('phones', [])}")
    print(f"  Emails: {node.user_data.get('emails', [])}")
    print(f"  Prices: {node.user_data.get('prices', [])}")
```

### AI/RAG Pipeline

```python
from graph_crawler.extensions.plugins.node.vectorization import RealTimeVectorizerPlugin

graph = gc.crawl(
    "https://docs.example.com",
    plugins=[RealTimeVectorizerPlugin()]
)

# Export embeddings for vector database
for node in graph:
    embedding = node.user_data.get('embedding')
    if embedding:
        # Store in Pinecone, Chroma, etc.
        vector_db.upsert(node.url, embedding, node.metadata)



## 📖 Quick Links

| Resource      | Link                                                                           |
| ------------- | ------------------------------------------------------------------------------ |
| Installation  | [getting-started/installation.md](getting-started/installation.md)             |
| Quick Start   | [getting-started/quickstart.md](getting-started/quickstart.md)                 |
| API Reference | [api/API.md](api/API.md)                                                       |
| Plugin System | [extraction/plugins.md](extraction/plugins.md)                                 |
| Architecture  | [architecture/ARCHITECTURE_OVERVIEW.md](architecture/ARCHITECTURE_OVERVIEW.md) |
| Changelog     | [changelog.md](changelog.md)                                                   |

```
