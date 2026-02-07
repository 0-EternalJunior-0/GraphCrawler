"""File-based Job Storage (SQLite).

Це дефолтний storage для локального запуску.
Створює файл scans.db в директорії storage_dir.
"""

import asyncio
import json
import logging
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# SQL Schemas
CREATE_JOBS_TABLE = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    config TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    created_at TEXT,
    started_at TEXT,
    completed_at TEXT,
    progress TEXT,
    result TEXT,
    error TEXT
)
"""

CREATE_JOBS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)
"""


class FileJobStorage:
    """Job storage в SQLite файлі.

    Дефолтний storage для локального використання.
    Файл створюється в ./crawl_data/scans.db

    Переваги:
    - Persistence між сесіями
    - Низьке споживання RAM
    - Не потребує зовнішніх сервісів

    Example:
        storage = FileJobStorage(storage_dir="./crawl_data")
        await storage.create_job("job_1", {"url": "..."})
    """

    def __init__(self, storage_dir: str = "./crawl_data"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.storage_dir / "scans.db"

        # Thread pool для async SQLite
        self._executor = ThreadPoolExecutor(max_workers=1)

        # Ініціалізація БД
        self._init_db()
        logger.info(f"FileJobStorage initialized: {self.db_path}")

    def _init_db(self):
        """Створює таблиці якщо не існують."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(CREATE_JOBS_TABLE)
            conn.execute(CREATE_JOBS_INDEX)
            conn.commit()
        finally:
            conn.close()

    def _get_conn(self) -> sqlite3.Connection:
        """Отримує з'єднання з БД."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Конвертує row в dict."""
        result = dict(row)
        # Parse JSON fields
        for field in ["config", "progress", "result"]:
            if result.get(field):
                try:
                    result[field] = json.loads(result[field])
                except (json.JSONDecodeError, TypeError):
                    pass
        return result

    async def _run_in_executor(self, func, *args):
        """Виконує sync функцію в thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, func, *args)

    def _sync_create_job(
        self, job_id: str, config: Dict[str, Any], status: str
    ) -> None:
        """Sync версія create_job."""
        conn = self._get_conn()
        try:
            progress = {
                "pages_crawled": 0,
                "pages_total": config.get("max_pages", 100),
                "urls_in_queue": 0,
            }

            conn.execute(
                """
                INSERT INTO jobs (job_id, config, status, created_at, progress)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    json.dumps(config),
                    status,
                    datetime.now().isoformat(),
                    json.dumps(progress),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    async def create_job(
        self, job_id: str, config: Dict[str, Any], status: str = "pending"
    ) -> None:
        """Створює новий job."""
        await self._run_in_executor(self._sync_create_job, job_id, config, status)
        logger.debug(f"Created job {job_id} in SQLite")

    def _sync_get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Sync версія get_job."""
        conn = self._get_conn()
        try:
            cursor = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
            row = cursor.fetchone()
            return self._row_to_dict(row) if row else None
        finally:
            conn.close()

    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Отримує job за ID."""
        return await self._run_in_executor(self._sync_get_job, job_id)

    def _sync_update_job(self, job_id: str, updates: Dict[str, Any]) -> bool:
        """Sync версія update_job."""
        conn = self._get_conn()
        try:
            # Get current job
            cursor = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
            row = cursor.fetchone()
            if not row:
                return False

            current = self._row_to_dict(row)

            # Merge updates
            set_parts = []
            values = []

            for key, value in updates.items():
                if key == "progress" and isinstance(value, dict):
                    # Merge progress
                    current_progress = current.get("progress", {})
                    if isinstance(current_progress, dict):
                        current_progress.update(value)
                    else:
                        current_progress = value
                    set_parts.append("progress = ?")
                    values.append(json.dumps(current_progress))
                elif key in ["config", "result"]:
                    set_parts.append(f"{key} = ?")
                    values.append(json.dumps(value) if value else None)
                else:
                    set_parts.append(f"{key} = ?")
                    values.append(value)

            if set_parts:
                values.append(job_id)
                conn.execute(
                    f"UPDATE jobs SET {', '.join(set_parts)} WHERE job_id = ?",
                    tuple(values),
                )
                conn.commit()

            return True
        finally:
            conn.close()

    async def update_job(self, job_id: str, updates: Dict[str, Any]) -> bool:
        """Оновлює поля job."""
        return await self._run_in_executor(self._sync_update_job, job_id, updates)

    def _sync_list_jobs(
        self, status: Optional[str], limit: int, offset: int
    ) -> List[Dict[str, Any]]:
        """Sync версія list_jobs."""
        conn = self._get_conn()
        try:
            if status:
                cursor = conn.execute(
                    """
                    SELECT * FROM jobs
                    WHERE status = ?
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (status, limit, offset),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT * FROM jobs
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (limit, offset),
                )

            return [self._row_to_dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    async def list_jobs(
        self, status: Optional[str] = None, limit: int = 100, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Список jobs."""
        return await self._run_in_executor(self._sync_list_jobs, status, limit, offset)

    def _sync_delete_job(self, job_id: str) -> bool:
        """Sync версія delete_job."""
        conn = self._get_conn()
        try:
            cursor = conn.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    async def delete_job(self, job_id: str) -> bool:
        """Видаляє job."""
        return await self._run_in_executor(self._sync_delete_job, job_id)

    async def close(self) -> None:
        """Закриває executor."""
        self._executor.shutdown(wait=True)
        logger.info("FileJobStorage closed")
