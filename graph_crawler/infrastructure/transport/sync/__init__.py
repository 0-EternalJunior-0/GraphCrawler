"""Sync драйвери для legacy коду.

WARNING: Використовуйте async драйвери де можливо!

Доступні драйвери:
- RequestsDriver: Стандартний sync HTTP (requests)
- CloudscraperDriver: Для обходу Cloudflare та інших захистів
"""

from graph_crawler.infrastructure.transport.sync.requests_driver import RequestsDriver

# CloudscraperDriver опціональний (потрібен pip install cloudscraper)
try:
    from graph_crawler.infrastructure.transport.sync.cloudscraper_driver import CloudscraperDriver
except ImportError:
    CloudscraperDriver = None

__all__ = ["RequestsDriver", "CloudscraperDriver"]
