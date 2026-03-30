"""Модуль CRAWLER - Логіка краулінгу веб-сайту.

Цей модуль реалізує головну бізнес-логіку обходу веб-сайту:
"""

from graph_crawler.application.use_cases.crawling.crawl_coordinator import (
    CrawlCoordinator,
)
from graph_crawler.application.use_cases.crawling.filters.base import BaseURLFilter
from graph_crawler.application.use_cases.crawling.filters.domain_filter import (
    DomainFilter,
)
from graph_crawler.application.use_cases.crawling.filters.path_filter import PathFilter
from graph_crawler.application.use_cases.crawling.incremental_strategy import (
    IncrementalCrawlStrategy,
)
from graph_crawler.application.use_cases.crawling.link_processor import LinkProcessor
from graph_crawler.application.use_cases.crawling.multiprocess_spider import (
    MultiprocessSpider,
)
from graph_crawler.application.use_cases.crawling.node_scanner import NodeScanner
from graph_crawler.application.use_cases.crawling.progress_tracker import (
    CrawlProgressTracker,
)
from graph_crawler.application.use_cases.crawling.scheduler import CrawlScheduler
from graph_crawler.application.use_cases.crawling.spider import GraphSpider

# Нові компоненти (SRP Refactoring 2.1)
from graph_crawler.application.use_cases.crawling.spider_lifecycle import (
    SpiderLifecycleManager,
)

# Try to import optional spiders
try:
    from graph_crawler.application.use_cases.crawling.celery_batch_spider import (  # RECOMMENDED
        CeleryBatchSpider,
    )
    from graph_crawler.application.use_cases.crawling.celery_spider import (  # DEPRECATED
        CelerySpider,
    )
    from graph_crawler.application.use_cases.crawling.serialization_mixin import (
        ConfigSerializationMixin,
        create_instance_from_path,
        import_class_from_path,
    )

    __all__ = [
        "GraphSpider",
        "MultiprocessSpider",
        "CelerySpider",  # DEPRECATED - use CeleryBatchSpider
        "CeleryBatchSpider",  # RECOMMENDED - 24x faster
        "ConfigSerializationMixin",  # Serialization Mixin
        "import_class_from_path",
        "create_instance_from_path",
        "NodeScanner",
        "LinkProcessor",
        "CrawlScheduler",
        "BaseURLFilter",
        "DomainFilter",
        "PathFilter",
        "SpiderLifecycleManager",
        "IncrementalCrawlStrategy",
        "CrawlProgressTracker",
        "CrawlCoordinator",
    ]
except ImportError:
    CelerySpider = None
    CeleryBatchSpider = None
    ConfigSerializationMixin = None
    __all__ = [
        "GraphSpider",
        "MultiprocessSpider",
        "NodeScanner",
        "LinkProcessor",
        "CrawlScheduler",
        "BaseURLFilter",
        "DomainFilter",
        "PathFilter",
        "SpiderLifecycleManager",
        "IncrementalCrawlStrategy",
        "CrawlProgressTracker",
        "CrawlCoordinator",
    ]
