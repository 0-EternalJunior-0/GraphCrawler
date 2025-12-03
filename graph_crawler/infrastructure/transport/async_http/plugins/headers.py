"""
Async Headers плагін для Async HTTP драйвера.

Додає або модифікує HTTP headers перед запитом.
Асинхронна версія HeadersPlugin.
"""

import logging
from typing import Any, Dict, List

from graph_crawler.infrastructure.transport.async_http.context import AsyncHTTPContext
from graph_crawler.infrastructure.transport.async_http.stages import AsyncHTTPStage
from graph_crawler.infrastructure.transport.base_plugin import BaseDriverPlugin
from graph_crawler.infrastructure.transport.context import EventPriority

logger = logging.getLogger(__name__)


class AsyncHeadersPlugin(BaseDriverPlugin):
    """
    Async плагін для управління HTTP headers.

    Конфігурація:
        custom_headers: Словник headers для додавання
        overwrite: Чи перезаписувати існуючі headers (default: False)
        remove_headers: Список headers для видалення

    Приклад:
        plugin = AsyncHeadersPlugin(AsyncHeadersPlugin.config(
            custom_headers={
                'X-Custom-Header': 'value',
                'Accept-Language': 'en-US'
            },
            remove_headers=['Referer']
        ))
    """

    @property
    def name(self) -> str:
        return "async_headers"

    def get_hooks(self) -> List[str]:
        return [AsyncHTTPStage.PREPARING_REQUEST]

    async def on_preparing_request(self, ctx: AsyncHTTPContext) -> AsyncHTTPContext:
        """
        Модифікує headers перед запитом (async).

        Args:
            ctx: Async HTTP контекст

        Returns:
            Оновлений контекст
        """
        # Додаємо кастомні headers
        custom_headers = self.config.get("custom_headers", {})
        overwrite = self.config.get("overwrite", False)

        for key, value in custom_headers.items():
            if overwrite or key not in ctx.headers:
                ctx.headers[key] = value
                logger.debug(f"Added header: {key}={value}")

        # Видаляємо непотрібні headers
        remove_headers = self.config.get("remove_headers", [])
        for key in remove_headers:
            if key in ctx.headers:
                del ctx.headers[key]
                logger.debug(f"Removed header: {key}")

        return ctx
