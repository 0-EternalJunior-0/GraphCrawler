# Installation Guide

> **Час читання:** 5 хвилин  
> **Рівень:** Початківець

---

## 📋 Системні вимоги

### Python Version

| Version | Status | Notes |
|---------|--------|-------|
| **Python 3.14** | ✅ Recommended | Free-threading support, 3.2x faster |
| **Python 3.12-3.13** | ✅ Supported | Full visualization support |
| **Python 3.11** | ✅ Minimum | All features work |
| Python 3.10 | ⚠️ Limited | May work, not tested |
| Python < 3.10 | ❌ Not supported | - |

### Operating Systems

- ✅ Linux (Ubuntu 20.04+, Debian 11+, CentOS 8+)
- ✅ macOS (11.0+)
- ✅ Windows (10/11, WSL2 recommended)

---

## 🚀 Quick Installation

### Using pip (Recommended)

```bash
pip install graph-crawler
```

### From Source (Development)

```bash
git clone https://github.com/0-EternalJunior-0/GraphCrawler.git
cd web_graf
pip install -e .
```

---

## 📦 Optional Dependencies

GraphCrawler uses optional dependencies to keep the base installation lightweight.

### Playwright Driver (JavaScript Sites)

For sites with JavaScript rendering:

```bash
pip install graph-crawler[playwright]

# Install browser binaries
playwright install chromium
```

### Embeddings & Vectorization

For AI/ML pipelines:

```bash
pip install graph-crawler[embeddings]
```

Includes: `sentence-transformers`, `torch`

### Article Extraction

For content extraction:

```bash
pip install graph-crawler[articles]
```

Includes: `goose3`, `newspaper3k`

### Database Backends

```bash
# MongoDB
pip install graph-crawler[mongodb]

# PostgreSQL
pip install graph-crawler[postgresql]

# Both
pip install graph-crawler[mongodb,postgresql]
```

### Everything (Full Installation)

```bash
pip install graph-crawler[all]
```

---

## 🐍 Python 3.14 Setup (Recommended)

For maximum performance, use Python 3.14 with free-threading:

### 1. Install Python 3.14

```bash
# Ubuntu/Debian
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.14

# macOS (Homebrew)
brew install python@3.14

# Windows
# Download from python.org
```

### 2. Create Virtual Environment

```bash
python3.14 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate     # Windows
```

### 3. Enable Free-Threading

```bash
# Add to your shell profile (~/.bashrc, ~/.zshrc)
export PYTHON_GIL=0
export PYTHON_JIT=1
```

### 4. Install GraphCrawler

```bash
pip install graph-crawler
```

### 5. Verify Installation

```python
import graph_crawler as gc
print(gc.__version__)  # Should print 4.0.4

# Check free-threading
import sys
print(f"GIL enabled: {sys.flags.gil}")
```

---

## 🐳 Docker Installation

### Using Docker

```dockerfile
# Dockerfile
FROM python:3.14-slim

WORKDIR /app

# Install GraphCrawler
RUN pip install graph-crawler[all]

# For Playwright
RUN playwright install chromium
RUN playwright install-deps

COPY . .

CMD ["python", "crawl.py"]
```

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  crawler:
    build: .
    environment:
      - PYTHON_GIL=0
    volumes:
      - ./data:/app/data
    
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    
  mongodb:
    image: mongo:7
    ports:
      - "27017:27017"
    volumes:
      - mongo_data:/data/db

volumes:
  mongo_data:
```

---

## ✅ Verification

### Basic Test

```python
import graph_crawler as gc

# Simple crawl
graph = gc.crawl("https://httpbin.org/html", max_depth=1)

print(f"✅ GraphCrawler {gc.__version__} working!")
print(f"   Nodes: {len(graph.nodes)}")
print(f"   Edges: {len(graph.edges)}")
```

### Full Test Suite

```bash
# Clone repository
git clone https://github.com/0-EternalJunior-0/GraphCrawler.git
cd web_graf

# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=graph_crawler
```

---

## 🔧 Troubleshooting

### Common Issues

#### `ModuleNotFoundError: No module named 'graph_crawler'`

```bash
# Check installation
pip show graph-crawler

# Reinstall
pip uninstall graph-crawler
pip install graph-crawler
```

#### Playwright Not Working

```bash
# Install browser
playwright install chromium

# Install system dependencies (Linux)
sudo apt-get install libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0

# Or use Playwright's auto-install
playwright install-deps
```

#### SSL Certificate Errors

```python
import graph_crawler as gc

# Disable SSL verification (not recommended for production)
graph = gc.crawl(
    "https://example.com",
    driver_config={"ssl_verify": False}
)
```

#### Memory Issues with Large Crawls

```python
# Use SQLite storage for large crawls
graph = gc.crawl(
    "https://large-site.com",
    storage="sqlite",
    storage_config={"path": "./crawl.db"},
    max_pages=100000
)
```

---

## 📊 Performance Tips

### 1. Use Free-Threading (Python 3.14)

```bash
export PYTHON_GIL=0
```

**Result:** ~3.2x faster crawling

### 2. Tune Concurrency

```python
graph = gc.crawl(
    url,
    driver_config={
        "max_connections": 100,  # Increase for faster crawls
        "timeout": 10,
    }
)
```

### 3. Use Appropriate Storage

| Pages | Recommended Storage |
|-------|--------------------|
| < 1,000 | `memory` (default) |
| 1K - 20K | `json` |
| 20K+ | `sqlite` |
| 100K+ | `postgresql` / `mongodb` |

### 4. Disable Unnecessary Plugins

```python
# Only use needed plugins
from graph_crawler.extensions.plugins.node import (
    MetadataExtractorPlugin,
    LinkExtractorPlugin,
)

graph = gc.crawl(
    url,
    plugins=[MetadataExtractorPlugin(), LinkExtractorPlugin()]
)
```

---

## 🔗 Next Steps

- [Quick Start Guide →](quickstart.md)
- [Code Examples →](examples.md)
- [API Reference →](../api/API.md)

---

**Need help?** Open an issue on [GitHub](https://github.com/0-EternalJunior-0/GraphCrawler/-/issues)
