"""
Memory Profiler - Моніторинг пам'яті під час краулінгу

Відстежує використання пам'яті та виявляє витоки:
- Snapshots пам'яті кожні N сторінок
- Порівняння snapshots для виявлення зростання
- Топ споживачів пам'яті
- Звіти з детальною статистикою

"""

import json
import logging
import time
import tracemalloc
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from graph_crawler.domain.events import CrawlerEvent, EventBus, EventType

logger = logging.getLogger(__name__)


class MemorySnapshot:
    """
    Snapshot пам'яті в конкретний момент часу.

    Attributes:
        timestamp: Час створення snapshot
        pages_crawled: Кількість сторінок на момент snapshot
        current_memory: Поточне використання пам'яті (MB)
        peak_memory: Пікове використання пам'яті (MB)
        top_stats: Топ споживачів пам'яті
    """

    def __init__(
        self,
        timestamp: float,
        pages_crawled: int,
        current_memory: float,
        peak_memory: float,
        top_stats: List[Tuple[str, int, int]],
    ):
        self.timestamp = timestamp
        self.pages_crawled = pages_crawled
        self.current_memory = current_memory
        self.peak_memory = peak_memory
        self.top_stats = top_stats

    def to_dict(self) -> Dict[str, Any]:
        """Конвертує snapshot в словник."""
        return {
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
            "pages_crawled": self.pages_crawled,
            "current_memory_mb": round(self.current_memory, 2),
            "peak_memory_mb": round(self.peak_memory, 2),
            "top_consumers": [
                {
                    "file": stat[0],
                    "size_mb": round(stat[1] / (1024 * 1024), 2),
                    "count": stat[2],
                }
                for stat in self.top_stats[:10]
            ],
        }


class MemoryProfiler:
    """
    Моніторинг пам'яті під час краулінгу з використанням tracemalloc.

    Features:
    - Автоматичні snapshots кожні N сторінок
    - Виявлення витоків пам'яті (порівняння snapshots)
    - Топ споживачів пам'яті по файлах
    - Експорт звітів в JSON
    - Warnings при перевищенні порогів

    Example:
        >>> from graph_crawler.domain.events import EventBus
        >>> from graph_crawler.monitoring import MemoryProfiler
        >>>
        >>> event_bus = EventBus()
        >>> profiler = MemoryProfiler(event_bus, snapshot_interval=100)
        >>>
        >>> # Після краулінгу
        >>> print(profiler.get_summary())
        >>> profiler.export_report("memory_report.json")
        >>>
        >>> # Перевірити чи є витоки
        >>> leaks = profiler.detect_memory_leaks()
        >>> if leaks:
        >>>     print(f"Warning: Memory leak detected! Growing: {leaks['growth_rate_mb_per_page']} MB/page")
    """

    def __init__(
        self,
        event_bus: EventBus,
        snapshot_interval: int = 100,
        max_snapshots: int = 50,
        memory_warning_threshold_mb: float = 500.0,
        enable_tracemalloc: bool = True,
    ):
        """
        Ініціалізує MemoryProfiler.

        Args:
            event_bus: EventBus для підписки на події
            snapshot_interval: Інтервал створення snapshots (кількість сторінок)
            max_snapshots: Максимальна кількість snapshots (старі видаляються)
            memory_warning_threshold_mb: Поріг для warning (MB)
            enable_tracemalloc: Чи включати tracemalloc (може уповільнити краулінг)
        """
        self.event_bus = event_bus
        self.snapshot_interval = snapshot_interval
        self.max_snapshots = max_snapshots
        self.memory_warning_threshold_mb = memory_warning_threshold_mb
        self.enable_tracemalloc = enable_tracemalloc

        # Стан
        self.is_running = False
        self.pages_crawled = 0
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None

        # Snapshots
        self.snapshots: List[MemorySnapshot] = []
        self.last_snapshot_pages = 0

        # Статистика
        self.peak_memory_mb = 0.0
        self.warnings_issued = 0
        self.warning_history: List[Dict[str, Any]] = []

        # Tracemalloc
        self.tracemalloc_started = False

        # Підписуємося на події
        self._subscribe_to_events()

        logger.info(
            f"MemoryProfiler initialized: "
            f"snapshot_interval={snapshot_interval}, "
            f"threshold={memory_warning_threshold_mb}MB"
        )

    def _subscribe_to_events(self):
        """Підписується на події краулінгу."""
        self.event_bus.subscribe(EventType.CRAWL_STARTED, self._on_crawl_started)
        self.event_bus.subscribe(EventType.CRAWL_COMPLETED, self._on_crawl_completed)
        self.event_bus.subscribe(EventType.NODE_SCANNED, self._on_node_scanned)

    def _on_crawl_started(self, event: CrawlerEvent):
        """Обробка події початку краулінгу."""
        self.is_running = True
        self.start_time = time.time()
        self.pages_crawled = 0
        self.last_snapshot_pages = 0

        # Запускаємо tracemalloc
        if self.enable_tracemalloc and not self.tracemalloc_started:
            try:
                tracemalloc.start()
                self.tracemalloc_started = True
                logger.info("tracemalloc started for memory profiling")
            except Exception as e:
                logger.warning(f"Failed to start tracemalloc: {e}")

        # Створюємо початковий snapshot
        self._create_snapshot()

        logger.info(" Memory profiling started")

    def _on_crawl_completed(self, event: CrawlerEvent):
        """Обробка події завершення краулінгу."""
        self.is_running = False
        self.end_time = time.time()

        # Створюємо фінальний snapshot
        self._create_snapshot()

        # Аналізуємо витоки
        leaks = self.detect_memory_leaks()
        if leaks:
            logger.warning(
                f" Memory leak detected: "
                f"{leaks['growth_rate_mb_per_page']:.3f} MB/page growth"
            )

        logger.info(
            f" Memory profiling completed: "
            f"peak={self.peak_memory_mb:.2f}MB, "
            f"snapshots={len(self.snapshots)}, "
            f"warnings={self.warnings_issued}"
        )

    def _on_node_scanned(self, event: CrawlerEvent):
        """Обробка події сканування вузла."""
        self.pages_crawled += 1

        # Перевіряємо чи треба створити snapshot
        if self.pages_crawled - self.last_snapshot_pages >= self.snapshot_interval:
            self._create_snapshot()
            self.last_snapshot_pages = self.pages_crawled

    def _create_snapshot(self):
        """Створює snapshot поточного стану пам'яті."""
        if not self.tracemalloc_started:
            return

        try:
            # Отримуємо поточну та пікову пам'ять
            current, peak = tracemalloc.get_traced_memory()
            current_mb = current / (1024 * 1024)
            peak_mb = peak / (1024 * 1024)

            # Оновлюємо піковий показник
            if peak_mb > self.peak_memory_mb:
                self.peak_memory_mb = peak_mb

            # Перевіряємо threshold
            if current_mb > self.memory_warning_threshold_mb:
                self._issue_warning(current_mb)

            # Отримуємо топ споживачів
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics("lineno")

            # Групуємо по файлах
            file_stats: Dict[str, Tuple[int, int]] = defaultdict(lambda: (0, 0))
            for stat in top_stats:
                filename = stat.traceback.format()[0] if stat.traceback else "unknown"
                size, count = file_stats[filename]
                file_stats[filename] = (size + stat.size, count + stat.count)

            # Сортуємо по розміру
            top_files = sorted(
                [(f, s, c) for f, (s, c) in file_stats.items()],
                key=lambda x: x[1],
                reverse=True,
            )[:20]

            # Створюємо snapshot
            mem_snapshot = MemorySnapshot(
                timestamp=time.time(),
                pages_crawled=self.pages_crawled,
                current_memory=current_mb,
                peak_memory=peak_mb,
                top_stats=top_files,
            )

            self.snapshots.append(mem_snapshot)

            # Обмежуємо кількість snapshots
            if len(self.snapshots) > self.max_snapshots:
                self.snapshots.pop(0)

            logger.debug(
                f" Memory snapshot created: "
                f"pages={self.pages_crawled}, "
                f"current={current_mb:.2f}MB, "
                f"peak={peak_mb:.2f}MB"
            )

        except Exception as e:
            logger.error(f"Failed to create memory snapshot: {e}", exc_info=True)

    def _issue_warning(self, current_mb: float):
        """Видає попередження про високе використання пам'яті."""
        self.warnings_issued += 1
        warning = {
            "timestamp": time.time(),
            "pages_crawled": self.pages_crawled,
            "memory_mb": current_mb,
            "threshold_mb": self.memory_warning_threshold_mb,
        }
        self.warning_history.append(warning)

        logger.warning(
            f" Memory warning #{self.warnings_issued}: "
            f"{current_mb:.2f}MB exceeds threshold {self.memory_warning_threshold_mb}MB "
            f"(pages: {self.pages_crawled})"
        )

        # Публікуємо подію
        self.event_bus.publish(
            CrawlerEvent.create(
                EventType.ERROR_OCCURRED,
                data={
                    "error_type": "MemoryWarning",
                    "message": f"Memory usage {current_mb:.2f}MB exceeds threshold",
                    "memory_mb": current_mb,
                    "threshold_mb": self.memory_warning_threshold_mb,
                },
            )
        )

    def detect_memory_leaks(self) -> Optional[Dict[str, Any]]:
        """
        Виявляє витоки пам'яті шляхом аналізу snapshots.

        Витік виявляється якщо пам'ять постійно зростає між snapshots.

        Returns:
            Словник з інформацією про витік або None якщо витоку немає
        """
        if len(self.snapshots) < 3:
            return None

        # Беремо перший та останній snapshot
        first = self.snapshots[0]
        last = self.snapshots[-1]

        # Розраховуємо зростання
        memory_growth = last.current_memory - first.current_memory
        pages_diff = last.pages_crawled - first.pages_crawled

        if pages_diff == 0:
            return None

        growth_rate = memory_growth / pages_diff

        # Витік якщо зростання > 0.1 MB на сторінку
        if growth_rate > 0.1:
            # Знаходимо файли що найбільше виросли
            growing_files = self._find_growing_files()

            return {
                "detected": True,
                "memory_growth_mb": round(memory_growth, 2),
                "pages_crawled": pages_diff,
                "growth_rate_mb_per_page": round(growth_rate, 3),
                "initial_memory_mb": round(first.current_memory, 2),
                "final_memory_mb": round(last.current_memory, 2),
                "growing_files": growing_files[:10],
                "recommendation": "Check for unclosed resources, large caches, or circular references",
            }

        return None

    def _find_growing_files(self) -> List[Dict[str, Any]]:
        """Знаходить файли де пам'ять найбільше зростає."""
        if len(self.snapshots) < 2:
            return []

        first = self.snapshots[0]
        last = self.snapshots[-1]

        # Створюємо мапу файл → розмір для першого snapshot
        first_sizes = {stat[0]: stat[1] for stat in first.top_stats}

        # Порівнюємо з останнім snapshot
        growing = []
        for filename, size, count in last.top_stats:
            initial_size = first_sizes.get(filename, 0)
            growth = size - initial_size

            if growth > 0:
                growing.append(
                    {
                        "file": filename,
                        "growth_bytes": growth,
                        "growth_mb": round(growth / (1024 * 1024), 2),
                        "initial_mb": round(initial_size / (1024 * 1024), 2),
                        "final_mb": round(size / (1024 * 1024), 2),
                    }
                )

        # Сортуємо по зростанню
        growing.sort(key=lambda x: x["growth_bytes"], reverse=True)
        return growing

    def get_summary(self) -> str:
        """
        Генерує текстовий звіт про використання пам'яті.

        Returns:
            Багаторядковий текстовий звіт
        """
        lines = []
        lines.append("=" * 60)
        lines.append(" MEMORY PROFILING REPORT")
        lines.append("=" * 60)

        # Загальна інформація
        lines.append(f"\n General Statistics:")
        lines.append(f"  Pages crawled: {self.pages_crawled}")
        lines.append(f"  Snapshots taken: {len(self.snapshots)}")
        lines.append(f"  Peak memory: {self.peak_memory_mb:.2f} MB")
        lines.append(f"  Warnings issued: {self.warnings_issued}")

        if self.start_time and self.end_time:
            duration = self.end_time - self.start_time
            lines.append(f"  Duration: {duration:.1f}s")

        # Snapshot статистика
        if self.snapshots:
            first = self.snapshots[0]
            last = self.snapshots[-1]

            lines.append(f"\n Memory Snapshots:")
            lines.append(f"  Initial memory: {first.current_memory:.2f} MB")
            lines.append(f"  Final memory: {last.current_memory:.2f} MB")
            lines.append(
                f"  Memory change: {last.current_memory - first.current_memory:+.2f} MB"
            )

            if last.pages_crawled > 0:
                avg_per_page = last.current_memory / last.pages_crawled
                lines.append(f"  Avg per page: {avg_per_page:.3f} MB/page")

        # Витоки пам'яті
        leaks = self.detect_memory_leaks()
        if leaks:
            lines.append(f"\n MEMORY LEAK DETECTED:")
            lines.append(f"  Growth rate: {leaks['growth_rate_mb_per_page']} MB/page")
            lines.append(f"  Total growth: {leaks['memory_growth_mb']} MB")
            lines.append(f"  Recommendation: {leaks['recommendation']}")

            if leaks.get("growing_files"):
                lines.append(f"\n  Top growing files:")
                for file_info in leaks["growing_files"][:5]:
                    lines.append(
                        f"    - {file_info['file']}: "
                        f"+{file_info['growth_mb']} MB "
                        f"({file_info['initial_mb']} → {file_info['final_mb']} MB)"
                    )
        else:
            lines.append(f"\nNo significant memory leaks detected")

        # Warnings
        if self.warning_history:
            lines.append(f"\n Warnings History:")
            for warning in self.warning_history[-5:]:
                lines.append(
                    f"  - Pages {warning['pages_crawled']}: "
                    f"{warning['memory_mb']:.2f} MB "
                    f"(threshold: {warning['threshold_mb']} MB)"
                )

        # Топ споживачі
        if self.snapshots:
            last_snapshot = self.snapshots[-1]
            lines.append(f"\n Top Memory Consumers (Current):")
            for i, stat in enumerate(last_snapshot.top_stats[:10], 1):
                filename, size, count = stat
                size_mb = size / (1024 * 1024)
                lines.append(
                    f"  {i}. {filename[:50]}: {size_mb:.2f} MB ({count} objects)"
                )

        lines.append("\n" + "=" * 60)

        return "\n".join(lines)

    def export_report(self, filepath: str):
        """
        Експортує повний звіт в JSON файл.

        Args:
            filepath: Шлях до файлу для збереження
        """
        report = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "pages_crawled": self.pages_crawled,
                "duration_seconds": (
                    (self.end_time - self.start_time)
                    if self.start_time and self.end_time
                    else None
                ),
                "peak_memory_mb": round(self.peak_memory_mb, 2),
                "warnings_issued": self.warnings_issued,
            },
            "configuration": {
                "snapshot_interval": self.snapshot_interval,
                "max_snapshots": self.max_snapshots,
                "memory_warning_threshold_mb": self.memory_warning_threshold_mb,
                "tracemalloc_enabled": self.enable_tracemalloc,
            },
            "snapshots": [snapshot.to_dict() for snapshot in self.snapshots],
            "memory_leak_analysis": self.detect_memory_leaks(),
            "warnings": self.warning_history,
        }

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            logger.info(f"Memory report exported to {filepath}")
        except Exception as e:
            logger.error(f"Failed to export memory report: {e}", exc_info=True)

    def reset(self):
        """Скидає всю статистику (для нового краулінгу)."""
        self.pages_crawled = 0
        self.start_time = None
        self.end_time = None
        self.snapshots.clear()
        self.last_snapshot_pages = 0
        self.peak_memory_mb = 0.0
        self.warnings_issued = 0
        self.warning_history.clear()
        logger.info(" MemoryProfiler reset")

    def stop(self):
        """Зупиняє profiling та tracemalloc."""
        if self.tracemalloc_started:
            try:
                tracemalloc.stop()
                self.tracemalloc_started = False
                logger.info("⏹ tracemalloc stopped")
            except Exception as e:
                logger.warning(f"Failed to stop tracemalloc: {e}")

        self.is_running = False
