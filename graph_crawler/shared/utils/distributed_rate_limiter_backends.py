"""Backend implementations for the distributed rate limiter.

The goal of this module is to keep the *core* rate limiting algorithm and
backends decoupled from any higher-level coordination logic. The
``DistributedRateLimiter`` composes these backends and is implemented in
``distributed_rate_limiter.py``.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from threading import Lock
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class RateLimiterBackend(ABC):
    """Abstract base class for rate-limiting backends.

    Backends operate on *domains* (already-normalized) and implement a
    simple sliding-window semantic via three methods:

    - :meth:`can_make_request`
    - :meth:`record_request`
    - :meth:`get_wait_time`
    """

    @abstractmethod
    def can_make_request(self, domain: str) -> bool:
        """Return ``True`` if a request is currently allowed for the domain."""

    @abstractmethod
    def record_request(self, domain: str) -> None:
        """Record that a request was performed for the domain."""

    @abstractmethod
    def get_wait_time(self, domain: str) -> float:
        """Return required wait time (in seconds) until next request.

        ``0.0`` means a request can be issued immediately.
        """

    @abstractmethod
    def get_statistics(self) -> Dict[str, Any]:
        """Return backend-specific statistics as a plain dict."""

    @abstractmethod
    def close(self) -> None:
        """Release any backend resources (e.g., Redis connections)."""


class LocalSlidingWindowBackend(RateLimiterBackend):
    """Process-local sliding window rate limiter.

    Used both as a standalone backend and as a fallback when Redis is not
    available.
    """

    def __init__(self, requests_per_minute: int = 60, window_size: int = 60):
        self.requests_per_minute = requests_per_minute
        self.window_size = window_size
        self._request_times: Dict[str, list[float]] = {}
        self._lock = Lock()
        logger.debug(
            "LocalSlidingWindowBackend initialized: %s req/min, window=%ss",
            requests_per_minute,
            window_size,
        )

    def can_make_request(self, domain: str) -> bool:
        with self._lock:
            now = time.time()
            cutoff_time = now - self.window_size

            times = self._request_times.get(domain, [])
            times = [t for t in times if t > cutoff_time]
            self._request_times[domain] = times

            current_count = len(times)
            can_proceed = current_count < self.requests_per_minute

            if not can_proceed:
                logger.debug(
                    "⏸ Local rate limit reached for %s: %s/%s req/min",
                    domain,
                    current_count,
                    self.requests_per_minute,
                )

            return can_proceed

    def record_request(self, domain: str) -> None:
        with self._lock:
            now = time.time()
            self._request_times.setdefault(domain, []).append(now)
            logger.debug("Local request recorded for %s", domain)

    def get_wait_time(self, domain: str) -> float:
        with self._lock:
            now = time.time()
            cutoff_time = now - self.window_size

            times = self._request_times.get(domain, [])
            times = [t for t in times if t > cutoff_time]
            self._request_times[domain] = times

            if len(times) < self.requests_per_minute:
                return 0.0

            oldest = min(times)
            wait_time = max(0.0, float(self.window_size) - (now - oldest))
            return wait_time

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            now = time.time()
            cutoff_time = now - self.window_size

            active_domains = 0
            total_requests = 0
            for times in self._request_times.values():
                recent = [t for t in times if t > cutoff_time]
                if recent:
                    active_domains += 1
                    total_requests += len(recent)

            return {
                "type": "local",
                "requests_per_minute": self.requests_per_minute,
                "window_size": self.window_size,
                "active_domains": active_domains,
                "total_recent_requests": total_requests,
                "tracked_domains": len(self._request_times),
            }

    def close(self) -> None:  # pragma: no cover - nothing to close
        """No-op for local backend."""
        return None


class RedisSlidingWindowBackend(RateLimiterBackend):
    """Redis-based sliding window backend.

    Each domain uses a per-window counter key. The window index is derived
    from ``time.time() / window_size`` which keeps the implementation simple
    and cheap.
    """

    def __init__(
        self,
        redis_url: str,
        requests_per_minute: int = 60,
        window_size: int = 60,
        key_prefix: str = "ratelimit",
    ) -> None:
        self.redis_url = redis_url
        self.requests_per_minute = requests_per_minute
        self.window_size = window_size
        self.key_prefix = key_prefix

        self._redis = None
        self._available = False

        self._total_requests = 0
        self._failures = 0

        self._initialize_redis()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _initialize_redis(self) -> None:
        try:
            import redis

            self._redis = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            self._redis.ping()
            self._available = True
            logger.info("RedisSlidingWindowBackend connected: %s", self.redis_url)
        except ImportError:
            logger.warning("Redis library is not installed. pip install redis")
            self._available = False
        except Exception as exc:  # pragma: no cover - defensive path
            logger.warning("Failed to connect to Redis: %s", exc)
            self._available = False

    def _get_key(self, domain: str) -> str:
        timestamp = int(time.time() / self.window_size)
        return f"{self.key_prefix}:{domain}:{timestamp}"

    # ------------------------------------------------------------------
    # RateLimiterBackend API
    # ------------------------------------------------------------------
    def can_make_request(self, domain: str) -> bool:
        if not self._available or self._redis is None:
            return True

        try:
            key = self._get_key(domain)
            current = self._redis.get(key)
            current_count = int(current) if current else 0
            can_proceed = current_count < self.requests_per_minute

            if not can_proceed:
                logger.debug(
                    "⏸ [Redis] rate limit for %s: %s/%s req/min",
                    domain,
                    current_count,
                    self.requests_per_minute,
                )

            return can_proceed
        except Exception as exc:  # pragma: no cover - network issues
            logger.warning("Redis error in can_make_request: %s", exc)
            self._available = False
            self._failures += 1
            return True

    def record_request(self, domain: str) -> None:
        self._total_requests += 1

        if not self._available or self._redis is None:
            return

        try:
            key = self._get_key(domain)
            pipe = self._redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, self.window_size)
            pipe.execute()
            logger.debug("[Redis] request recorded for %s", domain)
        except Exception as exc:  # pragma: no cover - network issues
            logger.warning("Redis error in record_request: %s", exc)
            self._available = False
            self._failures += 1

    def get_wait_time(self, domain: str) -> float:
        if not self._available or self._redis is None:
            return 0.0

        try:
            key = self._get_key(domain)
            current = self._redis.get(key)
            current_count = int(current) if current else 0

            if current_count < self.requests_per_minute:
                return 0.0

            ttl = self._redis.ttl(key)
            return max(0.0, float(ttl)) if ttl and ttl > 0 else 0.0
        except Exception as exc:  # pragma: no cover - network issues
            logger.warning("Redis error in get_wait_time: %s", exc)
            self._available = False
            self._failures += 1
            return 0.0

    def get_statistics(self) -> Dict[str, Any]:
        return {
            "type": "redis",
            "redis_url": self.redis_url,
            "requests_per_minute": self.requests_per_minute,
            "window_size": self.window_size,
            "available": self._available,
            "total_requests": self._total_requests,
            "failures": self._failures,
        }

    def close(self) -> None:
        if self._redis is not None:
            try:
                self._redis.close()
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Error while closing Redis connection: %s", exc)


__all__ = [
    "RateLimiterBackend",
    "LocalSlidingWindowBackend",
    "RedisSlidingWindowBackend",
]
