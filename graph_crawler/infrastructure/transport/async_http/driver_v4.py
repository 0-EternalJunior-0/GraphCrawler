"""AsyncDriver - Clean Configuration-based Architecture.

Всі параметри беруться з конфігу - НІЧОГО захардкодженого!

- Всі параметри конфігуровані через DriverConfig або dict
- Python 3.14 free-threading auto-detection
- Adaptive optimization (опціонально)
- Fast path methods для max performance
"""

import asyncio
import logging
import sys
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
from graph_crawler.shared.constants import (
    DEFAULT_BROWSER_HEADERS,
    DEFAULT_CONNECTOR_LIMIT,
    DEFAULT_CONNECTOR_LIMIT_PER_HOST,
    DEFAULT_DNS_CACHE_TTL,
    DEFAULT_KEEPALIVE_TIMEOUT,
    DEFAULT_MAX_CONCURRENT_REQUESTS,
    DEFAULT_MAX_RETRIES,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_RETRY_DELAY,
    DEFAULT_USER_AGENT,
    FREE_THREADING_CONCURRENT_MULTIPLIER,
    FREE_THREADING_CONNECTOR_LIMIT,
    FREE_THREADING_CONNECTOR_LIMIT_PER_HOST,
)

logger = logging.getLogger(__name__)


def is_free_threading_enabled() -> bool:
    """Detect Python 3.14+ free-threading mode (GIL disabled)."""
    if hasattr(sys, "_is_gil_enabled"):
        return not sys._is_gil_enabled()
    return False


class AsyncDriver(BaseAsyncDriver, PluginSupportMixin, RetryMixin):
    """
    Async HTTP драйвер на основі aiohttp.

    Example:
        >>> # Default config
        >>> async with AsyncDriver() as driver:
        ...     response = await driver.fetch('https://example.com')
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
            config: Конфігурація драйвера (всі параметри опціональні)
            event_bus: EventBus для подій
            plugins: Список плагінів
        """
        BaseAsyncDriver.__init__(self, config, event_bus)
        self._init_plugin_support(plugins, is_async=True)

        # Session management
        self._session: Optional[aiohttp.ClientSession] = None
        self._connector: Optional[aiohttp.TCPConnector] = None
        # Basic settings
        self._timeout = self.config.get("timeout", DEFAULT_REQUEST_TIMEOUT)
        self._user_agent = self.config.get("user_agent", DEFAULT_USER_AGENT)
        self._max_retries = self.config.get("max_retries", DEFAULT_MAX_RETRIES)
        self._retry_delay = self.config.get("retry_delay", DEFAULT_RETRY_DELAY)

        # Concurrency
        self._base_concurrent = self.config.get(
            "max_concurrent_requests", DEFAULT_MAX_CONCURRENT_REQUESTS
        )

        # TCP Connector settings
        self._connector_limit = self.config.get("connector_limit", DEFAULT_CONNECTOR_LIMIT)
        self._connector_limit_per_host = self.config.get(
            "connector_limit_per_host", DEFAULT_CONNECTOR_LIMIT_PER_HOST
        )
        self._dns_cache_ttl = self.config.get("dns_cache_ttl", DEFAULT_DNS_CACHE_TTL)
        self._keepalive_timeout = self.config.get("keepalive_timeout", DEFAULT_KEEPALIVE_TIMEOUT)

        # Python 3.14 free-threading optimization
        self._auto_optimize = self.config.get("auto_optimize_for_free_threading", True)
        self._ft_multiplier = self.config.get(
            "free_threading_concurrent_multiplier", FREE_THREADING_CONCURRENT_MULTIPLIER
        )
        self._free_threading = is_free_threading_enabled()

        if self._free_threading and self._auto_optimize:
            # Apply free-threading optimized values
            self.max_concurrent = self._base_concurrent * self._ft_multiplier
            self._connector_limit = self.config.get(
                "connector_limit", FREE_THREADING_CONNECTOR_LIMIT
            )
            self._connector_limit_per_host = self.config.get(
                "connector_limit_per_host", FREE_THREADING_CONNECTOR_LIMIT_PER_HOST
            )
            logger.info(
                f"🚀 Free-threading detected! Auto-optimized: "
                f"concurrent={self.max_concurrent}, "
                f"connector_limit={self._connector_limit}"
            )
        else:
            self.max_concurrent = self._base_concurrent

        logger.info(
            f"AsyncDriver: "
            f"concurrent={self.max_concurrent}, "
            f"connector={self._connector_limit}/{self._connector_limit_per_host}, "
            f"timeout={self._timeout}s, "
            f"free_threading={self._free_threading}"
        )

    async def _get_session(self) -> aiohttp.ClientSession:
        """
        Створює або повертає існуючу aiohttp session.

        Всі параметри з конфігу!

        """
        if not self._session or self._session.closed:
            # SSL/TLS Configuration
            ssl_verify = self.config.get("ssl_verify", True)
            ssl_context = None

            if ssl_verify:
                # Створюємо secure SSL context
                import ssl

                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = True
                ssl_context.verify_mode = ssl.CERT_REQUIRED

                # Custom CA bundle (опціонально)
                ssl_ca_bundle = self.config.get("ssl_ca_bundle")
                if ssl_ca_bundle:
                    ssl_context.load_verify_locations(ssl_ca_bundle)
            else:
                # Disabled verification (тільки для тестування!)
                logger.warning(" SSL verification DISABLED! Use only for testing.")
                ssl_context = False

            self._connector = aiohttp.TCPConnector(
                limit=self._connector_limit,
                limit_per_host=self._connector_limit_per_host,
                ttl_dns_cache=self._dns_cache_ttl,
                use_dns_cache=True,
                keepalive_timeout=self._keepalive_timeout,
                enable_cleanup_closed=True,
                force_close=False,
                ssl=ssl_context,  # SSL/TLS verification
            )

            timeout = aiohttp.ClientTimeout(
                total=self._timeout,
                connect=min(5, self._timeout),
                sock_read=self._timeout,
            )

            self._session = aiohttp.ClientSession(
                connector=self._connector,
                headers={
                    "User-Agent": self._user_agent,
                    **DEFAULT_BROWSER_HEADERS,
                },
                timeout=timeout,
                raise_for_status=False,
            )
        return self._session

    async def _do_fetch(self, url: str) -> FetchResponse:
        """Core fetch з retry support."""
        return await self._with_retry_async(
            self._fetch_with_plugins,
            url,
            max_retries=self._max_retries,
            retry_delay=self._retry_delay,
            retry_on=(aiohttp.ClientError, asyncio.TimeoutError),
        )

    async def _fetch_with_plugins(self, url: str) -> FetchResponse:
        """Fetch з підтримкою плагінів."""
        session = await self._get_session()

        ctx = AsyncHTTPContext(
            url=url,
            method="GET",
            headers={},
            cookies={},
            timeout=self._timeout,
            session=session,
        )

        if self._plugin_manager:
            self._plugin_manager.setup_event_subscriptions(ctx)

        try:
            ctx = await self._execute_plugin_stage(AsyncHTTPStage.PREPARING_REQUEST, ctx)
            if ctx.cancelled:
                return self._cancelled_response(ctx)

            ctx = await self._execute_plugin_stage(AsyncHTTPStage.SENDING_REQUEST, ctx)
            if ctx.cancelled:
                return self._cancelled_response(ctx)

            async with session.get(url, headers=ctx.headers or {}, params=ctx.params) as response:
                ctx.response = response
                ctx.status_code = response.status
                # Конвертуємо всі header values в string (проблема з Cython в Python 3.14)
                ctx.response_headers = {k: str(v) for k, v in response.headers.items()}

                ctx = await self._execute_plugin_stage(AsyncHTTPStage.RESPONSE_RECEIVED, ctx)

                try:
                    ctx.html = await response.text()
                except UnicodeDecodeError:
                    ctx.html = None

                ctx = await self._execute_plugin_stage(AsyncHTTPStage.PROCESSING_RESPONSE, ctx)

            ctx = await self._execute_plugin_stage(AsyncHTTPStage.REQUEST_COMPLETED, ctx)

            return FetchResponse(
                url=url,
                html=ctx.html,
                status_code=ctx.status_code,
                headers=ctx.response_headers or {},
                error=ctx.error,
            )

        except Exception as e:
            ctx.error = str(e)
            ctx = await self._execute_plugin_stage(AsyncHTTPStage.REQUEST_FAILED, ctx)
            if ctx.data.get("should_retry", False):
                raise
            raise

    async def _execute_plugin_stage(
        self, stage: AsyncHTTPStage, ctx: AsyncHTTPContext
    ) -> AsyncHTTPContext:
        """Execute plugin stage if plugin_manager exists."""
        if self._plugin_manager:
            return await self._plugin_manager.execute_hook_async(stage, ctx)
        return ctx

    def _cancelled_response(self, ctx: AsyncHTTPContext) -> FetchResponse:
        """Create response for cancelled request."""
        reason = ctx.data.get("cancellation_reason", "Unknown")
        return FetchResponse(
            url=ctx.url,
            html=None,
            status_code=None,
            headers={},
            error=f"Cancelled: {reason}",
        )

    async def fetch_many(self, urls: List[str]) -> List[FetchResponse]:
        """
        Паралельне завантаження з контролем concurrency.

        Concurrency контролюється через config['max_concurrent_requests'].
        """
        if not urls:
            return []

        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def fetch_limited(url: str) -> FetchResponse:
            async with semaphore:
                return await self.fetch(url)

        tasks = [fetch_limited(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        processed = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed.append(
                    self._create_error_response(urls[i], f"{type(result).__name__}: {result}")
                )
            else:
                processed.append(result)

        return processed

    async def fetch_fast(self, url: str) -> FetchResponse:
        """
        Ultra-fast fetch БЕЗ плагінів.

        Для максимальної швидкості коли не потрібні:
        - Rate limiting
        - Retry logic
        - Custom headers/cookies
        """
        session = await self._get_session()

        try:
            async with session.get(url) as response:
                try:
                    html = await response.text()
                except UnicodeDecodeError:
                    html = None

                # Конвертуємо всі header values в string (проблема з Cython в Python 3.14)
                return FetchResponse(
                    url=url,
                    html=html,
                    status_code=response.status,
                    headers={k: str(v) for k, v in response.headers.items()},
                )
        except Exception as e:
            return FetchResponse(
                url=url,
                html=None,
                status_code=None,
                headers={},
                error=f"{type(e).__name__}: {e}",
            )

    async def fetch_many_fast(self, urls: List[str]) -> List[FetchResponse]:
        """Ultra-fast batch fetch БЕЗ плагінів."""
        if not urls:
            return []

        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def fetch_limited(url: str) -> FetchResponse:
            async with semaphore:
                return await self.fetch_fast(url)

        tasks = [asyncio.create_task(fetch_limited(url)) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        processed = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed.append(
                    FetchResponse(
                        url=urls[i],
                        html=None,
                        status_code=None,
                        headers={},
                        error=f"{type(result).__name__}: {result}",
                    )
                )
            else:
                processed.append(result)

        return processed

    async def _do_close(self) -> None:
        """Close session and connector."""
        if self._session and not self._session.closed:
            await self._session.close()

        if self._connector and not self._connector.closed:
            await self._connector.close()

        await asyncio.sleep(0.1)

        self._session = None
        self._connector = None

        await self._teardown_plugins_async()
