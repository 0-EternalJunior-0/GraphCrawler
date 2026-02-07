"""
Async Rate Limiter плагін для Async HTTP драйвера.

Обмежує кількість запитів в секунду для уникнення блокування.
"""

import asyncio
import logging
import time
from collections import deque
from typing import Any, Dict, List

from graph_crawler.infrastructure.transport.async_http.context import AsyncHTTPContext
from graph_crawler.infrastructure.transport.async_http.stages import AsyncHTTPStage
from graph_crawler.infrastructure.transport.base_plugin import BaseDriverPlugin
from graph_crawler.infrastructure.transport.context import EventPriority

logger = logging.getLogger(__name__)


class AsyncRateLimiterPlugin(BaseDriverPlugin):
    """
    Async плагін для rate limiting.

    Використовує sliding window алгоритм для обмеження запитів.

    Конфігурація:
        requests_per_second: Максимум запитів в секунду (default: 10)
        requests_per_minute: Максимум запитів в хвилину (default: None)
        burst_size: Дозволений burst (default: requests_per_second * 2)

    Приклад:
        plugin = AsyncRateLimiterPlugin(AsyncRateLimiterPlugin.config(
            requests_per_second=5,
            burst_size=10
        ))
    """

    def __init__(
        self, config: Dict[str, Any] = None, priority: int = EventPriority.HIGH
    ):
        super().__init__(config, priority)
        self._request_times: deque = deque()
        self._lock = asyncio.Lock()

    @property
    def name(self) -> str:
        return "async_rate_limiter"

    def get_hooks(self) -> List[str]:
        return [AsyncHTTPStage.PREPARING_REQUEST]

    async def on_preparing_request(self, ctx: AsyncHTTPContext) -> AsyncHTTPContext:
        """
        Застосовує rate limiting перед запитом.

        Args:
            ctx: Async HTTP контекст

        Returns:
            Оновлений контекст
        """
        requests_per_second = self.config.get("requests_per_second", 10)
        window_size = 1.0  # 1 секунда

        async with self._lock:
            now = time.time()

            # Видаляємо старі записи
            while self._request_times and (now - self._request_times[0]) > window_size:
                self._request_times.popleft()

            # Перевіряємо ліміт
            if len(self._request_times) >= requests_per_second:
                # Потрібно почекати
                oldest = self._request_times[0]
                wait_time = window_size - (now - oldest)

                if wait_time > 0:
                    logger.debug(f"Rate limit reached, waiting {wait_time:.2f}s")
                    await asyncio.sleep(wait_time)
                    now = time.time()

                    # Очищаємо знову після очікування
                    while (
                        self._request_times
                        and (now - self._request_times[0]) > window_size
                    ):
                        self._request_times.popleft()

            # Додаємо поточний запит
            self._request_times.append(now)

        return ctx

    def reset(self):
        """Скидає лічильник запитів."""
        self._request_times.clear()
