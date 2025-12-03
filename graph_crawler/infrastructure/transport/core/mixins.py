"""Mixins для драйверів - переиспользуема логіка.

Mixins дозволяють комбінувати функціональність:
- PluginSupportMixin - підтримка плагінів
- RetryMixin - автоматичні retry
- MetricsMixin - збір метрик

v4.0: Винесено з базових класів для гнучкості
"""

import asyncio
import logging
import time
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, TypeVar

from graph_crawler.domain.value_objects.models import FetchResponse

logger = logging.getLogger(__name__)

T = TypeVar("T")


class PluginSupportMixin:
    """
    Mixin для підтримки плагінів в драйверах.

    Надає:
    - plugin_manager property
    - register_plugin() метод
    - Автоматичний виклик setup/teardown

    Example:
        >>> class MyDriver(BaseAsyncDriver, PluginSupportMixin):
        ...     def __init__(self, plugins=None):
        ...         super().__init__()
        ...         self._init_plugin_support(plugins, is_async=True)
    """

    _plugin_manager: Optional[Any] = None

    def _init_plugin_support(
        self, plugins: Optional[List[Any]] = None, is_async: bool = True
    ) -> None:
        """
        Ініціалізує підтримку плагінів.

        Args:
            plugins: Список плагінів для реєстрації
            is_async: True для async plugin manager
        """
        from graph_crawler.infrastructure.transport.plugin_manager import (
            DriverPluginManager,
        )

        self._plugin_manager = DriverPluginManager(is_async=is_async)

        if plugins:
            for plugin in plugins:
                self.register_plugin(plugin)

    @property
    def plugin_manager(self) -> Any:
        """Повертає plugin manager."""
        return self._plugin_manager

    def register_plugin(self, plugin: Any) -> None:
        """
        Реєструє плагін.

        Args:
            plugin: Плагін для реєстрації
        """
        if self._plugin_manager:
            self._plugin_manager.register(plugin)

    async def _teardown_plugins_async(self) -> None:
        """Async закриває всі плагіни."""
        if self._plugin_manager:
            await self._plugin_manager.teardown_all_async()

    def _teardown_plugins_sync(self) -> None:
        """Sync закриває всі плагіни."""
        if self._plugin_manager:
            self._plugin_manager.teardown_all_sync()


class RetryMixin:
    """
    Mixin для автоматичних retry в драйверах.

    Налаштування:
    - max_retries: кількість спроб (default: 3)
    - retry_delay: затримка між спробами (default: 1.0)
    - retry_on: типи exceptions для retry

    Example:
        >>> class MyDriver(BaseAsyncDriver, RetryMixin):
        ...     async def fetch(self, url):
        ...         return await self._with_retry_async(
        ...             self._do_fetch, url,
        ...             max_retries=3,
        ...             retry_delay=1.0
        ...         )
    """

    async def _with_retry_async(
        self,
        func: Callable,
        *args,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        retry_on: tuple = (Exception,),
        **kwargs,
    ) -> T:
        """
        Async виконує функцію з retry.

        Args:
            func: Async функція для виконання
            max_retries: Кількість спроб
            retry_delay: Затримка між спробами (секунди)
            retry_on: Tuple exceptions для retry

        Returns:
            Результат функції

        Raises:
            Останній exception якщо всі спроби невдалі
        """
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except retry_on as e:
                last_error = e
                if attempt < max_retries:
                    logger.warning(
                        f"Attempt {attempt + 1}/{max_retries + 1} failed: "
                        f"{type(e).__name__}: {str(e)[:100]}"
                    )
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error(f"All {max_retries + 1} attempts failed")

        raise last_error

    def _with_retry_sync(
        self,
        func: Callable,
        *args,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        retry_on: tuple = (Exception,),
        **kwargs,
    ) -> T:
        """
        Sync виконує функцію з retry.
        """
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                return func(*args, **kwargs)
            except retry_on as e:
                last_error = e
                if attempt < max_retries:
                    logger.warning(
                        f"Attempt {attempt + 1}/{max_retries + 1} failed: "
                        f"{type(e).__name__}: {str(e)[:100]}"
                    )
                    time.sleep(retry_delay)
                else:
                    logger.error(f"All {max_retries + 1} attempts failed")

        raise last_error


class MetricsMixin:
    """
    Mixin для збору метрик в драйверах.

    Збирає:
    - Кількість запитів
    - Час виконання
    - Успішні/невдалі запити
    - Статус коди

    Example:
        >>> class MyDriver(BaseAsyncDriver, MetricsMixin):
        ...     def __init__(self):
        ...         self._init_metrics()
        ...
        ...     async def fetch(self, url):
        ...         with self._track_request() as tracker:
        ...             response = await self._do_fetch(url)
        ...             tracker.set_status(response.status_code)
        ...             return response
    """

    _metrics: Optional[Dict[str, Any]] = None

    def _init_metrics(self) -> None:
        """Ініціалізує збір метрик."""
        self._metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_time": 0.0,
            "status_codes": {},
            "errors": {},
        }

    def _record_request(
        self,
        duration: float,
        status_code: Optional[int] = None,
        error: Optional[str] = None,
    ) -> None:
        """
        Записує метрики запиту.

        Args:
            duration: Час виконання (секунди)
            status_code: HTTP статус код
            error: Повідомлення про помилку
        """
        if self._metrics is None:
            return

        self._metrics["total_requests"] += 1
        self._metrics["total_time"] += duration

        if error:
            self._metrics["failed_requests"] += 1
            error_type = error.split(":")[0] if ":" in error else "Unknown"
            self._metrics["errors"][error_type] = (
                self._metrics["errors"].get(error_type, 0) + 1
            )
        else:
            self._metrics["successful_requests"] += 1

        if status_code:
            self._metrics["status_codes"][status_code] = (
                self._metrics["status_codes"].get(status_code, 0) + 1
            )

    def get_metrics(self) -> Dict[str, Any]:
        """
        Повертає зібрані метрики.

        Returns:
            Dict з метриками
        """
        if self._metrics is None:
            return {}

        metrics = self._metrics.copy()

        # Додаємо обчислювані поля
        total = metrics["total_requests"]
        if total > 0:
            metrics["avg_time"] = round(metrics["total_time"] / total, 3)
            metrics["success_rate"] = round(
                metrics["successful_requests"] / total * 100, 1
            )
        else:
            metrics["avg_time"] = 0.0
            metrics["success_rate"] = 0.0

        return metrics

    def reset_metrics(self) -> None:
        """Скидає метрики."""
        self._init_metrics()
