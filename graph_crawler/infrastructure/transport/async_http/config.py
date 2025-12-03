"""Configuration for Async HTTP Driver."""

from dataclasses import dataclass

from graph_crawler.shared.constants import (
    DEFAULT_MAX_CONCURRENT_REQUESTS,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_USER_AGENT,
)


@dataclass
class AsyncDriverConfig:
    """
    Конфігурація для Async HTTP драйвера.

    Attributes:
        timeout: Таймаут запиту в секундах
        user_agent: User-Agent header
        max_concurrent_requests: Максимум одночасних запитів
        verify_ssl: Перевіряти SSL сертифікати
    """

    timeout: int = DEFAULT_REQUEST_TIMEOUT
    user_agent: str = DEFAULT_USER_AGENT
    max_concurrent_requests: int = DEFAULT_MAX_CONCURRENT_REQUESTS
    verify_ssl: bool = True

    def to_dict(self) -> dict:
        """Конвертує config в словник."""
        return {
            "timeout": self.timeout,
            "user_agent": self.user_agent,
            "max_concurrent_requests": self.max_concurrent_requests,
            "verify_ssl": self.verify_ssl,
        }
