"""Асинхронний HTTP драйвер.

Async-first HTTP driver на базі aiohttp.
Всі методи async: fetch, fetch_many, close.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

import aiohttp

from graph_crawler.domain.events import EventBus
from graph_crawler.domain.value_objects.models import FetchResponse
from graph_crawler.infrastructure.transport.async_http.context import AsyncHTTPContext
from graph_crawler.infrastructure.transport.async_http.stages import AsyncHTTPStage
from graph_crawler.infrastructure.transport.base import BaseDriver
from graph_crawler.infrastructure.transport.base_plugin import BaseDriverPlugin
from graph_crawler.infrastructure.transport.plugin_manager import DriverPluginManager
from graph_crawler.shared.constants import (
    DEFAULT_MAX_CONCURRENT_REQUESTS,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_USER_AGENT,
)

logger = logging.getLogger(__name__)


class AsyncDriver(BaseDriver):
    """
    Async-First HTTP драйвер на основі aiohttp .

    Основна перевага: ПАРАЛЕЛЬНА обробка URL-ів через fetch_many().

    Підтримує:
    - Driver-specific плагіни через PluginManager
    - Async HTTP lifecycle hooks
    - Доступ до aiohttp.ClientSession через контекст

    Приклад:
        >>> async with AsyncDriver() as driver:
        ...     response = await driver.fetch('https://example.com')
        ...     # Паралельно:
        ...     results = await driver.fetch_many([url1, url2, url3])
    """

    def __init__(
        self,
        config: Dict[str, Any] = None,
        event_bus: Optional["EventBus"] = None,
        plugins: Optional[List[BaseDriverPlugin]] = None,
    ):
        """
        Ініціалізація AsyncDriver з плагінами.

        Args:
            config: Конфігурація драйвера
            event_bus: EventBus для публікації подій
            plugins: Список плагінів для реєстрації
        """
        super().__init__(config, event_bus)
        self.session: Optional[aiohttp.ClientSession] = None

        # Кількість одночасних запитів
        self.max_concurrent = self.config.get(
            "max_concurrent_requests", DEFAULT_MAX_CONCURRENT_REQUESTS
        )

        # Створюємо Plugin Manager (async)
        self.plugin_manager = DriverPluginManager(is_async=True)

        # Реєструємо плагіни
        if plugins:
            for plugin in plugins:
                self.plugin_manager.register(plugin)

        logger.info(
            f"AsyncDriver initialized with max_concurrent_requests={self.max_concurrent}, "
            f"{len(self.plugin_manager.plugins)} plugin(s)"
        )

    def supports_batch_fetching(self) -> bool:
        """AsyncDriver підтримує ефективний паралельний batch fetching."""
        return True

    async def _get_session(self) -> aiohttp.ClientSession:
        """Отримує або створює aiohttp session з оптимізованим resolver."""
        if not self.session or self.session.closed:
            timeout = aiohttp.ClientTimeout(
                total=self.config.get("timeout", DEFAULT_REQUEST_TIMEOUT)
            )
            
            # ОПТИМІЗАЦІЯ: aiodns для швидшого async DNS resolution
            try:
                resolver = aiohttp.AsyncResolver()
            except Exception as e:
                logger.debug(f"aiodns not available, using default resolver: {e}")
                resolver = None
            
            connector = aiohttp.TCPConnector(
                limit=1000,                # Загальний ліміт на всі з’єднання
                limit_per_host=100,        # Ліміт на один домен
                ttl_dns_cache=300,         # Кеш DNS 5 хв
                keepalive_timeout=60,      # Keep-alive
                enable_cleanup_closed=True,
                resolver=resolver          # Async DNS resolver
            )
            self.session = aiohttp.ClientSession(
                headers={"User-Agent": self.config.get("user_agent", DEFAULT_USER_AGENT)},
                timeout=timeout,
                connector=connector
            )
        return self.session

    async def fetch(self, url: str) -> FetchResponse:
        """
        Async завантаження однієї сторінки з підтримкою плагінів.

        Args:
            url: URL для завантаження

        Returns:
            FetchResponse об'єкт з даними
        """
        start_time = time.time()

        # Отримуємо session
        session = await self._get_session()

        # Створюємо контекст
        ctx = AsyncHTTPContext(
            url=url,
            method="GET",
            headers={},
            cookies={},
            timeout=self.config.get("timeout", DEFAULT_REQUEST_TIMEOUT),
            session=session,
        )

        # Налаштовуємо підписки на події плагінів
        self.plugin_manager.setup_event_subscriptions(ctx)

        # Подія: FETCH_STARTED
        self._publish_fetch_started(url, "async")

        try:
            # === ЕТАП 1: SESSION (перевірка/створення) ===
            if self.session and not self.session.closed:
                ctx = await self.plugin_manager.execute_hook_async(
                    AsyncHTTPStage.SESSION_REUSED, ctx
                )
            else:
                ctx = await self.plugin_manager.execute_hook_async(
                    AsyncHTTPStage.SESSION_CREATING, ctx
                )
                session = await self._get_session()
                ctx.session = session
                ctx = await self.plugin_manager.execute_hook_async(
                    AsyncHTTPStage.SESSION_CREATED, ctx
                )

            if ctx.cancelled:
                return self._create_cancelled_response(ctx)

            # === ЕТАП 2: PREPARING_REQUEST ===
            ctx = await self.plugin_manager.execute_hook_async(
                AsyncHTTPStage.PREPARING_REQUEST, ctx
            )

            if ctx.cancelled:
                return self._create_cancelled_response(ctx)

            # === ЕТАП 3: SENDING_REQUEST ===
            ctx = await self.plugin_manager.execute_hook_async(
                AsyncHTTPStage.SENDING_REQUEST, ctx
            )

            if ctx.cancelled:
                return self._create_cancelled_response(ctx)

            # Формуємо параметри запиту з контексту
            request_headers = {**ctx.headers} if ctx.headers else {}

            # Виконуємо запит
            async with ctx.session.get(
                url, headers=request_headers, params=ctx.params if ctx.params else None
            ) as response:
                # Заповнюємо контекст даними відповіді
                ctx.response = response
                ctx.status_code = response.status
                ctx.response_headers = dict(response.headers)

                # === REDIRECT INFO ===
                # Збираємо інформацію про редіректи з aiohttp response
                final_url = str(response.url) if str(response.url) != url else None
                redirect_chain = (
                    [str(r.url) for r in response.history] if response.history else []
                )

                # === ЕТАП 4: RESPONSE_RECEIVED ===
                ctx = await self.plugin_manager.execute_hook_async(
                    AsyncHTTPStage.RESPONSE_RECEIVED, ctx
                )

                # Читаємо контент
                try:
                    ctx.html = await response.text()
                except UnicodeDecodeError:
                    logger.debug(f"Binary content detected for {url}, skipping")
                    ctx.html = None

                # === ЕТАП 5: PROCESSING_RESPONSE ===
                ctx = await self.plugin_manager.execute_hook_async(
                    AsyncHTTPStage.PROCESSING_RESPONSE, ctx
                )

            duration = time.time() - start_time

            # Подія: FETCH_SUCCESS
            self._publish_fetch_success(url, ctx.status_code, duration, "async")

            # === ЕТАП 7: REQUEST_COMPLETED ===
            ctx = await self.plugin_manager.execute_hook_async(
                AsyncHTTPStage.REQUEST_COMPLETED, ctx
            )

            return FetchResponse(
                url=url,
                html=ctx.html,
                status_code=ctx.status_code,
                headers=ctx.response_headers,
                error=ctx.error,
                final_url=final_url,
                redirect_chain=redirect_chain,
            )

        except Exception as e:
            # === ЕТАП 6: REQUEST_FAILED ===
            ctx.error = str(e)
            ctx = await self.plugin_manager.execute_hook_async(
                AsyncHTTPStage.REQUEST_FAILED, ctx
            )

            # Перевіряємо чи потрібен retry
            if ctx.data.get("should_retry", False):
                retry_delay = ctx.data.get("retry_delay", 1.0)
                logger.info(f"Retrying after {retry_delay}s...")
                await asyncio.sleep(retry_delay)

                # Рекурсивний виклик для retry
                return await self.fetch(url)

            # Якщо retry не потрібен
            return self._handle_fetch_error(url, e, start_time, "async")

    def _create_cancelled_response(self, ctx: AsyncHTTPContext) -> FetchResponse:
        """Створює FetchResponse для скасованого запиту."""
        reason = ctx.data.get("cancellation_reason", "Unknown")
        logger.warning(f"Request to {ctx.url} was cancelled: {reason}")

        return FetchResponse(
            url=ctx.url,
            html=None,
            status_code=None,
            headers={},
            error=f"Cancelled: {reason}",
        )

    async def fetch_many(self, urls: List[str]) -> List[FetchResponse]:
        """
        Async ПАРАЛЕЛЬНЕ завантаження декількох сторінок.

        Використовує asyncio.Semaphore для контролю кількості одночасних запитів.

        Args:
            urls: Список URL для завантаження

        Returns:
            Список FetchResponse об'єктів (в тому ж порядку що й URLs)
        """
        if not urls:
            return []

        logger.info(
            f"Batch fetching {len(urls)} URLs with max_concurrent={self.max_concurrent}"
        )

        # Semaphore для контролю concurrent requests
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def fetch_with_semaphore(url: str) -> FetchResponse:
            """Wrapper для fetch з semaphore."""
            async with semaphore:
                return await self.fetch(url)

        # Створюємо задачі для всіх URLs
        tasks = [fetch_with_semaphore(url) for url in urls]

        # Виконуємо всі задачі паралельно
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Обробляємо exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Exception for {urls[i]}: {result}")
                processed_results.append(
                    FetchResponse(
                        url=urls[i],
                        html=None,
                        status_code=None,
                        headers={},
                        error=str(result),
                    )
                )
            else:
                processed_results.append(result)

        logger.info(f"Batch fetch completed: {len(processed_results)} results")
        return processed_results

    async def close(self) -> None:
        """Async закриває aiohttp session та плагіни."""
        if self.session and not self.session.closed:
            await self.session.close()
            # ВАЖЛИВО: aiohttp потребує час для закриття connector
            await asyncio.sleep(0.25)
        self.session = None

        await self.plugin_manager.teardown_all_async()
        logger.debug("AsyncDriver closed")
