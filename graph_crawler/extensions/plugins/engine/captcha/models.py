"""Models для CAPTCHA Solver.

Містить dataclasses та enums для роботи з CAPTCHA.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class CaptchaType(str, Enum):
    """Типи CAPTCHA."""

    RECAPTCHA_V2 = "recaptcha_v2"
    RECAPTCHA_V3 = "recaptcha_v3"
    HCAPTCHA = "hcaptcha"
    IMAGE = "image"
    FUNCAPTCHA = "funcaptcha"
    GEETEST = "geetest"


class CaptchaService(str, Enum):
    """CAPTCHA solving сервіси."""

    TWO_CAPTCHA = "2captcha"
    ANTI_CAPTCHA = "anticaptcha"
    CAPSOLVER = "capsolver"


@dataclass
class CaptchaInfo:
    """
    Інформація про виявлений CAPTCHA.

    Attributes:
        captcha_type: Тип CAPTCHA
        site_key: Site key для CAPTCHA
        page_url: URL сторінки з CAPTCHA
        data_s: Додатковий параметр для reCAPTCHA v3
        action: Action для reCAPTCHA v3
    """

    captcha_type: CaptchaType
    site_key: str
    page_url: str
    data_s: Optional[str] = None
    action: Optional[str] = None

    def __repr__(self):
        return (
            f"CaptchaInfo(type={self.captcha_type}, site_key={self.site_key[:20]}...)"
        )


@dataclass
class CaptchaSolution:
    """
    Розв'язок CAPTCHA.

    Attributes:
        token: Розв'язаний CAPTCHA token
        captcha_type: Тип CAPTCHA
        solve_time: Час розв'язання (секунди)
        cost: Вартість розв'язання
        service: Використаний сервіс
    """

    token: str
    captcha_type: CaptchaType
    solve_time: float
    cost: float = 0.0
    service: Optional[str] = None

    def __repr__(self):
        return f"CaptchaSolution(type={self.captcha_type}, time={self.solve_time:.1f}s, cost=${self.cost:.4f})"
