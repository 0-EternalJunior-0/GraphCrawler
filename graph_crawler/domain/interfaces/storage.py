"""Protocol для систем зберігання графів.

Розділено на менші інтерфейси:
- IStorageReader - тільки читання
- IStorageWriter - тільки запис
- IStorageLifecycle - управління життєвим циклом
- IStorage - повний інтерфейс (об'єднує всі)
"""

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class IStorageReader(Protocol):
    """Інтерфейс для читання з сховища (ISP - тільки read операції)."""

    async def load_graph(self):
        """Async завантажує граф."""
        ...

    async def exists(self) -> bool:
        """Async перевіряє чи існує збережений граф."""
        ...


@runtime_checkable
class IStorageWriter(Protocol):
    """Інтерфейс для запису в сховище (ISP - тільки write операції)."""

    async def save_graph(self, graph) -> bool:
        """Async зберігає граф."""
        ...

    async def save_partial(self, nodes: List[Dict], edges: List[Dict]) -> bool:
        """Async зберігає частину графу (інкрементально)."""
        ...

    async def clear(self) -> bool:
        """Async очищує сховище."""
        ...


@runtime_checkable
class IStorageLifecycle(Protocol):
    """Інтерфейс для управління життєвим циклом сховища (ISP)."""

    async def close(self) -> None:
        """Async закриває з'єднання зі сховищем."""
        ...

    async def __aenter__(self) -> "IStorageLifecycle":
        """Async context manager entry."""
        ...

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        ...


@runtime_checkable
class IStorage(IStorageReader, IStorageWriter, IStorageLifecycle, Protocol):
    """
    Повний Async-First інтерфейс для систем зберігання графів.

    Тепер IStorage складається з менших інтерфейсів:
    - IStorageReader - для клієнтів що тільки читають
    - IStorageWriter - для клієнтів що тільки пишуть
    - IStorageLifecycle - для управління ресурсами

    Повністю async інтерфейс з використанням:
    - aiofiles для файлового I/O
    - aiosqlite для SQLite
    - motor для MongoDB
    - asyncpg для PostgreSQL
    """

    pass


# Для зворотної сумісності
__all__ = [
    "IStorage",
    "IStorageReader",
    "IStorageWriter",
    "IStorageLifecycle",
]
