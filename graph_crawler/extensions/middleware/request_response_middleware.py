"""Request/Response Middleware - універсальна обробка запитів та відповідей.

Функціонал:
- Модифікація headers запиту
- Додавання/видалення cookies
- Custom request transformations
- Response filtering та transformation
- Request/Response logging
- Header normalization
- Query parameters manipulation
"""

import json
import logging
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from graph_crawler.extensions.middleware.base import (
    BaseMiddleware,
    MiddlewareContext,
    MiddlewareType,
)

logger = logging.getLogger(__name__)


class RequestMiddleware(BaseMiddleware):
    """
    Middleware для модифікації HTTP запитів.

    Конфігурація:
        headers: Додаткові headers для всіх запитів (dict)
            Приклад: {"X-Custom-Header": "value"}

        cookies: Cookies для додавання до запитів (dict)
            Приклад: {"session_id": "abc123"}

        remove_headers: Список headers для видалення (list)
            Приклад: ["X-Forwarded-For", "Via"]

        query_params: Query параметри для додавання до URL (dict)
            Приклад: {"utm_source": "crawler"}

        normalize_headers: Нормалізувати headers (default: True)
            - Видаляє headers що видають bot
            - Додає стандартні browser headers

        custom_transform: Custom функція для трансформації request
            Callable[[MiddlewareContext], MiddlewareContext]

        log_requests: Логувати всі запити (default: False)

        max_url_length: Максимальна довжина URL (default: 2048)

    Приклади конфігурації:

    1. Додати custom headers:
        config = {
            "headers": {
                "X-API-Key": "secret_key",
                "X-Custom-Header": "value"
            }
        }

    2. Додати query параметри до всіх URL:
        config = {
            "query_params": {
                "utm_source": "bot",
                "key": "api_key"
            }
        }

    3. З логуванням:
        config = {
            "log_requests": True,
            "normalize_headers": True
        }
    """

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.request_count = 0
        self.transformed_count = 0

    @property
    def middleware_type(self) -> MiddlewareType:
        return MiddlewareType.PRE_REQUEST

    @property
    def name(self) -> str:
        return "request"

    def setup(self):
        """Ініціалізація middleware."""
        logger.info("Request Middleware initialized")

        if self.config.get("log_requests"):
            logger.info("Request logging enabled")

    def _normalize_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """
        Нормалізує headers для імітації справжнього браузера.

        Args:
            headers: Поточні headers

        Returns:
            Нормалізовані headers
        """
        normalized = headers.copy()

        # Видаляємо headers що видають bot
        bot_headers = [
            "X-Crawler",
            "X-Bot",
            "X-Spider",
            "X-Scraper",
            "Python-urllib",
            "Python-requests",
        ]

        for header in bot_headers:
            normalized.pop(header, None)

        # Додаємо стандартні browser headers якщо відсутні
        if "Accept" not in normalized:
            normalized["Accept"] = (
                "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            )

        if "Accept-Language" not in normalized:
            normalized["Accept-Language"] = "en-US,en;q=0.9"

        if "Accept-Encoding" not in normalized:
            normalized["Accept-Encoding"] = "gzip, deflate, br"

        if "Connection" not in normalized:
            normalized["Connection"] = "keep-alive"

        return normalized

    def _add_query_params(self, url: str, params: Dict[str, str]) -> str:
        """
        Додає query параметри до URL.

        Args:
            url: Оригінальний URL
            params: Параметри для додавання

        Returns:
            URL з доданими параметрами
        """
        parsed = urlparse(url)
        query_dict = parse_qs(parsed.query)

        # Додаємо нові параметри
        for key, value in params.items():
            if key not in query_dict:
                query_dict[key] = [value]

        # Перетворюємо назад в query string
        new_query = urlencode(query_dict, doseq=True)

        # Створюємо новий URL
        new_url = urlunparse(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                new_query,
                parsed.fragment,
            )
        )

        return new_url

    def _validate_url(self, url: str) -> bool:
        """
        Валідує URL.

        Args:
            url: URL для перевірки

        Returns:
            True якщо URL валідний
        """
        max_length = self.config.get("max_url_length", 2048)

        if len(url) > max_length:
            logger.warning(f"URL too long ({len(url)} > {max_length}): {url[:100]}...")
            return False

        parsed = urlparse(url)

        if not parsed.scheme or not parsed.netloc:
            logger.warning(f"Invalid URL structure: {url}")
            return False

        return True

    def process(self, context: MiddlewareContext) -> MiddlewareContext:
        """
        Обробляє запит.

        Args:
            context: Контекст запиту

        Returns:
            Оновлений контекст
        """
        self.request_count += 1

        # Валідація URL
        if not self._validate_url(context.url):
            context.skip_request = True
            return context

        # Додаємо custom headers
        custom_headers = self.config.get("headers", {})
        if custom_headers:
            context.headers.update(custom_headers)
            self.transformed_count += 1

        # Видаляємо headers
        remove_headers = self.config.get("remove_headers", [])
        for header in remove_headers:
            context.headers.pop(header, None)

        # Нормалізуємо headers
        if self.config.get("normalize_headers", True):
            context.headers = self._normalize_headers(context.headers)

        # Додаємо cookies
        cookies = self.config.get("cookies", {})
        if cookies:
            # Зберігаємо cookies в metadata для драйвера
            context.metadata["cookies"] = cookies

        # Додаємо query параметри
        query_params = self.config.get("query_params", {})
        if query_params:
            context.url = self._add_query_params(context.url, query_params)
            self.transformed_count += 1

        # Custom transformation
        custom_transform = self.config.get("custom_transform")
        if custom_transform and callable(custom_transform):
            context = custom_transform(context)
            self.transformed_count += 1

        # Логування
        if self.config.get("log_requests"):
            logger.info(
                f"Request #{self.request_count}: {context.url} "
                f"(headers: {len(context.headers)})"
            )

        # Додаємо метадані
        context.metadata["request_middleware"] = {
            "processed": True,
            "request_count": self.request_count,
            "transformed": self.transformed_count > 0,
        }

        return context

    def get_stats(self) -> Dict[str, Any]:
        """
        Повертає статистику.

        Returns:
            Словник зі статистикою
        """
        return {
            "request_count": self.request_count,
            "transformed_count": self.transformed_count,
            "transformation_rate": (
                self.transformed_count / self.request_count
                if self.request_count > 0
                else 0.0
            ),
        }


class ResponseMiddleware(BaseMiddleware):
    """
    Middleware для обробки HTTP відповідей.

    Конфігурація:
        filter_status_codes: Список статус кодів для фільтрації (list)
            Приклад: [404, 500] - пропустити ці статуси

        min_content_length: Мінімальна довжина контенту (int)
            Відповіді коротші цього будуть відхилені

        max_content_length: Максимальна довжина контенту (int)
            Відповіді довші цього будуть обрізані

        extract_cookies: Зберігати cookies з відповіді (default: True)

        follow_redirects: Автоматично слідувати за редіректами (default: True)

        max_redirects: Максимум редіректів (default: 10)

        custom_transform: Custom функція для трансформації response
            Callable[[MiddlewareContext], MiddlewareContext]

        log_responses: Логувати всі відповіді (default: False)

        validate_html: Перевіряти валідність HTML (default: False)

        save_failed_responses: Зберігати відповіді з помилками (default: False)

    Приклади конфігурації:

    1. Фільтрувати помилки:
        config = {
            "filter_status_codes": [404, 500, 503],
            "min_content_length": 100
        }

    2. З логуванням:
        config = {
            "log_responses": True,
            "extract_cookies": True
        }

    3. Обмеження розміру:
        config = {
            "max_content_length": 1024 * 1024,  # 1MB
            "validate_html": True
        }
    """

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.response_count = 0
        self.filtered_count = 0
        self.error_count = 0
        self.status_code_stats: Dict[int, int] = {}

    @property
    def middleware_type(self) -> MiddlewareType:
        return MiddlewareType.POST_REQUEST

    @property
    def name(self) -> str:
        return "response"

    def setup(self):
        """Ініціалізація middleware."""
        logger.info("Response Middleware initialized")

        if self.config.get("log_responses"):
            logger.info("Response logging enabled")

    def _should_filter(self, context: MiddlewareContext) -> bool:
        """
        Перевіряє чи потрібно фільтрувати відповідь.

        Args:
            context: Контекст з відповіддю

        Returns:
            True якщо відповідь потрібно відфільтрувати
        """
        # Фільтрувати за статус кодом
        filter_codes = self.config.get("filter_status_codes", [])
        if context.status_code in filter_codes:
            logger.debug(f"Filtering response with status code {context.status_code}")
            return True

        # Фільтрувати за довжиною контенту
        if context.html:
            content_length = len(context.html)

            min_length = self.config.get("min_content_length")
            if min_length and content_length < min_length:
                logger.debug(f"Content too short ({content_length} < {min_length})")
                return True

            max_length = self.config.get("max_content_length")
            if max_length and content_length > max_length:
                logger.debug(f"Content too long ({content_length} > {max_length})")
                # Обрізаємо замість фільтрації
                context.html = context.html[:max_length]
                logger.info(f"Content truncated to {max_length} bytes")

        return False

    def _validate_html(self, html: str) -> bool:
        """
        Валідує HTML контент.

        Args:
            html: HTML для перевірки

        Returns:
            True якщо HTML валідний
        """
        if not html:
            return False

        # Базова перевірка HTML структури
        html_lower = html.lower()

        # Перевіряємо наявність базових тегів
        has_html_tag = "<html" in html_lower or "<!doctype" in html_lower
        has_body = "<body" in html_lower

        # Якщо це не HTML документ - може бути JSON або XML
        is_json = html.strip().startswith("{") or html.strip().startswith("[")
        is_xml = html.strip().startswith("<?xml")

        if not (has_html_tag or is_json or is_xml):
            logger.warning("Response doesn't appear to be valid HTML/JSON/XML")
            return False

        return True

    def _extract_cookies(self, context: MiddlewareContext) -> Dict[str, str]:
        """
        Витягує cookies з відповіді.

        Args:
            context: Контекст з відповіддю

        Returns:
            Словник з cookies
        """
        cookies = {}

        # Витягуємо з headers
        set_cookie_headers = context.headers.get("Set-Cookie", "")
        if set_cookie_headers:
            # Простий парсинг (для складних випадків використовувати http.cookies)
            for cookie_str in set_cookie_headers.split(";"):
                if "=" in cookie_str:
                    key, value = cookie_str.split("=", 1)
                    cookies[key.strip()] = value.strip()

        return cookies

    def process(self, context: MiddlewareContext) -> MiddlewareContext:
        """
        Обробляє відповідь.

        Args:
            context: Контекст з відповіддю

        Returns:
            Оновлений контекст
        """
        self.response_count += 1

        # Оновлюємо статистику статус кодів
        if context.status_code:
            self.status_code_stats[context.status_code] = (
                self.status_code_stats.get(context.status_code, 0) + 1
            )

        # Перевіряємо помилки
        if context.error:
            self.error_count += 1

            if self.config.get("save_failed_responses"):
                # Зберігаємо в metadata для подальшого аналізу
                context.metadata["failed_response"] = {
                    "error": str(context.error),
                    "url": context.url,
                    "status_code": context.status_code,
                }

        # Фільтруємо відповідь якщо потрібно
        if self._should_filter(context):
            self.filtered_count += 1
            context.skip_request = True  # Марк для пропуску
            return context

        # Валідація HTML
        if self.config.get("validate_html") and context.html:
            if not self._validate_html(context.html):
                logger.warning(f"Invalid HTML response from {context.url}")
                context.metadata["html_valid"] = False
            else:
                context.metadata["html_valid"] = True

        # Витягуємо cookies
        if self.config.get("extract_cookies", True):
            cookies = self._extract_cookies(context)
            if cookies:
                context.metadata["response_cookies"] = cookies

        # Custom transformation
        custom_transform = self.config.get("custom_transform")
        if custom_transform and callable(custom_transform):
            context = custom_transform(context)

        # Логування
        if self.config.get("log_responses"):
            content_length = len(context.html) if context.html else 0
            logger.info(
                f"Response #{self.response_count}: {context.url} "
                f"(status: {context.status_code}, size: {content_length} bytes)"
            )

        # Додаємо метадані
        context.metadata["response_middleware"] = {
            "processed": True,
            "response_count": self.response_count,
            "filtered": context.skip_request,
        }

        return context

    def get_stats(self) -> Dict[str, Any]:
        """
        Повертає статистику.

        Returns:
            Словник зі статистикою
        """
        return {
            "response_count": self.response_count,
            "filtered_count": self.filtered_count,
            "error_count": self.error_count,
            "filter_rate": (
                self.filtered_count / self.response_count
                if self.response_count > 0
                else 0.0
            ),
            "error_rate": (
                self.error_count / self.response_count
                if self.response_count > 0
                else 0.0
            ),
            "status_codes": self.status_code_stats,
        }
