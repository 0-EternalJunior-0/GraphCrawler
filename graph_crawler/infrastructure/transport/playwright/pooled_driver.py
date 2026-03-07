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
    DEFAULT_BLOCK_RESOURCES,
    DEFAULT_BROWSER_TYPE,
    DEFAULT_BROWSER_VIEWPORT_HEIGHT,
    DEFAULT_BROWSER_VIEWPORT_WIDTH,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_USER_AGENT,
    PLAYWRIGHT_MEMORY_ARGS,
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
        
        # Fetch timeout для Cloudflare challenge (за замовчуванням 90 секунд)
        self.fetch_timeout = self.config.get("fetch_timeout", 90)
        
        # Затримки після операцій (параметризовані замість hardcoded)
        self.post_selector_delay = self.config.get("post_selector_delay", 0.5)
        self.post_scroll_delay = self.config.get("post_scroll_delay", 0.3)

        # Resource blocking (за замовчуванням блокуємо для економії RAM)
        self.block_resources = self.config.get("block_resources", list(DEFAULT_BLOCK_RESOURCES))

        # Memory optimization
        self.memory_optimization = self.config.get("memory_optimization", True)

        logger.info(
            f"PooledPlaywrightDriver initialized: "
            f"max {self.max_browsers} browsers × {self.max_tabs_per_browser} tabs, "
            f"browser={self.browser_type}, headless={self.headless}, "
            f"memory_opt={self.memory_optimization}, block={self.block_resources}"
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
            # Використовуємо конфігурований fetch_timeout замість жорстко закодованих 45 секунд
            return await asyncio.wait_for(
                self._fetch_with_page_internal(url, page, ctx, browser_id, tab_id, start_time),
                timeout=float(self.fetch_timeout)
            )
        except asyncio.TimeoutError:
            # Спробувати отримати частковий HTML що вже завантажився
            partial_html = None
            try:
                partial_html = await page.content()
            except Exception:
                pass
            
            error_msg = f"Fetch timeout ({self.fetch_timeout}s) for {url}"
            logger.warning(f"{error_msg} (partial_html: {bool(partial_html)})")
            return FetchResponse(
                url=url, 
                html=partial_html,  # Partial content замість None
                status_code=None, 
                headers={}, 
                error=error_msg,
                is_partial=bool(partial_html)  # Позначаємо як partial
            )
        except Exception as e:
            error_msg = f"Error fetching {url}: {type(e).__name__}: {e}"
            logger.error(error_msg)
            return FetchResponse(
                url=url, html=None, status_code=None, headers={}, error=error_msg
            )

    async def _fetch_with_page_internal(
            self, url: str, page: Any, ctx: BrowserContext,
            browser_id: int, tab_id: int, start_time: float
    ) -> FetchResponse:
        try:
            # Хук перед навігацією
            ctx = await self.plugin_manager.execute_hook_async(
                BrowserStage.NAVIGATION_STARTING, ctx
            )

            # Навігація на сторінку
            try:
                response = await page.goto(url, wait_until=self.wait_until, timeout=self.timeout)
            except Exception as nav_error:
                if "Timeout" in str(nav_error) and self.wait_until == "networkidle":
                    response = await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout)
                else:
                    raise

            ctx.response = response
            ctx.status_code = response.status if response else None

            ctx = await self.plugin_manager.execute_hook_async(
                BrowserStage.NAVIGATION_COMPLETED, ctx
            )

            # Перевіряємо чи не заблоковано Cloudflare
            if ctx.data.get("cloudflare_failed") or ctx.data.get("cloudflare_blocked"):
                error_msg = f"Cloudflare challenge failed for {url}"
                logger.warning(error_msg)
                return FetchResponse(
                    url=url, html=None, status_code=ctx.status_code,
                    headers={}, error=error_msg
                )

            # Очікування селектора
            if self.wait_selector:
                try:
                    await page.wait_for_selector(self.wait_selector, timeout=self.wait_timeout)
                except Exception:
                    pass
            
            # Параметризована затримка після селектора (замість hardcoded 2 сек)
            if self.post_selector_delay > 0:
                await asyncio.sleep(self.post_selector_delay)
            
            # Скрол сторінки (швидкий, виконується в браузері)
            if self.scroll_page:
                await self._scroll_page(page)
                # Параметризована затримка після скролу (замість hardcoded 1 сек)
                if self.post_scroll_delay > 0:
                    await asyncio.sleep(self.post_scroll_delay)
            # Отримуємо HTML після скролу
            html = await page.content()
            ctx.html = html

            # Хук після отримання контенту
            ctx = await self.plugin_manager.execute_hook_async(
                BrowserStage.CONTENT_READY, ctx
            )

            # Фінальна перевірка на Cloudflare
            if ctx.data.get("cloudflare_failed") or ctx.data.get("cloudflare_blocked"):
                error_msg = f"Cloudflare challenge failed after content ready for {url}"
                logger.warning(error_msg)
                return FetchResponse(
                    url=url, html=ctx.html, status_code=ctx.status_code,
                    headers={}, error=error_msg
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

        except asyncio.TimeoutError:
            # Спробувати отримати частковий HTML при navigation timeout
            partial_html = None
            partial_status = ctx.status_code if ctx else None
            try:
                partial_html = await page.content()
            except Exception:
                pass
            
            error_msg = f"Navigation timeout for {url}"
            logger.warning(f"{error_msg} (partial_html: {bool(partial_html)})")
            return FetchResponse(
                url=url, 
                html=partial_html,
                status_code=partial_status, 
                headers={}, 
                error=error_msg,
                is_partial=bool(partial_html)
            )

        except Exception as e:
            error_msg = f"Error in fetch_with_page_internal: {type(e).__name__}: {e}"
            logger.error(error_msg)
            return FetchResponse(
                url=url, html=None, status_code=None, headers={}, error=error_msg
            )


    async def _scroll_page(self, page):
        """
        Швидкий скрол сторінки для завантаження lazy content.
        Оптимізовано: менше ітерацій, менші паузи.
        """
        try:
            # Швидкий скрол до кінця і назад (замість поступового)
            await page.evaluate("""
                async () => {
                    const delay = ms => new Promise(r => setTimeout(r, ms));
                    const height = document.body.scrollHeight;
                    const step = Math.max(height / 5, 500);

                    // Скрол вниз
                    for (let y = 0; y < height; y += step) {
                        window.scrollTo(0, y);
                        await delay(100);
                    }
                    window.scrollTo(0, height);
                    await delay(200);

                    // Скрол назад
                    window.scrollTo(0, 0);
                }
            """)
        except Exception:
            # Fallback на простий скрол
            try:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(0.2)
                await page.evaluate("window.scrollTo(0, 0)")
            except Exception:
                pass

    async def _fetch_many_async(self, urls: List[str]) -> List[FetchResponse]:
        """
        Завантажує URLs батчами по total_slots (browsers × tabs).

        Якщо URLs > total_slots, обробляємо в кілька раундів:
        - Раунд 1: URLs[0:10]
        - Раунд 2: URLs[10:20]
        - і т.д.
        """
        if not urls:
            return []

        # Якщо URLs більше ніж слотів - обробляємо батчами
        if len(urls) > self.total_slots:
            logger.info(
                f"URLs ({len(urls)}) > slots ({self.total_slots}), "
                f"processing in batches of {self.total_slots}"
            )
            all_responses = []
            for i in range(0, len(urls), self.total_slots):
                batch = urls[i:i + self.total_slots]
                batch_num = i // self.total_slots + 1
                total_batches = (len(urls) + self.total_slots - 1) // self.total_slots
                logger.info(f"Processing batch {batch_num}/{total_batches}: {len(batch)} URLs")

                batch_responses = await self._fetch_batch(batch)
                all_responses.extend(batch_responses)

                # Невелика пауза між батчами для стабільності
                if i + self.total_slots < len(urls):
                    await asyncio.sleep(1.0)

            return all_responses
        else:
            return await self._fetch_batch(urls)

    async def _fetch_batch(self, urls: List[str]) -> List[FetchResponse]:
        """Обробляє один батч URLs (≤ total_slots)."""
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

        # Формуємо аргументи запуску
        # Можна перевизначити через config['args']
        if self.config.get("args"):
            launch_args = list(self.config.get("args"))
        else:
            launch_args = list(PLAYWRIGHT_STEALTH_ARGS)
            if self.memory_optimization:
                launch_args.extend(PLAYWRIGHT_MEMORY_ARGS)

        # Канал браузера (chrome, msedge, chrome-beta, etc.)
        browser_channel = self.config.get("channel")

        try:
            
            launch_kwargs = {
                "headless": self.headless,
                "args": launch_args,
            }
            if browser_channel:
                launch_kwargs["channel"] = browser_channel

            async def _launch_browser_with_tabs(browser_id: int, num_tabs: int):
                """Запускає один браузер з вкладками (виконується паралельно)."""
                browser = await browser_launcher.launch(**launch_kwargs)
                
                context = await browser.new_context(
                    user_agent=self.user_agent,
                    viewport=self.viewport,
                    java_script_enabled=self.javascript_enabled,
                )
                
                # Plugin hook для context
                ctx = BrowserContext(url="", context=context)
                await self.plugin_manager.execute_hook_async(
                    BrowserStage.CONTEXT_CREATED, ctx
                )
                
                # Паралельне створення вкладок в межах одного браузера
                browser_pages = await asyncio.gather(*[
                    context.new_page() for _ in range(num_tabs)
                ])
                
                # Паралельне налаштування всіх вкладок
                async def _setup_page(page):
                    """Налаштовує одну вкладку (виконується паралельно)."""
                    page.set_default_timeout(self.timeout)
                    
                    # Plugin hook для page
                    page_ctx = BrowserContext(
                        url="", browser=browser, context=context, page=page
                    )
                    await self.plugin_manager.execute_hook_async(
                        BrowserStage.PAGE_CREATED, page_ctx
                    )
                    
                    # Resource blocking з closure для block_resources
                    if self.block_resources:
                        block_types = self.block_resources  # Capture в closure
                        
                        async def route_handler(route, block_types=block_types):
                            if route.request.resource_type in block_types:
                                await route.abort()
                            else:
                                await route.continue_()
                        
                        await page.route("**/*", route_handler)
                    
                    return page
                
                # Налаштовуємо всі вкладки паралельно
                await asyncio.gather(*[_setup_page(page) for page in browser_pages])
                
                logger.debug(f"Browser {browser_id} launched with {num_tabs} tabs")
                return browser, context, browser_pages

            # Паралельний запуск всіх браузерів
            browser_results = await asyncio.gather(*[
                _launch_browser_with_tabs(browser_id, num_tabs)
                for browser_id, num_tabs in enumerate(distribution)
            ])
            
            # Розпаковуємо результати
            for browser, context, browser_pages in browser_results:
                browsers.append(browser)
                contexts.append(context)
                pages.extend(browser_pages)
            
            # Створюємо tasks для fetch
            for i, page in enumerate(pages):
                browser_id = 0
                accumulated = 0
                for bid, num_tabs in enumerate(distribution):
                    if i < accumulated + num_tabs:
                        browser_id = bid
                        break
                    accumulated += num_tabs
                
                url = urls[url_index]
                task = self._fetch_with_page(url, page, browser_id, i % self.max_tabs_per_browser)
                tasks.append((url_index, task))
                url_index += 1

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
            failed_count = sum(1 for r in responses if r and r.error)
            cloudflare_failed = sum(
                1 for r in responses
                if r and r.error and "Cloudflare" in r.error
            )
            timeout_count = sum(
                1 for r in responses
                if r and r.error and "timeout" in r.error.lower()
            )

            logger.info(
                f"Fetch completed: {success_count}/{len(urls)} successful, "
                f"{failed_count} failed (Cloudflare: {cloudflare_failed}, Timeout: {timeout_count})"
            )

            return responses

        finally:
            logger.debug("Closing all browsers...")

            # === ПАРАЛЕЛЬНЕ ЗАКРИТТЯ РЕСУРСІВ ===
            
            async def _safe_close(coro, name: str, timeout: float = 2.0):
                """Безпечно закриває ресурс з таймаутом."""
                try:
                    await asyncio.wait_for(coro, timeout=timeout)
                except asyncio.TimeoutError:
                    logger.warning(f"⚠️ {name} close timeout - forcing")
                except Exception as e:
                    logger.debug(f"{name} close error: {e}")

            # Закриваємо всі сторінки паралельно
            if pages:
                await asyncio.gather(*[
                    _safe_close(page.close(), f"Page {i}", 2.0)
                    for i, page in enumerate(pages)
                ])

            # Закриваємо всі контексти паралельно
            if contexts:
                await asyncio.gather(*[
                    _safe_close(context.close(), f"Context {i}", 2.0)
                    for i, context in enumerate(contexts)
                ])

            # Закриваємо всі браузери паралельно
            if browsers:
                await asyncio.gather(*[
                    _safe_close(browser.close(), f"Browser {i}", 3.0)
                    for i, browser in enumerate(browsers)
                ])

            # Зупиняємо Playwright з таймаутом
            if self.playwright:
                try:
                    await asyncio.wait_for(self.playwright.stop(), timeout=3.0)
                    logger.debug("Playwright stopped successfully")
                except asyncio.TimeoutError:
                    logger.error("🚨 Playwright.stop() TIMEOUT - forcing cleanup")
                    # Примусово очищуємо
                    self.playwright = None
                except Exception as e:
                    logger.error(f"Playwright stop error: {e}")
                finally:
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
        """Async закриває браузери, контексти, сторінки та плагіни."""

        # 1️⃣ Форсоване закриття плагінів з таймаутом
        try:
            await asyncio.wait_for(self.plugin_manager.teardown_all_async(), timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning("⚠️ Plugin teardown timeout - skipping")
        except Exception as e:
            logger.debug(f"Plugin teardown error: {e}")

        # 2️⃣ Паралельне закриття всіх браузерів
        if hasattr(self, 'browsers') and self.browsers:
            async def _close_browser(i: int, browser):
                """Закриває браузер з таймаутом та force kill."""
                try:
                    await asyncio.wait_for(browser.close(), timeout=3.0)
                except asyncio.TimeoutError:
                    logger.warning(f"⚠️ Browser {i} close timeout - forcing kill")
                    try:
                        browser.process().kill()
                    except Exception as e:
                        logger.error(f"Cannot kill browser {i}: {e}")
                except Exception as e:
                    logger.debug(f"Browser {i} close error: {e}")
            
            await asyncio.gather(*[
                _close_browser(i, browser)
                for i, browser in enumerate(self.browsers)
            ])

        # 3️⃣ Форсоване завершення Playwright
        if getattr(self, 'playwright', None):
            try:
                await asyncio.wait_for(self.playwright.stop(), timeout=3.0)
            except asyncio.TimeoutError:
                logger.warning("⚠️ Playwright.stop() timeout - forcing cleanup")
                self.playwright = None
            except Exception as e:
                logger.debug(f"Playwright stop error: {e}")
            finally:
                self.playwright = None

        logger.debug("PooledPlaywrightDriver closed (all resources released)")

