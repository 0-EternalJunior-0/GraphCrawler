"""Декоратор для автоматичного повтору при помилках .
- Додано async_retry() декоратор для async функцій з asyncio.sleep()
- Збережено sync retry() декоратор для зворотньої сумісності
"""

import asyncio
import functools
import logging
import time
from typing import Callable, Tuple, Type

logger = logging.getLogger(__name__)


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    exponential_backoff: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
):
    """
    Декоратор для повтору sync функції при помилці.

    WARNING: Блокуючий виклик! Використовуйте async_retry() для async функцій.

    Args:
        max_attempts: Максимум спроб
        delay: Затримка між спробами (сек)
        exponential_backoff: Експоненційна затримка
        exceptions: Tuple винятків для обробки

    Приклад:
        @retry(max_attempts=3, delay=1.0)
        def fetch_url(url):
            return requests.get(url)
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == max_attempts:
                        break

                    logger.warning(
                        f"Attempt {attempt}/{max_attempts} failed: {e}. Retrying in {current_delay}s..."
                    )
                    time.sleep(current_delay)

                    if exponential_backoff:
                        current_delay *= 2

            # Всі спроби вичерпано
            raise last_exception

        return wrapper

    return decorator


def async_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    exponential_backoff: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
):
    """
    Декоратор для повтору async функції при помилці .

    Використовує asyncio.sleep() для неблокуючого очікування.

    Args:
        max_attempts: Максимум спроб
        delay: Затримка між спробами (сек)
        exponential_backoff: Експоненційна затримка
        exceptions: Tuple винятків для обробки

    Приклад:
        @async_retry(max_attempts=3, delay=1.0)
        async def fetch_url(url):
            async with aiohttp.ClientSession() as session:
                return await session.get(url)
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay

            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == max_attempts:
                        break

                    logger.warning(
                        f"Attempt {attempt}/{max_attempts} failed: {e}. Retrying in {current_delay}s..."
                    )
                    await asyncio.sleep(current_delay)

                    if exponential_backoff:
                        current_delay *= 2

            # Всі спроби вичерпано
            raise last_exception

        return wrapper

    return decorator
