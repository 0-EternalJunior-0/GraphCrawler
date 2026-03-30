"""StateManager — Crawler state persistence для resume capability.

Critical для production crawlers:
- Збереження стану для incremental crawling
- Відновлення після crash
- Checkpoint mechanism

Usage:
    manager = StateManager(
        state_dir=".crawler_state",
        event_bus=event_bus
    )

    # Зберегти стан
    await manager.save_checkpoint(crawler_id, state_dict)

    # Відновити стан
    state = await manager.load_checkpoint(crawler_id)
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from graph_crawler.domain.events import CrawlerEvent, EventBus, EventType

logger = logging.getLogger(__name__)


class StateManager:
    """
    Crawler state persistence для resume capability.

    Зберігає:
    - visited URLs (для Bloom filter відновлення)
    - queue стан
    - crawler statistics
    - custom state data

    Features:
    - Atomic writes (через temp file + rename)
    - JSON format для портативності
    - EventBus інтеграція для моніторингу
    - Auto-checkpoint підтримка

    Attributes:
        state_dir: Директорія для зберігання стану
        event_bus: EventBus для публікації подій
        auto_checkpoint_interval: Інтервал автоматичного checkpoint

    Example:
        >>> manager = StateManager(
        ...     state_dir=".crawler_state",
        ...     event_bus=event_bus
        ... )
        >>> await manager.save_checkpoint("crawl_123", {"visited": ["url1", "url2"]})
        >>> state = await manager.load_checkpoint("crawl_123")
    """

    def __init__(
        self,
        state_dir: str = ".crawler_state",
        event_bus: Optional[EventBus] = None,
        auto_checkpoint_interval: float = 300.0,  # 5 хвилин
    ):
        """Initialize StateManager.

        Args:
            state_dir: Директорія для зберігання checkpoint файлів
            event_bus: EventBus для публікації подій (optional)
            auto_checkpoint_interval: Інтервал автоматичного checkpoint в секундах
        """
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.event_bus = event_bus
        self.auto_checkpoint_interval = auto_checkpoint_interval
        self._auto_checkpoint_task: Optional[asyncio.Task] = None
        self._current_crawler_id: Optional[str] = None
        self._state_getter: Optional[Any] = None

    async def save_checkpoint(
        self,
        crawler_id: str,
        state: dict[str, Any],
    ) -> Path:
        """
        Save crawler state checkpoint.

        Використовує atomic write (temp file + rename) для безпеки даних.

        Args:
            crawler_id: Unique identifier for crawler session
            state: State dictionary to save. Should be JSON-serializable.

        Returns:
            Path to saved state file

        Raises:
            TypeError: If state contains non-serializable objects
            OSError: If file write fails
        """
        state_file = self.state_dir / f"{crawler_id}.json"

        checkpoint = {
            "crawler_id": crawler_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "1.0",
            "state": state,
        }

        # Atomic write: write to temp file, then rename
        temp_file = state_file.with_suffix(".tmp")
        try:
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._write_checkpoint_sync,
                temp_file,
                state_file,
                checkpoint,
            )

            logger.info(
                "Checkpoint saved: %s (size: %d bytes)",
                state_file,
                state_file.stat().st_size,
            )

            # Publish event
            if self.event_bus:
                self.event_bus.publish(
                    CrawlerEvent.create(
                        EventType.GRAPH_SAVED,
                        data={
                            "crawler_id": crawler_id,
                            "path": str(state_file),
                            "checkpoint_type": "state_checkpoint",
                            "timestamp": checkpoint["timestamp"],
                        },
                    )
                )

            return state_file

        except Exception as e:
            # Cleanup temp file on error
            if temp_file.exists():
                temp_file.unlink()
            logger.error("Failed to save checkpoint for %s: %s", crawler_id, e)
            raise

    def _write_checkpoint_sync(
        self,
        temp_file: Path,
        state_file: Path,
        checkpoint: dict[str, Any],
    ) -> None:
        """Synchronous checkpoint write (runs in executor)."""
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(checkpoint, f, indent=2, default=str, ensure_ascii=False)
        temp_file.rename(state_file)

    async def load_checkpoint(
        self,
        crawler_id: str,
    ) -> Optional[dict[str, Any]]:
        """
        Load crawler state from checkpoint.

        Args:
            crawler_id: Unique identifier for crawler session

        Returns:
            State dictionary or None if not found
        """
        state_file = self.state_dir / f"{crawler_id}.json"

        if not state_file.exists():
            logger.info("No checkpoint found for: %s", crawler_id)
            return None

        try:
            loop = asyncio.get_event_loop()
            checkpoint = await loop.run_in_executor(
                None,
                self._read_checkpoint_sync,
                state_file,
            )

            logger.info(
                "Checkpoint loaded: %s (saved at %s)",
                crawler_id,
                checkpoint.get("timestamp", "unknown"),
            )

            # Publish event
            if self.event_bus:
                self.event_bus.publish(
                    CrawlerEvent.create(
                        EventType.GRAPH_LOADED,
                        data={
                            "crawler_id": crawler_id,
                            "path": str(state_file),
                            "checkpoint_type": "state_checkpoint",
                            "timestamp": checkpoint.get("timestamp"),
                        },
                    )
                )

            return checkpoint.get("state")

        except json.JSONDecodeError as e:
            logger.error("Corrupted checkpoint file %s: %s", state_file, e)
            return None
        except Exception as e:
            logger.error("Failed to load checkpoint %s: %s", crawler_id, e)
            return None

    def _read_checkpoint_sync(self, state_file: Path) -> dict[str, Any]:
        """Synchronous checkpoint read (runs in executor)."""
        with open(state_file, "r", encoding="utf-8") as f:
            result: dict[str, Any] = json.load(f)
            return result

    async def delete_checkpoint(self, crawler_id: str) -> bool:
        """Delete checkpoint after successful crawl completion.

        Args:
            crawler_id: Unique identifier for crawler session

        Returns:
            True if checkpoint was deleted, False if not found
        """
        state_file = self.state_dir / f"{crawler_id}.json"

        if state_file.exists():
            state_file.unlink()
            logger.info("Checkpoint deleted: %s", crawler_id)
            return True
        return False

    def list_checkpoints(self) -> list[str]:
        """List all available checkpoint IDs.

        Returns:
            List of crawler IDs with saved checkpoints
        """
        return [f.stem for f in self.state_dir.glob("*.json")]

    def get_checkpoint_info(self, crawler_id: str) -> Optional[dict[str, Any]]:
        """Get checkpoint metadata without loading full state.

        Args:
            crawler_id: Unique identifier for crawler session

        Returns:
            Dictionary with checkpoint info or None if not found
        """
        state_file = self.state_dir / f"{crawler_id}.json"

        if not state_file.exists():
            return None

        stat = state_file.stat()
        return {
            "crawler_id": crawler_id,
            "path": str(state_file),
            "size_bytes": stat.st_size,
            "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        }

    async def start_auto_checkpoint(
        self,
        crawler_id: str,
        state_getter: Any,
    ) -> None:
        """Start auto-checkpoint loop.

        Args:
            crawler_id: Unique identifier for crawler session
            state_getter: Callable that returns current state dict
        """
        self._current_crawler_id = crawler_id
        self._state_getter = state_getter
        self._auto_checkpoint_task = asyncio.create_task(self._auto_checkpoint_loop())
        logger.info(
            "Auto-checkpoint started for %s (interval: %.0fs)",
            crawler_id,
            self.auto_checkpoint_interval,
        )

    async def stop_auto_checkpoint(self) -> None:
        """Stop auto-checkpoint loop."""
        if self._auto_checkpoint_task:
            self._auto_checkpoint_task.cancel()
            try:
                await self._auto_checkpoint_task
            except asyncio.CancelledError:
                pass
            self._auto_checkpoint_task = None
        self._current_crawler_id = None
        self._state_getter = None
        logger.info("Auto-checkpoint stopped")

    async def _auto_checkpoint_loop(self) -> None:
        """Auto-checkpoint loop."""
        while True:
            try:
                await asyncio.sleep(self.auto_checkpoint_interval)
                if self._current_crawler_id and self._state_getter:
                    state = self._state_getter()
                    await self.save_checkpoint(self._current_crawler_id, state)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Auto-checkpoint error: %s", e)
