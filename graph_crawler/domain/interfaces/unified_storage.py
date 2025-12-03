"""Unified Storage Interfaces.

Цей модуль визначає інтерфейси для уніфікованої системи зберігання:
- IJobStorage - зберігання стану сканувань (jobs)
- IQueueStorage - черга URL для обробки
- IGraphStorage - зберігання графа (nodes, edges)

Принцип: "Користувач сам вирішує де зберігати"
"""

from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Tuple, runtime_checkable


class StorageBackend(Enum):
    """Типи backend для зберігання.

    Attributes:
        MEMORY: RAM (швидко, <10K сторінок)
        FILE: SQLite файл у локальній папці
        SQLITE: SQLite з явним шляхом
        POSTGRESQL: PostgreSQL БД (масштабування)
        MONGODB: MongoDB БД
        AUTO: Автоматичний вибір за розміром
    """

    MEMORY = "memory"
    FILE = "file"
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"
    MONGODB = "mongodb"
    AUTO = "auto"


@runtime_checkable
class IJobStorage(Protocol):
    """Інтерфейс для зберігання jobs (сканувань).

    Jobs зберігають стан сканування:
    - config - конфігурація
    - status - pending/running/completed/failed
    - progress - прогрес сканування
    - result - результат (graph_id)

    """

    async def create_job(
        self, job_id: str, config: Dict[str, Any], status: str = "pending"
    ) -> None:
        """Створює новий job.

        Args:
            job_id: Унікальний ідентифікатор
            config: Конфігурація сканування
            status: Початковий статус
        """
        ...

    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Отримує job за ID.

        Args:
            job_id: Ідентифікатор job

        Returns:
            Dict з даними job або None
        """
        ...

    async def update_job(self, job_id: str, updates: Dict[str, Any]) -> bool:
        """Оновлює поля job.

        Args:
            job_id: Ідентифікатор job
            updates: Dict з полями для оновлення

        Returns:
            True якщо успішно
        """
        ...

    async def list_jobs(
        self, status: Optional[str] = None, limit: int = 100, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Список jobs.

        Args:
            status: Фільтр за статусом (опціонально)
            limit: Максимум записів
            offset: Зсув для пагінації

        Returns:
            Список jobs
        """
        ...

    async def delete_job(self, job_id: str) -> bool:
        """Видаляє job.

        Args:
            job_id: Ідентифікатор job

        Returns:
            True якщо успішно видалено
        """
        ...

    async def close(self) -> None:
        """Закриває з'єднання."""
        ...


@runtime_checkable
class IQueueStorage(Protocol):
    """Інтерфейс для черги URL.

    Черга зберігає URL для обробки з пріоритетами.
    Для великих сканів (50M+) краще PostgreSQL ніж Redis.

    Структура запису:
    - url: URL для сканування
    - depth: Глибина від початкового URL
    - priority: Пріоритет (вищий = раніше)
    - status: pending/processing/done/failed
    """

    async def push_urls(
        self, scan_id: str, urls: List[Tuple[str, int, int]]  # (url, depth, priority)
    ) -> int:
        """Додає URLs до черги.

        Args:
            scan_id: ID сканування
            urls: Список (url, depth, priority)

        Returns:
            Кількість доданих (без дублікатів)
        """
        ...

    async def pop_urls(
        self, scan_id: str, batch_size: int = 24, worker_id: Optional[str] = None
    ) -> List[Tuple[str, int]]:
        """Отримує batch URLs для обробки.

        Args:
            scan_id: ID сканування
            batch_size: Кількість URL
            worker_id: ID воркера (для tracking)

        Returns:
            Список (url, depth)
        """
        ...

    async def mark_done(self, scan_id: str, urls: List[str]) -> None:
        """Позначає URLs як оброблені."""
        ...

    async def mark_failed(
        self, scan_id: str, urls: List[str], error: Optional[str] = None
    ) -> None:
        """Позначає URLs як failed."""
        ...

    async def get_stats(self, scan_id: str) -> Dict[str, int]:
        """Статистика черги.

        Returns:
            {
                'pending': кількість в очікуванні,
                'processing': в обробці,
                'done': завершено,
                'failed': помилки,
                'total': всього
            }
        """
        ...

    async def clear(self, scan_id: str) -> None:
        """Очищає чергу для scan_id."""
        ...

    async def close(self) -> None:
        """Закриває з'єднання."""
        ...


class StorageConfig:
    """Конфігурація Unified Storage.

    Example:
        # Default - файлова система
        config = StorageConfig()

        # SQLite з явним шляхом
        config = StorageConfig(
            backend=StorageBackend.SQLITE,
            storage_path="./my_crawl.db"
        )

        # PostgreSQL
        config = StorageConfig(
            backend=StorageBackend.POSTGRESQL,
            db_config={
                'host': 'localhost',
                'database': 'crawler',
                'user': 'user',
                'password': 'pass'
            }
        )
    """

    def __init__(
        self,
        backend: StorageBackend = StorageBackend.FILE,
        storage_dir: str = "./crawl_data",
        storage_path: Optional[str] = None,
        db_config: Optional[Dict[str, Any]] = None,
        auto_thresholds: Optional[Dict[str, int]] = None,
    ):
        """
        Args:
            backend: Тип backend
            storage_dir: Директорія для FILE backend
            storage_path: Шлях до файлу для SQLITE
            db_config: Конфігурація БД для POSTGRESQL/MONGODB
            auto_thresholds: Пороги для AUTO backend
                {'memory': 1000, 'file': 100000}
        """
        self.backend = backend
        self.storage_dir = Path(storage_dir)
        self.storage_path = Path(storage_path) if storage_path else None
        self.db_config = db_config or {}
        self.auto_thresholds = auto_thresholds or {
            "memory": 1000,  # До 1K - memory
            "file": 100000,  # До 100K - file/sqlite
            # Більше - database
        }

    def ensure_storage_dir(self) -> Path:
        """Створює директорію якщо не існує."""
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        return self.storage_dir
