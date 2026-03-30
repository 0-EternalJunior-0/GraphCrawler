"""
Async Retry плагін для Async HTTP драйвера.

Автоматично повторює запити при помилках або конкретних статус кодах.
Асинхронна версія RetryPlugin.
"""

import logging
from typing import List

from graph_crawler.infrastructure.transport.async_http.context import AsyncHTTPContext
from graph_crawler.infrastructure.transport.async_http.stages import AsyncHTTPStage
from graph_crawler.infrastructure.transport.base_plugin import BaseDriverPlugin

logger = logging.getLogger(__name__)


class _ConfigDescriptor:
    """
    Дескриптор для підтримки як статичного виклику AsyncRetryPlugin.config(...),
    так і instance property self.config для доступу до _config.
    """
    
    def __get__(self, obj, objtype=None):
        if obj is None:
            # Викликається на класі: AsyncRetryPlugin.config
            # Повертаємо статичний метод
            return objtype._create_config
        # Викликається на instance: self.config
        # Повертаємо _config з батьківського класу
        return obj._config


class AsyncRetryPlugin(BaseDriverPlugin):
    """
    Async плагін для автоматичного retry HTTP запитів.

    Конфігурація:
        max_retries: Максимальна кількість спроб (default: 3)
        retry_delay: Затримка між спробами в секундах (default: 1.0)
        retry_status_codes: Список статус кодів для retry (default: [429, 500, 502, 503, 504])
        backoff_factor: Мультиплікатор для експоненційної затримки (default: 2.0)

    Приклад:
        plugin = AsyncRetryPlugin(AsyncRetryPlugin.config(
            max_retries=5,
            retry_delay=2.0,
            backoff_factor=1.5
        ))
    """
    
    @staticmethod
    def _create_config(
        max_retries: int = 3,
        retry_delay: float = 1.0,
        retry_status_codes: List[int] = None,
        backoff_factor: float = 2.0,
    ) -> dict:
        """
        Створює конфігурацію для AsyncRetryPlugin.
        
        Args:
            max_retries: Максимальна кількість спроб
            retry_delay: Базова затримка між спробами в секундах
            retry_status_codes: Список статус кодів для retry
            backoff_factor: Мультиплікатор для експоненційної затримки
            
        Returns:
            Dict з конфігурацією
        """
        if retry_status_codes is None:
            retry_status_codes = [429, 500, 502, 503, 504]
        return {
            "max_retries": max_retries,
            "retry_delay": retry_delay,
            "retry_status_codes": retry_status_codes,
            "backoff_factor": backoff_factor,
        }
    
    # Дескриптор: клас.config(...) -> _create_config, instance.config -> _config
    config = _ConfigDescriptor()

    @property
    def name(self) -> str:
        return "async_retry"

    def get_hooks(self) -> List[str]:
        return [AsyncHTTPStage.REQUEST_FAILED, AsyncHTTPStage.RESPONSE_RECEIVED]

    async def on_request_failed(self, ctx: AsyncHTTPContext) -> AsyncHTTPContext:
        """
        Обробляє помилку запиту (async).

        Args:
            ctx: Async HTTP контекст

        Returns:
            Оновлений контекст
        """
        retry_count = ctx.data.get("retry_count", 0)
        max_retries = self.config.get("max_retries", 3)

        if retry_count < max_retries:
            # Обчислюємо затримку з експоненційним backoff
            base_delay = self.config.get("retry_delay", 1.0)
            backoff_factor = self.config.get("backoff_factor", 2.0)
            delay = base_delay * (backoff_factor**retry_count)

            logger.info(
                f"Retrying request to {ctx.url} (attempt {retry_count + 1}/{max_retries}) after {delay}s"
            )

            ctx.data["retry_count"] = retry_count + 1
            ctx.data["should_retry"] = True
            ctx.data["retry_delay"] = delay
        else:
            logger.warning("Max retries reached for %s", ctx.url)
            ctx.data["should_retry"] = False

        return ctx

    async def on_response_received(self, ctx: AsyncHTTPContext) -> AsyncHTTPContext:
        """
        Перевіряє статус код для retry (async).

        Args:
            ctx: Async HTTP контекст

        Returns:
            Оновлений контекст
        """
        retry_status_codes = self.config.get("retry_status_codes", [429, 500, 502, 503, 504])

        if ctx.status_code in retry_status_codes:
            retry_count = ctx.data.get("retry_count", 0)
            max_retries = self.config.get("max_retries", 3)

            if retry_count < max_retries:
                base_delay = self.config.get("retry_delay", 1.0)
                backoff_factor = self.config.get("backoff_factor", 2.0)
                delay = base_delay * (backoff_factor**retry_count)

                logger.info(
                    f"Status {ctx.status_code} for {ctx.url}, retrying "
                    f"(attempt {retry_count + 1}/{max_retries}) after {delay}s"
                )

                ctx.data["retry_count"] = retry_count + 1
                ctx.data["should_retry"] = True
                ctx.data["retry_delay"] = delay

        return ctx
