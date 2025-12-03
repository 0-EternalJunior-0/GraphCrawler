"""
Базова абстракція для Spider .
- crawl() тепер async
- Додано async context manager
- pause/resume/stop тепер async
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional

from graph_crawler.domain.entities.graph import Graph
from graph_crawler.domain.events import EventBus
from graph_crawler.domain.value_objects.configs import CrawlerConfig
from graph_crawler.infrastructure.persistence.base import BaseStorage
from graph_crawler.infrastructure.transport.base import BaseDriver


class CrawlerState(Enum):
    """Стани crawler для контролю виконання."""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


class BaseSpider(ABC):
    """
    Async-First базовий абстрактний клас для всіх Spider реалізацій . Всі операції тепер async.

    Responsibilities:
    - Визначає async інтерфейс для краулінгу
    - Гарантує що всі Spider мають async crawl()
    - Управління станом краулера (running/paused/stopped)

    Example:
        >>> async with CustomSpider(config, driver, storage) as spider:
        ...     graph = await spider.crawl()
        ...     await spider.pause()
        ...     await spider.resume()
        ...     await spider.stop()
    """

    def __init__(
        self,
        config: CrawlerConfig,
        driver: BaseDriver,
        storage: BaseStorage,
        event_bus: Optional[EventBus] = None,
    ):
        """
        Ініціалізує Spider з необхідними залежностями.
        """
        self.config = config
        self.driver = driver
        self.storage = storage
        self.event_bus = event_bus or EventBus()
        self._state = CrawlerState.IDLE

    @abstractmethod
    async def crawl(self, base_graph: Optional[Graph] = None) -> Graph:
        """
        Async запускає процес краулінгу.

        Args:
            base_graph: Базовий граф для incremental краулінгу (опціонально)

        Returns:
            Побудований граф
        """
        raise NotImplementedError("Subclass must implement async crawl() method")

    @abstractmethod
    def get_stats(self) -> dict:
        """
        Повертає статистику краулінгу (sync - in-memory операція).

        Returns:
            Dict зі статистикою
        """
        raise NotImplementedError("Subclass must implement get_stats() method")

    # Async control методи

    async def pause(self) -> bool:
        """
        Async призупинити активний краулінг.

        Returns:
            True якщо успішно призупинено
        """
        if self._state != CrawlerState.RUNNING:
            return False

        self._state = CrawlerState.PAUSED
        return True

    async def resume(self) -> bool:
        """
        Async відновити призупинений краулінг.

        Returns:
            True якщо успішно відновлено
        """
        if self._state != CrawlerState.PAUSED:
            return False

        self._state = CrawlerState.RUNNING
        return True

    async def stop(self) -> bool:
        """
        Async зупинити краулінг.

        Returns:
            True якщо успішно зупинено
        """
        if self._state == CrawlerState.STOPPED:
            return False

        self._state = CrawlerState.STOPPED
        return True

    def get_state(self) -> CrawlerState:
        """Отримати поточний стан краулера."""
        return self._state

    def is_running(self) -> bool:
        """Перевірити чи краулер активний."""
        return self._state == CrawlerState.RUNNING

    def is_paused(self) -> bool:
        """Перевірити чи краулер призупинений."""
        return self._state == CrawlerState.PAUSED

    def is_stopped(self) -> bool:
        """Перевірити чи краулер зупинений."""
        return self._state == CrawlerState.STOPPED

    async def close(self) -> None:
        """
        Async закриває всі ресурси Spider.
        """
        await self.driver.close()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
        return False
