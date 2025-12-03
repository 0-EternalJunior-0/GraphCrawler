# Basic Usage Examples / Базові Приклади

> **Складність**: Легко  
> **Python**: 3.9+

Прості приклади використання GraphCrawler.

## Приклади

| Файл | Опис |
|------|------|
| `00_quick_start.py` | Швидкий старт з API v3.1 |
| `01_domain_setup.py` | Налаштування домену |
| `02_scan_timing.py` | Контроль часу |
| `03_url_patterns.py` | URLRule патерни |
| `04_api_levels.py` | Рівні API |
| `05_graph_operations.py` | Операції з графами |

## Запуск

```bash
cd examples/basic_usage
python 00_quick_start.py
```

## API Рівні

```python
import graph_crawler as gc

# Level 1: crawl() - найпростіший
graph = gc.crawl("https://example.com")

# Level 2: Crawler - reusable
with gc.Crawler(max_depth=3) as crawler:
    graph = crawler.crawl("https://example.com")

# Level 3: AsyncCrawler - async
async with gc.AsyncCrawler() as crawler:
    graph = await crawler.crawl("https://example.com")
```
