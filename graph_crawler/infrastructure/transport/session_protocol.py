"""
HTTP Session Protocol - абстракція для HTTP session.

Dependency Inversion Principle
- Protocol замість прямої залежності від requests.Session
- Можливість підключення різних HTTP бібліотек (httpx, aiohttp, etc.)
"""

from typing import Any, Dict, Optional, Protocol

from requests import Response


class IHttpSession(Protocol):
    """
    Інтерфейс для HTTP session.

    Дозволяє підключити різні HTTP бібліотеки через адаптери,
    дотримуючись Dependency Inversion Principle.

    Приклад використання:
        >>> from graph_crawler.infrastructure.transport.session_adapters import RequestsSessionAdapter
        >>> session = RequestsSessionAdapter()
        >>> response = session.get("https://example.com")
        >>> session.close()
    """

    def get(self, url: str, **kwargs) -> Response:
        """
        Виконує GET запит.

        Args:
            url: URL для запиту
            **kwargs: Додаткові параметри (timeout, headers, etc.)

        Returns:
            Response об'єкт
        """
        ...

    def post(self, url: str, **kwargs) -> Response:
        """
        Виконує POST запит.

        Args:
            url: URL для запиту
            **kwargs: Додаткові параметри (data, json, headers, etc.)

        Returns:
            Response об'єкт
        """
        ...

    def close(self) -> None:
        """Закриває session та звільняє ресурси."""
        ...

    def add_headers(self, headers: Dict[str, str]) -> None:
        """
        Додає або оновлює headers для session.

        Args:
            headers: Словник з headers
        """
        ...

    def mount(self, prefix: str, adapter: Any) -> None:
        """
        Монтує адаптер для певного префіксу URL.

        Args:
            prefix: URL префікс (наприклад, "https://")
            adapter: HTTP адаптер
        """
        ...
