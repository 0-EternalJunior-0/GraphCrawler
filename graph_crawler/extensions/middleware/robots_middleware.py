"""Middleware для перевірки robots.txt перед сканування.

Використовує RobotsCache та RobotsValidator (композиція).
"""

import logging

from graph_crawler.extensions.middleware.base import (
    BaseMiddleware,
    MiddlewareContext,
    MiddlewareType,
)
from graph_crawler.extensions.middleware.robots_cache import RobotsCache
from graph_crawler.extensions.middleware.robots_validator import RobotsValidator

logger = logging.getLogger(__name__)


class RobotsTxtMiddleware(BaseMiddleware):
    """
    Middleware для перевірки дозволів robots.txt.

        Координує роботу RobotsCache (кешування) та RobotsValidator (валідація).
        Перевіряє чи дозволено сканувати URL перед запитом.

        Приклад використання:
            >>> from graph_crawler.middleware import RobotsTxtMiddleware, MiddlewareContext
            >>> middleware = RobotsTxtMiddleware(user_agent="GraphCrawler/0.1.0")
            >>> context = MiddlewareContext(url="https://example.com/page")
            >>> try:
            >>>     context = middleware.process(context)
            >>> except URLBlockedError:
            >>>     print("Blocked by robots.txt")
    """

    def __init__(self, user_agent: str = "GraphCrawler/0.1.0"):
        """
        Ініціалізація middleware.

        Args:
            user_agent: User-Agent для перевірки правил
        """
        super().__init__()
        self.cache = RobotsCache()
        self.validator = RobotsValidator(user_agent=user_agent)

    @property
    def middleware_type(self) -> MiddlewareType:
        """Тип middleware - виконується перед запитом."""
        return MiddlewareType.PRE_REQUEST

    @property
    def name(self) -> str:
        """Назва middleware."""
        return "RobotsTxtMiddleware"

    def process(self, context: MiddlewareContext) -> MiddlewareContext:
        """
        Обробляє контекст: перевіряє robots.txt.

        Args:
            context: Контекст з URL

        Returns:
            Оновлений контекст

        Raises:
            URLBlockedError: Якщо URL заблокований robots.txt
        """
        from graph_crawler.shared.utils.url_utils import URLUtils

        url = context.url
        domain = URLUtils.get_domain(url)

        # Отримати parser з кешу (автоматично завантажує якщо потрібно)
        parser = self.cache.get_parser(domain)

        # Валідувати URL (викидає URLBlockedError якщо заблокований)
        self.validator.validate(parser, url)

        # Зберегти дані у контекст
        context.middleware_data["robots_txt"] = {"allowed": True, "domain": domain}
        return context

    def check_url(self, url: str) -> bool:
        """
        HELPER: Перевіряє чи дозволено сканувати URL.

        Args:
            url: URL для перевірки

        Returns:
            True якщо дозволено, False якщо заблокований

        Raises:
            URLBlockedError: Якщо URL заблокований robots.txt
        """
        from graph_crawler.shared.utils.url_utils import URLUtils

        domain = URLUtils.get_domain(url)
        parser = self.cache.get_parser(domain)
        self.validator.validate(parser, url)
        return True

    def process_response(self, response: dict, **kwargs) -> dict:
        """Обробка відповіді (не використовується для robots.txt)."""
        return response
