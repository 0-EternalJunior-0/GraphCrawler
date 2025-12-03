"""
Adaptive Throttling - автоматичне регулювання швидкості краулінгу .
- Додано async метод wait_async() для async контексту
- Збережено sync метод wait() для зворотньої сумісності

Цей модуль автоматично адаптує швидкість краулінгу в залежності від:
- Response time сервера (швидкість відповіді)
- Error rate (відсоток помилок)

Якщо сервер відповідає швидко і без помилок - прискорюємо.
Якщо повільно або багато помилок - уповільнюємо.
"""

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ThrottleMetrics:
    """
    Метрики для адаптивного throttling.

    Attributes:
        total_requests: Загальна кількість запитів
        successful_requests: Кількість успішних запитів
        failed_requests: Кількість невдалих запитів
        response_times: Список часів відповіді (мс)
        current_delay: Поточна затримка між запитами (мс)
        adjustments_count: Кількість коригувань затримки
    """

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    response_times: List[float] = field(default_factory=list)
    current_delay: float = 0.0
    adjustments_count: int = 0

    def get_error_rate(self) -> float:
        """Обчислити відсоток помилок."""
        if self.total_requests == 0:
            return 0.0
        return (self.failed_requests / self.total_requests) * 100

    def get_avg_response_time(self) -> float:
        """Обчислити середній час відповіді (мс)."""
        if not self.response_times:
            return 0.0
        return sum(self.response_times) / len(self.response_times)


class AdaptiveThrottler:
    """
    Адаптивний throttler що автоматично регулює швидкість краулінгу.

    Алгоритм:
    1. Якщо error_rate > 10% → delay *= 1.5 (уповільнити)
    2. Якщо response_time < 500ms → delay *= 0.8 (прискорити)
    3. Min delay: 100ms, Max delay: 5000ms

    Приклад використання:
        ```python
        throttler = AdaptiveThrottler(
            initial_delay=0.5,
            min_delay=0.1,
            max_delay=5.0
        )

        # Перед запитом
        throttler.wait()

        # Після успішного запиту
        throttler.record_success(response_time=0.3)

        # Після невдалого запиту
        throttler.record_failure(response_time=2.0)

        # Статистика
        print(throttler.get_summary())
        ```
    """

    def __init__(
        self,
        initial_delay: float = 0.5,
        min_delay: float = 0.1,
        max_delay: float = 5.0,
        error_threshold: float = 10.0,
        fast_response_threshold: float = 0.5,
        slowdown_factor: float = 1.5,
        speedup_factor: float = 0.8,
        window_size: int = 100,
        adjustment_interval: int = 10,
    ):
        """
        Ініціалізація адаптивного throttler.

        Args:
            initial_delay: Початкова затримка між запитами (секунди)
            min_delay: Мінімальна затримка (секунди)
            max_delay: Максимальна затримка (секунди)
            error_threshold: Поріг помилок для уповільнення (%)
            fast_response_threshold: Поріг швидкої відповіді (секунди)
            slowdown_factor: Множник для уповільнення (default: 1.5)
            speedup_factor: Множник для прискорення (default: 0.8)
            window_size: Розмір вікна для підрахунку метрик
            adjustment_interval: Інтервал запитів між коригуваннями
        """
        self.initial_delay = initial_delay
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.error_threshold = error_threshold
        self.fast_response_threshold = fast_response_threshold
        self.slowdown_factor = slowdown_factor
        self.speedup_factor = speedup_factor
        self.window_size = window_size
        self.adjustment_interval = adjustment_interval

        # Поточна затримка
        self.current_delay = initial_delay

        # Метрики (використовуємо deque для ефективності)
        self.recent_response_times: deque = deque(maxlen=window_size)
        self.recent_errors: deque = deque(maxlen=window_size)

        # Загальна статистика
        self.metrics = ThrottleMetrics(current_delay=initial_delay)

        # Лічильник для коригувань
        self.requests_since_adjustment = 0

        # Історія коригувань
        self.adjustment_history: List[Dict[str, Any]] = []

        logger.info(
            f" AdaptiveThrottler initialized: "
            f"initial_delay={initial_delay}s, "
            f"min={min_delay}s, max={max_delay}s"
        )

    def wait(self) -> None:
        """
        Почекати перед наступним запитом (sync версія).
        Використовує поточну затримку.

        WARNING: Блокуючий виклик! Використовуйте wait_async() в async контексті.
        """
        if self.current_delay > 0:
            time.sleep(self.current_delay)

    async def wait_async(self) -> None:
        """
        Почекати перед наступним запитом .
        Використовує поточну затримку без блокування event loop.
        """
        if self.current_delay > 0:
            await asyncio.sleep(self.current_delay)

    def record_success(self, response_time: float) -> None:
        """
        Записати успішний запит.

        Args:
            response_time: Час відповіді в секундах
        """
        self.metrics.total_requests += 1
        self.metrics.successful_requests += 1

        # Додати в recent metrics
        response_time_ms = response_time * 1000
        self.recent_response_times.append(response_time_ms)
        self.recent_errors.append(False)

        # Додати в загальну статистику
        self.metrics.response_times.append(response_time_ms)

        # Перевірити чи потрібно коригувати
        self.requests_since_adjustment += 1
        if self.requests_since_adjustment >= self.adjustment_interval:
            self._adjust_delay()
            self.requests_since_adjustment = 0

    def record_failure(self, response_time: Optional[float] = None) -> None:
        """
        Записати невдалий запит.

        Args:
            response_time: Час відповіді (якщо є) в секундах
        """
        self.metrics.total_requests += 1
        self.metrics.failed_requests += 1

        # Додати в recent metrics
        if response_time is not None:
            response_time_ms = response_time * 1000
            self.recent_response_times.append(response_time_ms)
            self.metrics.response_times.append(response_time_ms)

        self.recent_errors.append(True)

        # Перевірити чи потрібно коригувати
        self.requests_since_adjustment += 1
        if self.requests_since_adjustment >= self.adjustment_interval:
            self._adjust_delay()
            self.requests_since_adjustment = 0

    def _adjust_delay(self) -> None:
        """
        Коригувати затримку на основі recent метрик.

        Логіка:
        1. Якщо error_rate > threshold → збільшити delay (slowdown)
        2. Якщо response_time < threshold → зменшити delay (speedup)
        3. Error має вищий пріоритет ніж response_time
        """
        if not self.recent_errors:
            return

        # Обчислити recent metrics
        error_count = sum(1 for e in self.recent_errors if e)
        error_rate = (error_count / len(self.recent_errors)) * 100

        avg_response_time = 0.0
        if self.recent_response_times:
            avg_response_time = sum(self.recent_response_times) / len(
                self.recent_response_times
            )
            avg_response_time_sec = avg_response_time / 1000

        old_delay = self.current_delay
        adjustment_reason = None

        # Правило 1: Багато помилок → уповільнити
        if error_rate > self.error_threshold:
            self.current_delay *= self.slowdown_factor
            adjustment_reason = f"high_error_rate ({error_rate:.1f}%)"
            logger.warning(
                f" High error rate {error_rate:.1f}% → "
                f"Slowing down: {old_delay:.3f}s → {self.current_delay:.3f}s"
            )

        # Правило 2: Швидкі відповіді → прискорити
        elif (
            self.recent_response_times
            and avg_response_time_sec < self.fast_response_threshold
        ):
            self.current_delay *= self.speedup_factor
            adjustment_reason = f"fast_response ({avg_response_time:.0f}ms)"
            logger.info(
                f"Fast responses {avg_response_time:.0f}ms → "
                f"Speeding up: {old_delay:.3f}s → {self.current_delay:.3f}s"
            )

        # Обмежити delay
        self.current_delay = max(
            self.min_delay, min(self.current_delay, self.max_delay)
        )

        # Якщо було коригування
        if adjustment_reason and abs(self.current_delay - old_delay) > 0.001:
            self.metrics.adjustments_count += 1
            self.metrics.current_delay = self.current_delay

            # Зберегти в історію
            self.adjustment_history.append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "old_delay": old_delay,
                    "new_delay": self.current_delay,
                    "reason": adjustment_reason,
                    "error_rate": error_rate,
                    "avg_response_time_ms": (
                        avg_response_time if self.recent_response_times else 0
                    ),
                }
            )

    def reset(self) -> None:
        """Скинути всю статистику та повернутись до початкової затримки."""
        self.current_delay = self.initial_delay
        self.recent_response_times.clear()
        self.recent_errors.clear()
        self.metrics = ThrottleMetrics(current_delay=self.initial_delay)
        self.requests_since_adjustment = 0
        self.adjustment_history.clear()
        logger.info(" AdaptiveThrottler reset to initial state")

    def get_statistics(self) -> Dict[str, Any]:
        """
        Отримати детальну статистику.

        Returns:
            Словник з метриками throttling
        """
        return {
            "current_delay_sec": self.current_delay,
            "min_delay_sec": self.min_delay,
            "max_delay_sec": self.max_delay,
            "total_requests": self.metrics.total_requests,
            "successful_requests": self.metrics.successful_requests,
            "failed_requests": self.metrics.failed_requests,
            "error_rate_percent": self.metrics.get_error_rate(),
            "avg_response_time_ms": self.metrics.get_avg_response_time(),
            "adjustments_count": self.metrics.adjustments_count,
            "recent_window_size": len(self.recent_errors),
            "adjustment_history": self.adjustment_history[-10:],  # Останні 10
        }

    def get_summary(self) -> str:
        """
        Отримати текстовий summary статистики.

        Returns:
            Форматований текст з метриками
        """
        stats = self.get_statistics()

        lines = [
            "=" * 60,
            " ADAPTIVE THROTTLER SUMMARY",
            "=" * 60,
            "",
            " Current State:",
            f"  • Current Delay:     {stats['current_delay_sec']:.3f}s",
            f"  • Min/Max Delay:     {stats['min_delay_sec']:.3f}s / {stats['max_delay_sec']:.3f}s",
            "",
            " Statistics:",
            f"  • Total Requests:    {stats['total_requests']}",
            f"  • Successful:        {stats['successful_requests']}",
            f"  • Failed:            {stats['failed_requests']}",
            f"  • Error Rate:        {stats['error_rate_percent']:.2f}%",
            f"  • Avg Response Time: {stats['avg_response_time_ms']:.0f}ms",
            "",
            " Adjustments:",
            f"  • Total Adjustments: {stats['adjustments_count']}",
            f"  • Window Size:       {stats['recent_window_size']}",
            "",
        ]

        # Додати історію коригувань
        if stats["adjustment_history"]:
            lines.append(" Recent Adjustments:")
            for adj in stats["adjustment_history"][-5:]:  # Останні 5
                lines.append(
                    f"  • {adj['timestamp']}: "
                    f"{adj['old_delay']:.3f}s → {adj['new_delay']:.3f}s "
                    f"({adj['reason']})"
                )
            lines.append("")

        lines.append("=" * 60)

        return "\n".join(lines)

    def export_to_dict(self) -> Dict[str, Any]:
        """
        Експортувати всю статистику в dict для JSON serialization.

        Returns:
            Повний словник з усією статистикою
        """
        return {
            "config": {
                "initial_delay": self.initial_delay,
                "min_delay": self.min_delay,
                "max_delay": self.max_delay,
                "error_threshold": self.error_threshold,
                "fast_response_threshold": self.fast_response_threshold,
                "slowdown_factor": self.slowdown_factor,
                "speedup_factor": self.speedup_factor,
                "window_size": self.window_size,
                "adjustment_interval": self.adjustment_interval,
            },
            "statistics": self.get_statistics(),
            "adjustment_history": self.adjustment_history,
        }
