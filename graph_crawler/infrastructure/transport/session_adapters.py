"""
Session Adapters - адаптери для різних HTTP бібліотек.

Dependency Inversion Principle
- RequestsSessionAdapter - адаптер для requests
- Можливість додати адаптери для httpx, aiohttp, etc.
"""

from typing import Any, Dict

import requests
from requests import Response
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from graph_crawler.shared.constants import (
    DEFAULT_CONNECTION_POOL_SIZE,
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_BACKOFF_FACTOR,
    DEFAULT_USER_AGENT,
    HTTP_METHODS_SAFE,
    HTTP_RETRYABLE_STATUS_CODES,
)

OPTIMIZED_POOL_SIZE = 100


class RequestsSessionAdapter:
    """
    Адаптер для requests.Session.

    Реалізує IHttpSession Protocol
    Інкапсулює всю логіку роботи з requests
    Дозволяє замінити на інший HTTP клієнт без зміни HTTPDriver

    Приклад:
        >>> adapter = RequestsSessionAdapter(
        ...     user_agent="MyBot/1.0",
        ...     max_retries=5,
        ...     pool_size=20
        ... )
        >>> response = adapter.get("https://example.com", timeout=10)
        >>> adapter.close()
    """

    def __init__(
        self,
        user_agent: str = DEFAULT_USER_AGENT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        pool_size: int = OPTIMIZED_POOL_SIZE,  # Оптимізовано: 100 замість 10
        **kwargs,
    ):
        """
        Ініціалізує адаптер з налаштуванням retry та connection pooling.

        Args:
            user_agent: User-Agent заголовок
            max_retries: Максимальна кількість повторів
            pool_size: Розмір connection pool (default: 100)
            **kwargs: Додаткові параметри
        """
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": user_agent})

        # Connection pooling + retry strategy
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=DEFAULT_RETRY_BACKOFF_FACTOR,
            status_forcelist=HTTP_RETRYABLE_STATUS_CODES,
            allowed_methods=HTTP_METHODS_SAFE,
        )

        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=pool_size,
            pool_maxsize=pool_size,
        )

        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)

    def get(self, url: str, **kwargs) -> Response:
        """
        Виконує GET запит.

        Args:
            url: URL для запиту
            **kwargs: Параметри запиту (timeout, headers, etc.)

        Returns:
            Response об'єкт
        """
        return self._session.get(url, **kwargs)

    def post(self, url: str, **kwargs) -> Response:
        """
        Виконує POST запит.

        Args:
            url: URL для запиту
            **kwargs: Параметри запиту (data, json, headers, etc.)

        Returns:
            Response об'єкт
        """
        return self._session.post(url, **kwargs)

    def close(self) -> None:
        """Закриває session та звільняє ресурси."""
        self._session.close()

    def add_headers(self, headers: Dict[str, str]) -> None:
        """
        Додає або оновлює headers.

        Args:
            headers: Словник з headers
        """
        self._session.headers.update(headers)

    def mount(self, prefix: str, adapter: Any) -> None:
        """
        Монтує адаптер для певного префіксу URL.

        Args:
            prefix: URL префікс (наприклад, "https://")
            adapter: HTTP адаптер
        """
        self._session.mount(prefix, adapter)

    def __enter__(self):
        """Context manager support."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup."""
        self.close()
