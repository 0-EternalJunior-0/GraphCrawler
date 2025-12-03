"""Етапи (stages) для Playwright драйвера.

Найскладніший lifecycle з багатьма етапами:
- Browser lifecycle (launch, close)
- Context lifecycle (create, close)
- Page lifecycle (create, navigate, close)
- Content loading (wait, scroll)
- Screenshots
"""

from enum import Enum


class BrowserStage(str, Enum):
    """
    Етапи виконання Playwright драйвера.

    Lifecycle Playwright драйвера складається з кількох рівнів:

    1. BROWSER LIFECYCLE:
       - browser_launching: перед запуском браузера
       - browser_launched: браузер запущено

    2. CONTEXT LIFECYCLE:
       - context_creating: перед створенням context
       - context_created: context створено (тут stealth scripts!)

    3. PAGE LIFECYCLE:
       - page_creating: перед створенням page
       - page_created: page створено

    4. NAVIGATION:
       - navigation_starting: перед page.goto()
       - navigation_completed: після page.goto()

    5. CONTENT:
       - waiting_for_selector: очікування елемента
       - scrolling: прокручування сторінки
       - content_ready: контент готовий (тут детект капчі!)

    6. SCREENSHOT:
       - before_screenshot: перед скріншотом
       - after_screenshot: після скріншоту

    7. CLEANUP:
       - page_closing: закриття page
       - context_closing: закриття context

    Приклад використання:
        class StealthPlugin(BaseDriverPlugin):
            def get_hooks(self):
                return [BrowserStage.CONTEXT_CREATED]

            async def on_context_created(self, ctx: BrowserContext):
                # Інжектимо stealth scripts
                await ctx.context.add_init_script(self.stealth_js)
                return ctx

        class CaptchaDetectorPlugin(BaseDriverPlugin):
            def get_hooks(self):
                return [BrowserStage.CONTENT_READY]

            async def on_content_ready(self, ctx: BrowserContext):
                # Детектимо капчу
                if await self._detect_captcha(ctx.page):
                    ctx.emit('captcha_detected', captcha_type='recaptcha')
                return ctx
    """

    # === BROWSER LIFECYCLE ===
    BROWSER_LAUNCHING = "browser_launching"
    BROWSER_LAUNCHED = "browser_launched"

    # === CONTEXT LIFECYCLE ===
    CONTEXT_CREATING = "context_creating"
    CONTEXT_CREATED = "context_created"  #  Stealth scripts інжектяться тут

    # === PAGE LIFECYCLE ===
    PAGE_CREATING = "page_creating"
    PAGE_CREATED = "page_created"

    # === NAVIGATION ===
    NAVIGATION_STARTING = "navigation_starting"
    NAVIGATION_COMPLETED = "navigation_completed"

    # === CONTENT ===
    WAITING_FOR_SELECTOR = "waiting_for_selector"
    SCROLLING = "scrolling"
    CONTENT_READY = "content_ready"  #  CAPTCHA detection тут

    # === SCREENSHOT ===
    BEFORE_SCREENSHOT = "before_screenshot"
    AFTER_SCREENSHOT = "after_screenshot"

    # === CLEANUP ===
    PAGE_CLOSING = "page_closing"
    CONTEXT_CLOSING = "context_closing"
