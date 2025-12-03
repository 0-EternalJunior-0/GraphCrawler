"""CAPTCHA Solver Plugin - backward compatibility wrapper.

Новий код має використовувати:
    from graph_crawler.extensions.plugins.engine.captcha import CaptchaSolverPlugin

Цей файл залишено для зворотної сумісності.
"""

# Re-export все з нового модуля
from graph_crawler.extensions.plugins.engine.captcha import (
    CaptchaDetector,
    CaptchaInfo,
    CaptchaService,
    CaptchaSolution,
    CaptchaSolverPlugin,
    CaptchaType,
)

__all__ = [
    "CaptchaType",
    "CaptchaService",
    "CaptchaInfo",
    "CaptchaSolution",
    "CaptchaDetector",
    "CaptchaSolverPlugin",
]
