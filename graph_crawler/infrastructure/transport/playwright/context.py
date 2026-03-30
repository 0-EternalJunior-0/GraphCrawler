"""Контекст для Playwright драйвера.

Найважливіший контекст - дає доступ до:
- browser: Browser об'єкт
- context: BrowserContext об'єкт
- page: Page об'єкт

Це дозволяє плагінам виконувати будь-які операції з браузером!
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from graph_crawler.infrastructure.transport.context import DriverContext

# Type hints (для IDE, реальні імпорти в рантаймі)
try:
    from playwright.async_api import (  # type: ignore[import-not-found]
        Browser,
        Page,
        Response,
    )
    from playwright.async_api import BrowserContext as PWContext  # type: ignore[import-not-found]

    PLAYWRIGHT_TYPES_AVAILABLE = True
except ImportError:
    # Fallback якщо playwright не встановлено
    Browser = None  # type: ignore[misc,assignment]
    PWContext = None  # type: ignore[misc,assignment]
    Page = None  # type: ignore[misc,assignment]
    Response = None  # type: ignore[misc,assignment]
    PLAYWRIGHT_TYPES_AVAILABLE = False


@dataclass
class BrowserContext(DriverContext):
    """
    Контекст для Playwright драйвера.

    """

    # Доступ до Playwright об'єктів ( ГОЛОВНЕ!)
    browser: Optional[Any] = None
    context: Optional[Any] = None
    page: Optional[Any] = None

    # Response дані
    response: Optional[Any] = None
    status_code: Optional[int] = None
    response_headers: Dict[str, str] = field(default_factory=dict)
    html: Optional[str] = None
    error: Optional[str] = None

    # Додаткові налаштування
    wait_selector: Optional[str] = None
    scroll_page: bool = False
    screenshot_path: Optional[str] = None
    timeout: int = 30000  # мілісекунди
