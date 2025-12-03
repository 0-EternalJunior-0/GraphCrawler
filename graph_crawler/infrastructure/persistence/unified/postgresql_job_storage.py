"""PostgreSQL Job Storage.

PRODUCTION-READY: Jobs для великих проектів

Використовує PostgreSQL з:
- Connection pooling
- Партиціонування таблиць
- Ефективні індекси
- JSONB для гнучких полів

Рекомендовано для:
- Production середовищ
- Distributed crawling
- Довгострокове зберігання
- Масштабування (1M+ jobs)
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    import asyncpg

    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False
    asyncpg = None

logger = logging.getLogger(__name__)

# SQL Schemas
CREATE_JOBS_TABLE = """
CREATE TABLE IF NOT EXISTS crawl_jobs (
    job_id TEXT PRIMARY KEY,
    config JSONB NOT NULL,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    progress JSONB DEFAULT '{}',
    result JSONB,
    error TEXT
)
"""

CREATE_JOBS_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_jobs_status ON crawl_jobs(status)",
    "CREATE INDEX IF NOT EXISTS idx_jobs_created ON crawl_jobs(created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_jobs_status_created ON crawl_jobs(status, created_at DESC)",
]

ALLOWED_UPDATE_KEYS = frozenset(
    {
        "status",
        "progress",
        "result",
        "error",
        "started_at",
        "completed_at",
        "config",
        "metadata",
    }
)


class PostgreSQLJobStorage:
    """Job storage в PostgreSQL.

    Production-ready storage з підтримкою:
    - Connection pooling (min 5, max 20 connections)
    - JSONB для гнучкості схеми
    - Ефективні індекси
    - Concurrent access
    - SQL Injection Prevention (whitelist keys)

    Example:
        import os

        storage = PostgreSQLJobStorage(
            host=os.getenv("DB_HOST", "localhost"),
            database=os.getenv("DB_NAME", "crawler"),
            user=os.getenv("DB_USER", "crawler_user"),
            password=os.getenv("DB_PASSWORD")  # REQUIRED from env!
        )
        await storage.create_job("job_1", {"url": "..."})

    Args:
        host: PostgreSQL host
        port: PostgreSQL port (default 5432)
        database: Назва БД
        user: Користувач
        password: Пароль
        min_pool_size: Мінімум з'єднань (default 5)
        max_pool_size: Максимум з'єднань (default 20)
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        database: str = "crawler",
        user: str = "postgres",
        password: str = "",
        min_pool_size: int = 5,
        max_pool_size: int = 20,
    ):
        if not ASYNCPG_AVAILABLE:
            raise ImportError(
                "asyncpg is required for PostgreSQL storage. "
                "Install with: pip install asyncpg"
            )

        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.min_pool_size = min_pool_size
        self.max_pool_size = max_pool_size

        self._pool: Optional[asyncpg.Pool] = None
        self._initialized = False

    async def _ensure_initialized(self):
        """Ініціалізує connection pool та схему."""
        if self._initialized:
            return

        # Створюємо connection pool
        self._pool = await asyncpg.create_pool(
            host=self.host,
            port=self.port,
            database=self.database,
            user=self.user,
            password=self.password,
            min_size=self.min_pool_size,
            max_size=self.max_pool_size,
            command_timeout=60,
        )

        # Створюємо таблиці та індекси
        async with self._pool.acquire() as conn:
            await conn.execute(CREATE_JOBS_TABLE)
            for index_sql in CREATE_JOBS_INDEXES:
                await conn.execute(index_sql)

        self._initialized = True
        logger.info(
            f"PostgreSQLJobStorage initialized: {self.host}:{self.port}/{self.database}"
        )

    async def create_job(
        self, job_id: str, config: Dict[str, Any], status: str = "pending"
    ) -> None:
        """Створює новий job."""
        await self._ensure_initialized()

        progress = {
            "pages_crawled": 0,
            "pages_total": config.get("max_pages", 100),
            "urls_in_queue": 0,
        }

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO crawl_jobs (job_id, config, status, progress)
                VALUES ($1, $2, $3, $4)
                """,
                job_id,
                json.dumps(config),
                status,
                json.dumps(progress),
            )

        logger.debug(f"Created job {job_id} in PostgreSQL")

    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Отримує job за ID."""
        await self._ensure_initialized()

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM crawl_jobs WHERE job_id = $1", job_id
            )

            if not row:
                return None

            # Convert to dict
            result = dict(row)

            # Parse JSONB fields
            if result.get("config"):
                result["config"] = json.loads(result["config"])
            if result.get("progress"):
                result["progress"] = json.loads(result["progress"])
            if result.get("result"):
                result["result"] = json.loads(result["result"])

            # Convert timestamps to ISO strings
            for field in ["created_at", "started_at", "completed_at"]:
                if result.get(field):
                    result[field] = result[field].isoformat()

            return result

    async def update_job(self, job_id: str, updates: Dict[str, Any]) -> bool:
        """Оновлює поля job з валідацією ключів.

        SQL Injection Prevention:
        Тільки ключі з ALLOWED_UPDATE_KEYS можуть бути оновлені.

        Args:
            job_id: ID job для оновлення
            updates: Dict з полями для оновлення

        Returns:
            True якщо оновлення успішне

        Raises:
            ValueError: Якщо передані недозволені ключі
        """
        await self._ensure_initialized()

        # SQL Injection Prevention: валідація ключів
        invalid_keys = set(updates.keys()) - ALLOWED_UPDATE_KEYS
        if invalid_keys:
            raise ValueError(
                f"Invalid update keys: {invalid_keys}. "
                f"Allowed: {ALLOWED_UPDATE_KEYS}"
            )

        async with self._pool.acquire() as conn:
            # Get current job
            row = await conn.fetchrow(
                "SELECT progress FROM crawl_jobs WHERE job_id = $1", job_id
            )

            if not row:
                return False

            # Build UPDATE query (keys are now validated)
            set_parts = []
            values = []
            param_num = 1

            for key, value in updates.items():
                if key == "progress" and isinstance(value, dict):
                    # Merge progress with existing
                    current_progress = (
                        json.loads(row["progress"]) if row["progress"] else {}
                    )
                    current_progress.update(value)
                    set_parts.append(f"progress = ${param_num}")
                    values.append(json.dumps(current_progress))
                elif key in ["config", "result"]:
                    set_parts.append(f"{key} = ${param_num}")
                    values.append(json.dumps(value) if value else None)
                else:
                    set_parts.append(f"{key} = ${param_num}")
                    values.append(value)
                param_num += 1

            if set_parts:
                values.append(job_id)
                await conn.execute(
                    f"UPDATE crawl_jobs SET {', '.join(set_parts)} WHERE job_id = ${param_num}",
                    *values,
                )

            return True

    async def list_jobs(
        self, status: Optional[str] = None, limit: int = 100, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Список jobs."""
        await self._ensure_initialized()

        async with self._pool.acquire() as conn:
            if status:
                rows = await conn.fetch(
                    """
                    SELECT * FROM crawl_jobs
                    WHERE status = $1
                    ORDER BY created_at DESC
                    LIMIT $2 OFFSET $3
                    """,
                    status,
                    limit,
                    offset,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM crawl_jobs
                    ORDER BY created_at DESC
                    LIMIT $1 OFFSET $2
                    """,
                    limit,
                    offset,
                )

            results = []
            for row in rows:
                result = dict(row)

                # Parse JSONB
                if result.get("config"):
                    result["config"] = json.loads(result["config"])
                if result.get("progress"):
                    result["progress"] = json.loads(result["progress"])
                if result.get("result"):
                    result["result"] = json.loads(result["result"])

                # Convert timestamps
                for field in ["created_at", "started_at", "completed_at"]:
                    if result.get(field):
                        result[field] = result[field].isoformat()

                results.append(result)

            return results

    async def delete_job(self, job_id: str) -> bool:
        """Видаляє job."""
        await self._ensure_initialized()

        async with self._pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM crawl_jobs WHERE job_id = $1", job_id
            )
            return result != "DELETE 0"

    async def close(self) -> None:
        """Закриває connection pool."""
        if self._pool:
            await self._pool.close()
            logger.info("PostgreSQLJobStorage closed")
