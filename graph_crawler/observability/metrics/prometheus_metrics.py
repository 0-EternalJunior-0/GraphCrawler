"""
Prometheus Metrics Integration

Провайдить metrics для моніторингу з Prometheus та Grafana.
"""

import logging
import threading
import time
from typing import Any, Dict, Optional

try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        CollectorRegistry,
        Counter,
        Gauge,
        Histogram,
        Summary,
        generate_latest,
    )

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

logger = logging.getLogger(__name__)


class PrometheusMetrics:
    """
    Prometheus metrics для GraphCrawler.

    Metrics:
    - pages_crawled_total: Counter - загальна кількість просканованих сторінок
    - pages_crawled_per_second: Gauge - поточна швидкість краулінгу
    - crawl_errors_total: Counter - загальна кількість помилок
    - queue_size: Gauge - розмір черги URL
    - active_crawls: Gauge - кількість активних краулінгів
    - crawl_duration_seconds: Histogram - тривалість краулінгу
    - page_fetch_duration_seconds: Histogram - час завантаження сторінки
    - response_status_codes: Counter - HTTP status codes

    Requirements:
        pip install prometheus-client

    Example:
        >>> from graph_crawler.monitoring import PrometheusMetrics
        >>>
        >>> metrics = PrometheusMetrics()
        >>> metrics.increment_pages_crawled()
        >>> metrics.update_queue_size(150)
        >>>
        >>> # Expose metrics endpoint
        >>> from fastapi import Response
        >>> @app.get('/metrics')
        >>> def metrics_endpoint():
        >>>     return Response(metrics.generate(), media_type=CONTENT_TYPE_LATEST)
    """

    def __init__(self, registry: Optional["CollectorRegistry"] = None):
        """
        Initialize Prometheus metrics.

        Args:
            registry: Prometheus registry (за замовчуванням створює новий)

        Raises:
            ImportError: Якщо prometheus_client не встановлено
        """
        if not PROMETHEUS_AVAILABLE:
            raise ImportError(
                "prometheus-client is required for PrometheusMetrics. "
                "Install with: pip install prometheus-client"
            )

        self.registry = registry or CollectorRegistry()
        self._lock = threading.Lock()
        self._start_time = time.time()

        # Initialize metrics
        self._init_metrics()

        logger.info("PrometheusMetrics initialized")

    def _init_metrics(self):
        """
        Initialize all Prometheus metrics.
        """
        # Counter metrics
        self.pages_crawled_total = Counter(
            "graphcrawler_pages_crawled_total",
            "Total number of pages crawled",
            registry=self.registry,
        )

        self.crawl_errors_total = Counter(
            "graphcrawler_errors_total",
            "Total number of crawl errors",
            ["error_type"],  # Labels: network, driver, parsing, etc.
            registry=self.registry,
        )

        self.response_status_codes = Counter(
            "graphcrawler_response_status_codes_total",
            "HTTP response status codes",
            ["status_code"],
            registry=self.registry,
        )

        # Gauge metrics
        self.pages_crawled_per_second = Gauge(
            "graphcrawler_pages_per_second",
            "Current crawl rate (pages per second)",
            registry=self.registry,
        )

        self.queue_size = Gauge(
            "graphcrawler_queue_size", "Current URL queue size", registry=self.registry
        )

        self.active_crawls = Gauge(
            "graphcrawler_active_crawls",
            "Number of active crawls",
            registry=self.registry,
        )

        # Histogram metrics
        self.crawl_duration_seconds = Histogram(
            "graphcrawler_crawl_duration_seconds",
            "Crawl session duration in seconds",
            buckets=(10, 30, 60, 300, 600, 1800, 3600),  # 10s to 1h
            registry=self.registry,
        )

        self.page_fetch_duration_seconds = Histogram(
            "graphcrawler_page_fetch_duration_seconds",
            "Time to fetch a single page",
            buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0),  # 100ms to 10s
            registry=self.registry,
        )

    def increment_pages_crawled(self, count: int = 1):
        """
        Increment pages crawled counter.

        Args:
            count: Number to increment by
        """
        with self._lock:
            self.pages_crawled_total.inc(count)

    def increment_errors(self, error_type: str = "unknown", count: int = 1):
        """
        Increment errors counter.

        Args:
            error_type: Type of error (network, driver, parsing, storage)
            count: Number to increment by
        """
        with self._lock:
            self.crawl_errors_total.labels(error_type=error_type).inc(count)

    def record_status_code(self, status_code: int):
        """
        Record HTTP status code.

        Args:
            status_code: HTTP status code
        """
        with self._lock:
            self.response_status_codes.labels(status_code=str(status_code)).inc()

    def update_pages_per_second(self, rate: float):
        """
        Update current crawl rate.

        Args:
            rate: Pages per second
        """
        with self._lock:
            self.pages_crawled_per_second.set(rate)

    def update_queue_size(self, size: int):
        """
        Update queue size.

        Args:
            size: Current queue size
        """
        with self._lock:
            self.queue_size.set(size)

    def increment_active_crawls(self):
        """
        Increment active crawls gauge.
        """
        with self._lock:
            self.active_crawls.inc()

    def decrement_active_crawls(self):
        """
        Decrement active crawls gauge.
        """
        with self._lock:
            self.active_crawls.dec()

    def record_crawl_duration(self, duration: float):
        """
        Record crawl session duration.

        Args:
            duration: Duration in seconds
        """
        with self._lock:
            self.crawl_duration_seconds.observe(duration)

    def record_page_fetch_duration(self, duration: float):
        """
        Record page fetch duration.

        Args:
            duration: Duration in seconds
        """
        with self._lock:
            self.page_fetch_duration_seconds.observe(duration)

    def generate(self) -> bytes:
        """
        Generate Prometheus metrics output.

        Returns:
            bytes: Prometheus format metrics
        """
        return generate_latest(self.registry)

    def get_metrics_dict(self) -> Dict[str, Any]:
        """
        Get metrics as dict (для debugging).

        Returns:
            Dict з поточними metrics
        """
        return {
            "pages_crawled_total": self.pages_crawled_total._value.get(),
            "queue_size": self.queue_size._value.get(),
            "pages_per_second": self.pages_crawled_per_second._value.get(),
            "active_crawls": self.active_crawls._value.get(),
            "uptime_seconds": time.time() - self._start_time,
        }


# Global metrics instance
_global_metrics: Optional[PrometheusMetrics] = None


def setup_metrics(registry: Optional["CollectorRegistry"] = None) -> PrometheusMetrics:
    """
    Setup global Prometheus metrics instance.

    Args:
        registry: Optional Prometheus registry

    Returns:
        PrometheusMetrics: Global metrics instance
    """
    global _global_metrics

    if _global_metrics is None:
        _global_metrics = PrometheusMetrics(registry)
        logger.info("Global Prometheus metrics setup complete")

    return _global_metrics


def get_metrics() -> Optional[PrometheusMetrics]:
    """
    Get global metrics instance.

    Returns:
        PrometheusMetrics or None якщо не ініціалізовано
    """
    return _global_metrics
