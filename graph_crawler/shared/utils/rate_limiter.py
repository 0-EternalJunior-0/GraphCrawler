"""
Rate Limiter Module.

Wrapper над бібліотекою 'ratelimit' для простих use cases глобального rate limiting.
"""

import functools
import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# Перевірка наявності ratelimit бібліотеки (Lazy - без warning при імпорті)
_RATELIMIT_CHECKED = False
_RATELIMIT_AVAILABLE = None


def _check_ratelimit_availability() -> bool:
    """Lazy перевірка наявності ratelimit бібліотеки (без warning при імпорті)."""
    global _RATELIMIT_CHECKED, _RATELIMIT_AVAILABLE
    if _RATELIMIT_CHECKED:
        return _RATELIMIT_AVAILABLE

    try:
        from ratelimit import RateLimitException, limits, sleep_and_retry

        _RATELIMIT_AVAILABLE = True
    except ImportError:
        _RATELIMIT_AVAILABLE = False

    _RATELIMIT_CHECKED = True
    return _RATELIMIT_AVAILABLE


# Backward compatibility
RATELIMIT_AVAILABLE = property(lambda self: _check_ratelimit_availability())


class RateLimiter:
    """
    Rate Limiter використовуючи бібліотеку 'ratelimit'.

    Для простих глобальних rate limits.

    Args:
        calls: Кількість викликів
        period: Період в секундах
        raise_on_limit: Викидати exception при досягненні ліміту

    Example:
        >>> # Глобальний rate limiter (10 запитів на секунду)
        >>> limiter = RateLimiter(calls=10, period=1)
        >>>
        >>> @limiter.limit
        ... def fetch_page(url):
        ...     return requests.get(url)
        >>>
        >>> # Викидає exception при досягненні ліміту
        >>> limiter_strict = RateLimiter(calls=10, period=1, raise_on_limit=True)
        >>>
        >>> @limiter_strict.limit
        ... def fetch_strict(url):
        ...     return requests.get(url)
    """

    def __init__(self, calls: int = 10, period: int = 1, raise_on_limit: bool = False):
        """Ініціалізує RateLimiter"""
        if not _check_ratelimit_availability():
            raise ImportError(
                "ratelimit бібліотека не встановлена. "
                "Встановіть: pip install ratelimit"
            )

        self.calls = calls
        self.period = period
        self.raise_on_limit = raise_on_limit

        logger.info(
            f" RateLimiter: {calls} calls/{period}s "
            f"(raise_on_limit={raise_on_limit})"
        )

    def limit(self, func: Callable) -> Callable:
        """
        Декоратор для rate limiting функції.

        Args:
            func: Функція для обгортання

        Returns:
            Обгорнута функція з rate limiting

        Example:
            >>> limiter = SimpleRateLimiter(calls=10, period=1)
            >>>
            >>> @limiter.limit
            ... def my_function():
            ...     pass
        """
        # Lazy import
        from ratelimit import limits, sleep_and_retry

        if self.raise_on_limit:
            # Режим з exception
            @limits(calls=self.calls, period=self.period)
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)

        else:
            # Режим з очікуванням (sleep)
            @sleep_and_retry
            @limits(calls=self.calls, period=self.period)
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)

        return wrapper

    def __call__(self, func: Callable) -> Callable:
        """Дозволяє використання як декоратор без виклику"""
        return self.limit(func)


def rate_limit(
    calls: int = 10, period: int = 1, raise_on_limit: bool = False
) -> Callable:
    """
    Декоратор для швидкого rate limiting.

    Args:
        calls: Кількість викликів
        period: Період в секундах
        raise_on_limit: Викидати exception при досягненні ліміту

    Returns:
        Декоратор функції

    Example:
        >>> @rate_limit(calls=10, period=1)
        ... def fetch_page(url):
        ...     return requests.get(url)
    """
    limiter = RateLimiter(calls=calls, period=period, raise_on_limit=raise_on_limit)
    return limiter.limit


# Готові конфігурації для популярних use cases
class RateLimitPresets:
    """Готові конфігурації rate limiting"""

    @staticmethod
    def conservative() -> RateLimiter:
        """Консервативний ліміт: 1 запит на секунду"""
        return RateLimiter(calls=1, period=1)

    @staticmethod
    def moderate() -> RateLimiter:
        """Помірний ліміт: 10 запитів на секунду"""
        return RateLimiter(calls=10, period=1)

    @staticmethod
    def aggressive() -> RateLimiter:
        """Агресивний ліміт: 100 запитів на секунду"""
        return RateLimiter(calls=100, period=1)

    @staticmethod
    def api_friendly() -> RateLimiter:
        """API-friendly: 60 запитів на хвилину"""
        return RateLimiter(calls=60, period=60)


# Factory функція для створення rate limiter
def create_rate_limiter(calls: int = 10, period: int = 1) -> RateLimiter:
    """
    Factory функція для створення rate limiter.

    Args:
        calls: Кількість викликів
        period: Період в секундах

    Returns:
        RateLimiter
    """
    return RateLimiter(calls=calls, period=period)


# Example usage
if __name__ == "__main__":
    # Приклад 1: Простий декоратор
    @rate_limit(calls=10, period=1)
    def fetch_data(url: str):
        print(f"Fetching: {url}")
        return f"Data from {url}"

    # Приклад 2: З об'єктом limiter
    limiter = RateLimiter(calls=5, period=1)

    @limiter.limit
    def process_item(item: Any):
        print(f"Processing: {item}")
        return item

    # Приклад 3: Використання presets
    conservative_limiter = RateLimitPresets.conservative()

    @conservative_limiter.limit
    def careful_operation():
        print("Careful operation")

    print(" RateLimiter examples ready")

# Backward compatibility aliases
DomainRateLimiter = RateLimiter  # Alias для старого коду
DomainLimitConfig = dict  # Placeholder для старого коду
