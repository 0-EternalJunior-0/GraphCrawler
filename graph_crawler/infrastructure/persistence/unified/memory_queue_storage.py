"""In-memory Queue Storage.

Для малих проектів або тестування.
"""

import logging
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class MemoryQueueStorage:
    """URL Queue в пам'яті.

     Використовувати тільки для:
    - Тестування
    - Малих проектів (<10K URLs)
    """

    def __init__(self):
        # scan_id -> list of (url, depth, priority, status)
        self._queues: Dict[str, List[Dict]] = defaultdict(list)
        # scan_id -> set of processed URLs (для дедуплікації)
        self._seen: Dict[str, Set[str]] = defaultdict(set)
        logger.info("MemoryQueueStorage initialized")

    async def push_urls(
        self, scan_id: str, urls: List[Tuple[str, int, int]]  # (url, depth, priority)
    ) -> int:
        """Додає URLs до черги."""
        added = 0
        seen = self._seen[scan_id]
        queue = self._queues[scan_id]

        for url, depth, priority in urls:
            if url not in seen:
                seen.add(url)
                queue.append(
                    {
                        "url": url,
                        "depth": depth,
                        "priority": priority,
                        "status": "pending",
                        "created_at": datetime.now().isoformat(),
                    }
                )
                added += 1

        # Sort by priority desc
        queue.sort(key=lambda x: x["priority"], reverse=True)

        logger.debug(f"Added {added} URLs to queue {scan_id}")
        return added

    async def pop_urls(
        self, scan_id: str, batch_size: int = 24, worker_id: Optional[str] = None
    ) -> List[Tuple[str, int]]:
        """Отримує batch URLs для обробки."""
        queue = self._queues[scan_id]
        result = []

        for item in queue:
            if item["status"] == "pending":
                item["status"] = "processing"
                item["worker_id"] = worker_id
                result.append((item["url"], item["depth"]))

                if len(result) >= batch_size:
                    break

        return result

    async def mark_done(self, scan_id: str, urls: List[str]) -> None:
        """Позначає URLs як оброблені."""
        url_set = set(urls)
        for item in self._queues[scan_id]:
            if item["url"] in url_set:
                item["status"] = "done"

    async def mark_failed(
        self, scan_id: str, urls: List[str], error: Optional[str] = None
    ) -> None:
        """Позначає URLs як failed."""
        url_set = set(urls)
        for item in self._queues[scan_id]:
            if item["url"] in url_set:
                item["status"] = "failed"
                item["error"] = error

    async def get_stats(self, scan_id: str) -> Dict[str, int]:
        """Статистика черги."""
        queue = self._queues[scan_id]
        stats = {
            "pending": 0,
            "processing": 0,
            "done": 0,
            "failed": 0,
            "total": len(queue),
        }

        for item in queue:
            status = item.get("status", "pending")
            if status in stats:
                stats[status] += 1

        return stats

    async def clear(self, scan_id: str) -> None:
        """Очищає чергу."""
        self._queues[scan_id] = []
        self._seen[scan_id] = set()

    async def close(self) -> None:
        """Memory storage не потребує закриття."""
        pass
