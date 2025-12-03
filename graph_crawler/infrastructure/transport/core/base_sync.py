"""Базовий sync драйвер - для legacy та специфічних провайдерів.

Для випадків коли async неможливий:
- Legacy бібліотеки (старі версії Selenium)
- Специфічні API без async підтримки
- CLI інструменти

АРХІТЕКТУРНА РЕКОМЕНДАЦІЯ:
Якщо можливо - використовуйте async драйвери!
Sync драйвери блокують event loop.

v4.0: Нова архітектура
"""

import logging
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from graph_crawler.domain.events.event_bus import EventBus
from graph_crawler.domain.events.events import EventType
from graph_crawler.domain.value_objects.models import FetchResponse
from graph_crawler.infrastructure.transport.protocols import ISyncDriver
from graph_crawler.shared.utils.event_publisher_mixin import EventPublisherMixin

logger = logging.getLogger(__name__)


class BaseSyncDriver(EventPublisherMixin, ABC):
    """
    Базовий клас для sync драйверів (Template Method pattern).

     WARNING: Sync драйвери блокують виконання!
    Використовуйте async драйвери де можливо.

    Підкласи повинні реалізувати:
    - _do_fetch(url) - специфічна sync логіка
    - _do_close() - закриття ресурсів (опціонально)

    Example:
        >>> class LegacySeleniumDriver(BaseSyncDriver):
        ...     def _do_fetch(self, url: str) -> FetchResponse:
        ...         self.browser.get(url)
        ...         return FetchResponse(
        ...             url=url,
        ...             html=self.browser.page_source,
        ...             status_code=200,
        ...             headers={}
        ...         )
    """

    driver_name: str = "base_sync"

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        event_bus: Optional[EventBus] = None,
    ):
        self.config = config or {}
        self.event_bus = event_bus

    def fetch(self, url: str) -> FetchResponse:
        """
        Template Method: sync завантаження з загальною логікою.
        """
        start_time = time.time()

        self._publish_fetch_started(url)

        try:
            response = self._do_fetch(url)

            duration = time.time() - start_time
            self._publish_fetch_success(url, response.status_code, duration)

            return response

        except Exception as e:
            return self._handle_fetch_error(url, e, start_time)

    @abstractmethod
    def _do_fetch(self, url: str) -> FetchResponse:
        """Абстрактний: специфічна sync логіка."""
        pass

    def fetch_many(self, urls: List[str]) -> List[FetchResponse]:
        """
        Sync паралельне завантаження через ThreadPoolExecutor.

        Args:
            urls: Список URL

        Returns:
            Список FetchResponse
        """
        if not urls:
            return []

        max_workers = self.config.get("max_workers", 5)

        results = [None] * len(urls)  # Зберігаємо порядок

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Створюємо словник future -> index
            future_to_idx = {
                executor.submit(self.fetch, url): i for i, url in enumerate(urls)
            }

            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    results[idx] = self._create_error_response(
                        urls[idx], f"{type(e).__name__}: {e}"
                    )

        return results

    def supports_batch_fetching(self) -> bool:
        """Sync драйвери підтримують batch через threads."""
        return True

    def close(self) -> None:
        """Закриває драйвер."""
        self._do_close()

    def _do_close(self) -> None:
        """Опціональний: специфічна логіка закриття."""
        pass

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False

    # Event helpers (копія з async для консистентності)

    def _publish_fetch_started(self, url: str) -> None:
        self.publish_event(
            EventType.FETCH_STARTED, data={"url": url, "driver": self.driver_name}
        )

    def _publish_fetch_success(
        self, url: str, status_code: Optional[int], duration: float
    ) -> None:
        self.publish_event(
            EventType.FETCH_SUCCESS,
            data={
                "url": url,
                "status_code": status_code,
                "duration": round(duration, 3),
                "driver": self.driver_name,
            },
        )

    def _handle_fetch_error(
        self, url: str, exception: Exception, start_time: float
    ) -> FetchResponse:
        duration = time.time() - start_time
        error_msg = f"{type(exception).__name__}: {exception}"

        logger.error(f"Fetch error for {url}: {error_msg}")

        self.publish_event(
            EventType.FETCH_ERROR,
            data={
                "url": url,
                "error": str(exception),
                "error_type": type(exception).__name__,
                "duration": round(duration, 3),
                "driver": self.driver_name,
            },
        )

        return self._create_error_response(url, error_msg)

    def _create_error_response(self, url: str, error: str) -> FetchResponse:
        return FetchResponse(
            url=url, html=None, status_code=None, headers={}, error=error
        )
