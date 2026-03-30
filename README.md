<div align="center">

<img src="https://raw.githubusercontent.com/0-EternalJunior-0/GraphCrawler/main/docs/assets/logo.svg" alt="GraphCrawler Logo" width="200"/>

# GraphCrawler

**Enterprise-Grade Web Crawling Framework for Graph-Based Site Analysis**

[![PyPI Version](https://img.shields.io/pypi/v/graph-crawler?color=blue&style=flat-square)](https://pypi.org/project/graph-crawler/)
[![Python Versions](https://img.shields.io/pypi/pyversions/graph-crawler?style=flat-square)](https://python.org)
[![Downloads](https://img.shields.io/pypi/dm/graph-crawler?color=green&style=flat-square)](https://pypi.org/project/graph-crawler/)
[![License](https://img.shields.io/github/license/0-EternalJunior-0/GraphCrawler?style=flat-square)](LICENSE)
[![Tests](https://img.shields.io/github/actions/workflow/status/0-EternalJunior-0/GraphCrawler/tests.yml?label=tests&style=flat-square)](https://github.com/0-EternalJunior-0/GraphCrawler/actions)
[![Coverage](https://img.shields.io/codecov/c/github/0-EternalJunior-0/GraphCrawler?style=flat-square)](https://codecov.io/gh/0-EternalJunior-0/GraphCrawler)
[![Code Style](https://img.shields.io/badge/code%20style-ruff-purple?style=flat-square)](https://github.com/astral-sh/ruff)
[![Documentation](https://img.shields.io/badge/docs-mkdocs-blue?style=flat-square)](https://0-eternaljunior-0.github.io/GraphCrawler/)

[Documentation](https://0-eternaljunior-0.github.io/GraphCrawler/) • [Examples](./examples) • [API Reference](https://0-eternaljunior-0.github.io/GraphCrawler/api/)  • [Changelog](CHANGELOG.md)

---

</div>

## Why GraphCrawler?

Modern web applications require sophisticated crawling solutions. GraphCrawler was built from the ground up with **Clean Architecture** principles, offering unmatched flexibility and performance for web analysis tasks.

<table>
<tr>
<td width="50%">

### 🎯 Built for Scale
- Process **1M+ pages** with low-memory mode
- **Distributed crawling** via Celery workers
- Automatic **rate limiting** & autothrottle
- **Checkpoint/resume** for long-running jobs
- **Python 3.14 free-threading** support (3.2x faster)

</td>
<td width="50%">

### 🧩 Extensible by Design
- **Plugin architecture** for custom logic
- Multiple **storage backends**
- Swappable **transport drivers**
- **Event-driven** processing pipeline
- **Webhook notifications** for real-time updates

</td>
</tr>
<tr>
<td width="50%">

### 🛡️ Production Ready
- Battle-tested in **enterprise environments**
- Comprehensive **error handling**
- **SSRF protection** built-in
- Full **type annotations** (mypy strict)
- **Anti-bot bypass** (Cloudflare, DataDome, PerimeterX)

</td>
<td width="50%">

### 🤖 AI-Native
- Integrated **LLM extraction** (OpenAI, Anthropic, Bedrock)
- **Vector embeddings** for semantic search
- Smart **content classification**
- **ML-powered URL prioritization**
- **CAPTCHA solving** integration

</td>
</tr>
</table>

---

## Table of Contents

- [What's New in v4.0](#whats-new-in-v40)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Core Concepts](#core-concepts)
- [Configuration](#configuration)
- [Drivers](#drivers)
- [Storage Backends](#storage-backends)
- [Plugin System](#plugin-system)
- [Smart Crawling (ML)](#smart-crawling-ml)
- [Anti-Bot & CAPTCHA](#anti-bot--captcha)
- [Distributed Crawling](#distributed-crawling)
- [REST API & Dashboard](#rest-api--dashboard)
- [Webhooks](#webhooks)
- [AI Integration](#ai-integration)
- [Data Extraction](#data-extraction)
- [CLI Reference](#cli-reference)
- [Architecture](#architecture)
- [Performance](#performance)

---

## What's New in v4.0

### 🚀 Python 3.14 Free-Threading Support

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

### 📡 Real-Time Dashboard & WebSocket

```python
# Start dashboard server
uvicorn graph_crawler.api.dashboard:app --port 8000

# WebSocket endpoint for live updates
# ws://localhost:8000/ws/crawl
```

---

## Installation

### From PyPI (Recommended)

```bash
pip install graph-crawler
```

### Optional Dependencies

```bash
# JavaScript/SPA rendering
pip install graph-crawler[playwright]

# Vector embeddings & ML
pip install graph-crawler[embeddings]

# MongoDB storage backend
pip install graph-crawler[mongodb]

# PostgreSQL storage backend  
pip install graph-crawler[postgresql]

# Distributed crawling (Celery)
pip install graph-crawler[distributed]

# Full installation
pip install graph-crawler[all]
```

### System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| Python | 3.11 | 3.14+ (free-threading) |
| Memory | 512 MB | 4 GB+ |
| OS | Linux, macOS, Windows | Linux (Ubuntu 22.04+) |

---

## Quick Start

### Basic Usage

```python
import graph_crawler as gc

# Crawl a website
graph = gc.crawl(
    url="https://example.com",
    max_depth=3,
    max_pages=100
)

# Analyze results
print(f"Discovered {len(graph.nodes):,} pages")
print(f"Mapped {len(graph.edges):,} links")

# Persist to disk
gc.save_graph(graph, "example_graph.json")
```

### Async API

```python
import asyncio
import graph_crawler as gc

async def main():
    graph = await gc.async_crawl(
        url="https://example.com",
        max_depth=5,
        max_pages=1000,
        request_delay=0.25
    )
    
    # Process nodes concurrently
    async for node in graph.iter_nodes_async():
        print(f"[{node.response_status}] {node.url}")
    
    return graph

graph = asyncio.run(main())
```

### Client Interface

```python
from graph_crawler import GraphCrawlerClient

async with GraphCrawlerClient(
    driver="playwright",
    storage="sqlite"
) as client:
    # Configure and execute
    graph = await client.crawl(
        "https://spa-application.com",
        max_depth=4
    )
    
    # Save with metadata
    await client.save("spa_graph", graph, tags=["spa", "react"])
```

---

## Core Concepts

### Graph Model

GraphCrawler represents websites as directed graphs:

```
┌─────────────────────────────────────────────────────────┐
│                        Graph                             │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐             │
│  │  Node   │───▶│  Node   │───▶│  Node   │             │
│  │ (root)  │    │ /about  │    │ /team   │             │
│  └─────────┘    └─────────┘    └─────────┘             │
│       │              │                                   │
│       │         ┌────┴────┐                             │
│       ▼         ▼         ▼                             │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐                 │
│  │  Node   │  │  Node   │  │  Node   │                 │
│  │ /blog   │  │/contact │  │/careers │                 │
│  └─────────┘  └─────────┘  └─────────┘                 │
└─────────────────────────────────────────────────────────┘
```

**Node** — represents a single page with:
- URL, depth, status code
- Content hash (SHA-256) and SimHash
- Metadata (title, description, headers)
- Custom user data

**Edge** — represents a link between pages:
- Source and target URLs
- Link text and attributes
- Edge type (internal, external, resource)

### Graph Operations

```python
# Graph algebra
merged = graph1 + graph2           # Union
diff = graph1 - graph2             # Difference  
common = graph1 & graph2           # Intersection
symmetric = graph1 ^ graph2        # Symmetric difference

# Subgraph detection
if graph1 < graph2:
    print("graph1 is a subgraph of graph2")

# Find popular pages
popular = graph.get_popular_nodes(top_n=10, by='in_degree')

# Find orphan pages (no incoming links)
for node in graph:
    if graph.get_in_degree(node) == 0 and node.depth > 0:
        print(f"Orphan: {node.url}")
```

---

## Configuration

### Crawl Parameters

| Parameter | Type | Default | Description |
|:----------|:-----|:--------|:------------|
| `url` | `str` | *required* | Starting URL |
| `seed_urls` | `list[str]` | `None` | Multiple starting URLs |
| `max_depth` | `int` | `3` | Maximum link depth from root |
| `max_pages` | `int` | `100` | Maximum pages to crawl |
| `same_domain` | `bool` | `True` | Restrict to starting domain |
| `request_delay` | `float` | `0.5` | Delay between requests (seconds) |
| `timeout` | `int` | `300` | Global timeout (seconds) |
| `driver` | `str` | `"http"` | Transport driver |
| `url_rules` | `list[URLRule]` | `[]` | URL filtering/priority rules |
| `node_plugins` | `list[Plugin]` | `[]` | Content processing plugins |
| `respect_robots` | `bool` | `True` | Honor robots.txt |
| `base_graph` | `Graph` | `None` | Continue incremental crawl |
| `low_memory_mode` | `bool` | `False` | Enable eviction for large crawls |

### URL Rules

```python
from graph_crawler import URLRule, SmartURLRule, build_smart_rules

# Pattern-based filtering
rules = [
    # Skip non-HTML resources
    URLRule(pattern=r"\.(pdf|zip|exe|dmg)$", should_scan=False),
    
    # Skip admin areas
    URLRule(pattern=r"/(admin|wp-admin|dashboard)/", should_scan=False),
    
    # Prioritize product pages
    URLRule(pattern=r"/products?/[\w-]+$", priority=10),
    
    # Deprioritize pagination
    URLRule(pattern=r"\?page=\d+", priority=-5),
]

# Or use smart presets
rules = build_smart_rules(
    skip_extensions=[".pdf", ".zip"],
    skip_paths=["/admin", "/api"],
    priority_paths=["/products", "/categories"],
    skip_query_params=["session", "token"]
)

graph = gc.crawl("https://shop.example.com", url_rules=rules)
```

### Settings Files

```yaml
# crawler_settings.yaml
project_name: "my_crawler"

crawler:
  max_depth: 5
  max_pages: 10000
  request_delay: 0.25
  timeout: 3600
  respect_robots: true

driver:
  type: playwright
  headless: true
  wait_for: networkidle

storage:
  type: sqlite
  path: ./data/crawl.db

plugins:
  - graph_crawler.extensions.plugins.node.SEOPlugin
  - graph_crawler.extensions.plugins.node.StructuredDataPlugin
```

```python
from graph_crawler import CrawlerSettings

settings = CrawlerSettings.from_yaml("crawler_settings.yaml")
graph = gc.crawl("https://example.com", settings=settings)
```

---

## Drivers

GraphCrawler supports multiple transport drivers:

| Driver | Engine | Best For | Anti-Bot | JS Rendering |
|:-------|:-------|:---------|:--------:|:------------:|
| `http` | `httpx` | Static sites, APIs | ❌ | ❌ |
| `async` | `aiohttp` | High concurrency | ❌ | ❌ |
| `playwright` | Chromium | SPAs, modern sites | ✅ | ✅ |
| `cloudscraper` | requests | Cloudflare sites | ✅ | ❌ |

### Playwright Driver

```python
graph = gc.crawl(
    "https://react-application.com",
    driver="playwright",
    
    # Playwright-specific options
    headless=True,
    wait_for_selector=".app-loaded",
    wait_for_timeout=5000,
    viewport={"width": 1920, "height": 1080},
    
    # Browser context
    ignore_https_errors=True,
    java_script_enabled=True
)
```

---

## Storage Backends

| Backend | Capacity | Persistence | Query Speed | Use Case |
|:--------|:---------|:------------|:------------|:---------|
| `memory` | ~10K nodes | ❌ | ⚡ Fastest | Development, testing |
| `json` | ~50K nodes | ✅ | 🐌 Slow | Small projects, export |
| `sqlite` | ~500K nodes | ✅ | ⚡ Fast | Local production |
| `mongodb` | Unlimited | ✅ | ⚡ Fast | Distributed, cloud |
| `postgresql` | Unlimited | ✅ | ⚡ Fast | Analytics, enterprise |

### Low-Memory Mode

For crawling sites with millions of pages:

```python
graph = gc.crawl(
    "https://large-site.com",
    max_pages=1_000_000,
    low_memory_mode=True,          # Enable eviction
    eviction_threshold=50_000,     # Nodes in RAM
    eviction_storage="sqlite"      # Where to evict
)
```

---

## Plugin System

### Plugin Types

| Type | Hook Point | Use Case |
|:-----|:-----------|:---------|
| `NodePlugin` | After page fetch | Content extraction, SEO analysis |
| `EdgePlugin` | After link discovery | Link classification, filtering |
| `EnginePlugin` | Before/during crawl | URL prioritization, rate limiting |
| `ExportPlugin` | During export | Data transformation |

### Built-in Node Plugins

```python
from graph_crawler.extensions.plugins.node import (
    StructuredDataPlugin,  # JSON-LD, OpenGraph, Microdata, RDFa, Twitter Cards
    SEOPlugin,             # Meta tags, headings, schema
    ContentHashPlugin,     # Duplicate detection (SHA-256 + SimHash)
    VectorizationPlugin,   # Text embeddings
)

from graph_crawler.extensions.plugins.node.extractors import (
    PhoneExtractorPlugin,  # UA, US, RU phone formats
    EmailExtractorPlugin,  # RFC 5322 compliant
    PriceExtractorPlugin,  # USD, EUR, UAH with ranges
)

graph = gc.crawl(
    "https://shop.example.com",
    node_plugins=[
        StructuredDataPlugin(),
        PhoneExtractorPlugin(),
        EmailExtractorPlugin(),
        PriceExtractorPlugin(),
    ]
)

# Access extracted data
for node in graph.nodes:
    print(f"Page: {node.url}")
    print(f"  Phones: {node.user_data.get('phones', [])}")
    print(f"  Emails: {node.user_data.get('emails', [])}")
    print(f"  Prices: {node.user_data.get('prices', [])}")
    print(f"  OpenGraph: {node.user_data.get('opengraph', {})}")
```

### Custom Plugin

```python
from graph_crawler import BaseNodePlugin, NodePluginType

class PriceMonitorPlugin(BaseNodePlugin):
    """Monitor product prices across e-commerce sites."""
    
    plugin_type = NodePluginType.ON_HTML_PARSED
    priority = 100
    
    def execute(self, context):
        if not context.html_tree:
            return context
        
        # Extract price using CSS selectors
        price_elem = context.html_tree.select_one('[data-price], .price, #price')
        if price_elem:
            context.user_data["price"] = {
                "raw": price_elem.get_text(strip=True),
                "currency": self._detect_currency(price_elem),
                "value": self._parse_price(price_elem)
            }
        
        return context

graph = gc.crawl(url, node_plugins=[PriceMonitorPlugin()])
```

---

## Smart Crawling (ML)

### SmartPageFinderPlugin

ML-powered plugin that uses LLM or keyword analysis to find relevant pages:

```python
from graph_crawler.extensions.plugins.node import SmartPageFinderPlugin

plugin = SmartPageFinderPlugin(
    search_prompt="Python developer jobs in Kyiv",
    config={
        "min_relevance_score": 0.7,
        "analyze_links": True,
        "model": "gpt-4o-mini"  # Optional LLM
    }
)

graph = gc.crawl("https://jobs.example.com", node_plugins=[plugin])

# Find target pages
for node in graph.nodes:
    if node.user_data.get("is_target_page"):
        print(f"Found: {node.url}")
        print(f"  Score: {node.user_data['relevance_score']:.2f}")
        print(f"  Reason: {node.user_data['relevance_reason']}")
```

### VectorCrawlEnginePlugin

Vector-based URL prioritization using embeddings:

```python
from graph_crawler.extensions.plugins.crawl_engine import VectorCrawlEnginePlugin

plugin = VectorCrawlEnginePlugin(
    keywords=["python", "developer", "remote", "jobs"],
    min_priority=1,
    max_priority=15,
    model_name="paraphrase-multilingual-MiniLM-L12-v2"
)
plugin.setup()  # Load model

graph = gc.crawl(
    "https://careers.example.com",
    engine_plugins=[plugin]
)
```

### SmartCrawlEnginePlugin

Intelligent URL prioritization before scanning:

```python
from graph_crawler.extensions.plugins.crawl_engine import SmartCrawlEnginePlugin

plugin = SmartCrawlEnginePlugin(
    search_prompt="Machine learning engineer positions",
    config={
        "aggressive_filtering": True,  # Skip irrelevant URLs without scanning
        "use_llm": False  # Use fast keyword-based analysis
    }
)

graph = gc.crawl("https://linkedin.com/jobs", engine_plugins=[plugin])
```

---

## Anti-Bot & CAPTCHA

### Anti-Bot Detection

GraphCrawler can detect and bypass various anti-bot systems:

```python
from graph_crawler.extensions.plugins.engine import AntiBotSystem, detect_anti_bot_system

# Automatic detection
system = detect_anti_bot_system(html_content)
# Returns: AntiBotSystem.CLOUDFLARE, AKAMAI, DATADOME, PERIMETERX, etc.
```

Supported anti-bot systems:
- **Cloudflare** (Challenge, Turnstile)
- **Akamai** (Bot Manager)
- **DataDome**
- **PerimeterX**
- **Imperva/Incapsula**

### CAPTCHA Solving

Integration with popular CAPTCHA solving services:

```python
from graph_crawler.extensions.plugins.engine.captcha import (
    CaptchaPlugin,
    create_solver,
    CaptchaType
)

# Create solver
solver = create_solver(
    service="2captcha",  # or "anticaptcha", "capsolver"
    api_key="your-api-key"
)

# Check balance
balance = solver.check_balance()
print(f"Balance: ${balance}")

# Use with crawler
plugin = CaptchaPlugin(solver=solver)
graph = gc.crawl(
    "https://protected-site.com",
    driver="playwright",
    engine_plugins=[plugin]
)
```

Supported CAPTCHA types:
- reCAPTCHA v2/v3
- hCaptcha
- Image CAPTCHA

---

## Distributed Crawling

Scale horizontally with Celery workers:

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │────▶│    Redis    │◀────│   Worker 1  │
└─────────────┘     │   (Broker)  │     └─────────────┘
                    └─────────────┘             │
                          ▲                     ▼
                          │               ┌───────────┐
                    ┌─────────────┐       │  MongoDB  │
                    │   Worker 2  │──────▶│ (Results) │
                    └─────────────┘       └───────────┘
                          ▲
                    ┌─────────────┐
                    │   Worker N  │
                    └─────────────┘
```

### Setup

```bash
# Start Redis
docker run -d -p 6379:6379 redis:alpine

# Start workers
celery -A graph_crawler.infrastructure.messaging worker -l INFO -c 4
```

### Usage

```python
from graph_crawler import EasyDistributedCrawler

crawler = EasyDistributedCrawler(
    broker_url="redis://localhost:6379/0",
    result_backend="redis://localhost:6379/1",
    mongodb_uri="mongodb://localhost:27017"
)

# Submit crawl job
job_id = await crawler.submit(
    url="https://large-site.com",
    max_pages=100_000,
    max_depth=10,
    workers=8
)

# Monitor progress
while True:
    status = await crawler.get_status(job_id)
    print(f"Progress: {status.pages_crawled}/{status.pages_total}")
    
    if status.is_complete:
        break
    
    await asyncio.sleep(5)

# Get results
graph = await crawler.get_result(job_id)
```

---

## REST API & Dashboard

### REST API

Built-in FastAPI-based REST API for remote control:

```python
# Start API server
uvicorn graph_crawler.api.rest_api:router --port 8001
```

**Endpoints:**

| Method | Endpoint | Description |
|:-------|:---------|:------------|
| `POST` | `/api/v1/crawl/start` | Start new crawl |
| `POST` | `/api/v1/crawl/{id}/pause` | Pause crawl |
| `POST` | `/api/v1/crawl/{id}/resume` | Resume crawl |
| `POST` | `/api/v1/crawl/{id}/stop` | Stop crawl |
| `GET` | `/api/v1/crawl/{id}/status` | Get crawl status |
| `GET` | `/api/v1/crawl/list` | List all crawls |

### Real-Time Dashboard

```python
# Start dashboard
uvicorn graph_crawler.api.dashboard:app --port 8000
```

**Features:**
- 📊 Real-time statistics via WebSocket
- 📈 Live crawl progress visualization
- ⏯️ Pause/Resume/Stop controls
- 📝 Error monitoring
- 📉 Performance metrics

**WebSocket Events:**
- `initial_state` — Current state on connect
- `stats_update` — Statistics update
- `page_crawled` — New page scanned
- `error` — Crawl error occurred

---

## Webhooks

Receive real-time notifications for crawl events:

```python
from graph_crawler.api.webhooks import WebhookManager, WebhookEvent

# Setup webhooks
manager = WebhookManager()

manager.add_webhook(
    url="https://your-server.com/webhook",
    events=[
        WebhookEvent.CRAWL_STARTED,
        WebhookEvent.CRAWL_FINISHED,
        WebhookEvent.PAGE_CRAWLED,
        WebhookEvent.CRAWL_ERROR,
        WebhookEvent.MILESTONE_REACHED,  # Every N pages
    ],
    secret="your-hmac-secret",  # For signature verification
    headers={"Authorization": "Bearer token"}
)

# Start async delivery
await manager.start()

# Integrate with crawler
await integrate_webhooks_with_crawler(event_bus, webhook_configs)
```

**Webhook Payload:**

```json
{
    "event": "page_crawled",
    "data": {
        "url": "https://example.com/page",
        "status": 200,
        "depth": 2
    },
    "timestamp": "2024-01-15T10:30:00Z"
}
```

---

## AI Integration

### LLM-Powered Extraction

```python
from graph_crawler.ai import ExtractionPlugin
from graph_crawler.ai.models import OpenAIModel, AnthropicModel, BedrockModel

# Configure model
model = OpenAIModel(
    api_key="sk-...",
    model="gpt-4o",
    temperature=0
)

# Create extraction plugin
extractor = ExtractionPlugin(
    model=model,
    prompt="""
    Extract the following from this page:
    - Main topic
    - Key entities (people, companies, products)
    - Sentiment (positive/neutral/negative)
    
    Return as JSON.
    """
)

graph = gc.crawl(
    "https://news-site.com",
    max_pages=50,
    node_plugins=[extractor]
)

# Access AI-extracted data
for node in graph.nodes:
    ai_data = node.user_data.get("ai_extraction", {})
    print(f"{node.url}: {ai_data.get('main_topic')}")
```

### Vector Search

```python
from graph_crawler.extensions.plugins.node.vectorization import (
    VectorizationPlugin,
    semantic_search,
    cluster_by_similarity
)

vectorizer = VectorizationPlugin(
    model="text-embedding-3-small",
    api_key="sk-..."
)

graph = gc.crawl("https://docs.example.com", node_plugins=[vectorizer])

# Semantic search across crawled pages
results = semantic_search(
    graph=graph,
    query="How to configure authentication?",
    top_k=5
)

for node, score in results:
    print(f"[{score:.3f}] {node.url}")

# Cluster similar pages
clusters = cluster_by_similarity(graph, method="kmeans", n_clusters=5)
```

---

## Data Extraction

### Built-in Extractors

| Extractor | Data Types | Formats |
|:----------|:-----------|:--------|
| **PhoneExtractor** | Phone numbers | UA, US, RU, international |
| **EmailExtractor** | Email addresses | RFC 5322 compliant |
| **PriceExtractor** | Prices | USD, EUR, UAH, ranges |
| **StructuredData** | Schema.org | JSON-LD, Microdata, RDFa |
| **OpenGraph** | Social meta | og:title, og:image, etc. |
| **TwitterCards** | Twitter meta | twitter:card, etc. |

### Structured Data Extraction

```python
from graph_crawler.extensions.plugins.node import StructuredDataPlugin

graph = gc.crawl(
    "https://shop.example.com",
    node_plugins=[StructuredDataPlugin()]
)

for node in graph.nodes:
    # JSON-LD data
    jsonld = node.user_data.get("jsonld", [])
    for item in jsonld:
        if item.get("@type") == "Product":
            print(f"Product: {item.get('name')}")
            print(f"Price: {item.get('offers', {}).get('price')}")
    
    # OpenGraph
    og = node.user_data.get("opengraph", {})
    print(f"OG Title: {og.get('og:title')}")
    
    # Microdata
    microdata = node.user_data.get("microdata", [])
```

---

## CLI Reference

```bash
# Crawl website
graph-crawler crawl https://example.com \
    --max-depth 5 \
    --max-pages 1000 \
    --driver playwright \
    --output ./results/

# List saved graphs
graph-crawler list --storage sqlite --path ./data/

# Graph information
graph-crawler info my_graph --detailed

# Export graph
graph-crawler export my_graph \
    --format csv \
    --output ./exports/graph.csv

# Compare two graphs
graph-crawler diff graph_v1 graph_v2 --show-added --show-removed

# Start API server
graph-crawler serve --host 0.0.0.0 --port 8000

# Initialize new project
graph-crawler init my_crawler_project
```

---

## Architecture

GraphCrawler follows **Clean Architecture** principles:

```
┌──────────────────────────────────────────────────────────────┐
│                        Presentation                           │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐             │
│  │    CLI     │  │  REST API  │  │  WebSocket │             │
│  └────────────┘  └────────────┘  └────────────┘             │
├──────────────────────────────────────────────────────────────┤
│                         Public API                            │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  crawl() • async_crawl() • GraphCrawlerClient           │ │
│  └─────────────────────────────────────────────────────────┘ │
├──────────────────────────────────────────────────────────────┤
│                      Application Layer                        │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐             │
│  │  Use Cases │  │  Services  │  │    DTOs    │             │
│  │  (Spider)  │  │ (Exporter) │  │  (Mapper)  │             │
│  └────────────┘  └────────────┘  └────────────┘             │
├──────────────────────────────────────────────────────────────┤
│                        Domain Layer                           │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐             │
│  │  Entities  │  │   Value    │  │ Interfaces │             │
│  │Graph,Node, │  │  Objects   │  │IDriver,    │             │
│  │   Edge     │  │Settings,   │  │IStorage    │             │
│  └────────────┘  └────────────┘  └────────────┘             │
├──────────────────────────────────────────────────────────────┤
│                     Infrastructure Layer                      │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐             │
│  │ Transport  │  │Persistence │  │ Messaging  │             │
│  │HTTP,       │  │SQLite,     │  │Celery,     │             │
│  │Playwright  │  │MongoDB     │  │Redis       │             │
│  └────────────┘  └────────────┘  └────────────┘             │
├──────────────────────────────────────────────────────────────┤
│                      Extensions Layer                         │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐             │
│  │   Node     │  │   Engine   │  │    AI      │             │
│  │  Plugins   │  │  Plugins   │  │  Models    │             │
│  └────────────┘  └────────────┘  └────────────┘             │
└──────────────────────────────────────────────────────────────┘
```

### Directory Structure

```
graph_crawler/
├── api/                      # Public API surface
│   ├── sync.py              # Synchronous API
│   ├── async_.py            # Asynchronous API
│   ├── client/              # OOP client interface
│   ├── rest_api.py          # FastAPI REST endpoints
│   ├── dashboard.py         # Real-time dashboard
│   ├── webhooks.py          # Webhook notifications
│   └── websocket_manager.py # WebSocket handling
├── domain/                   # Core business logic
│   ├── entities/            # Graph, Node, Edge
│   ├── value_objects/       # Settings, Configs, Rules
│   ├── interfaces/          # Abstract contracts
│   └── events/              # Domain events (EventBus)
├── application/              # Application services
│   ├── use_cases/           # Crawling, export logic
│   ├── services/            # Factories, helpers
│   └── dto/                 # Data transfer objects
├── infrastructure/           # External implementations
│   ├── transport/           # HTTP, Playwright drivers
│   ├── persistence/         # Storage backends
│   └── messaging/           # Celery, Redis
├── extensions/               # Plugin system
│   ├── plugins/
│   │   ├── node/           # Content extraction plugins
│   │   ├── crawl_engine/   # URL prioritization plugins
│   │   └── engine/         # Anti-bot, CAPTCHA plugins
│   └── middleware/          # Request middleware
├── ai/                       # AI/ML integrations
│   ├── models/              # OpenAI, Anthropic, Bedrock
│   └── extraction/          # LLM extraction
└── shared/                   # Cross-cutting concerns
    ├── exceptions.py        # Custom exceptions
    ├── constants.py         # Configuration
    └── utils/               # Helpers
```

---

## Performance

### Benchmarks

Tested on AWS c5.2xlarge (8 vCPU, 16 GB RAM):

| Scenario | Pages | Time | Memory | Rate |
|:---------|------:|-----:|-------:|-----:|
| Static site (HTTP) | 10,000 | 45s | 512 MB | 222 p/s |
| SPA (Playwright) | 1,000 | 180s | 2 GB | 5.5 p/s |
| Distributed (4 workers) | 100,000 | 15min | 8 GB | 111 p/s |
| Low-memory mode | 1,000,000 | 4h | 1 GB | 69 p/s |
| Python 3.14 free-threading | 10,000 | 14s | 430 MB | 714 p/s |

### Optimization Tips

```python
# 1. Use async driver for static sites
graph = gc.crawl(url, driver="async", concurrency=50)

# 2. Disable unnecessary features
graph = gc.crawl(
    url,
    compute_hashes=False,      # Skip content hashing
    extract_metadata=False,    # Skip meta extraction
    store_html=False           # Don't persist HTML
)

# 3. Use URL rules to focus crawl
rules = [URLRule(pattern=r"/blog/", should_scan=False)]
graph = gc.crawl(url, url_rules=rules)

# 4. Enable low-memory for large crawls
graph = gc.crawl(url, max_pages=500_000, low_memory_mode=True)

# 5. Enable Python 3.14 free-threading
# export PYTHON_GIL=0
```

---

