"""Domain-based Rate Limiter - обмеження запитів по доменам.



Забезпечує:
- Per-domain rate limiting (наприклад, max 10 req/sec на домен)
- Автоматичне throttling при 429 статусах
- Захист від випадкового DDoS сайту
- Thread-safe для async контексту

Приклад:
    >>> limiter = DomainRateLimiter(requests_per_second=10)
    >>> 
    >>> # Перевірка чи можна робити запит
    >>> if await limiter.acquire("example.com"):
    ...     await make_request()
    ... else:
    ...     await asyncio.sleep(limiter.get_wait_time("example.com"))
"""

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Set

from graph_crawler.shared.utils.url_utils import URLUtils

logger = logging.getLogger(__name__)


@dataclass
class DomainStats:
    """Статистика запитів для одного домену."""
    
    # Ліміти
    requests_per_second: float = 10.0
    burst_limit: int = 20
    
    # Стан
    tokens: float = 20.0  # Token bucket
    last_request_time: float = 0.0
    total_requests: int = 0
    rate_limited_count: int = 0  # Кількість 429 відповідей
    
    # Backoff
    backoff_until: float = 0.0
    backoff_multiplier: float = 1.0


class DomainRateLimiter:
    """
    Per-domain Rate Limiter з Token Bucket алгоритмом.
    
    Забезпечує:
    - Ліміт запитів на секунду для кожного домену
    - Burst support (можна зробити N запитів одразу)
    - Автоматичний backoff при 429 статусах
    - Thread-safe для asyncio
    
    Алгоритм Token Bucket:
    - Кожен домен має "bucket" з токенами
    - Токени поповнюються з часом (requests_per_second)
    - Запит споживає 1 токен
    - Якщо токенів немає - потрібно чекати
    
    Приклад:
        >>> limiter = DomainRateLimiter(
        ...     requests_per_second=10,
        ...     burst_limit=20
        ... )
        >>> 
        >>> async def crawl(url):
        ...     domain = URLUtils.get_domain(url)
        ...     await limiter.acquire(domain)
        ...     response = await fetch(url)
        ...     if response.status == 429:
        ...         limiter.report_rate_limited(domain)
    """
    
    def __init__(
        self,
        requests_per_second: float = 10.0,
        burst_limit: int = 20,
        backoff_base: float = 2.0,
        max_backoff: float = 60.0,
        default_wait: float = 0.1,
    ):
        """
        Ініціалізація Rate Limiter.
        
        Args:
            requests_per_second: Максимум запитів на секунду на домен
            burst_limit: Максимум запитів "вибухом" (burst)
            backoff_base: База для exponential backoff
            max_backoff: Максимальний час backoff (секунди)
            default_wait: Затримка за замовчуванням якщо немає токенів
        """
        self.requests_per_second = requests_per_second
        self.burst_limit = burst_limit
        self.backoff_base = backoff_base
        self.max_backoff = max_backoff
        self.default_wait = default_wait
        
        # Per-domain статистика
        self._domains: Dict[str, DomainStats] = defaultdict(
            lambda: DomainStats(
                requests_per_second=self.requests_per_second,
                burst_limit=self.burst_limit,
                tokens=float(self.burst_limit),
            )
        )
        
        # Lock для thread-safety
        self._lock = asyncio.Lock()
        
        logger.info(
            f"✅ DomainRateLimiter initialized: "
            f"{requests_per_second} req/s, burst={burst_limit}"
        )
    
    async def acquire(self, domain: str, tokens: int = 1) -> bool:
        """
        Запитати дозвіл на запит до домену.
        
        Non-blocking: повертає False якщо треба чекати.
        
        Args:
            domain: Домен для запиту
            tokens: Кількість токенів (за замовчуванням 1)
            
        Returns:
            True якщо запит дозволено, False якщо треба чекати
        """
        async with self._lock:
            stats = self._domains[domain]
            now = time.monotonic()
            
            # Перевірка backoff
            if stats.backoff_until > now:
                return False
            
            # Поповнення токенів з часом
            if stats.last_request_time > 0:
                elapsed = now - stats.last_request_time
                stats.tokens = min(
                    stats.burst_limit,
                    stats.tokens + elapsed * stats.requests_per_second
                )
            
            # Перевірка чи є токени
            if stats.tokens >= tokens:
                stats.tokens -= tokens
                stats.last_request_time = now
                stats.total_requests += 1
                return True
            
            return False
    
    async def acquire_wait(self, domain: str, timeout: float = 30.0) -> bool:
        """
        Запитати дозвіл і почекати якщо потрібно.
        
        Blocking: чекає поки не отримає дозвіл або timeout.
        
        Args:
            domain: Домен для запиту
            timeout: Максимальний час очікування
            
        Returns:
            True якщо отримано дозвіл, False якщо timeout
        """
        start = time.monotonic()
        
        while (time.monotonic() - start) < timeout:
            if await self.acquire(domain):
                return True
            
            # Чекаємо перед наступною спробою
            wait_time = self.get_wait_time(domain)
            await asyncio.sleep(min(wait_time, 0.5))
        
        return False
    
    def get_wait_time(self, domain: str) -> float:
        """
        Отримати час очікування до наступного запиту.
        
        Args:
            domain: Домен
            
        Returns:
            Час очікування в секундах
        """
        stats = self._domains[domain]
        now = time.monotonic()
        
        # Якщо backoff активний
        if stats.backoff_until > now:
            return stats.backoff_until - now
        
        # Якщо є токени - можна одразу
        if stats.tokens >= 1:
            return 0.0
        
        # Час до отримання 1 токена
        tokens_needed = 1 - stats.tokens
        return tokens_needed / stats.requests_per_second
    
    def report_rate_limited(self, domain: str) -> None:
        """
        Повідомити про 429 Rate Limited відповідь.
        
        Активує exponential backoff для домену.
        
        Args:
            domain: Домен що повернув 429
        """
        stats = self._domains[domain]
        stats.rate_limited_count += 1
        
        # Exponential backoff
        backoff_time = min(
            self.backoff_base ** stats.backoff_multiplier,
            self.max_backoff
        )
        stats.backoff_until = time.monotonic() + backoff_time
        stats.backoff_multiplier = min(stats.backoff_multiplier + 1, 6)
        
        logger.warning(
            f"⚠️ Rate limited by {domain}! "
            f"Backing off for {backoff_time:.1f}s "
            f"(count={stats.rate_limited_count})"
        )
    
    def report_success(self, domain: str) -> None:
        """
        Повідомити про успішний запит (скидає backoff).
        
        Args:
            domain: Домен
        """
        stats = self._domains[domain]
        
        # Поступово зменшуємо backoff multiplier
        if stats.backoff_multiplier > 1:
            stats.backoff_multiplier = max(1.0, stats.backoff_multiplier - 0.1)
    
    def get_domain_stats(self, domain: str) -> Dict[str, Any]:
        """
        Отримати статистику для домену.
        
        Args:
            domain: Домен
            
        Returns:
            Dict зі статистикою
        """
        stats = self._domains[domain]
        now = time.monotonic()
        
        return {
            "domain": domain,
            "requests_per_second": stats.requests_per_second,
            "burst_limit": stats.burst_limit,
            "current_tokens": stats.tokens,
            "total_requests": stats.total_requests,
            "rate_limited_count": stats.rate_limited_count,
            "is_backing_off": stats.backoff_until > now,
            "backoff_remaining": max(0, stats.backoff_until - now),
        }
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Отримати статистику для всіх доменів."""
        return {
            domain: self.get_domain_stats(domain)
            for domain in self._domains
        }
    
    def reset_domain(self, domain: str) -> None:
        """Скинути статистику для домену."""
        if domain in self._domains:
            del self._domains[domain]
            logger.info(f"Reset rate limiter for {domain}")
    
    def reset_all(self) -> None:
        """Скинути всю статистику."""
        self._domains.clear()
        logger.info("Reset all domain rate limiters")


# Глобальний rate limiter (singleton)
_global_rate_limiter: Optional[DomainRateLimiter] = None


def get_rate_limiter(
    requests_per_second: float = 10.0,
    burst_limit: int = 20,
) -> DomainRateLimiter:
    """
    Отримати глобальний rate limiter (singleton).
    
    Args:
        requests_per_second: Ліміт запитів на секунду
        burst_limit: Burst ліміт
        
    Returns:
        DomainRateLimiter instance
    """
    global _global_rate_limiter
    
    if _global_rate_limiter is None:
        _global_rate_limiter = DomainRateLimiter(
            requests_per_second=requests_per_second,
            burst_limit=burst_limit,
        )
    
    return _global_rate_limiter


__all__ = [
    "DomainRateLimiter",
    "DomainStats",
    "get_rate_limiter",
]
