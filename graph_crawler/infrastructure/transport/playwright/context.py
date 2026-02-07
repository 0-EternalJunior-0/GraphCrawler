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
    from playwright.async_api import (
        Browser,
    )
    from playwright.async_api import BrowserContext as PWContext
    from playwright.async_api import (
        Page,
        Response,
    )
except ImportError:
    # Fallback якщо playwright не встановлено
    Browser = Any
    PWContext = Any
    Page = Any
    Response = Any


@dataclass
class BrowserContext(DriverContext):
    """
    Контекст для Playwright драйвера.

    Найважливіша особливість: доступ до browser, context та page!

    Attributes:
        url: URL для завантаження

        # Доступ до Playwright об'єктів ( ГОЛОВНЕ!)
        browser: Browser об'єкт
        context: BrowserContext об'єкт (тут stealth scripts!)
        page: Page об'єкт (тут все!)

        # Response дані
        response: Response об'єкт
        status_code: HTTP статус
        response_headers: Response headers
        html: HTML контент
        error: Повідомлення про помилку

        # Додаткові налаштування
        wait_selector: CSS селектор для очікування
        scroll_page: Чи прокручувати сторінку
        screenshot_path: Шлях для скріншоту

        # Для комунікації між плагінами
        data: Словник для передачі даних

    Приклад використання в плагіні:
        async def on_context_created(self, ctx: BrowserContext):
            # Інжектимо JavaScript
            await ctx.context.add_init_script("alert('Hello!')")
            return ctx

        async def on_content_ready(self, ctx: BrowserContext):
            # Виконуємо операції з page
            html = await ctx.page.content()
            title = await ctx.page.title()

            # Детектимо капчу
            captcha_el = await ctx.page.query_selector('.g-recaptcha')
            if captcha_el:
                ctx.emit('captcha_detected', captcha_type='recaptcha')

            return ctx
    """

    # Доступ до Playwright об'єктів ( ГОЛОВНЕ!)
    browser: Optional[Browser] = None
    context: Optional[PWContext] = None
    page: Optional[Page] = None

    # Response дані
    response: Optional[Response] = None
    status_code: Optional[int] = None
    response_headers: Dict[str, str] = field(default_factory=dict)
    html: Optional[str] = None
    error: Optional[str] = None

    # Додаткові налаштування
    wait_selector: Optional[str] = None
    scroll_page: bool = False
    screenshot_path: Optional[str] = None
    timeout: int = 30000  # мілісекунди
