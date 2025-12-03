"""Оновлений AsyncDriver на новій архітектурі.

v4.0 Зміни:
- Наслідує BaseAsyncDriver (замість BaseDriver)
- Використовує PluginSupportMixin та RetryMixin
- Реалізує тільки _do_fetch() - специфічну логіку
- Загальна логіка (events, errors) в базовому класі
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

import aiohttp

from graph_crawler.domain.events.event_bus import EventBus
from graph_crawler.domain.value_objects.models import FetchResponse
from graph_crawler.infrastructure.transport.async_http.context import AsyncHTTPContext
from graph_crawler.infrastructure.transport.async_http.stages import AsyncHTTPStage
from graph_crawler.infrastructure.transport.base_plugin import BaseDriverPlugin
from graph_crawler.infrastructure.transport.core.base_async import BaseAsyncDriver
from graph_crawler.infrastructure.transport.core.mixins import (
    PluginSupportMixin,
    RetryMixin,
)
from graph_crawler.infrastructure.transport.plugin_manager import DriverPluginManager
from graph_crawler.shared.constants import (
    DEFAULT_MAX_CONCURRENT_REQUESTS,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_USER_AGENT,
)

logger = logging.getLogger(__name__)


class AsyncDriver(BaseAsyncDriver, PluginSupportMixin, RetryMixin):
    """
    Async HTTP драйвер на основі aiohttp (v4.0).

    Використовує нову архітектуру:
    - BaseAsyncDriver: Template Method для загальної логіки
    - PluginSupportMixin: підтримка плагінів
    - RetryMixin: автоматичні retry

    Основна перевага: ПАРАЛЕЛЬНА обробка URL-ів через fetch_many().

    Example:
        >>> async with AsyncDriver() as driver:
        ...     response = await driver.fetch('https://example.com')
        ...     # Паралельно:
        ...     results = await driver.fetch_many([url1, url2, url3])
    """

    driver_name = "aiohttp"

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        event_bus: Optional[EventBus] = None,
        plugins: Optional[List[BaseDriverPlugin]] = None,
    ):
        """
        Ініціалізація AsyncDriver.

        Args:
            config: Конфігурація (timeout, user_agent, max_concurrent_requests)
            event_bus: EventBus для подій
            plugins: Список плагінів
        """
        BaseAsyncDriver.__init__(self, config, event_bus)

        # Ініціалізуємо підтримку плагінів
        self._init_plugin_support(plugins, is_async=True)

        # aiohttp session
        self._session: Optional[aiohttp.ClientSession] = None

        # Конфігурація
        self.max_concurrent = self.config.get(
            "max_concurrent_requests", DEFAULT_MAX_CONCURRENT_REQUESTS
        )
        self._timeout = self.config.get("timeout", DEFAULT_REQUEST_TIMEOUT)
        self._user_agent = self.config.get("user_agent", DEFAULT_USER_AGENT)

        # Retry налаштування
        self._max_retries = self.config.get("max_retries", 2)
        self._retry_delay = self.config.get("retry_delay", 1.0)

        logger.info(
            f"AsyncDriver initialized: max_concurrent={self.max_concurrent}, "
            f"timeout={self._timeout}s, "
            f"{len(self._plugin_manager.plugins) if self._plugin_manager else 0} plugins"
        )

    # ==================== Session Management ====================

    async def _get_session(self) -> aiohttp.ClientSession:
        """Отримує або створює aiohttp session."""
        if not self._session or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self._timeout)
            self._session = aiohttp.ClientSession(
                headers={"User-Agent": self._user_agent}, timeout=timeout
            )
        return self._session

    # ==================== Template Method Implementation ====================

    async def _do_fetch(self, url: str) -> FetchResponse:
        """
        Специфічна логіка завантаження через aiohttp.

        Викликається з BaseAsyncDriver.fetch().

        Args:
            url: URL для завантаження

        Returns:
            FetchResponse
        """
        # Використовуємо RetryMixin для автоматичних retry
        return await self._with_retry_async(
            self._fetch_with_plugins,
            url,
            max_retries=self._max_retries,
            retry_delay=self._retry_delay,
            retry_on=(aiohttp.ClientError, asyncio.TimeoutError),
        )

    async def _fetch_with_plugins(self, url: str) -> FetchResponse:
        """
        Завантаження з підтримкою плагінів.
        """
        session = await self._get_session()

        # Створюємо контекст
        ctx = AsyncHTTPContext(
            url=url,
            method="GET",
            headers={},
            cookies={},
            timeout=self._timeout,
            session=session,
        )

        # Налаштовуємо підписки на події плагінів
        if self._plugin_manager:
            self._plugin_manager.setup_event_subscriptions(ctx)

        try:
            # Етапи плагінів
            ctx = await self._execute_plugin_stage(
                AsyncHTTPStage.PREPARING_REQUEST, ctx
            )
            if ctx.cancelled:
                return self._cancelled_response(ctx)

            ctx = await self._execute_plugin_stage(AsyncHTTPStage.SENDING_REQUEST, ctx)
            if ctx.cancelled:
                return self._cancelled_response(ctx)

            # HTTP запит
            async with session.get(
                url, headers=ctx.headers or {}, params=ctx.params
            ) as response:
                ctx.response = response
                ctx.status_code = response.status
                ctx.response_headers = dict(response.headers)

                # Етап: RESPONSE_RECEIVED
                ctx = await self._execute_plugin_stage(
                    AsyncHTTPStage.RESPONSE_RECEIVED, ctx
                )

                # Читаємо HTML
                try:
                    ctx.html = await response.text()
                except UnicodeDecodeError:
                    logger.debug(f"Binary content for {url}, skipping")
                    ctx.html = None

                # Етап: PROCESSING_RESPONSE
                ctx = await self._execute_plugin_stage(
                    AsyncHTTPStage.PROCESSING_RESPONSE, ctx
                )

            # Етап: REQUEST_COMPLETED
            ctx = await self._execute_plugin_stage(
                AsyncHTTPStage.REQUEST_COMPLETED, ctx
            )

            return FetchResponse(
                url=url,
                html=ctx.html,
                status_code=ctx.status_code,
                headers=ctx.response_headers or {},
                error=ctx.error,
            )

        except Exception as e:
            # Етап: REQUEST_FAILED
            ctx.error = str(e)
            ctx = await self._execute_plugin_stage(AsyncHTTPStage.REQUEST_FAILED, ctx)

            # Перевіряємо should_retry від плагіна
            if ctx.data.get("should_retry", False):
                raise  # Re-raise для RetryMixin

            raise

    async def _execute_plugin_stage(
        self, stage: AsyncHTTPStage, ctx: AsyncHTTPContext
    ) -> AsyncHTTPContext:
        """Виконує етап плагінів якщо є plugin_manager."""
        if self._plugin_manager:
            return await self._plugin_manager.execute_hook_async(stage, ctx)
        return ctx

    def _cancelled_response(self, ctx: AsyncHTTPContext) -> FetchResponse:
        """Створює response для скасованого запиту."""
        reason = ctx.data.get("cancellation_reason", "Unknown")
        return FetchResponse(
            url=ctx.url,
            html=None,
            status_code=None,
            headers={},
            error=f"Cancelled: {reason}",
        )

    # ==================== Batch Fetching (Override) ====================

    async def fetch_many(self, urls: List[str]) -> List[FetchResponse]:
        """
        Оптимізоване паралельне завантаження з semaphore.

        Args:
            urls: Список URL

        Returns:
            Список FetchResponse
        """
        if not urls:
            return []

        logger.info(
            f"Batch fetching {len(urls)} URLs "
            f"(max_concurrent={self.max_concurrent})"
        )

        # Semaphore для контролю concurrency
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def fetch_limited(url: str) -> FetchResponse:
            async with semaphore:
                return await self.fetch(url)

        tasks = [fetch_limited(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Обробляємо exceptions
        processed = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Exception for {urls[i]}: {result}")
                processed.append(
                    self._create_error_response(
                        urls[i], f"{type(result).__name__}: {result}"
                    )
                )
            else:
                processed.append(result)

        logger.info(f"Batch fetch completed: {len(processed)} results")
        return processed

    # ==================== Resource Management ====================

    async def _do_close(self) -> None:
        """Закриває aiohttp session та плагіни."""
        if self._session and not self._session.closed:
            await self._session.close()
            await asyncio.sleep(0.25)  # aiohttp needs time to close connector
        self._session = None

        await self._teardown_plugins_async()

        logger.debug("AsyncDriver closed")
