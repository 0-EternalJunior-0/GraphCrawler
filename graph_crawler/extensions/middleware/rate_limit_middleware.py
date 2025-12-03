"""Rate Limiting Middleware - контроль швидкості запитів .

Реалізує Token Bucket алгоритм для обмеження частоти запитів.
Використовує asyncio.sleep() замість time.sleep() для неблокуючого очікування.
"""

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Optional

from graph_crawler.extensions.middleware.base import (
    BaseMiddleware,
    MiddlewareContext,
    MiddlewareType,
)

if TYPE_CHECKING:
    from graph_crawler.domain.events import EventBus

logger = logging.getLogger(__name__)


class TokenBucket:
    """
    Token Bucket алгоритм для rate limiting .

    Принцип роботи:
    - Відро містить токени (початково повне)
    - Кожен запит споживає 1 токен
    - Токени поповнюються з постійною швидкістю
    - Якщо токенів немає - запит чекає асинхронно

    Переваги:
    - Дозволяє burst traffic (короткі спалахи)
    - Згладжує навантаження в довгостроковій перспективі
    - Простий та ефективний
    - Неблокуючий async wait

    Args:
        capacity: Максимальна кількість токенів (burst size)
        refill_rate: Швидкість поповнення токенів (токенів на секунду)
        event_bus: Event bus для публікації подій (опціонально, DI)
    """

    def __init__(
        self,
        capacity: float,
        refill_rate: float,
        event_bus: Optional["EventBus"] = None,
    ):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill_time = time.time()
        self._lock = asyncio.Lock()
        self.event_bus = event_bus

    def _refill(self):
        """Поповнює токени на основі часу, що минув."""
        now = time.time()
        elapsed = now - self.last_refill_time

        # Розраховуємо скільки токенів додати
        tokens_to_add = elapsed * self.refill_rate

        # Додаємо токени, але не більше capacity
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill_time = now

    async def consume(self, tokens: float = 1.0) -> float:
        """
        Async намагається споживати токени.

        Args:
            tokens: Кількість токенів для споживання

        Returns:
            Час очікування в секундах (0 якщо токени доступні)
        """
        async with self._lock:
            self._refill()

            if self.tokens >= tokens:
                # Достатньо токенів - споживаємо
                self.tokens -= tokens
                return 0.0
            else:
                # Недостатньо токенів - розраховуємо час очікування
                tokens_needed = tokens - self.tokens
                wait_time = tokens_needed / self.refill_rate
                return wait_time

    async def wait_for_token(self, tokens: float = 1.0, url: str = None):
        """
        Async чекає доки не з'явиться достатньо токенів .

        Використовує asyncio.sleep() замість time.sleep() для неблокуючого очікування.

        Args:
            tokens: Кількість токенів для споживання
            url: URL для логування (опціонально)
        """
        wait_time = await self.consume(tokens)
        if wait_time > 0:
            logger.debug(f"Rate limit: waiting {wait_time:.2f}s for token")

            # Публікуємо подію про очікування
            if self.event_bus:
                from graph_crawler.domain.events import CrawlerEvent, EventType

                self.event_bus.publish(
                    CrawlerEvent.create(
                        EventType.RATE_LIMIT_WAIT,
                        data={
                            "wait_time": wait_time,
                            "tokens_remaining": self.tokens,
                            "tokens_requested": tokens,
                            "url": url,
                        },
                    )
                )

            await asyncio.sleep(wait_time)

            # Після очікування споживаємо токени
            async with self._lock:
                self._refill()
                self.tokens -= tokens

                # Публікуємо подію про споживання токену
                if self.event_bus:
                    from graph_crawler.domain.events import CrawlerEvent, EventType

                    self.event_bus.publish(
                        CrawlerEvent.create(
                            EventType.RATE_LIMIT_TOKEN_CONSUMED,
                            data={
                                "tokens_consumed": tokens,
                                "tokens_remaining": self.tokens,
                                "url": url,
                            },
                        )
                    )


class RateLimitMiddleware(BaseMiddleware):
    """
    Async middleware для контролю швидкості запитів .

    Використовує Token Bucket алгоритм для обмеження частоти запитів. Неблокуючий async wait через asyncio.sleep().

    Конфігурація:
        requests_per_second: Кількість запитів на секунду (default: 2.0)
        requests_per_minute: Кількість запитів на хвилину (опціонально)
        burst_size: Максимальний burst (default: requests_per_second * 2)
    """

    def __init__(self, config: dict = None):
        super().__init__(config)
        self.bucket: Optional[TokenBucket] = None
        self.requests_count = 0
        self.start_time = time.time()

    @property
    def middleware_type(self) -> MiddlewareType:
        return MiddlewareType.PRE_REQUEST

    @property
    def name(self) -> str:
        return "rate_limit"

    async def setup(self):
        """Async ініціалізує Token Bucket."""
        # Визначаємо швидкість
        requests_per_second = self.config.get("requests_per_second")
        requests_per_minute = self.config.get("requests_per_minute")

        if requests_per_second:
            refill_rate = float(requests_per_second)
        elif requests_per_minute:
            refill_rate = float(requests_per_minute) / 60.0
        else:
            # Дефолт: 2 запити на секунду
            refill_rate = 2.0

        # Визначаємо burst size
        burst_size = self.config.get("burst_size")
        if burst_size:
            capacity = float(burst_size)
        else:
            # Дефолт: подвійна швидкість (дозволяє короткі спалахи)
            capacity = refill_rate * 2

        # Передаємо event_bus в TokenBucket через DI
        self.bucket = TokenBucket(
            capacity=capacity, refill_rate=refill_rate, event_bus=self.event_bus
        )

        logger.info(
            f"Rate limiting initialized: {refill_rate:.2f} req/s, "
            f"burst: {capacity:.0f}"
        )

    async def process(self, context: MiddlewareContext) -> MiddlewareContext:
        """
        Async контролює швидкість запитів .

        Args:
            context: Контекст запиту

        Returns:
            Оновлений контекст (може затримати виконання асинхронно)
        """
        if not self.bucket:
            # Якщо bucket не ініціалізовано - ініціалізуємо
            await self.setup()

        if not self.bucket:
            return context

        # Async чекаємо на токен (неблокуюча операція)
        await self.bucket.wait_for_token(tokens=1.0, url=context.url)

        # Оновлюємо статистику
        self.requests_count += 1

        # Додаємо метадані (використовуємо properties)
        context.metadata["rate_limit"] = {
            "requests_count": self.requests_count,
            "elapsed_time": self.elapsed_time,
            "current_rate": self.current_rate,
            "tokens_remaining": self.bucket.tokens,
        }

        return context

    @property
    def elapsed_time(self) -> float:
        """Повертає час з початку роботи middleware."""
        return time.time() - self.start_time

    @property
    def current_rate(self) -> float:
        """Повертає поточну швидкість запитів (requests per second)."""
        elapsed = self.elapsed_time
        return self.requests_count / elapsed if elapsed > 0 else 0.0

    def get_stats(self) -> dict:
        """Повертає статистику rate limiting."""
        return {
            "requests_count": self.requests_count,
            "elapsed_time": self.elapsed_time,
            "current_rate": self.current_rate,
            "tokens_remaining": self.bucket.tokens if self.bucket else 0,
            "bucket_capacity": self.bucket.capacity if self.bucket else 0,
            "refill_rate": self.bucket.refill_rate if self.bucket else 0,
        }

    async def reset(self):
        """Async скидає статистику та поповнює bucket."""
        self.requests_count = 0
        self.start_time = time.time()
        if self.bucket:
            async with self.bucket._lock:
                self.bucket.tokens = self.bucket.capacity
                self.bucket.last_refill_time = time.time()
