"""Unified Storage System.

Модуль надає єдину точку доступу до всіх типів storage:
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
