"""CAPTCHA Detector - автоматичне виявлення CAPTCHA на сторінці."""

import logging
import re
from typing import Optional

from graph_crawler.extensions.plugins.engine.captcha.models import (
    CaptchaInfo,
    CaptchaType,
)

logger = logging.getLogger(__name__)


class CaptchaDetector:
    """Детектор CAPTCHA на HTML сторінках."""

    @staticmethod
    def detect(html: str, page_url: str) -> Optional[CaptchaInfo]:
        """
        Автоматично визначає CAPTCHA на сторінці.

        Args:
            html: HTML код сторінки
            page_url: URL сторінки

        Returns:
            CaptchaInfo якщо знайдено CAPTCHA, інакше None
        """
        # reCAPTCHA v2 detection
        recaptcha_v2_match = re.search(
            r'g-recaptcha["\s]+.*?data-sitekey=["\']([^"\']+)', html, re.IGNORECASE
        )
        if recaptcha_v2_match:
            site_key = recaptcha_v2_match.group(1)
            data_s_match = re.search(r'data-s=["\']([^"\']+)', html)
            data_s = data_s_match.group(1) if data_s_match else None

            logger.info(f"Detected reCAPTCHA v2 on {page_url}")
            return CaptchaInfo(
                captcha_type=CaptchaType.RECAPTCHA_V2,
                site_key=site_key,
                page_url=page_url,
                data_s=data_s,
            )

        # reCAPTCHA v3 detection
        recaptcha_v3_match = re.search(
            r'grecaptcha\.execute\(["\']([^"\']+)["\']', html
        )
        if recaptcha_v3_match:
            site_key = recaptcha_v3_match.group(1)
            action_match = re.search(r'action:\s*["\']([^"\']+)', html)
            action = action_match.group(1) if action_match else "submit"

            logger.info(f"Detected reCAPTCHA v3 on {page_url}")
            return CaptchaInfo(
                captcha_type=CaptchaType.RECAPTCHA_V3,
                site_key=site_key,
                page_url=page_url,
                action=action,
            )

        # hCaptcha detection
        hcaptcha_match = re.search(
            r'h-captcha["\s]+.*?data-sitekey=["\']([^"\']+)', html, re.IGNORECASE
        )
        if hcaptcha_match:
            site_key = hcaptcha_match.group(1)
            logger.info(f"Detected hCaptcha on {page_url}")
            return CaptchaInfo(
                captcha_type=CaptchaType.HCAPTCHA, site_key=site_key, page_url=page_url
            )

        # FunCaptcha detection
        funcaptcha_match = re.search(
            r'data-callback=["\']setupCaptcha["\'][\s\S]*?data-public-key=["\']([^"\']+)',
            html,
            re.IGNORECASE,
        )
        if funcaptcha_match:
            site_key = funcaptcha_match.group(1)
            logger.info(f"Detected FunCaptcha on {page_url}")
            return CaptchaInfo(
                captcha_type=CaptchaType.FUNCAPTCHA,
                site_key=site_key,
                page_url=page_url,
            )

        # GeeTest detection
        if "geetest" in html.lower() or "gt-captcha" in html.lower():
            logger.info(f"Detected GeeTest on {page_url}")
            return CaptchaInfo(
                captcha_type=CaptchaType.GEETEST, site_key="", page_url=page_url
            )

        return None
