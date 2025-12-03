"""Configuration for Playwright Driver."""

from dataclasses import dataclass, field
from typing import List, Optional

from graph_crawler.shared.constants import (
    DEFAULT_BROWSER_TYPE,
    DEFAULT_BROWSER_VIEWPORT_HEIGHT,
    DEFAULT_BROWSER_VIEWPORT_WIDTH,
    DEFAULT_BROWSER_WAIT_TIMEOUT,
    DEFAULT_BROWSER_WAIT_UNTIL,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_SCREENSHOT_DIRECTORY,
    DEFAULT_USER_AGENT,
)


@dataclass
class PlaywrightDriverConfig:
    """
    Конфігурація для Playwright драйвера.

    Attributes:
        browser: Тип браузера (chromium, firefox, webkit)
        headless: Headless режим
        timeout: Таймаут в мілісекундах
        user_agent: User-Agent header
        viewport_width: Ширина viewport
        viewport_height: Висота viewport
        stealth_mode: Режим stealth (обхід webdriver detection)
        wait_until: Стратегія очікування (load, domcontentloaded, networkidle)
        wait_selector: CSS selector для очікування
        wait_timeout: Таймаут очікування selector
        screenshot: Вмікнути screenshot
        screenshot_path: Шлях для збереження screenshot
        screenshot_full_page: Screenshot всієї сторінки
        block_resources: Типи ресурсів для блокування
        javascript_enabled: Вмікнути JavaScript
    """

    browser: str = DEFAULT_BROWSER_TYPE
    headless: bool = True
    timeout: int = DEFAULT_REQUEST_TIMEOUT * 1000  # Convert to milliseconds
    user_agent: str = DEFAULT_USER_AGENT
    viewport_width: int = DEFAULT_BROWSER_VIEWPORT_WIDTH
    viewport_height: int = DEFAULT_BROWSER_VIEWPORT_HEIGHT
    stealth_mode: bool = True
    wait_until: str = DEFAULT_BROWSER_WAIT_UNTIL
    wait_selector: Optional[str] = None
    wait_timeout: int = DEFAULT_BROWSER_WAIT_TIMEOUT
    screenshot: bool = False
    screenshot_path: str = DEFAULT_SCREENSHOT_DIRECTORY
    screenshot_full_page: bool = True
    block_resources: List[str] = field(default_factory=list)
    javascript_enabled: bool = True

    def to_dict(self) -> dict:
        """Конвертує config в словник."""
        return {
            "browser": self.browser,
            "headless": self.headless,
            "timeout": self.timeout,
            "user_agent": self.user_agent,
            "viewport": {
                "width": self.viewport_width,
                "height": self.viewport_height,
            },
            "stealth_mode": self.stealth_mode,
            "wait_until": self.wait_until,
            "wait_selector": self.wait_selector,
            "wait_timeout": self.wait_timeout,
            "screenshot": self.screenshot,
            "screenshot_path": self.screenshot_path,
            "screenshot_full_page": self.screenshot_full_page,
            "block_resources": self.block_resources,
            "javascript_enabled": self.javascript_enabled,
        }
