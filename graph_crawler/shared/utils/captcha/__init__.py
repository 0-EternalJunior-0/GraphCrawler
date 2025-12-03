"""CAPTCHA Bypass Module - стратегії обходу CAPTCHA.

Нова структура:
- base.py: Базові класи, enums, dataclasses
- manager.py: CaptchaBypassManager
- strategies/: Окремі стратегії

Example:
    >>> from graph_crawler.shared.utils.captcha import (
    ...     CaptchaBypassManager,
    ...     BypassStrategy,
    ...     BypassResult,
    ... )
    >>>
    >>> manager = CaptchaBypassManager()
    >>> result = manager.try_bypass(url, strategy=BypassStrategy.COOKIE_PERSISTENCE)
"""

from graph_crawler.shared.utils.captcha.base import (
    BypassAttempt,
    BypassResult,
    BypassStrategy,
    SessionInfo,
)
from graph_crawler.shared.utils.captcha.manager import CaptchaBypassManager

__all__ = [
    # Enums
    "BypassStrategy",
    "BypassResult",
    # Dataclasses
    "BypassAttempt",
    "SessionInfo",
    # Manager
    "CaptchaBypassManager",
]
