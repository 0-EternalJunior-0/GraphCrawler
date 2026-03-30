"""MemoryGuard — Memory usage monitor з auto-shutdown.

Critical для production crawlers:
- Моніторинг RAM usage
- Graceful shutdown при memory pressure
- Інтеграція через EventBus

Usage:
    guard = MemoryGuard(
        event_bus=event_bus,
        config=MemoryGuardConfig(limit_mb=1024)
    )
    await guard.start()
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional

import psutil

from graph_crawler.domain.events import CrawlerEvent, EventBus, EventType

logger = logging.getLogger(__name__)


@dataclass
class MemoryGuardConfig:
    """Configuration for memory monitoring.

    Attributes:
        limit_mb: Максимальне використання RAM в MB (shutdown trigger)
        warning_mb: Попереджувальний рівень RAM в MB
        check_interval_seconds: Інтервал перевірки в секундах
        auto_shutdown: Чи автоматично викликати shutdown при перевищенні ліміту
    """

    limit_mb: int = 512
    warning_mb: int = 400
    check_interval_seconds: float = 60.0
    auto_shutdown: bool = True


class MemoryGuard:
    """
    Memory usage monitor з auto-shutdown.

    Інтегрується через EventBus для graceful shutdown.
    Публікує події:
    - EventType.ERROR_OCCURRED з error_type="memory_limit_exceeded"
    - EventType.ERROR_OCCURRED з error_type="memory_warning"

    Attributes:
        event_bus: EventBus для публікації подій
        config: Конфігурація моніторингу
        shutdown_callback: Callback для graceful shutdown

    Example:
        >>> guard = MemoryGuard(
        ...     event_bus=event_bus,
        ...     config=MemoryGuardConfig(limit_mb=1024)
        ... )
        >>> await guard.start()
        ...
        >>> await guard.stop()
    """

    def __init__(
        self,
        event_bus: EventBus,
        config: Optional[MemoryGuardConfig] = None,
        shutdown_callback: Optional[Callable[[], Awaitable[None]]] = None,
    ):
        """Initialize MemoryGuard.

        Args:
            event_bus: EventBus для публікації подій
            config: Конфігурація (default: MemoryGuardConfig())
            shutdown_callback: Async callback для graceful shutdown
        """
        self.event_bus = event_bus
        self.config = config or MemoryGuardConfig()
        self.shutdown_callback = shutdown_callback
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._warning_emitted = False

    async def start(self) -> None:
        """Start memory monitoring loop."""
        if self._running:
            logger.warning("MemoryGuard already running")
            return

        self._running = True
        self._warning_emitted = False
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info(
            "MemoryGuard started: limit=%dMB, warning=%dMB, interval=%.1fs",
            self.config.limit_mb,
            self.config.warning_mb,
            self.config.check_interval_seconds,
        )

    async def stop(self) -> None:
        """Stop memory monitoring."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("MemoryGuard stopped")

    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                await asyncio.sleep(self.config.check_interval_seconds)
                if self._running:
                    await self._check_memory()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("MemoryGuard error: %s", e)

    async def _check_memory(self) -> None:
        """Check current memory and take action if needed."""
        memory_mb = self.get_current_usage_mb()

        if memory_mb > self.config.limit_mb:
            logger.error(
                "Memory LIMIT exceeded: %.1fMB (limit: %dMB)",
                memory_mb,
                self.config.limit_mb,
            )

            # Publish error event
            self.event_bus.publish(
                CrawlerEvent.create(
                    EventType.ERROR_OCCURRED,
                    data={
                        "error_type": "memory_limit_exceeded",
                        "memory_mb": round(memory_mb, 1),
                        "limit_mb": self.config.limit_mb,
                        "action": "shutdown" if self.config.auto_shutdown else "warning_only",
                    },
                )
            )

            if self.config.auto_shutdown and self.shutdown_callback:
                logger.warning("Initiating graceful shutdown due to memory limit")
                await self.shutdown_callback()

        elif memory_mb > self.config.warning_mb:
            if not self._warning_emitted:
                logger.warning(
                    "Memory WARNING: %.1fMB (warning threshold: %dMB)",
                    memory_mb,
                    self.config.warning_mb,
                )

                self.event_bus.publish(
                    CrawlerEvent.create(
                        EventType.ERROR_OCCURRED,
                        data={
                            "error_type": "memory_warning",
                            "memory_mb": round(memory_mb, 1),
                            "warning_mb": self.config.warning_mb,
                            "limit_mb": self.config.limit_mb,
                        },
                    )
                )
                self._warning_emitted = True
        else:
            # Reset warning flag if memory dropped below warning level
            self._warning_emitted = False
            logger.debug("Memory OK: %.1fMB", memory_mb)

    @staticmethod
    def get_current_usage_mb() -> float:
        """Get current process memory in MB.

        Returns:
            Current RSS memory usage in megabytes
        """
        process = psutil.Process()
        rss_bytes: int = process.memory_info().rss
        return rss_bytes / (1024 * 1024)

    def get_stats(self) -> dict[str, Any]:
        """Get memory statistics.

        Returns:
            Dictionary with memory stats:
            - rss_mb: Resident Set Size
            - vms_mb: Virtual Memory Size
            - percent: Memory percentage
            - limit_mb: Configured limit
            - warning_mb: Configured warning threshold
            - is_running: Whether guard is active
        """
        process = psutil.Process()
        mem_info = process.memory_info()
        return {
            "rss_mb": round(mem_info.rss / (1024 * 1024), 2),
            "vms_mb": round(mem_info.vms / (1024 * 1024), 2),
            "percent": round(process.memory_percent(), 2),
            "limit_mb": self.config.limit_mb,
            "warning_mb": self.config.warning_mb,
            "is_running": self._running,
        }

    @property
    def is_running(self) -> bool:
        """Check if MemoryGuard is currently monitoring."""
        return self._running
