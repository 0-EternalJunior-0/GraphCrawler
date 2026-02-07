"""Observability Module для GraphCrawler.

Includes:
- Structured JSON Logging
- Prometheus-compatible Metrics
- Error Tracing with context

Usage:
    >>> from graph_crawler.observability import (
    ...     # Logging
    ...     setup_json_logging,
    ...     get_logger,
    ...     
    ...     # Metrics
    ...     get_metrics,
    ...     CrawlerMetrics,
    ...     
    ...     # Error tracing
    ...     trace_error,
    ...     get_error_summary,
    ... )
"""

from graph_crawler.observability.structured_logging import (
    setup_json_logging,
    get_logger,
    JSONFormatter,
    CorrelationIDFilter,
    LogContext,
)

from graph_crawler.observability.metrics_core import (
    get_metrics,
    MetricsRegistry,
    Counter,
    Gauge,
    Histogram,
    CrawlerMetrics,
)

from graph_crawler.observability.error_tracing import (
    trace_error,
    get_error_summary,
    get_error_tracer,
    ErrorTracer,
    ErrorContext,
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
]
