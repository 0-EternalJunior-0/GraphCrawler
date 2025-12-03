"""PostgreSQL Queue Storage.

PRODUCTION-READY: Черга URL для великих сканів

Критично для distributed crawling з 50M+ сторінок.
Використовує SELECT FOR UPDATE SKIP LOCKED для безпечної concurrent обробки.

Переваги:
- Підтримка 50M+ URL
- Concurrent access від multiple workers
- Партиціонування по scan_id
- Дедуплікація через UNIQUE constraint
- Пріоритети та статуси

Example:
    queue = PostgreSQLQueueStorage(
        host="localhost",
        database="crawler"
    )
    await queue.push_urls("scan_1", [("https://...", 0, 10)])
    urls = await queue.pop_urls("scan_1", batch_size=24)
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

try:
    import asyncpg

    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False
    asyncpg = None

logger = logging.getLogger(__name__)

# SQL Schemas
CREATE_QUEUE_TABLE = """
CREATE TABLE IF NOT EXISTS url_queue (
    id BIGSERIAL PRIMARY KEY,
    scan_id TEXT NOT NULL,
    url TEXT NOT NULL,
    depth INTEGER DEFAULT 0,
    priority INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    worker_id TEXT,
    error TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    processed_at TIMESTAMP,
    UNIQUE(scan_id, url)
)
"""

# Партиціонування для великих сканів (опціонально)
CREATE_PARTITIONED_QUEUE_TABLE = """
CREATE TABLE IF NOT EXISTS url_queue (
    id BIGSERIAL,
    scan_id TEXT NOT NULL,
    url TEXT NOT NULL,
    depth INTEGER DEFAULT 0,
    priority INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    worker_id TEXT,
    error TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    processed_at TIMESTAMP,
    UNIQUE(scan_id, url)
) PARTITION BY HASH (scan_id)
"""

CREATE_QUEUE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_queue_scan_status ON url_queue(scan_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_queue_priority ON url_queue(scan_id, priority DESC, created_at) WHERE status = 'pending'",
    "CREATE INDEX IF NOT EXISTS idx_queue_worker ON url_queue(worker_id) WHERE status = 'processing'",
]


class PostgreSQLQueueStorage:
    """URL Queue в PostgreSQL.

    Production-ready черга з підтримкою:
    - Concurrent workers (SELECT FOR UPDATE SKIP LOCKED)
    - Великі обсяги (50M+ URL з партиціонуванням)
    - Дедуплікація (UNIQUE constraint)
    - Пріоритети

    Args:
        host: PostgreSQL host
        port: PostgreSQL port (default 5432)
        database: Назва БД
        user: Користувач
        password: Пароль
        min_pool_size: Мінімум з'єднань (default 10)
        max_pool_size: Максимум з'єднань (default 50)
        use_partitioning: Використовувати партиціонування (для 50M+)
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        database: str = "crawler",
        user: str = "postgres",
        password: str = "",
        min_pool_size: int = 10,
        max_pool_size: int = 50,
        use_partitioning: bool = False,
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
        self.use_partitioning = use_partitioning

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

        # Створюємо таблицю (з або без партиціонування)
        async with self._pool.acquire() as conn:
            if self.use_partitioning:
                await conn.execute(CREATE_PARTITIONED_QUEUE_TABLE)
                logger.info("Created partitioned url_queue table")
            else:
                await conn.execute(CREATE_QUEUE_TABLE)
                logger.info("Created url_queue table")

            # Створюємо індекси
            for index_sql in CREATE_QUEUE_INDEXES:
                try:
                    await conn.execute(index_sql)
                except Exception as e:
                    logger.warning(f"Failed to create index: {e}")

        self._initialized = True
        logger.info(
            f"PostgreSQLQueueStorage initialized: {self.host}:{self.port}/{self.database} "
            f"(partitioning={self.use_partitioning})"
        )

    async def push_urls(
        self, scan_id: str, urls: List[Tuple[str, int, int]]  # (url, depth, priority)
    ) -> int:
        """Додає URLs до черги.

        Використовує INSERT ... ON CONFLICT DO NOTHING для дедуплікації.

        Returns:
            Кількість доданих URL (без дублікатів)
        """
        await self._ensure_initialized()

        if not urls:
            return 0

        async with self._pool.acquire() as conn:
            # Batch insert з ON CONFLICT
            added = 0
            for url, depth, priority in urls:
                try:
                    result = await conn.execute(
                        """
                        INSERT INTO url_queue (scan_id, url, depth, priority, status)
                        VALUES ($1, $2, $3, $4, 'pending')
                        ON CONFLICT (scan_id, url) DO NOTHING
                        """,
                        scan_id,
                        url,
                        depth,
                        priority,
                    )
                    # Parse result: "INSERT 0 1" означає 1 рядок додано
                    if result.endswith(" 1"):
                        added += 1
                except Exception as e:
                    logger.error(f"Failed to insert URL {url}: {e}")

            logger.debug(f"Added {added}/{len(urls)} URLs to queue {scan_id}")
            return added

    async def pop_urls(
        self, scan_id: str, batch_size: int = 24, worker_id: Optional[str] = None
    ) -> List[Tuple[str, int]]:
        """Отримує batch URLs для обробки.

        Використовує SELECT FOR UPDATE SKIP LOCKED для безпечної
        concurrent обробки від multiple workers.

        Returns:
            Список (url, depth)
        """
        await self._ensure_initialized()

        async with self._pool.acquire() as conn:
            # SELECT FOR UPDATE SKIP LOCKED - кожен worker бере свої URL
            rows = await conn.fetch(
                """
                UPDATE url_queue
                SET status = 'processing',
                    worker_id = $1,
                    processed_at = NOW()
                WHERE id IN (
                    SELECT id FROM url_queue
                    WHERE scan_id = $2 AND status = 'pending'
                    ORDER BY priority DESC, created_at
                    LIMIT $3
                    FOR UPDATE SKIP LOCKED
                )
                RETURNING url, depth
                """,
                worker_id or "unknown",
                scan_id,
                batch_size,
            )

            result = [(row["url"], row["depth"]) for row in rows]

            if result:
                logger.debug(
                    f"Popped {len(result)} URLs from queue {scan_id} "
                    f"(worker: {worker_id})"
                )

            return result

    async def mark_done(self, scan_id: str, urls: List[str]) -> None:
        """Позначає URLs як оброблені."""
        await self._ensure_initialized()

        if not urls:
            return

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE url_queue
                SET status = 'done', processed_at = NOW()
                WHERE scan_id = $1 AND url = ANY($2)
                """,
                scan_id,
                urls,
            )

    async def mark_failed(
        self, scan_id: str, urls: List[str], error: Optional[str] = None
    ) -> None:
        """Позначає URLs як failed."""
        await self._ensure_initialized()

        if not urls:
            return

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE url_queue
                SET status = 'failed', error = $3, processed_at = NOW()
                WHERE scan_id = $1 AND url = ANY($2)
                """,
                scan_id,
                urls,
                error,
            )

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
        await self._ensure_initialized()

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT status, COUNT(*) as count
                FROM url_queue
                WHERE scan_id = $1
                GROUP BY status
                """,
                scan_id,
            )

            stats = {
                "pending": 0,
                "processing": 0,
                "done": 0,
                "failed": 0,
                "total": 0,
            }

            for row in rows:
                stats[row["status"]] = row["count"]
                stats["total"] += row["count"]

            return stats

    async def clear(self, scan_id: str) -> None:
        """Очищає чергу для scan_id."""
        await self._ensure_initialized()

        async with self._pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM url_queue WHERE scan_id = $1", scan_id
            )
            logger.info(f"Cleared queue {scan_id}: {result}")

    async def reset_stuck_urls(self, scan_id: str, timeout_minutes: int = 30) -> int:
        """Скидає завислі URL назад в pending.

        Якщо URL в статусі 'processing' довше ніж timeout_minutes,
        він повертається в 'pending' для повторної обробки.

        Args:
            scan_id: ID сканування
            timeout_minutes: Таймаут в хвилинах

        Returns:
            Кількість скинутих URL
        """
        await self._ensure_initialized()

        async with self._pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE url_queue
                SET status = 'pending', worker_id = NULL
                WHERE scan_id = $1
                  AND status = 'processing'
                  AND processed_at < NOW() - INTERVAL '$2 minutes'
                """,
                scan_id,
                timeout_minutes,
            )

            # Parse result: "UPDATE 123"
            count = int(result.split()[-1]) if result.split() else 0

            if count > 0:
                logger.warning(
                    f"Reset {count} stuck URLs in queue {scan_id} "
                    f"(timeout: {timeout_minutes}m)"
                )

            return count

    async def close(self) -> None:
        """Закриває connection pool."""
        if self._pool:
            await self._pool.close()
            logger.info("PostgreSQLQueueStorage closed")
