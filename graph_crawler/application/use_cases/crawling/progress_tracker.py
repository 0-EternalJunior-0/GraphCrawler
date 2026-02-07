"""
Crawl Progress Tracker - відстеження прогресу краулінгу.

Відокремлює відповідальність за tracking прогресу та публікацію подій
від основного класу GraphSpider (SRP - Single Responsibility Principle).
"""

import logging
import time
from typing import Optional

from graph_crawler.application.use_cases.crawling.scheduler import CrawlScheduler
from graph_crawler.domain.events import CrawlerEvent, EventBus, EventType
from graph_crawler.domain.value_objects.configs import CrawlerConfig
from graph_crawler.shared.constants import (
    MAX_PAGES_WARNING_THRESHOLD,
    PROGRESS_UPDATE_INTERVAL,
)

logger = logging.getLogger(__name__)


class CrawlProgressTracker:
    """
    Відстежує прогрес краулінгу та публікує події.

    Responsibilities:
    - Відстеження кількості просканованих сторінок
    - Публікація progress events
    - Попередження про досягнення лімітів
    - Обчислення метрик (avg time per page, progress %)

    Це окремий клас для дотримання SRP - тільки progress tracking.
    """

    def __init__(
        self,
        config: CrawlerConfig,
        scheduler: CrawlScheduler,
        event_bus: Optional[EventBus] = None,
    ):
        """
        Ініціалізує Progress Tracker.

        Args:
            config: Конфігурація краулера
            scheduler: Scheduler для отримання queue_size
            event_bus: Event bus для публікації подій
        """
        self.config = config
        self.scheduler = scheduler
        self.event_bus = event_bus

        self.pages_crawled = 0
        self.start_time = time.time()

    def increment_pages(self, count: int = 1) -> None:
        """
        Збільшує лічильник просканованих сторінок.

        Args:
            count: Кількість сторінок для додавання (для batch mode)
        """
        self.pages_crawled += count

        # Попередження про велику кількість сторінок
        if self.pages_crawled == MAX_PAGES_WARNING_THRESHOLD:
            logger.warning(
                f"  WARNING: Crawled {MAX_PAGES_WARNING_THRESHOLD} pages! "
                f"Consider using database storage for large graphs. "
                f"Current memory usage may be high."
            )

    def should_publish_progress(self) -> bool:
        """
        Перевіряє чи потрібно публікувати progress event.

        Returns:
            True якщо настав час публікації (кратне PROGRESS_UPDATE_INTERVAL)
        """
        return self.pages_crawled % PROGRESS_UPDATE_INTERVAL == 0

    def publish_progress_event(self) -> None:
        """Публікує подію про поточний прогрес."""
        if not self.event_bus:
            return

        progress_pct = 0.0
        if self.config.max_pages:
            progress_pct = self.pages_crawled / self.config.max_pages * 100

        self.event_bus.publish(
            CrawlerEvent.create(
                EventType.PROGRESS_UPDATE,
                data={
                    "pages_crawled": self.pages_crawled,
                    "max_pages": self.config.max_pages,
                    "queue_size": self.scheduler.size(),
                    "progress_pct": progress_pct,
                },
            )
        )

    def publish_node_scan_started(self, url: str, depth: int) -> None:
        """
        Публікує подію перед початком скану ноди.

        Args:
            url: URL ноди
            depth: Глибина ноди
        """
        if not self.event_bus:
            return

        self.event_bus.publish(
            CrawlerEvent.create(
                EventType.NODE_SCAN_STARTED, data={"url": url, "depth": depth}
            )
        )

    def publish_node_scanned(
        self,
        url: str,
        depth: int,
        title: Optional[str],
        links_found: int,
        fetch_time: float,
    ) -> None:
        """
        Публікує подію після скану ноди.

        Args:
            url: URL ноди
            depth: Глибина ноди
            title: Заголовок сторінки
            links_found: Кількість знайдених посилань
            fetch_time: Час завантаження сторінки
        """
        if not self.event_bus:
            return

        self.event_bus.publish(
            CrawlerEvent.create(
                EventType.NODE_SCANNED,
                data={
                    "url": url,
                    "depth": depth,
                    "title": title,
                    "links_found": links_found,
                    "fetch_time": fetch_time,
                },
            )
        )

    def publish_batch_completed(
        self,
        batch_size: int,
        batch_time: float,
    ) -> None:
        """
        Публікує подію після обробки batch.

        Args:
            batch_size: Розмір обробленого batch
            batch_time: Час обробки batch
        """
        if not self.event_bus:
            return

        avg_time_per_page = batch_time / batch_size if batch_size > 0 else 0

        self.event_bus.publish(
            CrawlerEvent.create(
                EventType.BATCH_COMPLETED,
                data={
                    "batch_size": batch_size,
                    "total_pages": self.pages_crawled,
                    "batch_time": batch_time,
                    "avg_time_per_page": avg_time_per_page,
                },
            )
        )

    @property
    def elapsed_time(self) -> float:
        """
        Повертає час з початку краулінгу.

        Returns:
            Час в секундах
        """
        return time.time() - self.start_time

    @property
    def avg_time_per_page(self) -> float:
        """
        Повертає середній час на одну сторінку.

        Returns:
            Середній час в секундах
        """
        return self.elapsed_time / max(self.pages_crawled, 1)

    @property
    def crawl_rate(self) -> float:
        """
        Повертає швидкість краулінгу (pages per second).

        Returns:
            Кількість сторінок за секунду
        """
        elapsed = self.elapsed_time
        return self.pages_crawled / elapsed if elapsed > 0 else 0.0

    def publish_crawl_completed(self) -> None:
        """Публікує подію про завершення краулінгу."""
        if not self.event_bus:
            return

        self.event_bus.publish(
            CrawlerEvent.create(
                EventType.CRAWL_COMPLETED,
                data={
                    "total_pages": self.pages_crawled,
                    "scanned_pages": self.pages_crawled,
                    "duration": self.elapsed_time,
                    "avg_time_per_page": self.avg_time_per_page,
                },
            )
        )

    def get_pages_crawled(self) -> int:
        """Повертає кількість просканованих сторінок."""
        return self.pages_crawled
