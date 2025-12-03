"""
Listeners для обробки подій.

Alpha 2.0: Реструктуризовано - прибрано непотрібну папку specialized/
"""

from graph_crawler.observability.listeners.base import BaseListener, IEventListener
from graph_crawler.observability.listeners.base_metrics_listener import (
    BaseMetricsListener,
)
from graph_crawler.observability.listeners.crawl_listener import BaseCrawlListener
from graph_crawler.observability.listeners.error_listener import BaseErrorListener
from graph_crawler.observability.listeners.logging_listener import LoggingListener
from graph_crawler.observability.listeners.metrics_listener import MetricsListener
from graph_crawler.observability.listeners.node_listener import BaseNodeListener
from graph_crawler.observability.listeners.plugin_listener import BasePluginListener
from graph_crawler.observability.listeners.storage_listener import BaseStorageListener
from graph_crawler.observability.listeners.url_listener import BaseURLListener

__all__ = [
    # Основні
    "IEventListener",
    "BaseListener",
    # Спеціалізовані базові класи
    "BaseCrawlListener",
    "BaseNodeListener",
    "BaseURLListener",
    "BasePluginListener",
    "BaseMetricsListener",
    "BaseStorageListener",
    "BaseErrorListener",
    # Реалізації
    "LoggingListener",
    "MetricsListener",
]
