"""Prometheus-compatible Metrics для GraphCrawler.

Features:
"""

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple


@dataclass
class MetricValue:
    """Single metric value with labels."""

    value: float = 0.0
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class Counter:
    """
    Prometheus-style Counter metric.

    Counters only go up (or reset to zero).

    Example:
        >>> counter = Counter("http_requests_total", "Total HTTP requests")
        >>> counter.inc()
        >>> counter.inc(5)
        >>> counter.labels(status="200", method="GET").inc()
    """

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self._values: Dict[Tuple, float] = defaultdict(float)
        self._lock = threading.Lock()

    def inc(self, amount: float = 1.0) -> None:
        """Increment counter by amount."""
        with self._lock:
            self._values[()] += amount

    def labels(self, **kwargs) -> "LabeledCounter":
        """Return counter with labels."""
        return LabeledCounter(self, kwargs)

    def get(self, labels: Optional[Dict[str, str]] = None) -> float:
        """Get current value."""
        key = tuple(sorted((labels or {}).items()))
        return self._values.get(key, 0.0)

    def _inc_with_labels(self, labels: Dict[str, str], amount: float = 1.0) -> None:
        """Internal: increment with labels."""
        key = tuple(sorted(labels.items()))
        with self._lock:
            self._values[key] += amount


class LabeledCounter:
    """Counter with labels attached."""

    def __init__(self, counter: Counter, labels: Dict[str, str]):
        self._counter = counter
        self._labels = labels

    def inc(self, amount: float = 1.0) -> None:
        """Increment counter."""
        self._counter._inc_with_labels(self._labels, amount)


class Gauge:
    """
    Prometheus-style Gauge metric.

    Gauges can go up and down.

    Example:
        >>> gauge = Gauge("active_connections", "Number of active connections")
        >>> gauge.set(10)
        >>> gauge.inc()
        >>> gauge.dec(5)
    """

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self._values: Dict[Tuple, float] = defaultdict(float)
        self._lock = threading.Lock()

    def set(self, value: float) -> None:
        """Set gauge to value."""
        with self._lock:
            self._values[()] = value

    def inc(self, amount: float = 1.0) -> None:
        """Increment gauge."""
        with self._lock:
            self._values[()] += amount

    def dec(self, amount: float = 1.0) -> None:
        """Decrement gauge."""
        with self._lock:
            self._values[()] -= amount

    def labels(self, **kwargs) -> "LabeledGauge":
        """Return gauge with labels."""
        return LabeledGauge(self, kwargs)

    def get(self, labels: Optional[Dict[str, str]] = None) -> float:
        """Get current value."""
        key = tuple(sorted((labels or {}).items()))
        return self._values.get(key, 0.0)

    def _set_with_labels(self, labels: Dict[str, str], value: float) -> None:
        key = tuple(sorted(labels.items()))
        with self._lock:
            self._values[key] = value


class LabeledGauge:
    """Gauge with labels attached."""

    def __init__(self, gauge: Gauge, labels: Dict[str, str]):
        self._gauge = gauge
        self._labels = labels

    def set(self, value: float) -> None:
        self._gauge._set_with_labels(self._labels, value)

    def inc(self, amount: float = 1.0) -> None:
        key = tuple(sorted(self._labels.items()))
        with self._gauge._lock:
            self._gauge._values[key] += amount

    def dec(self, amount: float = 1.0) -> None:
        key = tuple(sorted(self._labels.items()))
        with self._gauge._lock:
            self._gauge._values[key] -= amount


class Histogram:
    """
    Prometheus-style Histogram metric.

    Records observations in buckets.

    Example:
        >>> hist = Histogram("request_duration_seconds", buckets=[0.1, 0.5, 1.0, 5.0])
        >>> hist.observe(0.3)
        >>> hist.observe(1.5)
    """

    DEFAULT_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

    def __init__(
        self, name: str, description: str = "", buckets: Optional[Tuple[float, ...]] = None
    ):
        self.name = name
        self.description = description
        self.buckets = tuple(sorted(buckets or self.DEFAULT_BUCKETS))
        self._counts: Dict[Tuple, Dict[float, int]] = defaultdict(
            lambda: dict.fromkeys(self.buckets, 0)
        )
        self._sums: Dict[Tuple, float] = defaultdict(float)
        self._totals: Dict[Tuple, int] = defaultdict(int)
        self._lock = threading.Lock()

    def observe(self, value: float) -> None:
        """Record an observation."""
        with self._lock:
            key = ()
            self._sums[key] += value
            self._totals[key] += 1
            for bucket in self.buckets:
                if value <= bucket:
                    self._counts[key][bucket] += 1

    def labels(self, **kwargs) -> "LabeledHistogram":
        """Return histogram with labels."""
        return LabeledHistogram(self, kwargs)

    def get_sample_count(self, labels: Optional[Dict[str, str]] = None) -> int:
        key = tuple(sorted((labels or {}).items()))
        return self._totals.get(key, 0)

    def get_sample_sum(self, labels: Optional[Dict[str, str]] = None) -> float:
        key = tuple(sorted((labels or {}).items()))
        return self._sums.get(key, 0.0)


class LabeledHistogram:
    """Histogram with labels attached."""

    def __init__(self, histogram: Histogram, labels: Dict[str, str]):
        self._histogram = histogram
        self._labels = labels

    def observe(self, value: float) -> None:
        key = tuple(sorted(self._labels.items()))
        with self._histogram._lock:
            self._histogram._sums[key] += value
            self._histogram._totals[key] += 1
            if key not in self._histogram._counts:
                self._histogram._counts[key] = dict.fromkeys(self._histogram.buckets, 0)
            for bucket in self._histogram.buckets:
                if value <= bucket:
                    self._histogram._counts[key][bucket] += 1


class MetricsRegistry:
    """
    Central registry for all metrics.

    Example:
        >>> registry = MetricsRegistry()
        >>>
        >>> # Create metrics
        >>> requests = registry.counter("requests_total", "Total requests")
        >>> latency = registry.histogram("request_latency_seconds")
        >>>
        >>> # Record
        >>> requests.inc()
        >>> latency.observe(0.5)
        >>>
        >>> # Export
        >>> print(registry.export_prometheus())
    """

    def __init__(self, prefix: str = "graphcrawler"):
        self.prefix = prefix
        self._counters: Dict[str, Counter] = {}
        self._gauges: Dict[str, Gauge] = {}
        self._histograms: Dict[str, Histogram] = {}
        self._lock = threading.Lock()

    def counter(self, name: str, description: str = "") -> Counter:
        """Get or create a counter."""
        full_name = f"{self.prefix}_{name}" if self.prefix else name
        with self._lock:
            if full_name not in self._counters:
                self._counters[full_name] = Counter(full_name, description)
            return self._counters[full_name]

    def gauge(self, name: str, description: str = "") -> Gauge:
        """Get or create a gauge."""
        full_name = f"{self.prefix}_{name}" if self.prefix else name
        with self._lock:
            if full_name not in self._gauges:
                self._gauges[full_name] = Gauge(full_name, description)
            return self._gauges[full_name]

    def histogram(
        self, name: str, description: str = "", buckets: Optional[Tuple[float, ...]] = None
    ) -> Histogram:
        """Get or create a histogram."""
        full_name = f"{self.prefix}_{name}" if self.prefix else name
        with self._lock:
            if full_name not in self._histograms:
                self._histograms[full_name] = Histogram(full_name, description, buckets)
            return self._histograms[full_name]

    def export_prometheus(self) -> str:
        """
        Export all metrics in Prometheus text format.

        Returns:
            Prometheus-format string
        """
        lines = []

        # Export counters
        for name, counter in self._counters.items():
            lines.append(f"# HELP {name} {counter.description}")
            lines.append(f"# TYPE {name} counter")
            for labels_tuple, value in counter._values.items():
                labels_str = self._format_labels(dict(labels_tuple))
                lines.append(f"{name}{labels_str} {value}")

        # Export gauges
        for name, gauge in self._gauges.items():
            lines.append(f"# HELP {name} {gauge.description}")
            lines.append(f"# TYPE {name} gauge")
            for labels_tuple, value in gauge._values.items():
                labels_str = self._format_labels(dict(labels_tuple))
                lines.append(f"{name}{labels_str} {value}")

        # Export histograms
        for name, hist in self._histograms.items():
            lines.append(f"# HELP {name} {hist.description}")
            lines.append(f"# TYPE {name} histogram")
            for labels_tuple, counts in hist._counts.items():
                labels_dict = dict(labels_tuple)
                cumulative = 0
                for bucket in hist.buckets:
                    cumulative += counts[bucket]
                    bucket_labels = {**labels_dict, "le": str(bucket)}
                    labels_str = self._format_labels(bucket_labels)
                    lines.append(f"{name}_bucket{labels_str} {cumulative}")
                # +Inf bucket
                inf_labels = {**labels_dict, "le": "+Inf"}
                lines.append(
                    f"{name}_bucket{self._format_labels(inf_labels)} {hist._totals[labels_tuple]}"
                )
                lines.append(
                    f"{name}_sum{self._format_labels(labels_dict)} {hist._sums[labels_tuple]}"
                )
                lines.append(
                    f"{name}_count{self._format_labels(labels_dict)} {hist._totals[labels_tuple]}"
                )

        return "\n".join(lines)

    def export_dict(self) -> Dict[str, Any]:
        """Export all metrics as dictionary."""
        return {
            "counters": {name: dict(counter._values) for name, counter in self._counters.items()},
            "gauges": {name: dict(gauge._values) for name, gauge in self._gauges.items()},
            "histograms": {
                name: {
                    "counts": dict(hist._counts),
                    "sums": dict(hist._sums),
                    "totals": dict(hist._totals),
                }
                for name, hist in self._histograms.items()
            },
        }

    def _format_labels(self, labels: Dict[str, str]) -> str:
        """Format labels for Prometheus."""
        if not labels:
            return ""
        pairs = [f'{k}="{v}"' for k, v in sorted(labels.items())]
        return "{" + ",".join(pairs) + "}"

    def reset(self) -> None:
        """Reset all metrics."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()


# Global metrics registry (singleton)
_global_metrics: Optional[MetricsRegistry] = None


def get_metrics(prefix: str = "graphcrawler") -> MetricsRegistry:
    """
    Get global metrics registry (singleton).

    Args:
        prefix: Metric name prefix

    Returns:
        MetricsRegistry instance
    """
    global _global_metrics
    if _global_metrics is None:
        _global_metrics = MetricsRegistry(prefix)
    return _global_metrics


# Pre-defined metrics for GraphCrawler
class CrawlerMetrics:
    """
    Pre-defined metrics for GraphCrawler.

    Usage:
        >>> from graph_crawler.observability.metrics import CrawlerMetrics
        >>>
        >>> CrawlerMetrics.requests_total.inc()
        >>> CrawlerMetrics.pages_crawled.inc()
        >>> CrawlerMetrics.request_duration.observe(0.5)
    """

    _registry = get_metrics()

    # Counters
    requests_total = _registry.counter("requests_total", "Total number of HTTP requests")
    pages_crawled = _registry.counter("pages_crawled_total", "Total number of pages crawled")
    errors_total = _registry.counter("errors_total", "Total number of errors")

    # Gauges
    active_requests = _registry.gauge("active_requests", "Number of currently active requests")
    queue_size = _registry.gauge("queue_size", "Number of URLs in queue")
    memory_usage_bytes = _registry.gauge("memory_usage_bytes", "Current memory usage in bytes")

    # Histograms
    request_duration = _registry.histogram(
        "request_duration_seconds",
        "HTTP request duration in seconds",
        buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    )
    page_size_bytes = _registry.histogram(
        "page_size_bytes",
        "Page size in bytes",
        buckets=(1000, 10000, 50000, 100000, 500000, 1000000),
    )


__all__ = [
    "Counter",
    "Gauge",
    "Histogram",
    "MetricsRegistry",
    "get_metrics",
    "CrawlerMetrics",
]
