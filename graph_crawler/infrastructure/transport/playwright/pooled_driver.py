"""
Pooled Playwright Driver - динамічний пул браузерів з вкладками.

Features:
- Всі методи async (fetch, fetch_many, close)
- Async context manager (__aenter__, __aexit__)

Проста логіка як в PlaywrightDriver, але з контролем ресурсів:
1. Отримали N URLs
2. Розрахували скільки браузерів/вкладок потрібно (не більше лімітів)
3. Відкрили браузери з вкладками → виконали fetch паралельно → закрили ВСЕ
4. Звільнили ресурси

Приклад:
    async with PooledPlaywrightDriver(
        config={'headless': True},
        browsers=3,          # макс 3 браузери
        tabs_per_browser=5   # макс 5 вкладок на браузер
    ) as driver:
        # 10 URLs → 2 браузери (5+5 вкладок)
        # 7 URLs → 2 браузери (5+2 вкладок)
        # 3 URLs → 1 браузер (3 вкладки)
        responses = await driver.fetch_many(urls)

    # Після кожного fetch_many всі браузери закриваються!
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from graph_crawler.domain.value_objects.models import FetchResponse
from graph_crawler.infrastructure.transport.base import BaseDriver
from graph_crawler.infrastructure.transport.base_plugin import BaseDriverPlugin
from graph_crawler.infrastructure.transport.playwright.context import BrowserContext
from graph_crawler.infrastructure.transport.playwright.stages import BrowserStage
from graph_crawler.infrastructure.transport.plugin_manager import DriverPluginManager
from graph_crawler.shared.constants import (
    DEFAULT_BROWSER_TYPE,
    DEFAULT_BROWSER_VIEWPORT_HEIGHT,
    DEFAULT_BROWSER_VIEWPORT_WIDTH,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_USER_AGENT,
    PLAYWRIGHT_STEALTH_ARGS,
    SUPPORTED_BROWSERS,
)

logger = logging.getLogger(__name__)


class PooledPlaywrightDriver(BaseDriver):
    """
    Playwright драйвер з динамічним пулом браузерів та вкладок.

    Проста архітектура:
    - Відкриває браузери по потребі (не більше ліміту)
    - Кожен браузер має N вкладок (не більше ліміту)
    - Після fetch_many закриває ВСЕ (як PlaywrightDriver)

    Приклад для 10 URLs з browsers=3, tabs_per_browser=5:
        Browser 1: Tab1, Tab2, Tab3, Tab4, Tab5 (5 URLs)
        Browser 2: Tab1, Tab2, Tab3, Tab4, Tab5 (5 URLs)
        → Всього 2 браузери, 10 вкладок

    Args:
        config: Конфігурація (headless, timeout, wait_until, etc.)
        browsers: Максимум браузерів (default: 3)
        tabs_per_browser: Максимум вкладок на браузер (default: 5)
        plugins: Список плагінів
    """

    def __init__(
        self,
        config: Dict[str, Any] = None,
        browsers: int = 3,
        tabs_per_browser: int = 5,
        plugins: Optional[List[BaseDriverPlugin]] = None,
        event_bus: Optional[Any] = None,
    ):
        super().__init__(config or {}, event_bus)

        self.max_browsers = browsers
        self.max_tabs_per_browser = tabs_per_browser
        self.total_slots = self.max_browsers * self.max_tabs_per_browser

        self.playwright = None

        # Plugin Manager
        self.plugin_manager = DriverPluginManager(is_async=True)
        if plugins:
            for plugin in plugins:
                self.plugin_manager.register(plugin)

        browser_type = self.config.get("browser", DEFAULT_BROWSER_TYPE).lower()
        if browser_type not in SUPPORTED_BROWSERS:
            browser_type = DEFAULT_BROWSER_TYPE
        self.browser_type = browser_type

        self.headless = self.config.get("headless", True)

        timeout_seconds = self.config.get("timeout", DEFAULT_REQUEST_TIMEOUT)
        self.timeout = (
            timeout_seconds * 1000 if timeout_seconds < 1000 else timeout_seconds
        )

        self.user_agent = self.config.get("user_agent", DEFAULT_USER_AGENT)
        self.viewport = self.config.get(
            "viewport",
            {
                "width": DEFAULT_BROWSER_VIEWPORT_WIDTH,
                "height": DEFAULT_BROWSER_VIEWPORT_HEIGHT,
            },
        )

        self.wait_until = self.config.get("wait_until", "domcontentloaded")
        self.wait_selector = self.config.get("wait_selector")
        wait_timeout_seconds = self.config.get("wait_timeout", 10)
        self.wait_timeout = (
            wait_timeout_seconds * 1000
            if wait_timeout_seconds < 1000
            else wait_timeout_seconds
        )

        self.scroll_page = self.config.get("scroll_page", False)
        self.scroll_step = self.config.get("scroll_step", 500)
        self.scroll_pause = self.config.get("scroll_pause", 0.3)

        self.javascript_enabled = self.config.get("javascript_enabled", True)
        self.block_resources = self.config.get("block_resources", [])

        logger.info(
            f"PooledPlaywrightDriver initialized: "
            f"max {self.max_browsers} browsers × {self.max_tabs_per_browser} tabs, "
            f"browser={self.browser_type}, headless={self.headless}"
        )

    def _calculate_distribution(self, num_urls: int) -> List[int]:
        """
        Розраховує розподіл URLs по браузерах.
        """
        if num_urls == 0:
            return []

        distribution = []
        remaining = num_urls

        while remaining > 0 and len(distribution) < self.max_browsers:
            tabs_in_browser = min(remaining, self.max_tabs_per_browser)
            distribution.append(tabs_in_browser)
            remaining -= tabs_in_browser

        return distribution

    async def _fetch_with_page(
        self, url: str, page: Any, browser_id: int, tab_id: int
    ) -> FetchResponse:
        start_time = time.time()

        ctx = BrowserContext(
            url=url,
            page=page,
            wait_selector=self.wait_selector,
            scroll_page=self.scroll_page,
            timeout=self.timeout,
        )

        try:
            ctx = await self.plugin_manager.execute_hook_async(
                BrowserStage.NAVIGATION_STARTING, ctx
            )

            try:
                response = await page.goto(
                    url, wait_until=self.wait_until, timeout=self.timeout
                )
            except Exception as nav_error:
                if "Timeout" in str(nav_error) and self.wait_until == "networkidle":
                    response = await page.goto(
                        url, wait_until="domcontentloaded", timeout=self.timeout
                    )
                else:
                    raise

            ctx.response = response
            ctx.status_code = response.status if response else None

            ctx = await self.plugin_manager.execute_hook_async(
                BrowserStage.NAVIGATION_COMPLETED, ctx
            )

            if self.wait_selector:
                try:
                    await page.wait_for_selector(
                        self.wait_selector, timeout=self.wait_timeout
                    )
                except Exception:
                    pass

            if self.scroll_page:
                await self._scroll_page(page)

            html = await page.content()
            ctx.html = html

            ctx = await self.plugin_manager.execute_hook_async(
                BrowserStage.CONTENT_READY, ctx
            )

            headers = {}
            if response:
                headers = dict(await response.all_headers())

            duration = time.time() - start_time
            logger.debug(
                f"Fetched {url} in {duration:.2f}s (browser {browser_id}, tab {tab_id})"
            )

            return FetchResponse(
                url=url,
                html=ctx.html,
                status_code=ctx.status_code,
                headers=headers,
                error=ctx.error,
            )

        except Exception as e:
            error_msg = f"Error fetching {url}: {type(e).__name__}: {e}"
            logger.error(error_msg)
            return FetchResponse(
                url=url, html=None, status_code=None, headers={}, error=error_msg
            )

    async def _scroll_page(self, page):
        last_height = 0
        for _ in range(50):
            current_height = await page.evaluate("document.body.scrollHeight")
            if current_height == last_height:
                break
            scroll_pos = min(last_height + self.scroll_step, current_height)
            await page.evaluate(f"window.scrollTo(0, {scroll_pos})")
            last_height = scroll_pos
            await asyncio.sleep(self.scroll_pause)
        await page.evaluate("window.scrollTo(0, 0)")

    async def _fetch_many_async(self, urls: List[str]) -> List[FetchResponse]:
        if not urls:
            return []

        distribution = self._calculate_distribution(len(urls))

        logger.info(
            f"Fetching {len(urls)} URLs: "
            f"{len(distribution)} browser(s) with {distribution} tabs"
        )

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise ImportError(
                "Playwright не встановлено. Виконайте: pip install playwright && playwright install"
            )

        self.playwright = await async_playwright().start()
        browser_launcher = getattr(self.playwright, self.browser_type)

        browsers = []
        contexts = []
        pages = []
        tasks = []
        url_index = 0

        try:
            for browser_id, num_tabs in enumerate(distribution):
                browser = await browser_launcher.launch(
                    headless=self.headless,
                    args=list(PLAYWRIGHT_STEALTH_ARGS),
                )
                browsers.append(browser)

                context = await browser.new_context(
                    user_agent=self.user_agent,
                    viewport=self.viewport,
                    java_script_enabled=self.javascript_enabled,
                )
                contexts.append(context)

                ctx = BrowserContext(url="", context=context)
                await self.plugin_manager.execute_hook_async(
                    BrowserStage.CONTEXT_CREATED, ctx
                )

                for tab_id in range(num_tabs):
                    page = await context.new_page()
                    page.set_default_timeout(self.timeout)
                    pages.append(page)

                    ctx = BrowserContext(
                        url="", browser=browser, context=context, page=page
                    )
                    await self.plugin_manager.execute_hook_async(
                        BrowserStage.PAGE_CREATED, ctx
                    )

                    if self.block_resources:

                        async def route_handler(route):
                            if route.request.resource_type in self.block_resources:
                                await route.abort()
                            else:
                                await route.continue_()

                        await page.route("**/*", route_handler)

                    url = urls[url_index]
                    task = self._fetch_with_page(url, page, browser_id, tab_id)
                    tasks.append((url_index, task))
                    url_index += 1

                logger.debug(f"Browser {browser_id} launched with {num_tabs} tabs")

            logger.info(f"Starting parallel fetch on {len(tasks)} tabs...")

            task_results = await asyncio.gather(
                *[task for _, task in tasks], return_exceptions=True
            )

            responses = [None] * len(urls)
            for i, result in enumerate(task_results):
                original_index = tasks[i][0]
                if isinstance(result, Exception):
                    responses[original_index] = FetchResponse(
                        url=urls[original_index],
                        html=None,
                        status_code=None,
                        headers={},
                        error=f"Exception: {type(result).__name__}: {result}",
                    )
                else:
                    responses[original_index] = result

            success_count = sum(1 for r in responses if r and r.status_code == 200)
            logger.info(f"Fetch completed: {success_count}/{len(urls)} successful")

            return responses

        finally:
            logger.debug("Closing all browsers...")

            for page in pages:
                try:
                    await page.close()
                except Exception:
                    pass

            for context in contexts:
                try:
                    await context.close()
                except Exception:
                    pass

            for browser in browsers:
                try:
                    await browser.close()
                except Exception:
                    pass

            if self.playwright:
                try:
                    await self.playwright.stop()
                except Exception:
                    pass
                self.playwright = None

            logger.debug("All browsers closed")

    async def fetch(self, url: str) -> FetchResponse:
        """Async завантаження однієї сторінки."""
        results = await self._fetch_many_async([url])
        return (
            results[0]
            if results
            else FetchResponse(
                url=url, html=None, status_code=None, headers={}, error="No result"
            )
        )

    async def fetch_many(self, urls: List[str]) -> List[FetchResponse]:
        """Async паралельне завантаження багатьох сторінок."""
        return await self._fetch_many_async(urls)

    def supports_batch_fetching(self) -> bool:
        return True

    def get_pool_stats(self) -> Dict[str, Any]:
        return {
            "max_browsers": self.max_browsers,
            "max_tabs_per_browser": self.max_tabs_per_browser,
            "total_slots": self.total_slots,
        }

    async def close(self) -> None:
        """Async закриває ресурси та плагіни."""
        await self.plugin_manager.teardown_all_async()
        logger.debug("PooledPlaywrightDriver closed")
