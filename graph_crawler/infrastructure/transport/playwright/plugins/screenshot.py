"""
Screenshot плагін для Playwright драйвера.

Робить скріншоти на різних етапах:
- Після навігації
- При виявленні помилок
- При виявленні CAPTCHA
"""

import hashlib
import logging
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse

from graph_crawler.infrastructure.transport.base_plugin import BaseDriverPlugin
from graph_crawler.infrastructure.transport.context import EventPriority
from graph_crawler.infrastructure.transport.playwright.context import BrowserContext
from graph_crawler.infrastructure.transport.playwright.stages import BrowserStage

logger = logging.getLogger(__name__)


class ScreenshotPlugin(BaseDriverPlugin):
    """
    Плагін для збереження скріншотів.

    Конфігурація:
        output_dir: Директорія для скріншотів (default: './screenshots')
        full_page: Скріншот всієї сторінки (default: True)
        on_navigation: Скріншот після навігації (default: False)
        on_content_ready: Скріншот коли контент готовий (default: True)
        on_captcha: Скріншот при виявленні CAPTCHA (default: True)
        on_error: Скріншот при помилці (default: True)

    Приклад:
        plugin = ScreenshotPlugin(ScreenshotPlugin.config(
            output_dir='./debug_screenshots',
            full_page=True,
            on_captcha=True
        ))
    """

    def __init__(
        self, config: Dict[str, Any] = None, priority: int = EventPriority.LOW
    ):
        """Ініціалізація з низьким пріоритетом."""
        super().__init__(config, priority)
        self._screenshots_taken = 0

        # Створюємо директорію
        output_dir = self.config.get("output_dir", "./screenshots")
        self._output_path = Path(output_dir)
        self._output_path.mkdir(parents=True, exist_ok=True)

    @property
    def name(self) -> str:
        return "screenshot"

    def get_hooks(self) -> List[str]:
        hooks = []

        if self.config.get("on_navigation", False):
            hooks.append(BrowserStage.NAVIGATION_COMPLETED)

        if self.config.get("on_content_ready", True):
            hooks.append(BrowserStage.CONTENT_READY)

        return hooks

    def get_events(self) -> List[str]:
        events = []

        if self.config.get("on_captcha", True):
            events.append("captcha_detected")

        if self.config.get("on_error", True):
            events.append("plugin_error")

        return events

    async def _take_screenshot(
        self, page, ctx: BrowserContext, suffix: str = ""
    ) -> str:
        """
        Робить скріншот.

        Args:
            page: Playwright page
            ctx: Browser контекст
            suffix: Суфікс для імені файлу

        Returns:
            Шлях до скріншоту
        """
        url_hash = hashlib.sha256(ctx.url.encode()).hexdigest()[:10]
        domain = urlparse(ctx.url).netloc.replace(":", "_")

        filename = f"{domain}_{url_hash}"
        if suffix:
            filename += f"_{suffix}"
        filename += ".png"

        screenshot_path = self._output_path / filename
        full_page = self.config.get("full_page", True)

        await page.screenshot(path=str(screenshot_path), full_page=full_page)

        self._screenshots_taken += 1
        logger.info(f"Screenshot saved: {screenshot_path}")

        return str(screenshot_path)

    async def on_navigation_completed(self, ctx: BrowserContext) -> BrowserContext:
        """Скріншот після навігації."""
        if not ctx.page:
            return ctx

        try:
            path = await self._take_screenshot(ctx.page, ctx, "navigation")
            ctx.data["screenshot_navigation"] = path
        except Exception as e:
            logger.error(f"Error taking navigation screenshot: {e}")
            ctx.errors.append(e)

        return ctx

    async def on_content_ready(self, ctx: BrowserContext) -> BrowserContext:
        """Скріншот коли контент готовий."""
        if not ctx.page:
            return ctx

        try:
            path = await self._take_screenshot(ctx.page, ctx, "content")
            ctx.data["screenshot_content"] = path
            ctx.screenshot_path = path
        except Exception as e:
            logger.error(f"Error taking content screenshot: {e}")
            ctx.errors.append(e)

        return ctx

    async def on_captcha_detected(self, ctx: BrowserContext, **event_data):
        """Скріншот при виявленні CAPTCHA."""
        if not ctx.page:
            return

        try:
            captcha_type = event_data.get("captcha_type", "unknown")
            path = await self._take_screenshot(ctx.page, ctx, f"captcha_{captcha_type}")
            ctx.data["screenshot_captcha"] = path
            logger.info(f"CAPTCHA screenshot saved: {path}")
        except Exception as e:
            logger.error(f"Error taking CAPTCHA screenshot: {e}")

    async def on_plugin_error(self, ctx: BrowserContext, **event_data):
        """Скріншот при помилці плагіна."""
        if not ctx.page:
            return

        try:
            plugin_name = event_data.get("plugin_name", "unknown")
            path = await self._take_screenshot(ctx.page, ctx, f"error_{plugin_name}")
            ctx.data["screenshot_error"] = path
            logger.info(f"Error screenshot saved: {path}")
        except Exception as e:
            logger.error(f"Error taking error screenshot: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Statistics including screenshots taken."""
        stats = super().get_stats()
        stats["screenshots_taken"] = self._screenshots_taken
        return stats
