"""File-based URL Queue Storage (SQLite).

Черга URL для сканування, зберігається в SQLite.
Для великих сканів (50M+) рекомендується PostgreSQL.
"""

import asyncio
import logging
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# SQL Schemas
CREATE_QUEUE_TABLE = """
CREATE TABLE IF NOT EXISTS url_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id TEXT NOT NULL,
    url TEXT NOT NULL,
    depth INTEGER DEFAULT 0,
    priority INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    worker_id TEXT,
    error TEXT,
    created_at TEXT,
    processed_at TEXT,
    UNIQUE(scan_id, url)
)
"""

CREATE_QUEUE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_queue_scan_status ON url_queue(scan_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_queue_priority ON url_queue(scan_id, priority DESC, created_at)",
]


class FileQueueStorage:
    """URL Queue в SQLite файлі.

    Зберігає чергу URL для сканування з підтримкою:
    - Пріоритетів
    - Дедуплікації
    - Статусів (pending/processing/done/failed)

    Example:
        queue = FileQueueStorage(storage_dir="./crawl_data")
        await queue.push_urls("scan_1", [("https://...", 0, 10)])
        urls = await queue.pop_urls("scan_1", batch_size=24)
    """

    def __init__(self, storage_dir: str = "./crawl_data"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.storage_dir / "queue.db"

        self._executor = ThreadPoolExecutor(max_workers=2)
        self._init_db()
        logger.info(f"FileQueueStorage initialized: {self.db_path}")

    def _init_db(self):
        """Створює таблиці."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(CREATE_QUEUE_TABLE)
            for index_sql in CREATE_QUEUE_INDEXES:
                conn.execute(index_sql)
            conn.commit()
        finally:
            conn.close()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    async def _run_in_executor(self, func, *args):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, func, *args)

    def _sync_push_urls(self, scan_id: str, urls: List[Tuple[str, int, int]]) -> int:
        """Sync версія push_urls."""
        conn = self._get_conn()
        added = 0
        try:
            now = datetime.now().isoformat()
            for url, depth, priority in urls:
                try:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO url_queue
                        (scan_id, url, depth, priority, status, created_at)
                        VALUES (?, ?, ?, ?, 'pending', ?)
                        """,
                        (scan_id, url, depth, priority, now),
                    )
                    if conn.total_changes:
                        added += 1
                except sqlite3.IntegrityError:
                    # Duplicate URL - skip
                    pass
            conn.commit()
        finally:
            conn.close()
        return added

    async def push_urls(self, scan_id: str, urls: List[Tuple[str, int, int]]) -> int:
        """Додає URLs до черги."""
        result = await self._run_in_executor(self._sync_push_urls, scan_id, urls)
        logger.debug(f"Added {result} URLs to queue {scan_id}")
        return result

    def _sync_pop_urls(
        self, scan_id: str, batch_size: int, worker_id: Optional[str]
    ) -> List[Tuple[str, int]]:
        """Sync версія pop_urls."""
        conn = self._get_conn()
        try:
            # Select pending URLs
            cursor = conn.execute(
                """
                SELECT id, url, depth FROM url_queue
                WHERE scan_id = ? AND status = 'pending'
                ORDER BY priority DESC, created_at
                LIMIT ?
                """,
                (scan_id, batch_size),
            )
            rows = cursor.fetchall()

            if not rows:
                return []

            # Mark as processing
            ids = [row["id"] for row in rows]
            placeholders = ",".join("?" * len(ids))
            now = datetime.now().isoformat()

            conn.execute(
                f"""
                UPDATE url_queue
                SET status = 'processing', worker_id = ?, processed_at = ?
                WHERE id IN ({placeholders})
                """,
                [worker_id, now] + ids,
            )
            conn.commit()

            return [(row["url"], row["depth"]) for row in rows]
        finally:
            conn.close()

    async def pop_urls(
        self, scan_id: str, batch_size: int = 24, worker_id: Optional[str] = None
    ) -> List[Tuple[str, int]]:
        """Отримує batch URLs для обробки."""
        return await self._run_in_executor(
            self._sync_pop_urls, scan_id, batch_size, worker_id
        )

    def _sync_mark_done(self, scan_id: str, urls: List[str]) -> None:
        """Sync версія mark_done."""
        if not urls:
            return
        conn = self._get_conn()
        try:
            placeholders = ",".join("?" * len(urls))
            conn.execute(
                f"""
                UPDATE url_queue
                SET status = 'done'
                WHERE scan_id = ? AND url IN ({placeholders})
                """,
                [scan_id] + list(urls),
            )
            conn.commit()
        finally:
            conn.close()

    async def mark_done(self, scan_id: str, urls: List[str]) -> None:
        """Позначає URLs як оброблені."""
        await self._run_in_executor(self._sync_mark_done, scan_id, urls)

    def _sync_mark_failed(
        self, scan_id: str, urls: List[str], error: Optional[str]
    ) -> None:
        """Sync версія mark_failed."""
        if not urls:
            return
        conn = self._get_conn()
        try:
            placeholders = ",".join("?" * len(urls))
            conn.execute(
                f"""
                UPDATE url_queue
                SET status = 'failed', error = ?
                WHERE scan_id = ? AND url IN ({placeholders})
                """,
                [error, scan_id] + list(urls),
            )
            conn.commit()
        finally:
            conn.close()

    async def mark_failed(
        self, scan_id: str, urls: List[str], error: Optional[str] = None
    ) -> None:
        """Позначає URLs як failed."""
        await self._run_in_executor(self._sync_mark_failed, scan_id, urls, error)

    def _sync_get_stats(self, scan_id: str) -> Dict[str, int]:
        """Sync версія get_stats."""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                """
                SELECT status, COUNT(*) as count
                FROM url_queue
                WHERE scan_id = ?
                GROUP BY status
                """,
                (scan_id,),
            )

            stats = {"pending": 0, "processing": 0, "done": 0, "failed": 0, "total": 0}

            for row in cursor.fetchall():
                status = row["status"]
                count = row["count"]
                if status in stats:
                    stats[status] = count
                stats["total"] += count

            return stats
        finally:
            conn.close()

    async def get_stats(self, scan_id: str) -> Dict[str, int]:
        """Статистика черги."""
        return await self._run_in_executor(self._sync_get_stats, scan_id)

    def _sync_clear(self, scan_id: str) -> None:
        """Sync версія clear."""
        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM url_queue WHERE scan_id = ?", (scan_id,))
            conn.commit()
        finally:
            conn.close()

    async def clear(self, scan_id: str) -> None:
        """Очищає чергу."""
        await self._run_in_executor(self._sync_clear, scan_id)

    async def close(self) -> None:
        """Закриває executor."""
        self._executor.shutdown(wait=True)
        logger.info("FileQueueStorage closed")
