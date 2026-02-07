"""Контекст для Async HTTP драйвера.

Аналогічно HTTPContext, але з aiohttp.ClientSession.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import aiohttp

from graph_crawler.infrastructure.transport.context import DriverContext


@dataclass
class AsyncHTTPContext(DriverContext):
    """
    Контекст для Async HTTP драйвера (aiohttp).

    Attributes:
        url: URL для запиту
        method: HTTP метод
        headers: HTTP headers
        cookies: Cookies
        params: Query parameters
        body: Request body
        session: aiohttp.ClientSession об'єкт (доступ!)
        timeout: Timeout

        # Після відповіді:
        response: aiohttp.ClientResponse
        status_code: HTTP статус
        response_headers: Response headers
        html: HTML контент
        error: Повідомлення про помилку
    """

    # Request параметри
    method: str = "GET"
    headers: Dict[str, str] = field(default_factory=dict)
    cookies: Dict[str, str] = field(default_factory=dict)
    params: Dict[str, Any] = field(default_factory=dict)
    body: Optional[Any] = None
    timeout: int = 30

    # Доступ до внутрішніх об'єктів
    session: Optional[aiohttp.ClientSession] = None

    # Response дані
    response: Optional[aiohttp.ClientResponse] = None
    status_code: Optional[int] = None
    response_headers: Dict[str, str] = field(default_factory=dict)
    html: Optional[str] = None
    error: Optional[str] = None
