"""
Human Behavior Emulation плагін для Playwright драйвера.

Емулює поведінку людини для обходу bot detection:
- Випадкові рухи миші
- Випадкові затримки
- Природній scroll
- Кліки по елементах
"""

import asyncio
import logging
import random
from typing import Any, Dict, List

from graph_crawler.infrastructure.transport.base_plugin import BaseDriverPlugin
from graph_crawler.infrastructure.transport.context import EventPriority
from graph_crawler.infrastructure.transport.playwright.context import BrowserContext
from graph_crawler.infrastructure.transport.playwright.stages import BrowserStage

logger = logging.getLogger(__name__)


class HumanBehaviorPlugin(BaseDriverPlugin):
    """
    Плагін для емуляції людської поведінки.

    Допомагає обходити bot detection через емуляцію людської взаємодії.

    Конфігурація:
        mouse_movements: Кількість випадкових рухів миші (default: 3)
        random_delay_range: Діапазон випадкової затримки [min, max] секунд (default: [0.5, 2.0])
        scroll_behavior: Тип скролу ('smooth', 'instant') (default: 'smooth')
        click_random_elements: Чи клікати по випадкових елементах (default: False)

    Приклад:
        plugin = HumanBehaviorPlugin(HumanBehaviorPlugin.config(
            mouse_movements=5,
            random_delay_range=[1, 3]
        ))
    """

    @property
    def name(self) -> str:
        return "human_behavior"

    def get_hooks(self) -> List[str]:
        return [
            BrowserStage.PAGE_CREATED,
            BrowserStage.NAVIGATION_COMPLETED,
            BrowserStage.CONTENT_READY,
        ]

    async def _random_mouse_movement(self, page):
        """Виконує випадковий рух миші."""
        viewport = page.viewport_size
        if not viewport:
            viewport = {"width": 1920, "height": 1080}

        # Генеруємо випадкові координати
        x = random.randint(100, viewport["width"] - 100)
        y = random.randint(100, viewport["height"] - 100)

        # Рухаємо мишу з випадковою швидкістю
        steps = random.randint(5, 15)
        await page.mouse.move(x, y, steps=steps)

        logger.debug(f"Mouse moved to ({x}, {y}) in {steps} steps")

    async def _random_delay(self):
        """Виконує випадкову затримку."""
        delay_range = self.config.get("random_delay_range", [0.5, 2.0])
        delay = random.uniform(delay_range[0], delay_range[1])
        await asyncio.sleep(delay)
        logger.debug(f"Random delay: {delay:.2f}s")

    async def _natural_scroll(self, page):
        """Виконує природній скрол."""
        scroll_behavior = self.config.get("scroll_behavior", "smooth")

        # Випадковий скрол вниз
        scroll_amount = random.randint(100, 500)

        if scroll_behavior == "smooth":
            await page.evaluate(
                f"""
                window.scrollBy({{top: {scroll_amount}, behavior: 'smooth'}})
            """
            )
        else:
            await page.evaluate(f"window.scrollBy(0, {scroll_amount})")

        logger.debug(f"Scrolled down {scroll_amount}px")

    async def on_page_created(self, ctx: BrowserContext) -> BrowserContext:
        """
        Виконує початкові дії після створення сторінки.

        Args:
            ctx: Browser контекст

        Returns:
            Оновлений контекст
        """
        if not ctx.page:
            return ctx

        try:
            # Невелика затримка перед навігацією
            await asyncio.sleep(random.uniform(0.1, 0.3))
            logger.debug("Human behavior: initial delay applied")

        except Exception as e:
            logger.error(f"Error in human behavior on page created: {e}")
            ctx.errors.append(e)

        return ctx

    async def on_navigation_completed(self, ctx: BrowserContext) -> BrowserContext:
        """
        Виконує людські дії після навігації.

        Args:
            ctx: Browser контекст

        Returns:
            Оновлений контекст
        """
        if not ctx.page:
            return ctx

        try:
            mouse_movements = self.config.get("mouse_movements", 3)

            # Виконуємо випадкові рухи миші
            for _ in range(mouse_movements):
                await self._random_mouse_movement(ctx.page)
                await asyncio.sleep(random.uniform(0.1, 0.3))

            # Випадкова затримка
            await self._random_delay()

            logger.debug(f"Human behavior: {mouse_movements} mouse movements completed")
            ctx.data["human_behavior_applied"] = True

        except Exception as e:
            logger.error(f"Error in human behavior on navigation completed: {e}")
            ctx.errors.append(e)

        return ctx

    async def on_content_ready(self, ctx: BrowserContext) -> BrowserContext:
        """
        Виконує додаткові людські дії.

        Args:
            ctx: Browser контекст

        Returns:
            Оновлений контекст
        """
        if not ctx.page:
            return ctx

        try:
            # Природній скрол
            if random.random() < 0.7:  # 70% шанс
                await self._natural_scroll(ctx.page)

            # Ще один рух миші
            await self._random_mouse_movement(ctx.page)

        except Exception as e:
            logger.error(f"Error in human behavior on content ready: {e}")
            ctx.errors.append(e)

        return ctx
