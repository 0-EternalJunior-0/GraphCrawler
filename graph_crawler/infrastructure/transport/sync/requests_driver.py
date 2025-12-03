"""Sync HTTP драйвер на основі requests (для legacy).

 WARNING: Використовуйте AsyncDriver де можливо!
Sync драйвери блокують виконання.

Цей драйвер для випадків коли:
- Потрібна сумісність з sync кодом
- Використовуються legacy бібліотеки
- CLI інструменти

v4.0: Нова архітектура
"""

import logging
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from graph_crawler.domain.events.event_bus import EventBus
from graph_crawler.domain.value_objects.models import FetchResponse
from graph_crawler.infrastructure.transport.core.base_sync import BaseSyncDriver
from graph_crawler.infrastructure.transport.core.mixins import RetryMixin
from graph_crawler.shared.constants import (
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_USER_AGENT,
)

logger = logging.getLogger(__name__)


class RequestsDriver(BaseSyncDriver, RetryMixin):
    """
    Sync HTTP драйвер на основі requests.

     WARNING: БЛОКУЄ виконання! Використовуйте AsyncDriver.

    Example:
        >>> # Тільки для legacy коду!
        >>> with RequestsDriver() as driver:
        ...     response = driver.fetch('https://example.com')
    """

    driver_name = "requests"

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        event_bus: Optional[EventBus] = None,
    ):
        super().__init__(config, event_bus)

        self._timeout = self.config.get("timeout", DEFAULT_REQUEST_TIMEOUT)
        self._user_agent = self.config.get("user_agent", DEFAULT_USER_AGENT)
        self._max_retries = self.config.get("max_retries", 3)

        # Створюємо session з retry
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": self._user_agent})

        # Налаштовуємо retry
        retry_strategy = Retry(
            total=self._max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)

        logger.info(
            f"RequestsDriver initialized: timeout={self._timeout}s, "
            f"max_retries={self._max_retries}"
        )

    def _do_fetch(self, url: str) -> FetchResponse:
        """
        Sync завантаження через requests.
        """
        response = self._session.get(url, timeout=self._timeout)

        return FetchResponse(
            url=url,
            html=response.text,
            status_code=response.status_code,
            headers=dict(response.headers),
            error=None,
        )

    def _do_close(self) -> None:
        """Закриває requests session."""
        if self._session:
            self._session.close()
        logger.info("RequestsDriver closed")
