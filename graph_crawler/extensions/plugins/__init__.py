"""
 GraphCrawler - ДВІ НЕЗАЛЕЖНІ PLUGIN СИСТЕМИ

1⃣  DRIVER PLUGINS (BasePlugin) - Модифікація HTTP запитів/відповідей

 Призначення:
   - Втручання в процес HTTP запиту/відповіді
   - Модифікація headers, cookies, proxy
   - Обробка помилок запитів
   - Робота з браузером (screenshot, scroll)

 Lifecycle Hooks (PluginType):
   - PRE_REQUEST: перед відправкою запиту
   - POST_REQUEST: після отримання відповіді
   - PRE_PARSE: перед парсингом HTML
   - POST_PARSE: після парсингу HTML
   - ON_ERROR: при помилці запиту

2⃣  NODE PLUGINS (BaseNodePlugin) - Обробка контенту веб-сторінок

 Призначення:
   - Витягування даних з HTML контенту
   - Обробка metadata, текстів, посилань
   - Аналіз структури сторінки

 Lifecycle Hooks (NodePluginType):
   - ON_NODE_CREATED: після створення Node
   - ON_HTML_PARSED: після парсингу HTML
   - ON_AFTER_SCAN: після завершення сканування

3⃣  ENGINE PLUGINS - Плагіни рівня ядра

 Призначення:
   - Anti-bot обхід (Cloudflare, Akamai, DataDome)
   - CAPTCHA розв'язання
   - Stealth режими

 Built-in плагіни:
   - AntiBotStealthPlugin: обхід anti-bot систем
   - CaptchaSolverPlugin: розв'язання CAPTCHA

 СТРУКТУРА ПАПОК

plugins/
 __init__.py           # Головний експорт
 base.py               # BasePlugin, PluginContext, PluginType

 node/                 # Node плагіни (обробка контенту)
    __init__.py
    base.py           # BaseNodePlugin, NodePluginManager
    metadata.py       # MetadataExtractorPlugin
    links.py          # LinkExtractorPlugin
    text.py           # TextExtractorPlugin
    defaults.py       # get_default_node_plugins()
    content_extractors/

 engine/               # Engine плагіни (рівень ядра)
    __init__.py
    anti_bot_stealth.py
    captcha_solver.py

 builtin/              # Вбудовані плагіни
     stats_export_plugin.py

"""

# ============================================
# БАЗОВІ КЛАСИ DRIVER PLUGINS
# ============================================
from graph_crawler.extensions.plugins.base import (
    BasePlugin,
    PluginContext,
    PluginManager,
    PluginType,
)

# ============================================
# ENGINE PLUGINS
# ============================================
from graph_crawler.extensions.plugins.engine import (
    AntiBotStealthPlugin,
    AntiBotSystem,
    CaptchaInfo,
    CaptchaService,
    CaptchaSolution,
    CaptchaSolverPlugin,
    CaptchaType,
)

# ============================================
# NODE PLUGINS
# ============================================
from graph_crawler.extensions.plugins.node import (
    BaseNodePlugin,
    LinkExtractorPlugin,
    MetadataExtractorPlugin,
    NodePluginContext,
    NodePluginManager,
    NodePluginType,
    TextExtractorPlugin,
    get_default_node_plugins,
)

# ============================================
# PLAYWRIGHT PLUGINS (опціональні)
# ============================================
try:
    from graph_crawler.infrastructure.transport.playwright.plugins import (
        ScreenshotPlugin,
        ScrollPlugin,
    )
except ImportError:
    ScreenshotPlugin = None
    ScrollPlugin = None

# ============================================
# PROXY ROTATION PLUGIN
# ============================================
from graph_crawler.extensions.plugins.proxy_rotation import ProxyRotationPlugin

__all__ = [
    # Базові класи Driver plugins
    "BasePlugin",
    "PluginContext",
    "PluginType",
    "PluginManager",
    # Node plugins
    "BaseNodePlugin",
    "NodePluginType",
    "NodePluginContext",
    "NodePluginManager",
    "MetadataExtractorPlugin",
    "LinkExtractorPlugin",
    "TextExtractorPlugin",
    "get_default_node_plugins",
    # Engine plugins
    "AntiBotStealthPlugin",
    "AntiBotSystem",
    "CaptchaSolverPlugin",
    "CaptchaType",
    "CaptchaService",
    "CaptchaInfo",
    "CaptchaSolution",
    # Playwright plugins
    "ScreenshotPlugin",
    "ScrollPlugin",
    # Utils
    "ProxyRotationPlugin",
]
