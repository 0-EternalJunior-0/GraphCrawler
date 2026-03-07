"""Плагіни для Playwright драйвера (нова архітектура).

Всі плагіни інтегруються з DriverPluginManager та мають доступ до:
- browser, context, page через BrowserContext
- Систему подій для комунікації між плагінами

Enhanced Plugins (рекомендовано для anti-bot bypass):
- EnhancedStealthPlugin: Повна інтеграція playwright-stealth
- EnhancedCloudflarePlugin: Автоматичний Turnstile solver

Profile Plugins (для використання реальних профілів браузера):
- UserProfilePlugin: Підключення профілю користувача
- ProfilePoolPlugin: Ротація профілів для масштабування
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
from graph_crawler.infrastructure.transport.playwright.plugins.enhanced_cloudflare import (
    EnhancedCloudflarePlugin,
)

# Enhanced plugins for anti-bot bypass
from graph_crawler.infrastructure.transport.playwright.plugins.enhanced_stealth import (
    EnhancedStealthPlugin,
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

# Profile plugins for real user profile support
from graph_crawler.infrastructure.transport.playwright.plugins.user_profile import (
    UserProfilePlugin,
    ProfilePoolPlugin,
    get_default_chrome_profile_path,
    get_default_chromium_profile_path,
    create_profile_copy,
)

# Compatibility system for plugin conflict detection
from graph_crawler.infrastructure.transport.playwright.plugins.compatibility import (
    PluginCompatibilityChecker,
    CompatibilityReport,
    CompatibilityLevel,
    check_plugin_compatibility,
    get_stealth_plugins,
    RECOMMENDED_COMBINATIONS,
)

__all__ = [
    # Original plugins
    "StealthPlugin",
    "CaptchaDetectorPlugin",
    "CaptchaSolverPlugin",
    "ScreenshotPlugin",
    "CloudflarePlugin",
    "HumanBehaviorPlugin",
    "FormFillerPlugin",
    # Enhanced plugins (recommended)
    "EnhancedStealthPlugin",
    "EnhancedCloudflarePlugin",
    # Profile plugins (for real user profiles)
    "UserProfilePlugin",
    "ProfilePoolPlugin",
    # Helper functions
    "get_default_chrome_profile_path",
    "get_default_chromium_profile_path",
    "create_profile_copy",
    # Compatibility system
    "PluginCompatibilityChecker",
    "CompatibilityReport",
    "CompatibilityLevel",
    "check_plugin_compatibility",
    "get_stealth_plugins",
    "RECOMMENDED_COMBINATIONS",
]
