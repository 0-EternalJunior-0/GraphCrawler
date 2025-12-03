"""Спільна конфігурація для Celery модулів.

Цей модуль містить:
- get_broker_url(): Отримання URL Redis broker
- get_backend_url(): Отримання URL Redis backend
- get_celery_app_config(): Конфіг для celery_app (deprecated)
- get_celery_batch_config(): Конфіг для celery_batch (recommended)
- check_broker_connection(): Перевірка підключення до Redis
- validate_distributed_setup(): Повна валідація для distributed crawling
"""

import logging
import os
from typing import Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

# =====================================
# Default Values (з constants.py)
# =====================================

DEFAULT_REDIS_HOST = "localhost"
DEFAULT_REDIS_PORT = 6379
DEFAULT_REDIS_DB = 0
DEFAULT_CELERY_TASK_TIME_LIMIT = 600
DEFAULT_CELERY_TASK_SOFT_TIME_LIMIT = 540
DEFAULT_CELERY_RESULTS_TIMEOUT = 600

# =====================================
# Broker/Backend URL Functions
# =====================================


def get_broker_url() -> str:
    """Отримати URL для Celery broker (Redis).

    Priority:
    1. CELERY_BROKER_URL env variable
    2. REDIS_URL env variable
    3. Побудувати з REDIS_HOST/REDIS_PORT
    4. Fallback: redis://localhost:6379/0

    Returns:
        Redis URL для broker
    """
    # 1. Пряма змінна CELERY_BROKER_URL
    broker_url = os.environ.get("CELERY_BROKER_URL")
    if broker_url:
        return broker_url

    # 2. Загальна REDIS_URL
    redis_url = os.environ.get("REDIS_URL")
    if redis_url:
        return redis_url

    # 3. Побудувати з окремих змінних
    host = os.environ.get("REDIS_HOST", DEFAULT_REDIS_HOST)
    port = os.environ.get("REDIS_PORT", DEFAULT_REDIS_PORT)
    db = os.environ.get("REDIS_DB", DEFAULT_REDIS_DB)
    password = os.environ.get("REDIS_PASSWORD", "")

    if password:
        return f"redis://:{password}@{host}:{port}/{db}"

    # Fallback - warning виводиться тільки при явному виклику validate_distributed_setup()
    return f"redis://{host}:{port}/{db}"


def get_backend_url() -> str:
    """Отримати URL для Celery result backend (Redis).

    Пріоритет:
    1. CELERY_RESULT_BACKEND env variable
    2. Broker URL з іншою DB (якщо broker на db=0, backend на db=1)

    Returns:
        Redis URL для backend
    """
    # 1. Пряма змінна
    backend_url = os.environ.get("CELERY_RESULT_BACKEND")
    if backend_url:
        return backend_url

    # 2. Використовуємо broker URL з іншою DB
    broker_url = get_broker_url()
    if "/0" in broker_url:
        return broker_url.replace("/0", "/1")

    return broker_url


def is_broker_url_default() -> bool:
    """Перевіряє чи використовується fallback broker URL.

    Returns:
        True якщо не встановлено CELERY_BROKER_URL/REDIS_URL
    """
    return not (os.environ.get("CELERY_BROKER_URL") or os.environ.get("REDIS_URL"))


def warn_if_using_default_broker():
    """Виводить warning якщо використовується fallback broker.

    Викликається тільки при явному запуску distributed crawling.
    """
    if is_broker_url_default():
        logger.warning(
            " CELERY_BROKER_URL not set! Using fallback redis://localhost:6379/0\n"
            "Set CELERY_BROKER_URL env variable for production."
        )


# =====================================
# Celery Configuration
# =====================================


def get_celery_app_config() -> dict:
    """Отримати конфігурацію для celery_app (DEPRECATED).

     DEPRECATED: Використовуйте get_celery_batch_config() для кращої продуктивності.

    Returns:
        Dict з налаштуваннями Celery
    """
    return {
        # Serialization
        "task_serializer": "json",
        "result_serializer": "json",
        "accept_content": ["json"],
        # Timezone
        "timezone": "UTC",
        "enable_utc": True,
        # Task settings
        "task_default_queue": "graph_crawler",
        "task_time_limit": DEFAULT_CELERY_TASK_TIME_LIMIT,
        "task_soft_time_limit": DEFAULT_CELERY_TASK_SOFT_TIME_LIMIT,
        # Result settings
        "result_expires": 3600,  # 1 година
        # Worker settings
        "worker_prefetch_multiplier": 1,
        "worker_concurrency": 4,
    }


def get_celery_batch_config() -> dict:
    """Отримати конфігурацію для celery_batch (RECOMMENDED).

    Оптимізовано для batch tasks:
    - Більший prefetch для batch processing
    - Довший time limit для великих batches

    Returns:
        Dict з налаштуваннями Celery
    """
    return {
        # Serialization
        "task_serializer": "json",
        "result_serializer": "json",
        "accept_content": ["json"],
        # Timezone
        "timezone": "UTC",
        "enable_utc": True,
        # Task settings - окрема черга для batch tasks
        "task_default_queue": "graph_crawler_batch",
        "task_time_limit": DEFAULT_CELERY_TASK_TIME_LIMIT * 2,  # 20 хвилин для batch
        "task_soft_time_limit": DEFAULT_CELERY_TASK_SOFT_TIME_LIMIT * 2,
        # Result settings
        "result_expires": 3600,  # 1 година
        # Worker settings - оптимізовано для batch
        "worker_prefetch_multiplier": 4,  # Більше tasks per worker
        "worker_concurrency": 2,  # Менше workers, більше concurrent requests per task
    }


# =====================================
# Health Checks
# =====================================


def check_broker_connection(
    broker_url: Optional[str] = None, timeout: int = 5
) -> Tuple[bool, str]:
    """Перевірити підключення до Redis broker.


    Args:
        broker_url: URL Redis (якщо None - використовує get_broker_url())
        timeout: Таймаут підключення в секундах

    Returns:
        Tuple[bool, str]: (success, message)

    Example:
        ok, msg = check_broker_connection()
        if not ok:
            print(f"Redis error: {msg}")
    """
    if broker_url is None:
        broker_url = get_broker_url()

    try:
        import redis

        r = redis.from_url(
            broker_url, socket_timeout=timeout, socket_connect_timeout=timeout
        )
        r.ping()
        return True, f"Connected to Redis: {_mask_password(broker_url)}"
    except ImportError:
        return False, "redis package not installed. Run: pip install redis"
    except redis.ConnectionError as e:
        return False, f"Cannot connect to Redis at {_mask_password(broker_url)}: {e}"
    except redis.TimeoutError:
        return False, f"Redis connection timeout at {_mask_password(broker_url)}"
    except Exception as e:
        return False, f"Redis error: {e}"


def _check_workers_internal(celery_app: Any, timeout: int = 5) -> Tuple[bool, int, str]:
    """Внутрішня функція перевірки воркерів (уникає circular import)."""
    try:
        inspect = celery_app.control.inspect(timeout=timeout)
        ping_result = inspect.ping()

        if not ping_result:
            return False, 0, "No workers responding to ping"

        worker_count = len(ping_result)
        worker_names = list(ping_result.keys())

        return (
            True,
            worker_count,
            f"Found {worker_count} workers: {', '.join(worker_names[:3])}...",
        )

    except Exception as e:
        return False, 0, f"Error checking workers: {e}"


def check_workers(celery_app: Any, timeout: int = 5) -> Tuple[bool, int, str]:
    """Перевірити наявність активних воркерів.

    Args:
        celery_app: Celery application instance
        timeout: Таймаут для ping воркерів

    Returns:
        Tuple[bool, int, str]: (has_workers, worker_count, message)
    """
    try:
        inspect = celery_app.control.inspect(timeout=timeout)

        # Пробуємо отримати ping від воркерів
        ping_result = inspect.ping()

        if not ping_result:
            return False, 0, "No workers responding to ping"

        worker_count = len(ping_result)
        worker_names = list(ping_result.keys())

        return (
            True,
            worker_count,
            f"Found {worker_count} workers: {', '.join(worker_names[:3])}...",
        )

    except Exception as e:
        return False, 0, f"Error checking workers: {e}"


def validate_distributed_setup(
    celery_app: Optional[Any] = None,
    check_workers: bool = True,
    broker_url: Optional[str] = None,
) -> Tuple[bool, List[str]]:
    """Повна валідація для distributed crawling.


    Перевіряє:
    1. Підключення до Redis broker
    2. Наявність активних воркерів (опціонально)

    Args:
        celery_app: Celery app для перевірки воркерів (якщо None - пропускає)
        check_workers: Чи перевіряти воркерів
        broker_url: URL Redis (якщо None - автоматично)

    Returns:
        Tuple[bool, List[str]]: (all_ok, list_of_errors)

    Example:
        from graph_crawler.infrastructure.messaging.celery_batch import celery_batch

        ok, errors = validate_distributed_setup(celery_app=celery_batch)
        if not ok:
            for err in errors:
                print(f" {err}")
            raise RuntimeError("Setup validation failed")
    """
    errors = []

    # 1. Перевірка Redis
    redis_ok, redis_msg = check_broker_connection(broker_url)
    if not redis_ok:
        errors.append(f"Redis broker: {redis_msg}")
    else:
        logger.info(f" {redis_msg}")

    # 2. Перевірка воркерів
    if check_workers and celery_app is not None:
        workers_ok, worker_count, workers_msg = _check_workers_internal(celery_app)

        if not workers_ok:
            errors.append(
                f"No workers found: {workers_msg}\n"
                f"Start workers with: celery -A graph_crawler.celery_batch worker -Q graph_crawler_batch"
            )
        else:
            logger.info(f" {workers_msg}")

    all_ok = len(errors) == 0
    return all_ok, errors


def _mask_password(url: str) -> str:
    """Маскує пароль в URL для безпечного логування.

    Args:
        url: Redis URL з можливим паролем

    Returns:
        URL з замаскованим паролем
    """
    if "://:" in url:
        # redis://:password@host:port/db -> redis://:***@host:port/db
        parts = url.split("@")
        if len(parts) == 2:
            return parts[0].rsplit(":", 1)[0] + ":***@" + parts[1]
    return url


# =====================================
# Exports
# =====================================

__all__ = [
    "get_broker_url",
    "get_backend_url",
    "get_celery_app_config",
    "get_celery_batch_config",
    "check_broker_connection",
    "check_workers",
    "validate_distributed_setup",
    "is_broker_url_default",
    "warn_if_using_default_broker",
]
