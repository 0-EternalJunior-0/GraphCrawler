"""Драйвер на основі Playwright з повною підтримкою плагінів.

Features:
- Всі методи async (fetch, fetch_many, close)
- Async context manager (__aenter__, __aexit__)

Архітектура:
- Інтеграція з DriverPluginManager
- Виклик async хуків на всіх етапах lifecycle
- Доступ до browser, context, page через BrowserContext
- Плагіни можуть створювати та публікувати події

Етапи (BrowserStage):
- BROWSER_LAUNCHING / BROWSER_LAUNCHED
- CONTEXT_CREATING / CONTEXT_CREATED
- PAGE_CREATING / PAGE_CREATED
- NAVIGATION_STARTING / NAVIGATION_COMPLETED
- WAITING_FOR_SELECTOR / SCROLLING / CONTENT_READY
- BEFORE_SCREENSHOT / AFTER_SCREENSHOT
- PAGE_CLOSING / CONTEXT_CLOSING
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
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
    DEFAULT_BROWSER_WAIT_TIMEOUT,
    DEFAULT_BROWSER_WAIT_UNTIL,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_SCREENSHOT_DIRECTORY,
    DEFAULT_USER_AGENT,
    PLAYWRIGHT_STEALTH_ARGS,
    SUPPORTED_BROWSERS,
)

logger = logging.getLogger(__name__)


@dataclass
class PlaywrightDriverConfig:
    """
    Конфігурація для PlaywrightDriver.

    Використовуйте PlaywrightDriver.config() для створення:

    Examples:
        >>> config = PlaywrightDriver.config(
        ...     headless=False,
        ...     scroll_page=True,
        ...     timeout=60
        ... )
        >>> driver = PlaywrightDriver(config.to_dict())
    """

    # Browser settings
    browser: str = DEFAULT_BROWSER_TYPE
    headless: bool = True

    # Timeout settings (в секундах)
    timeout: int = DEFAULT_REQUEST_TIMEOUT

    # Wait strategy: 'load', 'domcontentloaded', 'networkidle', 'commit'
    wait_until: str = "domcontentloaded"
    wait_selector: Optional[str] = None
    wait_timeout: int = 10

    # Scroll settings для lazy-loaded контенту
    scroll_page: bool = False
    scroll_step: int = 500
    scroll_pause: float = 0.3
    scroll_timeout: int = 30

    # Viewport
    viewport_width: int = DEFAULT_BROWSER_VIEWPORT_WIDTH
    viewport_height: int = DEFAULT_BROWSER_VIEWPORT_HEIGHT

    # Stealth mode - через плагіни!
    stealth_mode: bool = False  # Змінено на False, використовуйте StealthPlugin
    user_agent: str = DEFAULT_USER_AGENT

    # Screenshots
    screenshot: bool = False
    screenshot_path: str = DEFAULT_SCREENSHOT_DIRECTORY
    screenshot_full_page: bool = True

    # Resource blocking
    block_resources: list = field(default_factory=list)

    # JavaScript
    javascript_enabled: bool = True

    # Retry settings
    max_retries: int = 2
    retry_delay: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        """Конвертує конфіг в словник."""
        return {
            "browser": self.browser,
            "headless": self.headless,
            "timeout": self.timeout,
            "wait_until": self.wait_until,
            "wait_selector": self.wait_selector,
            "wait_timeout": self.wait_timeout,
            "scroll_page": self.scroll_page,
            "scroll_step": self.scroll_step,
            "scroll_pause": self.scroll_pause,
            "scroll_timeout": self.scroll_timeout,
            "viewport": {"width": self.viewport_width, "height": self.viewport_height},
            "stealth_mode": self.stealth_mode,
            "user_agent": self.user_agent,
            "screenshot": self.screenshot,
            "screenshot_path": self.screenshot_path,
            "screenshot_full_page": self.screenshot_full_page,
            "block_resources": self.block_resources,
            "javascript_enabled": self.javascript_enabled,
            "max_retries": self.max_retries,
            "retry_delay": self.retry_delay,
        }


class PlaywrightDriver(BaseDriver):
    """
    Драйвер на основі Playwright з повною підтримкою плагінів.

    Підтримує:
    - Driver-specific плагіни через PluginManager
    - Browser lifecycle hooks (browser_launching, context_created, navigation_completed, etc.)
    - Доступ до browser, context, page через BrowserContext
    - Комунікація між плагінами через події

    Приклад:
        >>> from graph_crawler.infrastructure.transport.playwright.plugins_new import (
        ...     StealthPlugin, CaptchaDetectorPlugin, CaptchaSolverPlugin
        ... )
        >>> driver = PlaywrightDriver(`
        ...     config={'browser': 'chromium', 'headless': True},
        ...     plugins=[
        ...         StealthPlugin(StealthPlugin.config(stealth_mode='high')),
        ...         CaptchaDetectorPlugin(),
        ...         CaptchaSolverPlugin(CaptchaSolverPlugin.config(
        ...             service='2captcha', api_key='YOUR_KEY'
        ...         ))
        ...     ]
        ... )
        >>> response = driver.fetch('https://protected-site.com')
    """

    @staticmethod
    def config(**kwargs) -> PlaywrightDriverConfig:
        """
        Створює конфігурацію для PlaywrightDriver.

        Args:
            browser: Тип браузера ('chromium', 'firefox', 'webkit')
            headless: Чи приховувати вікно браузера (True/False)
            timeout: Таймаут завантаження в секундах
            wait_until: Стратегія очікування ('load', 'domcontentloaded', 'networkidle')
            wait_selector: CSS селектор для очікування елемента
            scroll_page: Чи скролити сторінку для lazy-loaded контенту
            screenshot: Чи робити скріншоти
            block_resources: Типи ресурсів для блокування ['image', 'font']
            max_retries: Кількість повторних спроб при помилці

        Returns:
            PlaywrightDriverConfig: Конфігурація драйвера
        """
        return PlaywrightDriverConfig(**kwargs)

    def __init__(
        self,
        config: dict[str, Any] = None,
        event_bus: Optional[Any] = None,
        plugins: Optional[List[BaseDriverPlugin]] = None,
    ):
        """
        Ініціалізація Playwright драйвера з плагінами.

        Args:
            config: Конфігурація драйвера (dict або PlaywrightDriverConfig.to_dict())
            event_bus: EventBus для публікації подій (опціонально)
            plugins: Список плагінів для реєстрації
        """
        super().__init__(config, event_bus)
        self.browser = None
        self.playwright = None

        # Створюємо Plugin Manager (async)
        self.plugin_manager = DriverPluginManager(is_async=True)

        # Реєструємо плагіни
        if plugins:
            for plugin in plugins:
                self.plugin_manager.register(plugin)

        # Validate browser
        browser_type = self.config.get("browser", DEFAULT_BROWSER_TYPE).lower()
        if browser_type not in SUPPORTED_BROWSERS:
            logger.warning(
                f"Unsupported browser '{browser_type}', falling back to '{DEFAULT_BROWSER_TYPE}'. "
                f"Supported: {SUPPORTED_BROWSERS}"
            )
            browser_type = DEFAULT_BROWSER_TYPE
        self.browser_type = browser_type

        # Configuration
        self.headless = self.config.get("headless", True)

        # Timeout: приймаємо в секундах, конвертуємо в мілісекунди для Playwright
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

        # Wait strategy
        self.wait_until = self.config.get("wait_until", "domcontentloaded")
        self.wait_selector = self.config.get("wait_selector", None)
        wait_timeout_seconds = self.config.get("wait_timeout", 10)
        self.wait_timeout = (
            wait_timeout_seconds * 1000
            if wait_timeout_seconds < 1000
            else wait_timeout_seconds
        )

        # Scroll settings
        self.scroll_page = self.config.get("scroll_page", False)
        self.scroll_step = self.config.get("scroll_step", 500)
        self.scroll_pause = self.config.get("scroll_pause", 0.3)
        self.scroll_timeout = self.config.get("scroll_timeout", 30)

        # Screenshot settings
        self.screenshot_enabled = self.config.get("screenshot", False)
        self.screenshot_path = Path(
            self.config.get("screenshot_path", DEFAULT_SCREENSHOT_DIRECTORY)
        )
        self.screenshot_full_page = self.config.get("screenshot_full_page", True)

        # Resource blocking
        self.block_resources = self.config.get("block_resources", [])
        self.javascript_enabled = self.config.get("javascript_enabled", True)

        # Retry settings
        self.max_retries = self.config.get("max_retries", 2)
        self.retry_delay = self.config.get("retry_delay", 1.0)

        # Create screenshot directory if needed
        if self.screenshot_enabled:
            self.screenshot_path.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"PlaywrightDriver initialized: browser={self.browser_type}, "
            f"headless={self.headless}, "
            f"wait_until={self.wait_until}, scroll={self.scroll_page}, "
            f"screenshot={self.screenshot_enabled}, "
            f"{len(self.plugin_manager.plugins)} plugin(s)"
        )

    async def _init_playwright(self, ctx: BrowserContext) -> BrowserContext:
        """
        Асинхронна ініціалізація Playwright та браузера з хуками.

        Args:
            ctx: Browser контекст

        Returns:
            Оновлений контекст
        """
        if self.playwright is None:
            try:
                from playwright.async_api import async_playwright
            except ImportError:
                raise ImportError(
                    "Playwright не встановлено. Виконайте: pip install playwright && playwright install"
                )

            # === ЕТАП: BROWSER_LAUNCHING ===
            ctx = await self.plugin_manager.execute_hook_async(
                BrowserStage.BROWSER_LAUNCHING, ctx
            )

            if ctx.cancelled:
                return ctx

            self.playwright = await async_playwright().start()

            # Launch browser
            browser_launcher = getattr(self.playwright, self.browser_type)
            launch_args = list(PLAYWRIGHT_STEALTH_ARGS)  # Базові аргументи

            self.browser = await browser_launcher.launch(
                headless=self.headless, args=launch_args
            )
            ctx.browser = self.browser

            # === ЕТАП: BROWSER_LAUNCHED ===
            ctx = await self.plugin_manager.execute_hook_async(
                BrowserStage.BROWSER_LAUNCHED, ctx
            )

            logger.info(
                f"Playwright browser '{self.browser_type}' launched successfully"
            )
        else:
            ctx.browser = self.browser

        return ctx

    async def _create_context(self, ctx: BrowserContext):
        """
        Створює browser context з хуками.

        Args:
            ctx: Browser контекст

        Returns:
            Playwright BrowserContext
        """
        # === ЕТАП: CONTEXT_CREATING ===
        ctx = await self.plugin_manager.execute_hook_async(
            BrowserStage.CONTEXT_CREATING, ctx
        )

        if ctx.cancelled:
            return ctx, None

        context_options = {
            "user_agent": self.user_agent,
            "viewport": self.viewport,
            "java_script_enabled": self.javascript_enabled,
        }

        pw_context = await self.browser.new_context(**context_options)
        ctx.context = pw_context

        # === ЕТАП: CONTEXT_CREATED ===
        # Тут плагіни (StealthPlugin) можуть інжектити scripts!
        ctx = await self.plugin_manager.execute_hook_async(
            BrowserStage.CONTEXT_CREATED, ctx
        )

        return ctx, pw_context

    async def _scroll_page(self, page, ctx: BrowserContext) -> BrowserContext:
        """
        Прокручує сторінку для завантаження lazy-loaded контенту.

        Args:
            page: Playwright page object
            ctx: Browser контекст

        Returns:
            Оновлений контекст
        """
        # === ЕТАП: SCROLLING ===
        ctx = await self.plugin_manager.execute_hook_async(BrowserStage.SCROLLING, ctx)

        if ctx.cancelled:
            return ctx

        logger.debug(
            f"Starting page scroll (step={self.scroll_step}, pause={self.scroll_pause})"
        )

        start_time = time.time()
        last_height = 0
        scroll_count = 0

        while True:
            if time.time() - start_time > self.scroll_timeout:
                logger.debug(f"Scroll timeout reached after {self.scroll_timeout}s")
                break

            current_height = await page.evaluate("document.body.scrollHeight")

            if current_height == last_height:
                await asyncio.sleep(self.scroll_pause * 2)
                new_height = await page.evaluate("document.body.scrollHeight")
                if new_height == current_height:
                    logger.debug(
                        f"Scroll complete: reached bottom after {scroll_count} scrolls"
                    )
                    break
                current_height = new_height

            scroll_position = min(last_height + self.scroll_step, current_height)
            await page.evaluate(f"window.scrollTo(0, {scroll_position})")

            last_height = scroll_position
            scroll_count += 1

            await asyncio.sleep(self.scroll_pause)

            if scroll_count > 200:
                logger.warning("Max scroll iterations reached (200), stopping")
                break

        await page.evaluate("window.scrollTo(0, 0)")
        logger.debug(f"Page scrolled: {scroll_count} scrolls, height={last_height}px")

        ctx.data["scroll_count"] = scroll_count
        ctx.data["scroll_height"] = last_height

        return ctx

    async def _fetch_async(self, url: str) -> FetchResponse:
        """
        Асинхронне завантаження сторінки через Playwright з повною підтримкою плагінів.

        Args:
            url: URL сторінки для завантаження

        Returns:
            FetchResponse об'єкт з даними
        """
        start_time = time.time()

        # Створюємо контекст
        ctx = BrowserContext(
            url=url,
            wait_selector=self.wait_selector,
            scroll_page=self.scroll_page,
            timeout=self.timeout,
        )

        # Налаштовуємо підписки на події плагінів
        self.plugin_manager.setup_event_subscriptions(ctx)

        # Подія: FETCH_STARTED
        self._publish_fetch_started(
            url, "playwright", extra_data={"browser": self.browser_type}
        )

        # Initialize Playwright if needed
        ctx = await self._init_playwright(ctx)

        if ctx.cancelled:
            return self._create_cancelled_response(ctx)

        pw_context = None
        page = None
        last_error = None

        # Retry loop
        for attempt in range(self.max_retries + 1):
            try:
                # Create context
                ctx, pw_context = await self._create_context(ctx)

                if ctx.cancelled:
                    return self._create_cancelled_response(ctx)

                # Block resources if configured
                if self.block_resources:

                    async def route_handler(route):
                        if route.request.resource_type in self.block_resources:
                            await route.abort()
                        else:
                            await route.continue_()

                    await pw_context.route("**/*", route_handler)

                # === ЕТАП: PAGE_CREATING ===
                ctx = await self.plugin_manager.execute_hook_async(
                    BrowserStage.PAGE_CREATING, ctx
                )

                if ctx.cancelled:
                    return self._create_cancelled_response(ctx)

                # Create new page
                page = await pw_context.new_page()
                page.set_default_timeout(self.timeout)
                ctx.page = page

                # === ЕТАП: PAGE_CREATED ===
                ctx = await self.plugin_manager.execute_hook_async(
                    BrowserStage.PAGE_CREATED, ctx
                )

                # === ЕТАП: NAVIGATION_STARTING ===
                ctx = await self.plugin_manager.execute_hook_async(
                    BrowserStage.NAVIGATION_STARTING, ctx
                )

                if ctx.cancelled:
                    return self._create_cancelled_response(ctx)

                # Navigate to URL
                try:
                    response = await page.goto(
                        url, wait_until=self.wait_until, timeout=self.timeout
                    )
                except Exception as nav_error:
                    if "Timeout" in str(nav_error) and self.wait_until == "networkidle":
                        logger.warning(
                            f"networkidle timeout for {url}, retrying with domcontentloaded"
                        )
                        response = await page.goto(
                            url, wait_until="domcontentloaded", timeout=self.timeout
                        )
                    else:
                        raise

                ctx.response = response
                ctx.status_code = response.status if response else None

                # === ЕТАП: NAVIGATION_COMPLETED ===
                ctx = await self.plugin_manager.execute_hook_async(
                    BrowserStage.NAVIGATION_COMPLETED, ctx
                )

                # Wait for selector if specified
                if self.wait_selector:
                    # === ЕТАП: WAITING_FOR_SELECTOR ===
                    ctx = await self.plugin_manager.execute_hook_async(
                        BrowserStage.WAITING_FOR_SELECTOR, ctx
                    )

                    try:
                        await page.wait_for_selector(
                            self.wait_selector, timeout=self.wait_timeout
                        )
                    except Exception as e:
                        logger.debug(
                            f"Wait selector '{self.wait_selector}' timeout for {url}: {e}"
                        )

                # Scroll page for lazy-loaded content
                if self.scroll_page:
                    try:
                        ctx = await self._scroll_page(page, ctx)
                    except Exception as e:
                        logger.warning(f"Scroll failed for {url}: {e}")

                # Get rendered HTML
                html = await page.content()
                ctx.html = html

                # === ЕТАП: CONTENT_READY ===
                # Тут плагіни (CaptchaDetector) детектять проблеми!
                ctx = await self.plugin_manager.execute_hook_async(
                    BrowserStage.CONTENT_READY, ctx
                )

                # Capture screenshot if enabled
                screenshot_path = None
                if self.screenshot_enabled:
                    # === ЕТАП: BEFORE_SCREENSHOT ===
                    ctx = await self.plugin_manager.execute_hook_async(
                        BrowserStage.BEFORE_SCREENSHOT, ctx
                    )

                    import hashlib
                    from urllib.parse import urlparse

                    url_hash = hashlib.sha256(url.encode()).hexdigest()[:10]
                    domain = urlparse(url).netloc.replace(":", "_")
                    screenshot_filename = f"{domain}_{url_hash}.png"
                    screenshot_path = self.screenshot_path / screenshot_filename
                    ctx.screenshot_path = str(screenshot_path)

                    await page.screenshot(
                        path=str(screenshot_path), full_page=self.screenshot_full_page
                    )
                    logger.info(f"Screenshot saved: {screenshot_path}")

                    # === ЕТАП: AFTER_SCREENSHOT ===
                    ctx = await self.plugin_manager.execute_hook_async(
                        BrowserStage.AFTER_SCREENSHOT, ctx
                    )

                # Get headers
                headers = {}
                if response:
                    response_headers = await response.all_headers()
                    headers = dict(response_headers)
                ctx.response_headers = headers

                duration = time.time() - start_time

                # Подія: FETCH_SUCCESS
                self._publish_fetch_success(
                    url,
                    ctx.status_code,
                    duration,
                    "playwright",
                    extra_data={
                        "browser": self.browser_type,
                        "scrolled": self.scroll_page,
                    },
                )

                return FetchResponse(
                    url=url,
                    html=ctx.html,
                    status_code=ctx.status_code,
                    headers=headers,
                    error=ctx.error,
                )

            except Exception as e:
                last_error = e
                error_type = type(e).__name__

                if attempt < self.max_retries:
                    logger.warning(
                        f"Attempt {attempt + 1}/{self.max_retries + 1} failed for {url}: "
                        f"{error_type}: {str(e)[:100]}"
                    )
                    await asyncio.sleep(self.retry_delay)
                else:
                    logger.error(f"All attempts failed for {url}: {error_type}: {e}")

            finally:
                # === ЕТАП: PAGE_CLOSING ===
                if page:
                    try:
                        ctx = await self.plugin_manager.execute_hook_async(
                            BrowserStage.PAGE_CLOSING, ctx
                        )
                        await page.close()
                    except Exception:
                        pass
                    page = None
                    ctx.page = None

                # === ЕТАП: CONTEXT_CLOSING ===
                if pw_context:
                    try:
                        ctx = await self.plugin_manager.execute_hook_async(
                            BrowserStage.CONTEXT_CLOSING, ctx
                        )
                        await pw_context.close()
                    except Exception:
                        pass
                    pw_context = None
                    ctx.context = None

        # Всі спроби невдалі
        return self._handle_fetch_error(
            url,
            last_error,
            start_time,
            "playwright",
            extra_data={"browser": self.browser_type, "attempts": self.max_retries + 1},
        )

    def _create_cancelled_response(self, ctx: BrowserContext) -> FetchResponse:
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

    async def fetch(self, url: str) -> FetchResponse:
        """
        Async завантажує сторінку через Playwright.

        Args:
            url: URL сторінки для завантаження

        Returns:
            FetchResponse об'єкт з даними
        """
        return await self._fetch_async(url)

    async def fetch_many(self, urls: list[str]) -> list[FetchResponse]:
        """
        Async паралельне завантаження декількох сторінок.

        Args:
            urls: Список URL для завантаження

        Returns:
            Список FetchResponse об'єктів
        """
        tasks = [self._fetch_async(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        responses = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                error_msg = f"Exception during fetch: {type(result).__name__}: {result}"
                responses.append(
                    FetchResponse(
                        url=urls[i],
                        html=None,
                        status_code=None,
                        headers={},
                        error=error_msg,
                    )
                )
            else:
                responses.append(result)

        return responses

    def supports_batch_fetching(self) -> bool:
        """
        PlaywrightDriver підтримує ефективний batch fetching.

        Returns:
            True (паралельна обробка через async/await)
        """
        return True

    async def close(self) -> None:
        """Async закриває браузер, плагіни та звільняє ресурси."""
        if self.browser:
            try:
                await self.browser.close()
            except Exception as e:
                logger.warning(f"Error closing browser: {e}")
            self.browser = None

        if self.playwright:
            try:
                await self.playwright.stop()
            except Exception as e:
                logger.warning(f"Error stopping playwright: {e}")
            self.playwright = None

        await self.plugin_manager.teardown_all_async()
        logger.info("PlaywrightDriver closed successfully")
