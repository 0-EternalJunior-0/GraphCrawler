"""
Cloudflare Bypass плагін для Playwright драйвера.

Автоматично виявляє та обходить Cloudflare захист:
- Challenge page (IUAM - I'm Under Attack Mode)
- Turnstile CAPTCHA
- Bot detection

Використовує логіку детектування на основі cloudscraper (https://github.com/VeNoMouS/cloudscraper)
для надійного виявлення справжніх Cloudflare challenge сторінок.
"""

import asyncio
import logging
import re
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from graph_crawler.infrastructure.transport.base_plugin import BaseDriverPlugin
from graph_crawler.infrastructure.transport.context import EventPriority
from graph_crawler.infrastructure.transport.playwright.context import BrowserContext
from graph_crawler.infrastructure.transport.playwright.stages import BrowserStage

logger = logging.getLogger(__name__)


class ChallengeType(Enum):
    """Типи Cloudflare challenge."""

    NONE = "none"
    IUAM_V1 = "iuam_v1"  # JavaScript challenge v1
    IUAM_V2 = "iuam_v2"  # JavaScript challenge v2 (новий)
    CAPTCHA_V1 = "captcha_v1"  # hCaptcha/reCaptcha v1
    CAPTCHA_V2 = "captcha_v2"  # hCaptcha/reCaptcha v2 (новий)
    TURNSTILE = "turnstile"  # Cloudflare Turnstile
    FIREWALL_1020 = "firewall_1020"  # Заблоковано Firewall


class CloudflareDetector:
    """
    Детектор Cloudflare challenge на основі логіки cloudscraper.

    Перевіряє:
    1. HTTP статус код (429, 503 для IUAM; 403 для captcha)
    2. Server header починається з 'cloudflare'
    3. Специфічні URL патерни в HTML (/cdn-cgi/...)
    4. Challenge форма з action="...__cf_chl_f_tk="
    """

    @staticmethod
    def is_cloudflare_server(headers: Dict[str, str]) -> bool:
        """Перевіряє чи сервер є Cloudflare."""
        server = headers.get("server", "") or headers.get("Server", "")
        return server.lower().startswith("cloudflare")

    @staticmethod
    def is_iuam_challenge(
        html: str, status_code: Optional[int], headers: Dict[str, str]
    ) -> bool:
        """
        Перевіряє на IUAM (I'm Under Attack Mode) challenge.

        Критерії (з cloudscraper):
        - Server header = 'cloudflare...'
        - Status code = 429 або 503
        - HTML містить /cdn-cgi/images/trace/jsch/
        - HTML містить challenge-form з __cf_chl_f_tk=
        """
        try:
            if not CloudflareDetector.is_cloudflare_server(headers):
                return False

            if status_code not in [429, 503]:
                return False

            # Перевіряємо наявність trace image
            if not re.search(r"/cdn-cgi/images/trace/jsch/", html, re.M | re.S):
                return False

            # Перевіряємо challenge форму
            if not re.search(
                r"""<form .*?="challenge-form" action="/\S+__cf_chl_f_tk=""",
                html,
                re.M | re.S,
            ):
                return False

            return True
        except Exception:
            return False

    @staticmethod
    def is_iuam_v2_challenge(
        html: str, status_code: Optional[int], headers: Dict[str, str]
    ) -> bool:
        """Перевіряє на новий IUAM v2 challenge."""
        try:
            if not CloudflareDetector.is_iuam_challenge(html, status_code, headers):
                return False

            # v2 використовує orchestrate/jsch/v1
            return bool(
                re.search(
                    r"""cpo.src\s*=\s*['"/]cdn-cgi/challenge-platform/\S+orchestrate/jsch/v1""",
                    html,
                    re.M | re.S,
                )
            )
        except Exception:
            return False

    @staticmethod
    def is_captcha_challenge(
        html: str, status_code: Optional[int], headers: Dict[str, str]
    ) -> bool:
        """
        Перевіряє на Captcha challenge.

        Критерії:
        - Server header = 'cloudflare...'
        - Status code = 403
        - HTML містить /cdn-cgi/images/trace/(captcha|managed)/
        - HTML містить challenge-form
        """
        try:
            if not CloudflareDetector.is_cloudflare_server(headers):
                return False

            if status_code != 403:
                return False

            # Перевіряємо captcha trace
            if not re.search(
                r"/cdn-cgi/images/trace/(captcha|managed)/", html, re.M | re.S
            ):
                return False

            # Перевіряємо challenge форму
            if not re.search(
                r"""<form .*?="challenge-form" action="/\S+__cf_chl_f_tk=""",
                html,
                re.M | re.S,
            ):
                return False

            return True
        except Exception:
            return False

    @staticmethod
    def is_captcha_v2_challenge(
        html: str, status_code: Optional[int], headers: Dict[str, str]
    ) -> bool:
        """Перевіряє на новий Captcha v2 challenge."""
        try:
            if not CloudflareDetector.is_captcha_challenge(html, status_code, headers):
                return False

            # v2 використовує orchestrate/captcha або managed
            return bool(
                re.search(
                    r"""cpo.src\s*=\s*['"/]cdn-cgi/challenge-platform/\S+orchestrate/(captcha|managed)/v1""",
                    html,
                    re.M | re.S,
                )
            )
        except Exception:
            return False

    @staticmethod
    def is_turnstile_challenge(
        html: str, status_code: Optional[int], headers: Dict[str, str]
    ) -> bool:
        """
        Перевіряє на Cloudflare Turnstile challenge.

        Критерії:
        - Server header = 'cloudflare...'
        - HTML містить turnstile елементи
        """
        try:
            if not CloudflareDetector.is_cloudflare_server(headers):
                return False

            # Turnstile маркери
            turnstile_patterns = [
                r"challenges\.cloudflare\.com/turnstile",
                r"cf-turnstile",
                r"data-sitekey.*turnstile",
                r"turnstile/v0/api\.js",
            ]

            for pattern in turnstile_patterns:
                if re.search(pattern, html, re.I):
                    return True

            return False
        except Exception:
            return False

    @staticmethod
    def is_firewall_blocked(
        html: str, status_code: Optional[int], headers: Dict[str, str]
    ) -> bool:
        """
        Перевіряє на Firewall 1020 блокування.

        Критерії:
        - Server header = 'cloudflare...'
        - Status code = 403
        - HTML містить error code 1020
        """
        try:
            if not CloudflareDetector.is_cloudflare_server(headers):
                return False

            if status_code != 403:
                return False

            return bool(
                re.search(
                    r'<span class="cf-error-code">1020</span>', html, re.M | re.DOTALL
                )
            )
        except Exception:
            return False

    @staticmethod
    def detect_challenge_type(
        html: str, status_code: Optional[int], headers: Dict[str, str]
    ) -> ChallengeType:
        """
        Визначає тип Cloudflare challenge.

        Returns:
            ChallengeType enum
        """
        # Перевіряємо в порядку специфічності (від більш специфічних до загальних)

        # 1. Firewall блокування (найвищий пріоритет)
        if CloudflareDetector.is_firewall_blocked(html, status_code, headers):
            return ChallengeType.FIREWALL_1020

        # 2. Captcha v2 (новий)
        if CloudflareDetector.is_captcha_v2_challenge(html, status_code, headers):
            return ChallengeType.CAPTCHA_V2

        # 3. Captcha v1
        if CloudflareDetector.is_captcha_challenge(html, status_code, headers):
            return ChallengeType.CAPTCHA_V1

        # 4. Turnstile
        if CloudflareDetector.is_turnstile_challenge(html, status_code, headers):
            return ChallengeType.TURNSTILE

        # 5. IUAM v2 (новий)
        if CloudflareDetector.is_iuam_v2_challenge(html, status_code, headers):
            return ChallengeType.IUAM_V2

        # 6. IUAM v1
        if CloudflareDetector.is_iuam_challenge(html, status_code, headers):
            return ChallengeType.IUAM_V1

        return ChallengeType.NONE


class CloudflarePlugin(BaseDriverPlugin):
    """
    Плагін для обходу Cloudflare захисту.

    Використовує логіку детектування на основі cloudscraper для надійного
    виявлення справжніх Cloudflare challenge сторінок (не просто CDN).

    Конфігурація:
        wait_timeout: Максимальний час очікування challenge (default: 30s)
        check_interval: Інтервал перевірки (default: 1s)
        handle_turnstile: Чи намагатись обійти Turnstile (default: True)

    Події:
        - cloudflare_detected: Виявлено Cloudflare challenge
        - cloudflare_passed: Challenge пройдено
        - cloudflare_failed: Не вдалося обійти
        - cloudflare_blocked: Заблоковано Firewall 1020

    Приклад:
        plugin = CloudflarePlugin(CloudflarePlugin.config(
            wait_timeout=60,
            check_interval=2
        ))
    """

    @property
    def name(self) -> str:
        return "cloudflare"

    def get_hooks(self) -> List[str]:
        return [BrowserStage.NAVIGATION_COMPLETED, BrowserStage.CONTENT_READY]

    async def _get_response_info(
        self, page, ctx: BrowserContext
    ) -> Tuple[str, Optional[int], Dict[str, str]]:
        """Отримує HTML, status code та headers."""
        try:
            html = await page.content()

            # Status code з контексту
            status_code = ctx.status_code

            # Headers з response
            headers = {}
            if ctx.response:
                try:
                    response_headers = await ctx.response.all_headers()
                    headers = dict(response_headers)
                except Exception:
                    headers = ctx.response_headers or {}

            return html, status_code, headers
        except Exception as e:
            logger.debug(f"Error getting response info: {e}")
            return "", None, {}

    async def _detect_cloudflare(self, page, ctx: BrowserContext) -> ChallengeType:
        """
        Виявляє тип Cloudflare challenge використовуючи логіку cloudscraper.

        Returns:
            ChallengeType enum
        """
        try:
            html, status_code, headers = await self._get_response_info(page, ctx)
            return CloudflareDetector.detect_challenge_type(html, status_code, headers)
        except Exception as e:
            logger.debug(f"Error detecting Cloudflare: {e}")
            return ChallengeType.NONE

    async def _wait_for_cloudflare(
        self, page, ctx: BrowserContext, challenge_type: ChallengeType
    ) -> bool:
        """
        Очікує завершення Cloudflare challenge.

        Args:
            page: Playwright page
            ctx: Browser context
            challenge_type: Тип challenge

        Returns:
            True якщо challenge пройдено
        """
        wait_timeout = self.config.get("wait_timeout", 30)
        check_interval = self.config.get("check_interval", 1)

        logger.info(
            f"⏳ Waiting for Cloudflare {challenge_type.value} challenge to complete (max {wait_timeout}s)..."
        )

        elapsed = 0
        while elapsed < wait_timeout:
            await asyncio.sleep(check_interval)
            elapsed += check_interval

            # Перевіряємо чи challenge завершено
            current_type = await self._detect_cloudflare(page, ctx)

            if current_type == ChallengeType.NONE:
                logger.info(f"Cloudflare challenge passed after {elapsed}s")
                return True

            # Якщо тип змінився на блокування - виходимо
            if current_type == ChallengeType.FIREWALL_1020:
                logger.warning(f" Cloudflare Firewall 1020 block detected")
                return False

            # Логуємо прогрес кожні 5 секунд
            if elapsed % 5 == 0:
                logger.debug(f"⏳ Still waiting... ({elapsed}s/{wait_timeout}s)")

        logger.warning(f"⏰ Cloudflare challenge timeout after {wait_timeout}s")
        return False

    async def on_navigation_completed(self, ctx: BrowserContext) -> BrowserContext:
        """
        Перевіряє наявність Cloudflare challenge після навігації.

        Args:
            ctx: Browser контекст

        Returns:
            Оновлений контекст
        """
        if not ctx.page:
            return ctx

        try:
            challenge_type = await self._detect_cloudflare(ctx.page, ctx)

            if challenge_type == ChallengeType.NONE:
                # Немає challenge - продовжуємо
                return ctx

            # Зберігаємо інформацію про challenge
            ctx.data["cloudflare_detected"] = True
            ctx.data["cloudflare_challenge_type"] = challenge_type.value

            # Логуємо та емітимо подію
            logger.warning(f" Cloudflare {challenge_type.value} detected on {ctx.url}")
            ctx.emit(
                "cloudflare_detected", url=ctx.url, challenge_type=challenge_type.value
            )

            # Обробка Firewall 1020
            if challenge_type == ChallengeType.FIREWALL_1020:
                logger.error(
                    f" Cloudflare Firewall has blocked access to {ctx.url} (Error 1020)"
                )
                ctx.emit("cloudflare_blocked", url=ctx.url, error_code=1020)
                ctx.data["cloudflare_blocked"] = True
                return ctx

            # Очікуємо завершення challenge
            if await self._wait_for_cloudflare(ctx.page, ctx, challenge_type):
                ctx.emit(
                    "cloudflare_passed",
                    url=ctx.url,
                    challenge_type=challenge_type.value,
                )
                ctx.data["cloudflare_passed"] = True
            else:
                ctx.emit(
                    "cloudflare_failed",
                    url=ctx.url,
                    challenge_type=challenge_type.value,
                )
                ctx.data["cloudflare_failed"] = True

        except Exception as e:
            logger.error(f"Error in Cloudflare detection: {e}")
            ctx.errors.append(e)

        return ctx

    async def on_content_ready(self, ctx: BrowserContext) -> BrowserContext:
        """
        Фінальна перевірка на Cloudflare challenge.

        Args:
            ctx: Browser контекст

        Returns:
            Оновлений контекст
        """
        if not ctx.page:
            return ctx

        # Якщо вже обробляли challenge - пропускаємо
        if ctx.data.get("cloudflare_detected"):
            return ctx

        try:
            challenge_type = await self._detect_cloudflare(ctx.page, ctx)

            if challenge_type == ChallengeType.NONE:
                return ctx

            # Late detection
            logger.warning(
                f" Late Cloudflare {challenge_type.value} detection on {ctx.url}"
            )
            ctx.data["cloudflare_detected"] = True
            ctx.data["cloudflare_challenge_type"] = challenge_type.value
            ctx.emit(
                "cloudflare_detected", url=ctx.url, challenge_type=challenge_type.value
            )

            if challenge_type == ChallengeType.FIREWALL_1020:
                ctx.emit("cloudflare_blocked", url=ctx.url, error_code=1020)
                ctx.data["cloudflare_blocked"] = True
                return ctx

            if await self._wait_for_cloudflare(ctx.page, ctx, challenge_type):
                ctx.emit("cloudflare_passed", url=ctx.url)
                ctx.data["cloudflare_passed"] = True

                # Оновлюємо HTML після проходження challenge
                ctx.html = await ctx.page.content()
            else:
                ctx.emit("cloudflare_failed", url=ctx.url)
                ctx.data["cloudflare_failed"] = True

        except Exception as e:
            logger.error(f"Error in Cloudflare content check: {e}")
            ctx.errors.append(e)

        return ctx
