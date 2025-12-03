"""Декоратор для логування виконання функцій."""

import functools
import logging
from typing import Callable

logger = logging.getLogger(__name__)


def log_execution(
    level: int = logging.INFO, include_args: bool = False, include_result: bool = False
):
    """
    Декоратор для логування виконання функцій.

    Args:
        level: Рівень логування
        include_args: Включати аргументи
        include_result: Включати результат

    Приклад:
        @log_execution(level=logging.DEBUG, include_args=True)
        def process_data(data):
            return data.upper()
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            func_name = func.__name__

            # Лог початку
            msg = f"Executing {func_name}"
            if include_args:
                msg += f" with args={args}, kwargs={kwargs}"
            logger.log(level, msg)

            try:
                result = func(*args, **kwargs)

                # Лог успіху
                msg = f"{func_name} completed successfully"
                if include_result:
                    msg += f" with result={result}"
                logger.log(level, msg)

                return result

            except Exception as e:
                # Лог помилки
                logger.error(f"{func_name} failed with error: {e}")
                raise

        return wrapper

    return decorator
