"""Базовий абстрактний драйвер для сканування.

Features:
- Всі методи async (fetch, fetch_many, close)
- Async context manager (__aenter__, __aexit__)
- Всі драйвери підтримують batch fetching
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional

from graph_crawler.domain.events.event_bus import EventBus
from graph_crawler.domain.events.events import EventType
from graph_crawler.domain.interfaces.driver import IDriver
from graph_crawler.domain.value_objects.models import FetchResponse
from graph_crawler.shared.utils.event_publisher_mixin import EventPublisherMixin

logger = logging.getLogger(__name__)


class DriverType(str, Enum):
    """Типи драйверів для сканування ."""

    HTTP = "http"  # Async HTTP (aiohttp) - замінив sync requests
    ASYNCIO = "asyncio"  # Alias для HTTP для зворотньої сумісності
    PLAYWRIGHT = "playwright"  # Async браузер з JS рендерингом


class BaseDriver(EventPublisherMixin, ABC, IDriver):
    """
    Async-First базовий клас для всіх драйверів .

    Всі операції виконуються асинхронно для максимальної продуктивності.
    Sync wrappers видалено - використовуйте asyncio.run() для запуску.

    Всі драйвери повинні реалізувати:
    1. async fetch() - завантаження однієї сторінки
    2. async fetch_many() - batch завантаження (паралельно)
    3. async close() - закриття ресурсів
    """

    def __init__(
        self, config: Dict[str, Any] = None, event_bus: Optional[EventBus] = None
    ):
        """
        Ініціалізація драйвера.

        Args:
            config: Конфігурація драйвера (timeout, user_agent, max_concurrent_requests, etc.)
            event_bus: EventBus для публікації подій (опціонально)
        """
        self.config = config or {}
        self.event_bus = event_bus

    @abstractmethod
    async def fetch(self, url: str) -> FetchResponse:
        """
        Async завантажує одну сторінку за URL.

        Args:
            url: URL сторінки для завантаження

        Returns:
            FetchResponse об'єкт з даними:
            - url: str (оригінальний URL запиту)
            - html: Optional[str]
            - status_code: Optional[int]
            - headers: Dict[str, str]
            - error: Optional[str]
            - final_url: Optional[str] (фінальний URL після редіректів, або None)
            - redirect_chain: List[str] (список проміжних редіректів)

        ВАЖЛИВО для реалізації драйверів:
            Всі драйвери ПОВИННІ заповнювати final_url та redirect_chain
            для коректної обробки редіректів у графі.

            Приклад (aiohttp):
                final_url = str(response.url) if str(response.url) != url else None
                redirect_chain = [str(r.url) for r in response.history]

            Приклад (playwright):
                final_url = page.url if page.url != url else None
        """
        pass

    async def fetch_many(self, urls: List[str]) -> List[FetchResponse]:
        """
        Async паралельне завантаження декількох сторінок.

        Дефолтна імплементація - паралельне завантаження через asyncio.gather.
        Конкретні драйвери можуть перевизначити для оптимізації.

        Args:
            urls: Список URL для завантаження

        Returns:
            Список FetchResponse об'єктів
        """
        tasks = [self.fetch(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Обробляємо exceptions
        processed = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed.append(self._create_error_response(urls[i], str(result)))
            else:
                processed.append(result)
        return processed

    def supports_batch_fetching(self) -> bool:
        """Всі драйвери підтримують batch fetching.

        Returns:
            True
        """
        return True

    async def close(self) -> None:
        """Async закриває драйвер та звільняє ресурси."""
        pass

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - автоматично закриває драйвер."""
        await self.close()
        return False

    # Helper методи для усунення дублювання error handling

    def _publish_fetch_started(
        self, url: str, driver_name: str, extra_data: Optional[Dict[str, Any]] = None
    ):
        """
        Публікує подію FETCH_STARTED.

        Args:
            url: URL що завантажується
            driver_name: Назва драйвера ('http', 'async', 'playwright')
            extra_data: Додаткові дані для події
        """
        data = {"url": url, "driver": driver_name}
        if extra_data:
            data.update(extra_data)
        self.publish_event(EventType.FETCH_STARTED, data=data)

    def _publish_fetch_success(
        self,
        url: str,
        status_code: Optional[int],
        duration: float,
        driver_name: str,
        extra_data: Optional[Dict[str, Any]] = None,
    ):
        """
        Публікує подію FETCH_SUCCESS з метриками.
        """
        data = {
            "url": url,
            "status_code": status_code,
            "duration": round(duration, 3),
            "driver": driver_name,
        }
        if extra_data:
            data.update(extra_data)
        self.publish_event(EventType.FETCH_SUCCESS, data=data)

    def _handle_fetch_error(
        self,
        url: str,
        exception: Exception,
        start_time: float,
        driver_name: str,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> FetchResponse:
        """
        Обробляє помилку fetch операції.

        Args:
            url: URL що не вдалося завантажити
            exception: Exception що виникла
            start_time: Час початку операції
            driver_name: Назва драйвера
            extra_data: Додаткові дані

        Returns:
            FetchResponse з error полем
        """
        error_msg = f"Error fetching {url}: {type(exception).__name__}: {exception}"
        logger.error(error_msg)

        duration = time.time() - start_time

        data = {
            "url": url,
            "error": str(exception),
            "error_type": type(exception).__name__,
            "duration": round(duration, 3),
            "driver": driver_name,
        }
        if extra_data:
            data.update(extra_data)
        self.publish_event(EventType.FETCH_ERROR, data=data)

        return self._create_error_response(url, error_msg)

    def _create_error_response(self, url: str, error_msg: str) -> FetchResponse:
        """
        Створює FetchResponse для випадку помилки.
        """
        return FetchResponse(
            url=url, html=None, status_code=None, headers={}, error=error_msg
        )
