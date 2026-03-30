"""
GraphCrawler - ДВІ НЕЗАЛЕЖНІ PLUGIN СИСТЕМИ

"""

# БАЗОВІ КЛАСИ DRIVER PLUGINS
from graph_crawler.extensions.plugins.base import (
    BasePlugin,
    PluginContext,
    PluginManager,
    PluginType,
)

# ENGINE PLUGINS
from graph_crawler.extensions.plugins.engine import (
    AntiBotStealthPlugin,
    AntiBotSystem,
    CaptchaInfo,
    CaptchaService,
    CaptchaSolution,
    CaptchaSolverPlugin,
    CaptchaType,
)

# NODE PLUGINS
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

# PLAYWRIGHT PLUGINS (опціональні)
try:
    from graph_crawler.infrastructure.transport.playwright.plugins import (
        ScreenshotPlugin,
        ScrollPlugin,
    )
except ImportError:
    ScreenshotPlugin = None
    ScrollPlugin = None

__all__ = [
    # Base classes - Driver Plugins
    "BasePlugin",
    "PluginContext",
    "PluginType",
    "PluginManager",
    # Node Plugins
    "BaseNodePlugin",
    "NodePluginType",
    "NodePluginContext",
    "NodePluginManager",
    "MetadataExtractorPlugin",
    "LinkExtractorPlugin",
    "TextExtractorPlugin",
    "get_default_node_plugins",
    # Engine Plugins
    "AntiBotStealthPlugin",
    "AntiBotSystem",
    "CaptchaSolverPlugin",
    "CaptchaType",
    "CaptchaService",
    "CaptchaInfo",
    "CaptchaSolution",
    # Playwright Plugins
    "ScreenshotPlugin",
    "ScrollPlugin",
]
