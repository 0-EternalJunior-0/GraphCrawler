"""Базовий абстрактний клас для збереження ."""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional

from graph_crawler.application.dto import GraphDTO
from graph_crawler.domain.events.event_bus import EventBus
from graph_crawler.domain.interfaces.storage import IStorage
from graph_crawler.shared.utils.event_publisher_mixin import EventPublisherMixin


class StorageType(str, Enum):
    """Типи сховищ."""

    MEMORY = "memory"  # У пам'яті (для малих сайтів <1k)
    JSON = "json"  # JSON файли (1k-20k)
    SQLITE = "sqlite"  # SQLite база даних (fallback для >20k)
    POSTGRESQL = "postgresql"  # PostgreSQL (для великих графів >20k)
    MONGODB = "mongodb"  # MongoDB (для великих графів >20k)
    AUTO = "auto"  # Автоматичний вибір storage


class BaseStorage(EventPublisherMixin, ABC, IStorage):
    """
    Async-First абстрактний базовий клас для збереження графу .

    Використовується для тимчасового збереження графу
    під час сканування, щоб не забивати RAM. Всі методи тепер async для неблокуючого I/O.
    Використовує aiofiles для file I/O, aiosqlite для SQLite, motor для MongoDB.
    """

    def __init__(self, event_bus: Optional[EventBus] = None, **kwargs):
        """
        Initialize storage з опціональним event bus.

        Args:
            event_bus: EventBus для публікації подій (опціонально)
            **kwargs: Додаткові параметри для конкретних storage
        """
        self.event_bus = event_bus

    @abstractmethod
    async def save_graph(self, graph_dto: GraphDTO) -> bool:
        """
        Async зберігає граф у сховище .

        BREAKING CHANGE: Тепер приймає GraphDTO замість Graph для ізоляції Domain Layer.

        Args:
            graph_dto: GraphDTO для збереження

        Returns:
            True якщо успішно
        """
        pass

    @abstractmethod
    async def load_graph(self, context: Optional[Dict[str, Any]] = None) -> Optional[GraphDTO]:
        """
        Async завантажує граф зі сховища .

        BREAKING CHANGE: Тепер повертає GraphDTO замість Graph для ізоляції Domain Layer.

        Args:
            context: Контекст з налаштуваннями (не використовується в базовій реалізації,
                    але може бути корисний для кастомних storage)

        Returns:
            GraphDTO або None якщо не знайдено
        """
        pass

    @abstractmethod
    async def save_partial(self, nodes: List[Dict], edges: List[Dict]) -> bool:
        """
        Async зберігає частину графу (інкрементально) .

        Важливо для великих сайтів - зберігаємо поетапно.
        """
        pass

    @abstractmethod
    async def clear(self) -> bool:
        """Async очищує сховище ."""
        pass

    @abstractmethod
    async def exists(self) -> bool:
        """Async перевіряє чи існує збережений граф ."""
        pass

    async def close(self) -> None:
        """Async закриває з'єднання до storage ."""
        # Базова реалізація - нічого не робить
        # Підкласи можуть перевизначити (SQLite, PostgreSQL, MongoDB)
        pass

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - закриває з'єднання."""
        await self.close()
        return False
