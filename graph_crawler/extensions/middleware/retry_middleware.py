"""Retry Middleware - розумний повтор при помилці з exponential backoff та jitter .

Team 3: Reliability & DevOps
Task 3.1: Smart Retry with Exponential Backoff (P0)
Week 1 Використовує asyncio.sleep() замість time.sleep() для неблокуючого очікування.
"""

import asyncio
import logging
import random
from typing import Dict, Optional

from graph_crawler.extensions.middleware.base import (
    BaseMiddleware,
    MiddlewareContext,
    MiddlewareType,
)
from graph_crawler.shared.constants import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_DELAY,
    DEFAULT_RETRY_EXPONENTIAL_BASE,
    HTTP_RETRYABLE_STATUS_CODES,
    HTTP_SERVICE_UNAVAILABLE,
    HTTP_TOO_MANY_REQUESTS,
)

logger = logging.getLogger(__name__)


class RetryMiddleware(BaseMiddleware):
    """
    Async розумні повтори при помилках з exponential backoff та jitter .

    Функціонал:
    - Exponential backoff: 1s, 2s, 4s, 8s...
    - Jitter для уникнення thundering herd
    - Різні стратегії для різних помилок:
      * 429 (Rate Limit) → довгий backoff (base_delay * 3)
      * 503 (Service Unavailable) → короткий backoff (base_delay * 0.5)
      * Timeout → середній backoff (base_delay * 1)
      * Інші 5xx → стандартний backoff (base_delay * 1)
    - Metrics: скільки разів retry спрацював Неблокуючий async sleep через asyncio.sleep().
    """

    def __init__(self, config: dict = None):
        super().__init__(config)
        self.attempt_counter: Dict[str, int] = {}  # URL -> кількість спроб

        # Metrics для tracking
        self.total_retries = 0
        self.retry_by_status: Dict[int, int] = {}  # status_code -> count
        self.successful_retries = 0  # Кількість успішних retry

    @property
    def middleware_type(self) -> MiddlewareType:
        return MiddlewareType.ON_ERROR

    @property
    def name(self) -> str:
        return "retry"

    def _get_status_code(self, context: MiddlewareContext) -> Optional[int]:
        """Витягує status code з контексту."""
        if context.response:
            return context.response.get("status_code")
        return None

    def _calculate_backoff(
        self,
        base_delay: float,
        attempt: int,
        status_code: Optional[int],
        enable_jitter: bool,
        jitter_factor: float,
    ) -> float:
        """
        Розраховує затримку з exponential backoff та jitter.
        """
        # Визначаємо множник на основі типу помилки
        if status_code == HTTP_TOO_MANY_REQUESTS:
            # Rate Limit - довгий backoff
            multiplier = 3.0
        elif status_code == HTTP_SERVICE_UNAVAILABLE:
            # Service Unavailable - короткий backoff
            multiplier = 0.5
        else:
            # Timeout та інші помилки - стандартний backoff
            multiplier = 1.0

        # Exponential backoff: delay = base_delay * multiplier * (2 ^ attempt)
        delay = base_delay * multiplier * (DEFAULT_RETRY_EXPONENTIAL_BASE**attempt)

        # Додаємо jitter для уникнення thundering herd
        if enable_jitter:
            jitter = random.uniform(0, delay * jitter_factor)
            delay += jitter

        return delay

    def get_metrics(self) -> dict:
        """Повертає метрики retry middleware."""
        return {
            "total_retries": self.total_retries,
            "successful_retries": self.successful_retries,
            "retry_by_status": dict(self.retry_by_status),
            "active_retries": len(self.attempt_counter),
        }

    async def process(self, context: MiddlewareContext) -> MiddlewareContext:
        """
        Async перевіряє чи потрібен повтор при помилці .

        Використовує asyncio.sleep() для неблокуючого очікування.

        Args:
            context: Контекст з помилкою

        Returns:
            Оновлений контекст з should_retry прапорцем
        """
        url = context.url
        max_retries = self.config.get("max_retries", DEFAULT_MAX_RETRIES)
        retry_delay = self.config.get("retry_delay", DEFAULT_RETRY_DELAY)
        exponential_backoff = self.config.get("exponential_backoff", True)
        retry_on_status = self.config.get(
            "retry_on_status", HTTP_RETRYABLE_STATUS_CODES
        )
        enable_jitter = self.config.get("enable_jitter", True)
        jitter_factor = self.config.get("jitter_factor", 0.1)

        # Ініціалізуємо лічільник для URL
        if url not in self.attempt_counter:
            self.attempt_counter[url] = 0

        status_code = self._get_status_code(context)

        # Перевіряємо чи була помилка
        if context.error or (status_code and status_code in retry_on_status):
            current_attempt = self.attempt_counter[url]

            # Перевіряємо чи не перевищено ліміт
            if current_attempt < max_retries:
                self.attempt_counter[url] += 1
                self.total_retries += 1

                # Оновлюємо статистику по status code
                if status_code:
                    self.retry_by_status[status_code] = (
                        self.retry_by_status.get(status_code, 0) + 1
                    )

                # Розраховуємо затримку з exponential backoff та jitter
                if exponential_backoff:
                    delay = self._calculate_backoff(
                        retry_delay,
                        current_attempt,
                        status_code,
                        enable_jitter,
                        jitter_factor,
                    )
                else:
                    delay = retry_delay

                error_msg = context.error or f"status {status_code}"
                logger.warning(
                    f"Retry {self.attempt_counter[url]}/{max_retries} for {url} "
                    f"after {delay:.2f}s (error: {error_msg})"
                )

                # Публікуємо подію про початок retry
                if self.event_bus:
                    from graph_crawler.domain.events.events import (
                        CrawlerEvent,
                        EventType,
                    )

                    self.event_bus.publish(
                        CrawlerEvent.create(
                            EventType.RETRY_STARTED,
                            data={
                                "url": url,
                                "attempt": self.attempt_counter[url],
                                "max_retries": max_retries,
                                "delay": delay,
                                "error": str(error_msg),
                                "status_code": status_code,
                                "exponential_backoff": exponential_backoff,
                            },
                        )
                    )

                await asyncio.sleep(delay)

                # Встановлюємо прапорець для повтору
                context.should_retry = True
            else:
                logger.error(f"Max retries ({max_retries}) exceeded for {url}")

                # Публікуємо подію про вичерпання retry
                if self.event_bus:
                    from graph_crawler.domain.events.events import (
                        CrawlerEvent,
                        EventType,
                    )

                    self.event_bus.publish(
                        CrawlerEvent.create(
                            EventType.RETRY_EXHAUSTED,
                            data={
                                "url": url,
                                "total_attempts": max_retries,
                                "error": (
                                    str(context.error)
                                    if context.error
                                    else f"status {status_code}"
                                ),
                                "status_code": status_code,
                            },
                        )
                    )

                context.should_retry = False
                # Очищаємо лічільник
                del self.attempt_counter[url]
        else:
            # Успішний запит
            if url in self.attempt_counter:
                # Це був успішний retry
                attempts_made = self.attempt_counter[url]
                self.successful_retries += 1
                logger.info(
                    f"Successful retry for {url} after {attempts_made} attempts"
                )

                # Публікуємо подію про успішний retry
                if self.event_bus:
                    from graph_crawler.domain.events.events import (
                        CrawlerEvent,
                        EventType,
                    )

                    self.event_bus.publish(
                        CrawlerEvent.create(
                            EventType.RETRY_SUCCESS,
                            data={
                                "url": url,
                                "attempts": attempts_made,
                                "total_retries": self.total_retries,
                                "successful_retries": self.successful_retries,
                            },
                        )
                    )

                del self.attempt_counter[url]
            context.should_retry = False

        return context
