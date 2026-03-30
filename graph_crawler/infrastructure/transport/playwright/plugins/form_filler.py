"""
Form Filler плагін для Playwright драйвера.

Автоматично заповнює форми на сторінці:
- Login форми
- Search форми
- Кастомні форми
"""

import logging
from typing import Any, Dict, List, Optional

from graph_crawler.infrastructure.transport.base_plugin import BaseDriverPlugin
from graph_crawler.infrastructure.transport.playwright.context import BrowserContext
from graph_crawler.infrastructure.transport.playwright.stages import BrowserStage

logger = logging.getLogger(__name__)


class FormFillerPlugin(BaseDriverPlugin):
    """
    Плагін для автоматичного заповнення форм.

    """

    @property
    def name(self) -> str:
        return "form_filler"

    def get_hooks(self) -> List[str]:
        return [BrowserStage.CONTENT_READY]

    def get_events(self) -> List[str]:
        # Підписуємось на подію login_required від інших плагінів
        return ["login_required", "fill_form_request"]

    async def _fill_form(self, page, form_config: Dict[str, Any], ctx: BrowserContext) -> bool:
        """
        Заповнює форму згідно з конфігурацією.

        Args:
            page: Playwright page
            form_config: Конфігурація форми
            ctx: Browser контекст

        Returns:
            True якщо форму заповнено
        """
        form_selector = form_config.get("selector")
        fields = form_config.get("fields", {})
        typing_delay = self.config.get("typing_delay", 50)

        try:
            # Перевіряємо наявність форми
            if form_selector:
                form = await page.query_selector(form_selector)
                if not form:
                    logger.debug("Form not found: %s", form_selector)
                    return False

            logger.info("Filling form: %s", form_selector or 'default')
            ctx.emit("form_found", form_selector=form_selector)

            # Заповнюємо поля
            for field_selector, value in fields.items():
                try:
                    field = await page.query_selector(field_selector)
                    if field:
                        await field.click()
                        await field.fill("")  # Очищаємо
                        await field.type(value, delay=typing_delay)
                        logger.debug("Filled field %s", field_selector)
                    else:
                        logger.warning("Field not found: %s", field_selector)
                except Exception as e:
                    logger.error("Error filling field %s: %s", field_selector, e)

            ctx.emit("form_filled", form_selector=form_selector)
            ctx.data["form_filled"] = True

            # Відправляємо форму якщо потрібно
            if self.config.get("auto_submit", False):
                submit_selector = form_config.get("submit")
                if submit_selector:
                    submit_btn = await page.query_selector(submit_selector)
                    if submit_btn:
                        await submit_btn.click()
                        logger.info("Form submitted via %s", submit_selector)
                        ctx.emit("form_submitted", form_selector=form_selector)
                        ctx.data["form_submitted"] = True

                        # Очікуємо навігацію
                        await page.wait_for_load_state("networkidle", timeout=10000)

            return True

        except Exception as e:
            logger.error("Error filling form: %s", e)
            ctx.errors.append(e)
            return False

    async def on_content_ready(self, ctx: BrowserContext) -> BrowserContext:
        """
        Перевіряє та заповнює форми.

        Args:
            ctx: Browser контекст

        Returns:
            Оновлений контекст
        """
        if not ctx.page:
            return ctx

        forms_config = self.config.get("forms", {})

        if not forms_config:
            return ctx

        try:
            # Перевіряємо всі налаштовані форми
            for form_name, form_config in forms_config.items():
                form_selector = form_config.get("selector")

                if form_selector:
                    form = await ctx.page.query_selector(form_selector)
                    if form:
                        logger.info("Found form '%s' on %s", form_name, ctx.url)
                        await self._fill_form(ctx.page, form_config, ctx)
                        break  # Заповнюємо першу знайдену

        except Exception as e:
            logger.error("Error in form filler: %s", e)
            ctx.errors.append(e)

        return ctx

    async def on_login_required(self, ctx: BrowserContext, **event_data):
        """
        Обробник події login_required.

        Args:
            ctx: Browser контекст
            **event_data: Дані події
        """
        if not ctx.page:
            return

        forms_config = self.config.get("forms", {})
        login_form = forms_config.get("login")

        if login_form:
            logger.info("Login required event received, attempting login...")
            await self._fill_form(ctx.page, login_form, ctx)

    async def on_fill_form_request(self, ctx: BrowserContext, form_name: Optional[str] = None, **event_data):
        """
        Обробник запиту на заповнення форми.

        Args:
            ctx: Browser контекст
            form_name: Назва форми для заповнення
            **event_data: Додаткові дані
        """
        if not ctx.page or not form_name:
            return

        forms_config = self.config.get("forms", {})
        form_config = forms_config.get(form_name)

        if form_config:
            logger.info("Fill form request for '%s'", form_name)
            await self._fill_form(ctx.page, form_config, ctx)
