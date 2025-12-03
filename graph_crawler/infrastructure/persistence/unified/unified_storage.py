"""Unified Storage - єдина точка доступу до storage.

Цей клас надає уніфікований інтерфейс для:
- Jobs storage (стан сканувань)
- Queue storage (черга URL)
- Graph storage (результати)

За замовчуванням використовує файлову систему (SQLite в ./crawl_data/).
Користувач може явно вказати backend через параметри.

Example:
    # Default - файлова система
    storage = UnifiedStorage()

    # Memory (для тестів)
    storage = UnifiedStorage(backend="memory")

    # PostgreSQL (для великих проектів)
    storage = UnifiedStorage(
        backend="postgresql",
        db_config={"host": "localhost", "database": "crawler"}
    )
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional, Union

from graph_crawler.domain.interfaces.unified_storage import (
    IJobStorage,
    IQueueStorage,
    StorageBackend,
    StorageConfig,
)
from graph_crawler.infrastructure.persistence.unified.file_job_storage import (
    FileJobStorage,
)
from graph_crawler.infrastructure.persistence.unified.file_queue_storage import (
    FileQueueStorage,
)
from graph_crawler.infrastructure.persistence.unified.memory_job_storage import (
    MemoryJobStorage,
)
from graph_crawler.infrastructure.persistence.unified.memory_queue_storage import (
    MemoryQueueStorage,
)

# PostgreSQL imports (optional)
try:
    from graph_crawler.infrastructure.persistence.unified.postgresql_job_storage import (
        PostgreSQLJobStorage,
    )
    from graph_crawler.infrastructure.persistence.unified.postgresql_queue_storage import (
        PostgreSQLQueueStorage,
    )

    POSTGRESQL_AVAILABLE = True
except ImportError:
    POSTGRESQL_AVAILABLE = False
    PostgreSQLJobStorage = None
    PostgreSQLQueueStorage = None

logger = logging.getLogger(__name__)


class UnifiedStorage:
    """Єдина точка доступу до всіх типів storage.

    Атрибути:
        jobs: IJobStorage - зберігання стану сканувань
        queue: IQueueStorage - черга URL для обробки
        graphs: IGraphStorage - зберігання графа (використовує існуючий storage)

    Приклади використання:

        # 1. Default - файлова система ./crawl_data/
        storage = UnifiedStorage()

        # 2. Memory (швидко, без persistence)
        storage = UnifiedStorage(backend="memory")

        # 3. Явний шлях до папки
        storage = UnifiedStorage(storage_dir="./my_project/data")

        # 4. SQLite з явним шляхом до файлу
        storage = UnifiedStorage(
            backend="sqlite",
            storage_path="./project.db"
        )

        # 5. PostgreSQL для великих проектів
        storage = UnifiedStorage(
            backend="postgresql",
            db_config={
                "host": "localhost",
                "port": 5432,
                "database": "crawler",
                "user": "user",
                "password": "pass"
            }
        )

    Використання jobs:
        await storage.jobs.create_job("job_1", {"url": "https://..."})
        job = await storage.jobs.get_job("job_1")
        await storage.jobs.update_job("job_1", {"status": "running"})
        jobs = await storage.jobs.list_jobs(status="pending")

    Використання queue:
        await storage.queue.push_urls("scan_1", [("https://...", 0, 10)])
        urls = await storage.queue.pop_urls("scan_1", batch_size=24)
        await storage.queue.mark_done("scan_1", ["https://..."])
        stats = await storage.queue.get_stats("scan_1")
    """

    def __init__(
        self,
        backend: Union[str, StorageBackend] = StorageBackend.FILE,
        storage_dir: str = "./crawl_data",
        storage_path: Optional[str] = None,
        db_config: Optional[Dict[str, Any]] = None,
        auto_thresholds: Optional[Dict[str, int]] = None,
    ):
        """
        Args:
            backend: Тип backend ('memory', 'file', 'sqlite', 'postgresql', 'mongodb', 'auto')
            storage_dir: Директорія для зберігання (для file/sqlite)
            storage_path: Повний шлях до файлу БД (для sqlite)
            db_config: Конфігурація БД (для postgresql/mongodb)
            auto_thresholds: Пороги для автоматичного вибору backend
        """
        # Normalize backend
        if isinstance(backend, str):
            backend = StorageBackend(backend.lower())

        self.backend = backend
        self.storage_dir = Path(storage_dir)
        self.storage_path = Path(storage_path) if storage_path else None
        self.db_config = db_config or {}
        self.auto_thresholds = auto_thresholds or {
            "memory": 1000,
            "file": 100000,
        }

        # Create storage directory
        if backend in (StorageBackend.FILE, StorageBackend.SQLITE, StorageBackend.AUTO):
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f" Storage directory: {self.storage_dir.absolute()}")

        # Initialize storages
        self.jobs: IJobStorage = self._create_job_storage()
        self.queue: IQueueStorage = self._create_queue_storage()

        # Graph storage буде використовувати існуючий AutoStorage/MemoryStorage
        # через application layer

        logger.info(
            f" UnifiedStorage initialized: backend={backend.value}, "
            f"storage_dir={self.storage_dir}"
        )

    def _create_job_storage(self) -> IJobStorage:
        """Створює storage для jobs."""
        if self.backend == StorageBackend.MEMORY:
            return MemoryJobStorage()

        elif self.backend in (
            StorageBackend.FILE,
            StorageBackend.SQLITE,
            StorageBackend.AUTO,
        ):
            return FileJobStorage(storage_dir=str(self.storage_dir))

        elif self.backend == StorageBackend.POSTGRESQL:
            if not POSTGRESQL_AVAILABLE:
                logger.error(
                    "PostgreSQL storage requested but asyncpg not installed. "
                    "Install with: pip install asyncpg"
                )
                logger.warning("Falling back to file storage")
                return FileJobStorage(storage_dir=str(self.storage_dir))

            return PostgreSQLJobStorage(
                host=self.db_config.get("host", "localhost"),
                port=self.db_config.get("port", 5432),
                database=self.db_config.get("database", "crawler"),
                user=self.db_config.get("user", "postgres"),
                password=self.db_config.get("password", ""),
                min_pool_size=self.db_config.get("min_pool_size", 5),
                max_pool_size=self.db_config.get("max_pool_size", 20),
            )

        elif self.backend == StorageBackend.MONGODB:
            # MongoDB storage планується в майбутній версії
            # Використовуйте PostgreSQL для production distributed crawling
            logger.warning(
                "MongoDB job storage not yet available. "
                "Using file storage as fallback. "
                "Consider PostgreSQL for production use."
            )
            return FileJobStorage(storage_dir=str(self.storage_dir))

        else:
            # Default to file
            return FileJobStorage(storage_dir=str(self.storage_dir))

    def _create_queue_storage(self) -> IQueueStorage:
        """Створює storage для URL queue."""
        if self.backend == StorageBackend.MEMORY:
            return MemoryQueueStorage()

        elif self.backend in (
            StorageBackend.FILE,
            StorageBackend.SQLITE,
            StorageBackend.AUTO,
        ):
            return FileQueueStorage(storage_dir=str(self.storage_dir))

        elif self.backend == StorageBackend.POSTGRESQL:
            if not POSTGRESQL_AVAILABLE:
                logger.error(
                    "PostgreSQL storage requested but asyncpg not installed. "
                    "Install with: pip install asyncpg"
                )
                logger.warning("Falling back to file storage")
                return FileQueueStorage(storage_dir=str(self.storage_dir))

            return PostgreSQLQueueStorage(
                host=self.db_config.get("host", "localhost"),
                port=self.db_config.get("port", 5432),
                database=self.db_config.get("database", "crawler"),
                user=self.db_config.get("user", "postgres"),
                password=self.db_config.get("password", ""),
                min_pool_size=self.db_config.get("min_pool_size", 10),
                max_pool_size=self.db_config.get("max_pool_size", 50),
                use_partitioning=self.db_config.get("use_partitioning", False),
            )

        elif self.backend == StorageBackend.MONGODB:
            # MongoDB storage планується в майбутній версії
            # Використовуйте PostgreSQL для production distributed crawling
            logger.warning(
                "MongoDB queue storage not yet available. "
                "Using file storage as fallback. "
                "Consider PostgreSQL for production use."
            )
            return FileQueueStorage(storage_dir=str(self.storage_dir))

        else:
            return FileQueueStorage(storage_dir=str(self.storage_dir))

    async def close(self) -> None:
        """Закриває всі з'єднання."""
        await self.jobs.close()
        await self.queue.close()
        logger.info("UnifiedStorage closed")

    async def __aenter__(self) -> "UnifiedStorage":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()

    def get_storage_info(self) -> Dict[str, Any]:
        """Інформація про storage."""
        return {
            "backend": self.backend.value,
            "storage_dir": str(self.storage_dir.absolute()),
            "storage_path": str(self.storage_path) if self.storage_path else None,
            "db_config": {
                k: "***" if "password" in k else v for k, v in self.db_config.items()
            },
            "auto_thresholds": self.auto_thresholds,
        }


# Singleton для глобального доступу (опціонально)
_default_storage: Optional[UnifiedStorage] = None


def get_storage(
    backend: Union[str, StorageBackend] = StorageBackend.FILE,
    storage_dir: str = "./crawl_data",
    **kwargs,
) -> UnifiedStorage:
    """Отримує або створює UnifiedStorage.

    Для простоти використання можна викликати без параметрів
    для отримання default storage.

    Example:
        storage = get_storage()  # Default file storage
        storage = get_storage(backend="memory")  # Memory storage
    """
    global _default_storage

    if _default_storage is None:
        _default_storage = UnifiedStorage(
            backend=backend, storage_dir=storage_dir, **kwargs
        )

    return _default_storage


def reset_storage() -> None:
    """Скидає глобальний storage."""
    global _default_storage
    _default_storage = None
