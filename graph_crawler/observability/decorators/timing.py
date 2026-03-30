"""Декоратор для вимірювання часу виконання."""

import functools
import logging
import time
from typing import Callable

logger = logging.getLogger(__name__)


def measure_time(verbose: bool = True):
    """
    Декоратор для вимірювання часу виконання функції.

    Використовує logger замість print для production-ready коду.
    НЕ мутує результат функції - тільки логує час виконання.

    Args:
        verbose: Виводити час у лог

    Приклад:
        @measure_time()
        def slow_function():
            time.sleep(2)
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()

            result = func(*args, **kwargs)

            elapsed = time.time() - start_time

            if verbose:
                logger.info(" %s виконано за %.3fs", func.__name__, elapsed)

            return result

        return wrapper

    return decorator
