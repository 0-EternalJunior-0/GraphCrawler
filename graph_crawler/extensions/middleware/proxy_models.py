"""Proxy domain model used by the proxy middleware.

This module keeps all state and statistics related to a single proxy
endpoint in one place, following the SRP and making the middleware
itself much thinner.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List

from graph_crawler.shared.constants import MAX_RESPONSE_TIME_SAMPLES


@dataclass
class ProxyInfo:
    """Value object holding proxy state and statistics.

    Attributes:
        url: URL of the proxy (http://host:port, socks5://host:port, etc.)
        is_alive: Health flag as last detected by the health checker.
        last_check_time: Timestamp of last health check.
        avg_response_time: Moving average of response time in seconds.
        total_requests: Total number of requests sent through this proxy.

    The class encapsulates internal counters and exposes read-only
    properties for external consumers. This avoids leaking internal
    bookkeeping to the rest of the system.
    """

    url: str
    is_alive: bool = True
    last_check_time: float = field(default_factory=time.time)
    avg_response_time: float = 0.0
    total_requests: int = 0
    response_times: List[float] = field(default_factory=list)

    _success_count: int = field(default=0, init=False, repr=False)
    _failure_count: int = field(default=0, init=False, repr=False)

    # ------------------------------------------------------------------
    # Derived metrics
    # ------------------------------------------------------------------
    @property
    def success_count(self) -> int:
        return self._success_count

    @property
    def failure_count(self) -> int:
        return self._failure_count

    @property
    def success_rate(self) -> float:
        total = self._success_count + self._failure_count
        if total == 0:
            return 1.0
        return self._success_count / total

    # ------------------------------------------------------------------
    # State mutation helpers
    # ------------------------------------------------------------------
    def mark_success(self, response_time: float = 0.0) -> None:
        self._success_count += 1
        self.total_requests += 1

        if response_time > 0:
            self.update_response_time(response_time)

    def mark_failure(self) -> None:
        self._failure_count += 1
        self.total_requests += 1

    def reset_stats(self) -> None:
        self._success_count = 0
        self._failure_count = 0
        self.total_requests = 0
        self.response_times.clear()
        self.avg_response_time = 0.0

    def update_response_time(self, response_time: float) -> None:
        self.response_times.append(response_time)
        if len(self.response_times) > MAX_RESPONSE_TIME_SAMPLES:
            self.response_times = self.response_times[-MAX_RESPONSE_TIME_SAMPLES:]
        self.avg_response_time = sum(self.response_times) / len(self.response_times)


__all__ = ["ProxyInfo"]
