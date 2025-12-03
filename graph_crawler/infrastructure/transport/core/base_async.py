"""Базовий async драйвер - Template Method pattern.

Шаблонний клас для всіх async драйверів:
- AioHTTP driver
- Playwright driver
- Майбутні async драйвери

Template Method забезпечує:
- Загальна логіка (events, error handling) в базовому класі
- Специфічна логіка (_do_fetch) в підкласах

v4.0: Нова архітектура з чітким розділенням
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from graph_crawler.domain.events.event_bus import EventBus
from graph_crawler.domain.events.events import EventType
from graph_crawler.domain.value_objects.models import FetchResponse
from graph_crawler.infrastructure.transport.protocols import IAsyncDriver
from graph_crawler.shared.utils.event_publisher_mixin import EventPublisherMixin

logger = logging.getLogger(__name__)


class BaseAsyncDriver(EventPublisherMixin, ABC):
    """
    Базовий клас для всіх async драйверів (Template Method pattern).

    Реалізує IAsyncDriver Protocol через:
    - fetch() - Template Method з загальною логікою
    - _do_fetch() - Abstract Method для специфічної реалізації

    Забезпечує:
    - Публікацію подій (FETCH_STARTED, FETCH_SUCCESS, FETCH_ERROR)
    - Error handling з FetchResponse
    - Async context manager
    - Дефолтний fetch_many через asyncio.gather

    Підкласи повинні реалізувати:
    - _do_fetch(url) - специфічна логіка завантаження
    - _do_close() - специфічна логіка закриття (опціонально)

    Example:
        >>> class MyAsyncDriver(BaseAsyncDriver):
        ...     async def _do_fetch(self, url: str) -> FetchResponse:
        ...         # Специфічна логіка
        ...         async with aiohttp.ClientSession() as session:
        ...             async with session.get(url) as response:
        ...                 html = await response.text()
        ...                 return FetchResponse(
        ...                     url=url, html=html,
        ...                     status_code=response.status,
        ...                     headers=dict(response.headers)
        ...                 )
    """

    # Назва драйвера для логів та подій
    driver_name: str = "base_async"

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        event_bus: Optional[EventBus] = None,
    ):
        """
        Ініціалізує базовий async драйвер.

        Args:
            config: Конфігурація драйвера
            event_bus: EventBus для подій (опціонально)
        """
        self.config = config or {}
        self.event_bus = event_bus

    # ==================== Template Method ====================

    async def fetch(self, url: str) -> FetchResponse:
        """
        Template Method: завантажує сторінку з загальною логікою.

        Порядок виконання:
        1. Публікує FETCH_STARTED
        2. Викликає _do_fetch() (абстрактний)
        3. Публікує FETCH_SUCCESS або FETCH_ERROR
        4. Повертає FetchResponse

        Args:
            url: URL для завантаження

        Returns:
            FetchResponse з результатом
        """
        start_time = time.time()

        # 1. Event: FETCH_STARTED
        self._publish_fetch_started(url)

        try:
            # 2. Викликаємо специфічну реалізацію
            response = await self._do_fetch(url)

            # 3. Event: FETCH_SUCCESS
            duration = time.time() - start_time
            self._publish_fetch_success(url, response.status_code, duration)

            return response

        except Exception as e:
            # 3. Event: FETCH_ERROR + error response
            return self._handle_fetch_error(url, e, start_time)

    @abstractmethod
    async def _do_fetch(self, url: str) -> FetchResponse:
        """
        Абстрактний метод: специфічна логіка завантаження.

        Підкласи ПОВИННІ реалізувати цей метод.

        Args:
            url: URL для завантаження

        Returns:
            FetchResponse з результатом

        Raises:
            Exception: При помилці (буде оброблено в fetch())
        """
        pass

    # ==================== Batch Fetching ====================

    async def fetch_many(self, urls: List[str]) -> List[FetchResponse]:
        """
        Async паралельне завантаження через asyncio.gather.

        Підкласи можуть перевизначити для оптимізації
        (наприклад, з semaphore для обмеження concurrency).

        Args:
            urls: Список URL

        Returns:
            Список FetchResponse (в тому ж порядку)
        """
        if not urls:
            return []

        tasks = [self.fetch(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Конвертуємо exceptions в FetchResponse
        processed = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed.append(
                    self._create_error_response(
                        urls[i], f"{type(result).__name__}: {result}"
                    )
                )
            else:
                processed.append(result)

        return processed

    def supports_batch_fetching(self) -> bool:
        """Всі async драйвери підтримують batch fetching."""
        return True

    # ==================== Resource Management ====================

    async def close(self) -> None:
        """
        Закриває драйвер та ресурси.

        Викликає _do_close() якщо реалізовано в підкласі.
        """
        await self._do_close()

    async def _do_close(self) -> None:
        """
        Опціональний метод: специфічна логіка закриття.

        Підкласи можуть перевизначити для закриття сесій, браузерів тощо.
        """
        pass

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
        return False

    # ==================== Event Helpers ====================

    def _publish_fetch_started(self, url: str) -> None:
        """Публікує подію FETCH_STARTED."""
        self.publish_event(
            EventType.FETCH_STARTED, data={"url": url, "driver": self.driver_name}
        )

    def _publish_fetch_success(
        self, url: str, status_code: Optional[int], duration: float
    ) -> None:
        """Публікує подію FETCH_SUCCESS."""
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
        """
        Обробляє помилку та повертає error response.

        Args:
            url: URL що не вдалося завантажити
            exception: Exception
            start_time: Час початку

        Returns:
            FetchResponse з error
        """
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
        """Створює FetchResponse для помилки."""
        return FetchResponse(
            url=url, html=None, status_code=None, headers={}, error=error
        )
