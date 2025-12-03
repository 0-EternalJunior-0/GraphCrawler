"""
Metrics Collector - Збір детальних метрик краулінгу

Збирає та аналізує метрики через EventBus:
- Кількість оброблених сторінок
- Швидкість краулінгу (pages/second)
- Час завантаження сторінок
- Помилки по типах
- Загальна кількість посилань

"""

import json
import logging
import time
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from graph_crawler.domain.events import CrawlerEvent, EventBus, EventType

logger = logging.getLogger(__name__)


class MetricsCollector:
    """
    Збирає детальні метрики краулінгу через EventBus.

    Metrics:
    - pages_crawled: кількість оброблених сторінок
    - pages_failed: кількість невдалих сторінок
    - total_links: загальна кількість знайдених посилань
    - pages_per_second: швидкість краулінгу
    - average_fetch_time: середній час завантаження
    - errors_by_type: помилки згруповані по типах
    - fetch_times: список часу завантаження кожної сторінки

    Example:
        >>> from graph_crawler.domain.events import EventBus
        >>> from graph_crawler.monitoring import MetricsCollector
        >>>
        >>> event_bus = EventBus()
        >>> collector = MetricsCollector(event_bus)
        >>>
        >>> # Після краулінгу
        >>> print(collector.get_summary())
        >>> collector.export_to_json("metrics.json")
    """

    def __init__(self, event_bus: EventBus):
        """
        Ініціалізує MetricsCollector.

        Args:
            event_bus: EventBus для підписки на події
        """
        self.event_bus = event_bus

        # Основні метрики
        self.pages_crawled = 0
        self.pages_failed = 0
        self.pages_skipped = 0
        self.total_links = 0
        self.total_edges = 0

        # Час
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.fetch_times: List[float] = []

        # Помилки
        self.errors_by_type: Dict[str, int] = defaultdict(int)
        self.error_details: List[Dict[str, Any]] = []

        # Статистика по глибині
        self.pages_by_depth: Dict[int, int] = defaultdict(int)

        # Історія метрик (для графіків)
        self.history: List[Dict[str, Any]] = []
        self.last_snapshot_time: Optional[float] = None

        # Підписуємося на події
        self._subscribe_to_events()

        logger.info("MetricsCollector initialized")

    def _subscribe_to_events(self):
        """Підписується на всі релевантні події."""
        # Crawler події
        self.event_bus.subscribe(EventType.CRAWL_STARTED, self._on_crawl_started)
        self.event_bus.subscribe(EventType.CRAWL_COMPLETED, self._on_crawl_completed)

        # Node події
        self.event_bus.subscribe(EventType.NODE_SCANNED, self._on_node_scanned)
        self.event_bus.subscribe(EventType.NODE_FAILED, self._on_node_failed)
        self.event_bus.subscribe(
            EventType.NODE_SKIPPED_UNCHANGED, self._on_node_skipped
        )

        # Edge події
        self.event_bus.subscribe(EventType.EDGE_CREATED, self._on_edge_created)

        # Performance події
        self.event_bus.subscribe(EventType.PAGE_FETCH_TIME, self._on_page_fetch_time)

        # Error події
        self.event_bus.subscribe(EventType.ERROR_OCCURRED, self._on_error_occurred)

        logger.debug("Subscribed to crawler events")

    # === Event Handlers ===

    def _on_crawl_started(self, event: CrawlerEvent):
        """Обробка початку краулінгу."""
        self.start_time = time.time()
        self.last_snapshot_time = self.start_time
        logger.info(f" Metrics collection started for URL: {event.data.get('url')}")

    def _on_crawl_completed(self, event: CrawlerEvent):
        """Обробка завершення краулінгу."""
        self.end_time = time.time()

        # Остання snapshot метрик
        self._take_snapshot()

        logger.info(
            f" Metrics collection completed: "
            f"{self.pages_crawled} pages, "
            f"{self.pages_failed} failures, "
            f"{self.get_pages_per_second():.2f} pages/sec"
        )

    def _on_node_scanned(self, event: CrawlerEvent):
        """Обробка успішного скану ноди."""
        self.pages_crawled += 1

        # Записуємо глибину
        depth = event.data.get("depth", 0)
        self.pages_by_depth[depth] += 1

        # Збираємо кількість посилань
        links_count = event.data.get("links_count", 0)
        self.total_links += links_count

        # Час завантаження (якщо є в події)
        fetch_time = event.data.get("fetch_time")
        if fetch_time is not None:
            self.fetch_times.append(fetch_time)

        # Робимо snapshot кожні 10 сторінок
        if self.pages_crawled % 10 == 0:
            self._take_snapshot()

    def _on_node_failed(self, event: CrawlerEvent):
        """Обробка невдалої ноди."""
        self.pages_failed += 1

        # Записуємо тип помилки
        error_type = event.data.get("error_type", "unknown")
        self.errors_by_type[error_type] += 1

    def _on_node_skipped(self, event: CrawlerEvent):
        """Обробка пропущеної ноди (incremental mode)."""
        self.pages_skipped += 1

    def _on_edge_created(self, event: CrawlerEvent):
        """Обробка створення edge."""
        self.total_edges += 1

    def _on_page_fetch_time(self, event: CrawlerEvent):
        """Обробка події з часом завантаження сторінки."""
        fetch_time = event.data.get("duration", 0)
        if fetch_time > 0:
            self.fetch_times.append(fetch_time)

    def _on_error_occurred(self, event: CrawlerEvent):
        """Обробка помилки."""
        error_type = event.data.get("error_type", "unknown")
        error_message = event.data.get("error", "")

        self.errors_by_type[error_type] += 1

        # Зберігаємо деталі помилки (максимум 100 останніх)
        if len(self.error_details) < 100:
            self.error_details.append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "type": error_type,
                    "message": error_message,
                    "url": event.data.get("url", "unknown"),
                }
            )

    # === Snapshot System ===

    def _take_snapshot(self):
        """Робить snapshot поточних метрик для історії."""
        if self.start_time is None:
            return

        current_time = time.time()
        elapsed = current_time - self.start_time

        snapshot = {
            "timestamp": datetime.now().isoformat(),
            "elapsed_seconds": elapsed,
            "pages_crawled": self.pages_crawled,
            "pages_failed": self.pages_failed,
            "total_links": self.total_links,
            "pages_per_second": self.get_pages_per_second(),
            "average_fetch_time": self.get_average_fetch_time(),
        }

        self.history.append(snapshot)
        self.last_snapshot_time = current_time

    # === Metrics Calculations ===

    def get_pages_per_second(self) -> float:
        """
        Розраховує швидкість краулінгу (pages/second).

        Returns:
            Кількість сторінок за секунду
        """
        if self.start_time is None:
            return 0.0

        end = self.end_time if self.end_time else time.time()
        elapsed = end - self.start_time

        if elapsed == 0:
            return 0.0

        return self.pages_crawled / elapsed

    def get_average_fetch_time(self) -> float:
        """
        Розраховує середній час завантаження сторінки.

        Returns:
            Середній час в секундах
        """
        if not self.fetch_times:
            return 0.0

        return sum(self.fetch_times) / len(self.fetch_times)

    def get_min_fetch_time(self) -> float:
        """Мінімальний час завантаження."""
        return min(self.fetch_times) if self.fetch_times else 0.0

    def get_max_fetch_time(self) -> float:
        """Максимальний час завантаження."""
        return max(self.fetch_times) if self.fetch_times else 0.0

    def get_total_errors(self) -> int:
        """Загальна кількість помилок."""
        return sum(self.errors_by_type.values())

    def get_success_rate(self) -> float:
        """
        Розраховує відсоток успішних сторінок.

        Returns:
            Відсоток від 0 до 100
        """
        total = self.pages_crawled + self.pages_failed
        if total == 0:
            return 0.0

        return (self.pages_crawled / total) * 100

    def get_elapsed_time(self) -> float:
        """
        Повертає час з початку краулінгу.

        Returns:
            Час в секундах
        """
        if self.start_time is None:
            return 0.0

        end = self.end_time if self.end_time else time.time()
        return end - self.start_time

    # === Summary & Export ===

    def get_summary(self) -> str:
        """
        Генерує текстовий summary метрик для консолі.

        Returns:
            Відформатований текстовий звіт
        """
        elapsed = self.get_elapsed_time()

        lines = [
            "",
            "=" * 60,
            " CRAWLER METRICS SUMMARY",
            "=" * 60,
            "",
            "⏱  Duration:",
            f"   Total time: {elapsed:.2f}s ({elapsed/60:.1f} minutes)",
            "",
            " Pages:",
            f"   Crawled: {self.pages_crawled}",
            f"    Failed: {self.pages_failed}",
            f"   ⏭  Skipped: {self.pages_skipped}",
            f"    Success rate: {self.get_success_rate():.1f}%",
            "",
            " Performance:",
            f"   Speed: {self.get_pages_per_second():.2f} pages/second",
            f"   Avg fetch time: {self.get_average_fetch_time():.3f}s",
            f"   Min fetch time: {self.get_min_fetch_time():.3f}s",
            f"   Max fetch time: {self.get_max_fetch_time():.3f}s",
            "",
            " Links & Edges:",
            f"   Total links found: {self.total_links}",
            f"   Total edges created: {self.total_edges}",
        ]

        # Помилки по типах
        if self.errors_by_type:
            lines.extend(["", " Errors by type:"])
            for error_type, count in sorted(
                self.errors_by_type.items(), key=lambda x: -x[1]
            ):
                lines.append(f"   {error_type}: {count}")

        # Сторінки по глибині
        if self.pages_by_depth:
            lines.extend(["", " Pages by depth:"])
            for depth in sorted(self.pages_by_depth.keys()):
                count = self.pages_by_depth[depth]
                lines.append(f"   Depth {depth}: {count} pages")

        lines.extend(["", "=" * 60, ""])

        return "\n".join(lines)

    def get_metrics_dict(self) -> Dict[str, Any]:
        """
        Повертає метрики як словник.

        Returns:
            Словник з усіма метриками
        """
        return {
            "summary": {
                "pages_crawled": self.pages_crawled,
                "pages_failed": self.pages_failed,
                "pages_skipped": self.pages_skipped,
                "total_links": self.total_links,
                "total_edges": self.total_edges,
                "total_errors": self.get_total_errors(),
            },
            "performance": {
                "elapsed_time_seconds": self.get_elapsed_time(),
                "pages_per_second": self.get_pages_per_second(),
                "average_fetch_time_seconds": self.get_average_fetch_time(),
                "min_fetch_time_seconds": self.get_min_fetch_time(),
                "max_fetch_time_seconds": self.get_max_fetch_time(),
                "success_rate_percent": self.get_success_rate(),
            },
            "errors": {
                "by_type": dict(self.errors_by_type),
                "details": self.error_details[:10],  # Останні 10 помилок
            },
            "depth_distribution": dict(self.pages_by_depth),
            "history": self.history,
            "timestamps": {
                "started_at": (
                    datetime.fromtimestamp(self.start_time).isoformat()
                    if self.start_time
                    else None
                ),
                "completed_at": (
                    datetime.fromtimestamp(self.end_time).isoformat()
                    if self.end_time
                    else None
                ),
            },
        }

    def export_to_json(self, filepath: str) -> None:
        """
        Експортує метрики в JSON файл.

        Args:
            filepath: Шлях до файлу для збереження

        Example:
            >>> collector.export_to_json("metrics.json")
        """
        metrics = self.get_metrics_dict()

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(metrics, f, indent=2, ensure_ascii=False)

            logger.info(f"Metrics exported to {filepath}")
        except Exception as e:
            logger.error(f" Failed to export metrics: {e}")
            raise

    def reset(self):
        """Скидає всі метрики (для нового краулінгу)."""
        self.pages_crawled = 0
        self.pages_failed = 0
        self.pages_skipped = 0
        self.total_links = 0
        self.total_edges = 0
        self.start_time = None
        self.end_time = None
        self.fetch_times = []
        self.errors_by_type = defaultdict(int)
        self.error_details = []
        self.pages_by_depth = defaultdict(int)
        self.history = []
        self.last_snapshot_time = None

        logger.info("Metrics reset")
