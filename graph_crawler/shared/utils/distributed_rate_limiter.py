"""Distributed Rate Limiter - розподілене обмеження швидкості запитів.

У цій версії модуль зосереджується на високорівневому API, а
алгоритмічна частина винесена в ``distributed_rate_limiter_backends``.

Публічний API:
- :class:`DistributedRateLimiter`
- :func:`create_rate_limiter`
"""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager, contextmanager
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from .distributed_rate_limiter_backends import (
    LocalSlidingWindowBackend,
    RateLimiterBackend,
    RedisSlidingWindowBackend,
)

logger = logging.getLogger(__name__)


class DistributedRateLimiter:
    """Розподілений rate limiter з підтримкою Redis та локального fallback.

    ``DistributedRateLimiter`` не реалізує алгоритм напряму, а делегує
    всю роботу бекендам (:class:`RedisSlidingWindowBackend`,
    :class:`LocalSlidingWindowBackend`). Це значно спрощує тестування та
    подальший розвиток (можна додати інші бекенди, наприклад Kafka).
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        requests_per_minute: int = 60,
        window_size: int = 60,
        key_prefix: str = "ratelimit",
        use_local_fallback: bool = True,
    ) -> None:
        self.redis_url = redis_url
        self.requests_per_minute = requests_per_minute
        self.window_size = window_size
        self.key_prefix = key_prefix
        self.use_local_fallback = use_local_fallback

        self._redis_backend: Optional[RateLimiterBackend] = None
        if redis_url:
            self._redis_backend = RedisSlidingWindowBackend(
                redis_url=redis_url,
                requests_per_minute=requests_per_minute,
                window_size=window_size,
                key_prefix=key_prefix,
            )

        self._local_backend: RateLimiterBackend = LocalSlidingWindowBackend(
            requests_per_minute=requests_per_minute,
            window_size=window_size,
        )

        self.total_requests = 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_domain(url_or_domain: str) -> str:
        if url_or_domain.startswith(("http://", "https://")):
            parsed = urlparse(url_or_domain)
            return parsed.netloc
        return url_or_domain

    def _select_backend(self) -> RateLimiterBackend:
        """Return active backend (Redis if available, otherwise local)."""
        if self._redis_backend is not None:
            stats = self._redis_backend.get_statistics()
            if stats.get("available", True):
                return self._redis_backend

        return self._local_backend

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------
    def can_make_request(self, url_or_domain: str) -> bool:
        domain = self._extract_domain(url_or_domain)
        backend = self._select_backend()
        return backend.can_make_request(domain)

    def record_request(self, url_or_domain: str) -> None:
        domain = self._extract_domain(url_or_domain)
        backend = self._select_backend()
        backend.record_request(domain)
        self.total_requests += 1

    def get_wait_time(self, url_or_domain: str) -> float:
        domain = self._extract_domain(url_or_domain)
        backend = self._select_backend()
        return backend.get_wait_time(domain)

    # ------------------------------------------------------------------
    # Context managers
    # ------------------------------------------------------------------
    @contextmanager
    def acquire(self, url_or_domain: str, timeout: float = 60.0):
        """Sync context manager для автоматичного rate limiting.

        WARNING: Блокує потік. В async-коді використовуйте
        :meth:`async_acquire`.
        """

        domain = self._extract_domain(url_or_domain)
        start_time = time.time()

        while True:
            if self.can_make_request(domain):
                self.record_request(domain)
                try:
                    yield
                finally:
                    pass
                break

            elapsed = time.time() - start_time
            if elapsed >= timeout:
                raise TimeoutError(
                    f"Rate limit timeout для {domain} після {elapsed:.1f}s",
                )

            wait_time = min(self.get_wait_time(domain), 1.0)
            if wait_time > 0:
                time.sleep(wait_time)
            else:
                time.sleep(0.1)

    @asynccontextmanager
    async def async_acquire(self, url_or_domain: str, timeout: float = 60.0):
        """Async context manager для автоматичного rate limiting.

        Використовує :func:`asyncio.sleep` для неблокуючого очікування.
        """

        domain = self._extract_domain(url_or_domain)
        start_time = time.time()

        while True:
            if self.can_make_request(domain):
                self.record_request(domain)
                try:
                    yield
                finally:
                    pass
                break

            elapsed = time.time() - start_time
            if elapsed >= timeout:
                raise TimeoutError(
                    f"Rate limit timeout для {domain} після {elapsed:.1f}s",
                )

            wait_time = min(self.get_wait_time(domain), 1.0)
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            else:
                await asyncio.sleep(0.1)

    # ------------------------------------------------------------------
    # Introspection & lifecycle
    # ------------------------------------------------------------------
    def get_statistics(self) -> Dict[str, Any]:
        stats: Dict[str, Any] = {
            "redis_url": self.redis_url,
            "requests_per_minute": self.requests_per_minute,
            "window_size": self.window_size,
            "total_requests": self.total_requests,
        }

        stats["local"] = self._local_backend.get_statistics()

        if self._redis_backend is not None:
            stats["redis"] = self._redis_backend.get_statistics()

        return stats

    def get_summary(self) -> str:
        s = self.get_statistics()

        lines = [
            "=" * 60,
            " Distributed Rate Limiter Statistics",
            "=" * 60,
            "",
            "Configuration:",
            f"  - Redis URL: {s.get('redis_url') or 'Not configured'}",
            f"  - Requests/minute: {s.get('requests_per_minute')}",
            f"  - Window size: {s.get('window_size')}s",
            "",
            "Usage:",
            f"  - Total requests: {s.get('total_requests')}",
        ]

        local = s.get("local") or {}
        lines.extend(
            [
                "",
                "Local Backend:",
                f"  - Active domains: {local.get('active_domains', 0)}",
                f"  - Recent requests: {local.get('total_recent_requests', 0)}",
                f"  - Tracked domains: {local.get('tracked_domains', 0)}",
            ]
        )

        if "redis" in s:
            redis_stats = s["redis"]
            lines.extend(
                [
                    "",
                    "Redis Backend:",
                    f"  - Available: {redis_stats.get('available', False)}",
                    f"  - Total requests: {redis_stats.get('total_requests', 0)}",
                    f"  - Failures: {redis_stats.get('failures', 0)}",
                ]
            )

        lines.append("=" * 60)
        return "\n".join(lines)

    def reset(self) -> None:
        """Скинути лічильники високорівневого об'єкта.

        Бекенди зберігають власну внутрішню історію, але її можна
        обнулити через перезавантаження об'єкта, якщо це потрібно.
        """

        self.total_requests = 0

    def close(self) -> None:
        """Закрити всі бекенди та звільнити ресурси."""
        self._local_backend.close()
        if self._redis_backend is not None:
            self._redis_backend.close()


def create_rate_limiter(
    redis_url: Optional[str] = None,
    requests_per_minute: int = 60,
    distributed: bool = True,
) -> DistributedRateLimiter:
    """Factory-функція для створення ``DistributedRateLimiter``.

    Args:
        redis_url: URL для Redis (якщо distributed=True)
        requests_per_minute: Максимальна кількість запитів на хвилину
        distributed: Чи використовувати розподілений режим (Redis)
    """

    if distributed and redis_url:
        return DistributedRateLimiter(
            redis_url=redis_url,
            requests_per_minute=requests_per_minute,
        )

    return DistributedRateLimiter(
        redis_url=None,
        requests_per_minute=requests_per_minute,
    )


__all__ = ["DistributedRateLimiter", "create_rate_limiter"]
