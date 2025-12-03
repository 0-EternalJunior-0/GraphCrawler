"""Плагіни для Playwright драйвера (нова архітектура).

Всі плагіни інтегруються з DriverPluginManager та мають доступ до:
- browser, context, page через BrowserContext
- Систему подій для комунікації між плагінами
"""

from graph_crawler.infrastructure.transport.playwright.plugins.captcha_detector import (
    CaptchaDetectorPlugin,
)
from graph_crawler.infrastructure.transport.playwright.plugins.captcha_solver import (
    CaptchaSolverPlugin,
)
from graph_crawler.infrastructure.transport.playwright.plugins.cloudflare import (
    CloudflarePlugin,
)
from graph_crawler.infrastructure.transport.playwright.plugins.form_filler import (
    FormFillerPlugin,
)
from graph_crawler.infrastructure.transport.playwright.plugins.human_behavior import (
    HumanBehaviorPlugin,
)
from graph_crawler.infrastructure.transport.playwright.plugins.screenshot import (
    ScreenshotPlugin,
)
from graph_crawler.infrastructure.transport.playwright.plugins.stealth import (
    StealthPlugin,
)

__all__ = [
    "StealthPlugin",
    "CaptchaDetectorPlugin",
    "CaptchaSolverPlugin",
    "ScreenshotPlugin",
    "CloudflarePlugin",
    "HumanBehaviorPlugin",
    "FormFillerPlugin",
]
