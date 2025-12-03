"""Logging Middleware - логування запитів."""

import logging
import time

from graph_crawler.extensions.middleware.base import (
    BaseMiddleware,
    MiddlewareContext,
    MiddlewareType,
)
from graph_crawler.shared.constants import HTTP_CLIENT_ERROR_START

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseMiddleware):
    """
    Middleware для логування запитів.

    Логує:
    - URL запитів
    - Status code
    - Час виконання
    - Помилки

    Конфіг:
        log_level: Рівень логування (default: INFO)
        log_response: Логувати відповіді (default: True)
        log_timing: Логувати час виконання (default: True)
    """

    def __init__(self, config: dict = None):
        super().__init__(config)
        self.start_times = {}  # URL -> час початку

        # Налаштування рівня логування
        log_level = self.config.get("log_level", "INFO")
        logger.setLevel(getattr(logging, log_level))

    @property
    def middleware_type(self) -> MiddlewareType:
        return MiddlewareType.PRE_REQUEST

    @property
    def name(self) -> str:
        return "logging"

    def process(self, context: MiddlewareContext) -> MiddlewareContext:
        """
        Логує запит та зберігає час початку.

        Args:
            context: Контекст запиту

        Returns:
            Оновлений контекст
        """
        url = context.url

        # Зберігаємо час початку
        if self.config.get("log_timing", True):
            self.start_times[url] = time.time()

        # Логуємо запит
        logger.info(f"→ Fetching: {url}")

        return context

    def process_response(self, response: dict, **kwargs) -> dict:
        """
        Логує відповідь.

        Args:
            response: Відповідь від драйвера
            **kwargs: Додаткові параметри (url, etc.)

        Returns:
            Відповідь без змін
        """
        if not self.config.get("log_response", True):
            return response

        url = response.get("url", kwargs.get("url", "unknown"))
        status_code = response.get("status_code")
        error = response.get("error")

        # Розраховуємо час виконання
        elapsed = None
        if url in self.start_times and self.config.get("log_timing", True):
            elapsed = time.time() - self.start_times[url]
            del self.start_times[url]

        # Логуємо результат
        if error:
            logger.error(f"← Error: {url} - {error}")
        elif status_code:
            timing_str = f" ({elapsed:.2f}s)" if elapsed else ""
            if status_code >= HTTP_CLIENT_ERROR_START:
                logger.warning(f"← Response: {url} - {status_code}{timing_str}")
            else:
                logger.info(f"← Response: {url} - {status_code}{timing_str}")

        return response
