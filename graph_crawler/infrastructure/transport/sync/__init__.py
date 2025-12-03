"""Sync драйвери для legacy коду.

WARNING: Використовуйте async драйвери де можливо!
"""

from graph_crawler.infrastructure.transport.sync.requests_driver import RequestsDriver

__all__ = ["RequestsDriver"]
