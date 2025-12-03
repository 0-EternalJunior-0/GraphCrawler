"""Playwright Driver module - browser-based driver with JavaScript rendering and plugin support."""

from graph_crawler.infrastructure.transport.playwright.config import (
    PlaywrightDriverConfig,
)
from graph_crawler.infrastructure.transport.playwright.context import BrowserContext
from graph_crawler.infrastructure.transport.playwright.driver import PlaywrightDriver
from graph_crawler.infrastructure.transport.playwright.pooled_driver import (
    PooledPlaywrightDriver,
)
from graph_crawler.infrastructure.transport.playwright.stages import BrowserStage

__all__ = [
    "PlaywrightDriver",
    "PooledPlaywrightDriver",
    "PlaywrightDriverConfig",
    "BrowserStage",
    "BrowserContext",
]
