"""Unified Storage System.

Модуль надає єдину точку доступу до всіх типів storage:
- Jobs (стан сканувань)
- Queue (черга URL)
- Graphs (результати)

Приклад використання:
    from graph_crawler.infrastructure.persistence.unified import UnifiedStorage

    # Default - файлова система ./crawl_data/
    storage = UnifiedStorage()

    # SQLite
    storage = UnifiedStorage(backend="sqlite", storage_path="./crawl.db")

    # PostgreSQL
    storage = UnifiedStorage(
        backend="postgresql",
        db_config={"host": "localhost", "database": "crawler"}
    )
"""

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
from graph_crawler.infrastructure.persistence.unified.unified_storage import (
    UnifiedStorage,
)

# PostgreSQL storage (optional)
try:
    from graph_crawler.infrastructure.persistence.unified.postgresql_job_storage import (
        PostgreSQLJobStorage,
    )
    from graph_crawler.infrastructure.persistence.unified.postgresql_queue_storage import (
        PostgreSQLQueueStorage,
    )

    __all__ = [
        "UnifiedStorage",
        "FileJobStorage",
        "FileQueueStorage",
        "MemoryJobStorage",
        "MemoryQueueStorage",
        "PostgreSQLJobStorage",
        "PostgreSQLQueueStorage",
    ]
except ImportError:
    __all__ = [
        "UnifiedStorage",
        "FileJobStorage",
        "FileQueueStorage",
        "MemoryJobStorage",
        "MemoryQueueStorage",
    ]
