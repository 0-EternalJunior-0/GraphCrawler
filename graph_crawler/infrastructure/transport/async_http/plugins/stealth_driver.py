"""
Stealth HTTP драйвер з curl_cffi.

Використовує curl_cffi для емуляції браузерного TLS fingerprint.
Це покращена альтернатива aiohttp для обходу anti-bot систем.

Features:
- Браузерний TLS fingerprint (Chrome, Firefox, Safari)
- JA3/JA4 fingerprint spoofing
- HTTP/2 підтримка
- Автоматичне вирішення Cloudflare challenges
"""

import asyncio
import logging
import random
import time
from typing import Any, Dict, List, Optional

from graph_crawler.domain.events import EventBus
from graph_crawler.domain.value_objects.models import FetchResponse
from graph_crawler.infrastructure.transport.async_http.context import AsyncHTTPContext
from graph_crawler.infrastructure.transport.async_http.stages import AsyncHTTPStage
from graph_crawler.infrastructure.transport.base import BaseDriver
from graph_crawler.infrastructure.transport.base_plugin import BaseDriverPlugin
from graph_crawler.infrastructure.transport.plugin_manager import DriverPluginManager
from graph_crawler.shared.constants import (
    DEFAULT_REQUEST_TIMEOUT,
)

logger = logging.getLogger(__name__)

# Browser impersonation options (supported by curl_cffi)
BROWSER_IMPERSONATIONS = [
    "chrome136",
    "chrome133a",
    "chrome131",
    "chrome124",
    "chrome123",
    "chrome120",
    "chrome119",
    "edge101",
    "edge99",
    "safari184",
    "safari180",
    "safari18_0",
    "safari17_0",
    "firefox135",
    "firefox133",
]

# Realistic User-Agents
USER_AGENTS = {
    "chrome136": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "chrome133a": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    "chrome131": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "chrome124": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "chrome123": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "chrome120": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "chrome119": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "edge101": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.0.0 Safari/537.36 Edg/101.0.0.0",
    "edge99": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.0.0 Safari/537.36 Edg/99.0.0.0",
    "safari184": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 Safari/605.1.15",
    "safari180": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
    "safari18_0": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
    "safari17_0": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "firefox135": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0",
    "firefox133": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
}

# Realistic Accept-Language headers
ACCEPT_LANGUAGES = [
    "en-US,en;q=0.9",
    "en-US,en;q=0.9,uk;q=0.8",
    "en-GB,en;q=0.9,en-US;q=0.8",
    "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7",
]


class StealthHTTPDriver(BaseDriver):
    """
    Stealth HTTP драйвер з curl_cffi.

    Емулює справжній браузер на рівні TLS/HTTP fingerprint.
    Набагато ефективніший за aiohttp для обходу anti-bot систем.

    Конфігурація:
        browser_impersonate: Браузер для емуляції ('chrome131', 'safari18_0', etc.)
        randomize_browser: Випадковий вибір браузера (default: True)
        max_concurrent: Максимум паралельних запитів (default: 50)
        timeout: Таймаут запиту в секундах (default: 30)
        retry_on_challenge: Retry при Cloudflare challenge (default: True)
        max_retries: Максимум retries (default: 3)

    Приклад:
        >>> async with StealthHTTPDriver() as driver:
        ...     response = await driver.fetch('https://protected-site.com')
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        event_bus: Optional["EventBus"] = None,
        plugins: Optional[List[BaseDriverPlugin]] = None,
    ):
        super().__init__(config, event_bus)

        self.session = None
        self._curl_cffi_available = self._check_curl_cffi()

        # Configuration
        self.max_concurrent = self.config.get("max_concurrent", 50)
        self.randomize_browser = self.config.get("randomize_browser", True)
        self.browser_impersonate = self.config.get("browser_impersonate", "chrome131")
        self.retry_on_challenge = self.config.get("retry_on_challenge", True)
        self.max_retries = self.config.get("max_retries", 3)

        # Plugin Manager
        self.plugin_manager = DriverPluginManager(is_async=True)
        if plugins:
            for plugin in plugins:
                self.plugin_manager.register(plugin)

        logger.info(
            "StealthHTTPDriver initialized: curl_cffi=%s, browser=%s, randomize=%s, plugins=%s",
            "available" if self._curl_cffi_available else "unavailable",
            self.browser_impersonate,
            self.randomize_browser,
            len(self.plugin_manager.plugins)
        )

    def _check_curl_cffi(self) -> bool:
        """Перевіряє доступність curl_cffi."""
        try:
            from curl_cffi.requests import AsyncSession  # type: ignore[import-not-found]

            return True
        except ImportError:
            logger.warning(
                "curl_cffi not available. Install with: pip install curl_cffi. "
                "Falling back to aiohttp."
            )
            return False

    def _get_browser_impersonation(self) -> str:
        """Повертає браузер для емуляції."""
        if self.randomize_browser:
            return random.choice(BROWSER_IMPERSONATIONS)
        return self.browser_impersonate

    def _get_headers(self, browser: str) -> Dict[str, str]:
        """Генерує реалістичні headers для браузера."""
        return {
            "User-Agent": USER_AGENTS.get(browser, USER_AGENTS["chrome131"]),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": random.choice(ACCEPT_LANGUAGES),
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
            "sec-ch-ua": f'"Chromium";v="{browser[-3:]}", "Google Chrome";v="{browser[-3:]}", "Not=A?Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        }

    def _is_cloudflare_challenge(self, html: str, status_code: int) -> bool:
        """Перевіряє чи це Cloudflare challenge."""
        if status_code in [403, 429, 503]:
            cloudflare_indicators = [
                "cf-browser-verification",
                "cf_chl_opt",
                "__cf_chl",
                "Checking your browser",
                "Just a moment",
                "challenge-platform",
                "turnstile",
            ]
            for indicator in cloudflare_indicators:
                if indicator.lower() in html.lower():
                    return True
        return False

    async def _get_session(self):
        """Створює curl_cffi AsyncSession."""
        if not self._curl_cffi_available:
            # Fallback to aiohttp
            import aiohttp

            if not self.session or self.session.closed:
                timeout = aiohttp.ClientTimeout(
                    total=self.config.get("timeout", DEFAULT_REQUEST_TIMEOUT)
                )
                self.session = aiohttp.ClientSession(timeout=timeout)
            return self.session

        from curl_cffi.requests import AsyncSession  # type: ignore[import-not-found]

        if not self.session:
            self.session = AsyncSession()

        return self.session

    async def _fetch_with_curl_cffi(
        self, url: str, browser: str, headers: Dict[str, str]
    ) -> FetchResponse:
        """Виконує запит через curl_cffi."""
        from curl_cffi.requests import AsyncSession  # type: ignore[import-not-found]

        timeout = self.config.get("timeout", DEFAULT_REQUEST_TIMEOUT)

        async with AsyncSession() as session:
            response = await session.get(
                url,
                impersonate=browser,
                headers=headers,
                timeout=timeout,
                allow_redirects=True,
            )

            html = response.text
            status_code = response.status_code
            # Конвертуємо всі header values в string (проблема з Cython в Python 3.14)
            response_headers = {k: str(v) for k, v in response.headers.items()}

            # Redirect info
            final_url = str(response.url) if str(response.url) != url else None

            return FetchResponse(
                url=url,
                html=html,
                status_code=status_code,
                headers=response_headers,
                final_url=final_url,
            )

    async def _fetch_with_aiohttp(self, url: str, headers: Dict[str, str]) -> FetchResponse:
        """Fallback до aiohttp."""

        session = await self._get_session()

        async with session.get(url, headers=headers) as response:
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
                final_url=str(response.url) if str(response.url) != url else None,
            )

    async def fetch(self, url: str) -> FetchResponse:
        """
        Виконує stealth HTTP запит.

        Args:
            url: URL для завантаження

        Returns:
            FetchResponse
        """
        start_time = time.time()
        last_error = None

        # Вибираємо браузер
        browser = self._get_browser_impersonation()
        headers = self._get_headers(browser)

        ctx = AsyncHTTPContext(
            url=url,
            method="GET",
            headers=headers,
            timeout=self.config.get("timeout", DEFAULT_REQUEST_TIMEOUT),
        )

        self.plugin_manager.setup_event_subscriptions(ctx)
        self._publish_fetch_started(url, "stealth_http")

        for attempt in range(self.max_retries + 1):
            try:
                # Execute hooks
                ctx = await self.plugin_manager.execute_hook_async(
                    AsyncHTTPStage.PREPARING_REQUEST, ctx
                )

                if ctx.cancelled:
                    return self._create_cancelled_response(ctx)

                # Виконуємо запит
                if self._curl_cffi_available:
                    response = await self._fetch_with_curl_cffi(url, browser, headers)
                else:
                    response = await self._fetch_with_aiohttp(url, headers)

                # Перевіряємо на Cloudflare challenge
                if (
                    self.retry_on_challenge
                    and response.html
                    and self._is_cloudflare_challenge(response.html, response.status_code)
                    and attempt < self.max_retries
                ):
                    logger.warning(
                        "[STEALTH] Cloudflare challenge detected for %s (attempt %s/%s)",
                        url, attempt + 1, self.max_retries + 1
                    )

                    # Змінюємо браузер для retry
                    browser = self._get_browser_impersonation()
                    headers = self._get_headers(browser)

                    # Exponential backoff
                    await asyncio.sleep(2**attempt + random.uniform(0.5, 1.5))
                    continue

                duration = time.time() - start_time
                self._publish_fetch_success(url, response.status_code, duration, "stealth_http")

                return response

            except Exception as e:
                last_error = e
                logger.warning(
                    "Attempt %s/%s failed for %s: %s",
                    attempt + 1, self.max_retries + 1, url, e
                )

                if attempt < self.max_retries:
                    await asyncio.sleep(2**attempt + random.uniform(0.5, 1.5))
                    browser = self._get_browser_impersonation()
                    headers = self._get_headers(browser)

        return self._handle_fetch_error(url, last_error, start_time, "stealth_http")

    def _create_cancelled_response(self, ctx: AsyncHTTPContext) -> FetchResponse:
        """Створює response для скасованого запиту."""
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
        Паралельне завантаження декількох URL.

        Args:
            urls: Список URL

        Returns:
            Список FetchResponse
        """
        if not urls:
            return []

        logger.info("Batch fetching %s URLs with StealthHTTPDriver", len(urls))

        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def fetch_with_semaphore(url: str) -> FetchResponse:
            async with semaphore:
                return await self.fetch(url)

        tasks = [fetch_with_semaphore(url) for url in urls]
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
                        error=str(result),
                    )
                )
            else:
                processed.append(result)

        return processed

    def supports_batch_fetching(self) -> bool:
        return True

    async def close(self) -> None:
        """Закриває session."""
        if self.session:
            if hasattr(self.session, "close"):
                if asyncio.iscoroutinefunction(self.session.close):
                    await self.session.close()
                else:
                    self.session.close()
            self.session = None

        await self.plugin_manager.teardown_all_async()
        logger.debug("StealthHTTPDriver closed")
