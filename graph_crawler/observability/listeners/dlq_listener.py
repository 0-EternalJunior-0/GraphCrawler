"""
DLQ Listener - підписується на події помилок та інтегрує з DeadLetterQueue

"""

import logging
from typing import Optional

from graph_crawler.application.use_cases.crawling.dead_letter_queue import (
    DeadLetterQueue,
)
from graph_crawler.domain.entities.error_handler import ErrorHandler
from graph_crawler.domain.events import CrawlerEvent, EventBus, EventType

logger = logging.getLogger(__name__)


class DLQListener:
    """
    Event listener що інтегрує DeadLetterQueue та ErrorHandler з EventBus.

    Підписується на події:
    - NODE_FAILED: коли node не вдалось завантажити
    - ERROR_OCCURRED: коли виникає будь-яка помилка
    - RETRY_ATTEMPTED: коли робиться retry спроба

    Автоматично додає failed URLs в DLQ та обробляє через ErrorHandler.

    Example:
        >>> from graph_crawler.domain.events import EventBus
        >>> from graph_crawler.application.use_cases.crawling.dead_letter_queue import DeadLetterQueue
        >>> from graph_crawler.domain.entities.error_handler import ErrorHandler
        >>> from graph_crawler.observability.listeners.dlq_listener import DLQListener
        >>>
        >>> event_bus = EventBus()
        >>> dlq = DeadLetterQueue(max_retries=3)
        >>> error_handler = ErrorHandler(dead_letter_queue=dlq)
        >>>
        >>> # Створюємо та підписуємо listener
        >>> dlq_listener = DLQListener(
        ...     event_bus=event_bus,
        ...     dead_letter_queue=dlq,
        ...     error_handler=error_handler
        ... )
        >>>
        >>> # Тепер всі події помилок автоматично обробляються
    """

    def __init__(
        self,
        event_bus: EventBus,
        dead_letter_queue: Optional[DeadLetterQueue] = None,
        error_handler: Optional[ErrorHandler] = None,
    ):
        """
        Ініціалізує DLQ Listener.

        Args:
            event_bus: EventBus для підписки на події
            dead_letter_queue: DeadLetterQueue (optional, створюється автоматично)
            error_handler: ErrorHandler (optional, створюється автоматично)
        """
        self.event_bus = event_bus
        self.dlq = dead_letter_queue or DeadLetterQueue()
        self.error_handler = error_handler or ErrorHandler(dead_letter_queue=self.dlq)

        # Підписуємось на події
        self._subscribe_to_events()

        logger.info("DLQListener initialized and subscribed to events")

    def _subscribe_to_events(self) -> None:
        """Підписується на події помилок."""
        self.event_bus.subscribe(EventType.NODE_FAILED, self._on_node_failed)
        self.event_bus.subscribe(EventType.ERROR_OCCURRED, self._on_error_occurred)
        self.event_bus.subscribe(EventType.RETRY_ATTEMPTED, self._on_retry_attempted)

        logger.debug(
            "Subscribed to NODE_FAILED, ERROR_OCCURRED, RETRY_ATTEMPTED events"
        )

    def _on_node_failed(self, event: CrawlerEvent) -> None:
        """
        Обробляє подію NODE_FAILED.

        Args:
            event: CrawlerEvent з данними про failed node
        """
        url = event.data.get("url", "unknown")
        error_message = event.data.get("error", "Unknown error")
        error_type = event.data.get("error_type", "UnknownError")
        depth = event.data.get("depth", 0)
        source_url = event.data.get("source_url")

        logger.info(f"DLQListener: NODE_FAILED event for {url}")

        # Додаємо в DLQ
        self.dlq.add_failed_url(
            url=url,
            error_message=str(error_message),
            error_type=error_type,
            depth=depth,
            source_url=source_url,
        )

        # Також обробляємо через ErrorHandler для класифікації
        try:
            # Створюємо Exception об'єкт для ErrorHandler
            error = Exception(error_message)
            error.__class__.__name__ = error_type

            self.error_handler.handle_error(
                error=error,
                url=url,
                context={
                    "depth": depth,
                    "source_url": source_url,
                    "event_type": "NODE_FAILED",
                },
            )
        except Exception as e:
            logger.error(f"Error in ErrorHandler: {e}", exc_info=True)

    def _on_error_occurred(self, event: CrawlerEvent) -> None:
        """
        Обробляє подію ERROR_OCCURRED.

        Args:
            event: CrawlerEvent з данними про помилку
        """
        error_message = event.data.get("error", "Unknown error")
        error_type = event.data.get("error_type", "UnknownError")
        url = event.data.get("url")

        if not url:
            logger.debug("ERROR_OCCURRED event without URL, skipping DLQ")
            return

        logger.info(f"DLQListener: ERROR_OCCURRED event for {url}")

        # Обробляємо через ErrorHandler
        try:
            # Створюємо error object з типом
            if error_type:
                # Створюємо динамічний exception клас з правильним типом
                error_class = type(error_type, (Exception,), {})
                error = error_class(error_message)
            else:
                error = Exception(error_message)

            self.error_handler.handle_error(
                error=error,
                url=url,
                context={"event_type": "ERROR_OCCURRED", **event.data},
            )
        except Exception as e:
            logger.error(f"Error in ErrorHandler: {e}", exc_info=True)

    def _on_retry_attempted(self, event: CrawlerEvent) -> None:
        """
        Обробляє подію RETRY_ATTEMPTED.

        Args:
            event: CrawlerEvent з данними про retry спробу
        """
        url = event.data.get("url", "unknown")
        attempt = event.data.get("attempt", 0)

        logger.info(f"DLQListener: RETRY_ATTEMPTED event for {url} (attempt {attempt})")

        # Просто логуємо, реальна retry логіка в DLQ
        if url in self.dlq.failed_urls:
            failed_url = self.dlq.failed_urls[url]
            logger.debug(
                f"URL in DLQ: attempts={failed_url.attempt_count}, "
                f"permanent={failed_url.is_permanent_failure}"
            )

    def get_statistics(self) -> dict:
        """
        Повертає об'єднану статистику DLQ та ErrorHandler.

        Returns:
            Dict з статистикою
        """
        dlq_stats = self.dlq.get_statistics()
        error_handler_stats = self.error_handler.get_statistics()

        return {"dlq": dlq_stats, "error_handler": error_handler_stats}

    def get_summary(self) -> str:
        """
        Повертає текстовий summary статистики.

        Returns:
            Форматований текст
        """
        dlq_summary = self.dlq.get_summary()
        error_stats = self.error_handler.get_statistics()

        summary = [
            dlq_summary,
            "",
            "=" * 60,
            "Error Handler Statistics",
            "=" * 60,
            f"Total Errors Processed:   {error_stats['total_errors']}",
            "",
            "By Category:",
            "-" * 60,
        ]

        for category, count in sorted(
            error_stats["errors_by_category"].items(), key=lambda x: x[1], reverse=True
        ):
            summary.append(f"  {category:20s} {count:>5d}")

        summary.append("")
        summary.append("By Severity:")
        summary.append("-" * 60)

        for severity, count in sorted(
            error_stats["errors_by_severity"].items(), key=lambda x: x[1], reverse=True
        ):
            summary.append(f"  {severity:20s} {count:>5d}")

        summary.append("=" * 60)

        return "\n".join(summary)
