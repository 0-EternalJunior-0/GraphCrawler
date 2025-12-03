"""Engine Plugins - плагіни рівня ядра краулера.

Engine плагіни впливають на всю систему краулінгу:
- Anti-bot обхід (Cloudflare, Akamai, DataDome)
- CAPTCHA розв'язувач
- Stealth режим

Example:
    >>> from graph_crawler.extensions.plugins.engine import (
    ...     AntiBotStealthPlugin,
    ...     CaptchaSolverPlugin,
    ... )
    >>>
    >>> anti_bot = AntiBotStealthPlugin(config={'stealth_mode': 'high'})
    >>> captcha = CaptchaSolverPlugin(config={'service': '2captcha', 'api_key': '...'})
"""

from graph_crawler.extensions.plugins.engine.anti_bot_stealth import (
    AntiBotStealthPlugin,
    AntiBotSystem,
)
from graph_crawler.extensions.plugins.engine.captcha_solver import (
    CaptchaInfo,
    CaptchaService,
    CaptchaSolution,
    CaptchaSolverPlugin,
    CaptchaType,
)

__all__ = [
    # Anti-Bot
    "AntiBotStealthPlugin",
    "AntiBotSystem",
    # CAPTCHA
    "CaptchaSolverPlugin",
    "CaptchaType",
    "CaptchaService",
    "CaptchaInfo",
    "CaptchaSolution",
]
