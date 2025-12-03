"""Декоратор для кешування результатів."""

import functools
import hashlib
import json
import logging
import time
from typing import Any, Callable, Dict, Optional

# Local constant to avoid circular imports
DEFAULT_CACHE_TTL = 3600  # 1 hour in seconds

logger = logging.getLogger(__name__)


class SimpleCache:
    """
    Простий in-memory кеш з TTL.

     ВАЖЛИВО: Це in-memory only кеш.
    - Дані зберігаються тільки в RAM
    - Кеш очищується при restart процесу
    - Немає персистентності на диск
    - Для персистентного кешу використовуйте diskcache або Redis
    """

    def __init__(self):
        self._cache: Dict[str, tuple[Any, float]] = {}

    def get(self, key: str, ttl: Optional[float] = None) -> Optional[Any]:
        """Отримує значення з кешу."""
        if key not in self._cache:
            return None

        value, timestamp = self._cache[key]

        if ttl and (time.time() - timestamp) > ttl:
            del self._cache[key]
            return None

        return value

    def set(self, key: str, value: Any):
        """Зберігає значення у кеш."""
        self._cache[key] = (value, time.time())

    def clear(self):
        """Очищує кеш."""
        self._cache.clear()


_global_cache = SimpleCache()


def make_cache_key(func_name: str, args: tuple, kwargs: dict) -> str:
    """
    Створює надійний ключ кешу з використанням хешування.

    Args:
        func_name: Назва функції
        args: Позиційні аргументи
        kwargs: Іменовані аргументи

    Returns:
        Хеш-ключ для кешу
    """
    try:
        # Спроба серіалізації через JSON
        key_data = {"func": func_name, "args": args, "kwargs": sorted(kwargs.items())}
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.md5(key_str.encode()).hexdigest()
    except (TypeError, ValueError):
        # Fallback для unhashable об'єктів
        return hashlib.md5(
            f"{func_name}:{repr(args)}:{repr(sorted(kwargs.items()))}".encode()
        ).hexdigest()


def cache(ttl: Optional[float] = DEFAULT_CACHE_TTL):
    """
    Декоратор для кешування результатів функції.

    Args:
        ttl: Time to live (секунди). None = безкінечно

    Приклад:
        @cache(ttl=3600)  # 1 година
        def fetch_url(url):
            return requests.get(url)
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Створюємо надійний ключ з використанням хешування
            cache_key = make_cache_key(func.__name__, args, kwargs)

            # Перевіряємо кеш
            cached_value = _global_cache.get(cache_key, ttl)
            if cached_value is not None:
                logger.debug(f"Cache hit: {func.__name__}")
                return cached_value

            # Виконуємо функцію
            result = func(*args, **kwargs)

            # Зберігаємо в кеш
            _global_cache.set(cache_key, result)

            return result

        return wrapper

    return decorator
