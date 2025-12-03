"""CAPTCHA Solver модуль - інтеграція з CAPTCHA solving сервісами.

Модульна структура для підтримки різних CAPTCHA сервісів.
"""

from graph_crawler.extensions.plugins.engine.captcha.detector import CaptchaDetector
from graph_crawler.extensions.plugins.engine.captcha.models import (
    CaptchaInfo,
    CaptchaService,
    CaptchaSolution,
    CaptchaType,
)
from graph_crawler.extensions.plugins.engine.captcha.plugin import CaptchaSolverPlugin

__all__ = [
    "CaptchaType",
    "CaptchaService",
    "CaptchaInfo",
    "CaptchaSolution",
    "CaptchaDetector",
    "CaptchaSolverPlugin",
]
