"""Module: domain/value_objects - Value Objects та конфігурації"""

from graph_crawler.domain.value_objects.models import (
    DomainFilterConfig,
    EdgeCreationStrategy,
    EdgeRule,
    FetchResponse,
    GraphComparisonResult,
    GraphMetadata,
    GraphStats,
    PageMetadata,
    PathFilterConfig,
    URLRule,
)

try:
    from graph_crawler.domain.value_objects.configs import (
        DriverConfig,
        MiddlewareConfig,
        StorageConfig,
    )
except ImportError:
    # Якщо configs.py не існує, пропускаємо
    DriverConfig = None
    StorageConfig = None
    MiddlewareConfig = None

__all__ = [
    # Models
    "URLRule",
    "EdgeCreationStrategy",
    "EdgeRule",
    "FetchResponse",
    "DomainFilterConfig",
    "PathFilterConfig",
    "PageMetadata",
    "GraphMetadata",
    "GraphStats",
    "GraphComparisonResult",
    # Configs
    "DriverConfig",
    "StorageConfig",
    "MiddlewareConfig",
]
