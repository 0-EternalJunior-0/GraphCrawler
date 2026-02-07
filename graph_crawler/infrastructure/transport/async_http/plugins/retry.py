"""
Async Retry плагін для Async HTTP драйвера.

Автоматично повторює запити при помилках або конкретних статус кодах.
Асинхронна версія RetryPlugin.
"""

import logging
from typing import Any, Dict, List

from graph_crawler.infrastructure.transport.async_http.context import AsyncHTTPContext
from graph_crawler.infrastructure.transport.async_http.stages import AsyncHTTPStage
from graph_crawler.infrastructure.transport.base_plugin import BaseDriverPlugin
from graph_crawler.infrastructure.transport.context import EventPriority

logger = logging.getLogger(__name__)


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
            logger.warning(f"Max retries reached for {ctx.url}")
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
        retry_status_codes = self.config.get(
            "retry_status_codes", [429, 500, 502, 503, 504]
        )

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
