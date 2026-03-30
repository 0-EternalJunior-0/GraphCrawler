"""Observability Module для GraphCrawler.

Includes:
- Structured logging з JSON format
- Metrics collection (Counter, Gauge, Histogram)
- Error tracing з context
- Extensions: MemoryGuard, StateManager
"""

from graph_crawler.observability.error_tracing import (
    ErrorContext,
    ErrorTracer,
    get_error_summary,
    get_error_tracer,
    trace_error,
)
from graph_crawler.observability.extensions import (
    MemoryGuard,
    MemoryGuardConfig,
    StateManager,
)
from graph_crawler.observability.metrics_core import (
    Counter,
    CrawlerMetrics,
    Gauge,
    Histogram,
    MetricsRegistry,
    get_metrics,
)
from graph_crawler.observability.structured_logging import (
    CorrelationIDFilter,
    JSONFormatter,
    LogContext,
    get_logger,
    setup_json_logging,
)

__all__ = [
    # Logging
    "setup_json_logging",
    "get_logger",
    "JSONFormatter",
    "CorrelationIDFilter",
    "LogContext",
    # Metrics
    "get_metrics",
    "MetricsRegistry",
    "Counter",
    "Gauge",
    "Histogram",
    "CrawlerMetrics",
    # Error tracing
    "trace_error",
    "get_error_summary",
    "get_error_tracer",
    "ErrorTracer",
    "ErrorContext",
    # Extensions
    "MemoryGuard",
    "MemoryGuardConfig",
    "StateManager",
]
