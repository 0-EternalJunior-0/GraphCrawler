"""
CAPTCHA Detector плагін для Playwright.

Детектить CAPTCHA на сторінці та публікує подію 'captcha_detected'.
Інші плагіни (наприклад, CaptchaSolver) можуть підписатися на цю подію.
"""

import logging
import re
from typing import Any, Dict, List, Optional

from graph_crawler.infrastructure.transport.base_plugin import BaseDriverPlugin
from graph_crawler.infrastructure.transport.playwright.context import BrowserContext
from graph_crawler.infrastructure.transport.playwright.stages import BrowserStage

logger = logging.getLogger(__name__)


class CaptchaDetectorPlugin(BaseDriverPlugin):
    """
    Плагін для автоматичного виявлення CAPTCHA.

    Підтримує:
    - reCAPTCHA v2
    - reCAPTCHA v3
    - hCaptcha
    - FunCaptcha
    - GeeTest

    Публікує подію 'captcha_detected' з даними:
    - captcha_type: тип CAPTCHA
    - site_key: site key (якщо є)
    - page_url: URL сторінки

    Конфігурація:
        enabled: Чи вмікнено детекцію (default: True)

    Приклад:
        detector = CaptchaDetectorPlugin()
        solver = CaptchaSolverPlugin()  # Підписується на captcha_detected
    """

    @property
    def name(self) -> str:
        return "captcha_detector"

    def get_hooks(self) -> List[str]:
        # Детектимо CAPTCHA коли контент готовий
        return [BrowserStage.CONTENT_READY]

    async def _detect_recaptcha_v2(
        self, ctx: BrowserContext
    ) -> Optional[Dict[str, Any]]:
        """Детекція reCAPTCHA v2."""
        try:
            # Шукаємо g-recaptcha елемент
            element = await ctx.page.query_selector(".g-recaptcha, [data-sitekey]")

            if element:
                # Отримуємо site key
                site_key = await element.get_attribute("data-sitekey")

                if site_key:
                    logger.info(f"Detected reCAPTCHA v2 (site_key: {site_key[:20]}...)")
                    return {
                        "captcha_type": "recaptcha_v2",
                        "site_key": site_key,
                        "page_url": ctx.url,
                    }
        except Exception as e:
            logger.debug(f"Error detecting reCAPTCHA v2: {e}")

        return None

    async def _detect_recaptcha_v3(
        self, ctx: BrowserContext
    ) -> Optional[Dict[str, Any]]:
        """Детекція reCAPTCHA v3."""
        try:
            html = await ctx.page.content()

            # Шукаємо grecaptcha.execute в HTML
            match = re.search(r'grecaptcha\.execute\([\'"]([^\'"]+)[\'"]', html)

            if match:
                site_key = match.group(1)
                logger.info(f"Detected reCAPTCHA v3 (site_key: {site_key[:20]}...)")

                # Пробуємо знайти action
                action_match = re.search(r'action:\s*[\'"]([^\'"]+)', html)
                action = action_match.group(1) if action_match else "submit"

                return {
                    "captcha_type": "recaptcha_v3",
                    "site_key": site_key,
                    "action": action,
                    "page_url": ctx.url,
                }
        except Exception as e:
            logger.debug(f"Error detecting reCAPTCHA v3: {e}")

        return None

    async def _detect_hcaptcha(self, ctx: BrowserContext) -> Optional[Dict[str, Any]]:
        """Детекція hCaptcha."""
        try:
            element = await ctx.page.query_selector(
                ".h-captcha, [data-hcaptcha-site-key]"
            )

            if element:
                # Отримуємо site key
                site_key = await element.get_attribute(
                    "data-sitekey"
                ) or await element.get_attribute("data-hcaptcha-site-key")

                if site_key:
                    logger.info(f"Detected hCaptcha (site_key: {site_key[:20]}...)")
                    return {
                        "captcha_type": "hcaptcha",
                        "site_key": site_key,
                        "page_url": ctx.url,
                    }
        except Exception as e:
            logger.debug(f"Error detecting hCaptcha: {e}")

        return None

    async def _detect_funcaptcha(self, ctx: BrowserContext) -> Optional[Dict[str, Any]]:
        """Детекція FunCaptcha."""
        try:
            html = await ctx.page.content()

            if "funcaptcha" in html.lower() or "arkoselabs" in html.lower():
                match = re.search(
                    r'data-public-key=[\'"]([^\'"]+)', html, re.IGNORECASE
                )

                if match:
                    public_key = match.group(1)
                    logger.info(f"Detected FunCaptcha (key: {public_key[:20]}...)")
                    return {
                        "captcha_type": "funcaptcha",
                        "site_key": public_key,
                        "page_url": ctx.url,
                    }
        except Exception as e:
            logger.debug(f"Error detecting FunCaptcha: {e}")

        return None

    async def _detect_geetest(self, ctx: BrowserContext) -> Optional[Dict[str, Any]]:
        """Детекція GeeTest."""
        try:
            html = await ctx.page.content()

            if "geetest" in html.lower() or "gt-captcha" in html.lower():
                logger.info("Detected GeeTest CAPTCHA")
                return {"captcha_type": "geetest", "page_url": ctx.url}
        except Exception as e:
            logger.debug(f"Error detecting GeeTest: {e}")

        return None

    async def on_content_ready(self, ctx: BrowserContext) -> BrowserContext:
        """
        Виявляє CAPTCHA на сторінці.

        Args:
            ctx: Browser контекст

        Returns:
            Оновлений контекст
        """
        if not ctx.page:
            return ctx

        try:
            # Пробуємо всі типи CAPTCHA
            detectors = [
                self._detect_recaptcha_v2,
                self._detect_recaptcha_v3,
                self._detect_hcaptcha,
                self._detect_funcaptcha,
                self._detect_geetest,
            ]

            for detector in detectors:
                result = await detector(ctx)

                if result:
                    # Публікуємо подію 'captcha_detected' для інших плагінів
                    logger.warning(
                        f"CAPTCHA detected on {ctx.url}: {result['captcha_type']}"
                    )
                    ctx.emit("captcha_detected", **result)

                    # Зберігаємо в контексті
                    ctx.data["captcha_info"] = result

                    # Виходимо після першого знайденого
                    break

        except Exception as e:
            logger.error(f"Error in CAPTCHA detection: {e}")
            ctx.errors.append(e)

        return ctx
