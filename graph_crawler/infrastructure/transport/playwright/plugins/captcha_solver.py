"""
CAPTCHA Solver плагін для Playwright.

Підписується на подію 'captcha_detected' від CaptchaDetector та розв'язує CAPTCHA.
Це приклад комунікації між плагінами через події!
"""

import asyncio
import logging
from typing import Any, Dict, List

from graph_crawler.infrastructure.transport.base_plugin import BaseDriverPlugin
from graph_crawler.infrastructure.transport.playwright.context import BrowserContext

logger = logging.getLogger(__name__)


class CaptchaSolverPlugin(BaseDriverPlugin):
    """
    Плагін для розв'язання CAPTCHA.

    Підписується на подію 'captcha_detected' від CaptchaDetectorPlugin.
    Це приклад event-driven архітектури плагінів!

    Конфігурація:
        service: Captcha solving сервіс ('2captcha', 'anticaptcha') (required)
        api_key: API key для сервісу (required)
        solve_timeout: Timeout для розв'язання (default: 120s)

    Приклад:
        solver = CaptchaSolverPlugin(CaptchaSolverPlugin.config(
            service='2captcha',
            api_key='YOUR_API_KEY'
        ))
    """

    @property
    def name(self) -> str:
        return "captcha_solver"

    def get_hooks(self) -> List[str]:
        # Не підписуємось на етапи драйвера
        return []

    def get_events(self) -> List[str]:
        # Підписуємось на подію від іншого плагіна!
        return ["captcha_detected"]

    def setup(self):
        """Перевіряє наявність API key."""
        api_key = self.config.get("api_key")

        if not api_key:
            logger.warning(
                "CaptchaSolver: API key not provided - plugin will be disabled"
            )
            self.enabled = False
            return

        service = self.config.get("service", "2captcha")
        logger.info(f"CaptchaSolver initialized with service: {service}")

    async def on_captcha_detected(self, ctx: BrowserContext, **captcha_data) -> None:
        """
        Обробник події 'captcha_detected'.

        Викликається автоматично коли CaptchaDetector публікує подію!

        Args:
            ctx: Browser контекст
            **captcha_data: Дані про CAPTCHA (від detector)
        """
        captcha_type = captcha_data.get("captcha_type")
        site_key = captcha_data.get("site_key")
        page_url = captcha_data.get("page_url")

        logger.info(f"Attempting to solve {captcha_type} on {page_url}")

        try:
            # Тут була б логіка розв'язання через API
            # Зараз просто імітуємо

            logger.info("Sending CAPTCHA to solving service...")
            await asyncio.sleep(2)  # Імітація розв'язання

            # Публікуємо подію про успішне розв'язання
            ctx.emit("captcha_solved", captcha_type=captcha_type, token="mock_token")

            # Зберігаємо в контексті
            ctx.data["captcha_solved"] = True
            ctx.data["captcha_token"] = "mock_token"

            logger.info(f"CAPTCHA solved successfully: {captcha_type}")

        except Exception as e:
            logger.error(f"Error solving CAPTCHA: {e}")
            ctx.emit("captcha_solve_failed", error=str(e))
            ctx.errors.append(e)
