"""In-memory Job Storage.

Для малих проектів або тестування.
Всі дані втрачаються при перезапуску.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MemoryJobStorage:
    """Job storage в пам'яті.

     Використовувати тільки для:
    - Тестування
    - Малих проектів (<100 jobs)
    - Коли persistence не потрібен
    """

    def __init__(self):
        self._jobs: Dict[str, Dict[str, Any]] = {}
        logger.info("MemoryJobStorage initialized (no persistence!)")

    async def create_job(
        self, job_id: str, config: Dict[str, Any], status: str = "pending"
    ) -> None:
        """Створює новий job в пам'яті."""
        self._jobs[job_id] = {
            "job_id": job_id,
            "config": config,
            "status": status,
            "created_at": datetime.now().isoformat(),
            "started_at": None,
            "completed_at": None,
            "progress": {
                "pages_crawled": 0,
                "pages_total": config.get("max_pages", 100),
                "urls_in_queue": 0,
            },
            "result": None,
            "error": None,
        }
        logger.debug(f"Created job {job_id} in memory")

    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Отримує job за ID."""
        return self._jobs.get(job_id)

    async def update_job(self, job_id: str, updates: Dict[str, Any]) -> bool:
        """Оновлює поля job."""
        if job_id not in self._jobs:
            return False

        job = self._jobs[job_id]

        for key, value in updates.items():
            if key == "progress" and isinstance(value, dict):
                # Merge progress
                job.setdefault("progress", {})
                job["progress"].update(value)
            else:
                job[key] = value

        return True

    async def list_jobs(
        self, status: Optional[str] = None, limit: int = 100, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Список jobs."""
        jobs = list(self._jobs.values())

        if status:
            jobs = [j for j in jobs if j.get("status") == status]

        # Sort by created_at desc
        jobs.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        return jobs[offset : offset + limit]

    async def delete_job(self, job_id: str) -> bool:
        """Видаляє job."""
        if job_id in self._jobs:
            del self._jobs[job_id]
            return True
        return False

    async def close(self) -> None:
        """Memory storage не потребує закриття."""
        pass

    def __len__(self) -> int:
        return len(self._jobs)
