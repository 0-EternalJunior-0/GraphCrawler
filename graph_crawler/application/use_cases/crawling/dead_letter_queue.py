"""Dead Letter Queue - Збереження та обробка failed URLs.

Зберігає всі URLs які не вдалось завантажити і дозволяє їх retry або аналіз.
"""

import json
import logging
import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class FailedURL:
    """
    Інформація про failed URL.

    Attributes:
        url: URL що не вдалось завантажити
        error_message: Опис помилки
        error_type: Тип помилки (HTTPError, Timeout, ConnectionError, тощо)
        attempt_count: Кількість спроб завантаження
        first_failed_at: Timestamp першої невдалої спроби
        last_failed_at: Timestamp останньої невдалої спроби
        depth: Глибина URL в графі
        source_url: URL з якого прийшло посилання (optional)
        retry_after: Timestamp коли можна робити наступну спробу (exponential backoff)
        is_permanent_failure: Чи це остаточна невдача (після max retries)
    """

    url: str
    error_message: str
    error_type: str
    attempt_count: int = 0
    first_failed_at: Optional[float] = None
    last_failed_at: Optional[float] = None
    depth: int = 0
    source_url: Optional[str] = None
    retry_after: Optional[float] = None
    is_permanent_failure: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Конвертація в dict для JSON серіалізації."""
        return {
            "url": self.url,
            "error_message": self.error_message,
            "error_type": self.error_type,
            "attempt_count": self.attempt_count,
            "first_failed_at": self.first_failed_at,
            "last_failed_at": self.last_failed_at,
            "depth": self.depth,
            "source_url": self.source_url,
            "retry_after": self.retry_after,
            "is_permanent_failure": self.is_permanent_failure,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FailedURL":
        """Створення з dict (для десеріалізації)."""
        return cls(**data)


class DeadLetterQueue:
    """
    Dead Letter Queue для зберігання та обробки failed URLs.

    Функціонал:
    - Зберігає failed URLs з детальною інформацією про помилку
    - Retry механізм з exponential backoff
    - Максимум 3 спроби, після цього → permanent failure
    - Експорт списку failed URLs для аналізу
    - Статистика по типах помилок

    Exponential Backoff:
    - Спроба 1: retry через 1 секунду
    - Спроба 2: retry через 2 секунди
    - Спроба 3: retry через 4 секунди
    - Після 3 спроб → permanent failure

    Example:
        >>> dlq = DeadLetterQueue(max_retries=3)
        >>>
        >>> # Додати failed URL
        >>> dlq.add_failed_url(
        ...     url="https://site.com/page",
        ...     error_message="Connection timeout",
        ...     error_type="TimeoutError"
        ... )
        >>>
        >>> # Отримати URLs для retry
        >>> urls_to_retry = dlq.get_urls_for_retry()
        >>>
        >>> # Експорт failed URLs
        >>> dlq.export_to_json("failed_urls.json")
        >>>
        >>> # Статистика
        >>> stats = dlq.get_statistics()
        >>> print(f"Total failed: {stats['total_failed']}")
        >>> print(f"Permanent failures: {stats['permanent_failures']}")
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_retry_delay: float = 1.0,
        exponential_base: float = 2.0,
    ):
        """
        Ініціалізує Dead Letter Queue.

        Args:
            max_retries: Максимальна кількість retry спроб (default: 3)
            base_retry_delay: Базова затримка між спробами в секундах (default: 1.0)
            exponential_base: База для exponential backoff (default: 2.0)
                             Затримка = base_delay * (exponential_base ^ attempt_count)
        """
        self.max_retries = max_retries
        self.base_retry_delay = base_retry_delay
        self.exponential_base = exponential_base

        # Зберігання failed URLs: url -> FailedURL
        self.failed_urls: Dict[str, FailedURL] = {}

        # Статистика по типах помилок
        self.error_stats: Dict[str, int] = defaultdict(int)

        logger.info(
            f"DeadLetterQueue initialized: max_retries={max_retries}, "
            f"base_delay={base_retry_delay}s, exponential_base={exponential_base}"
        )

    def add_failed_url(
        self,
        url: str,
        error_message: str,
        error_type: str,
        depth: int = 0,
        source_url: Optional[str] = None,
    ) -> None:
        """
        Додає failed URL в DLQ або оновлює існуючий.

        Args:
            url: URL що не вдалось завантажити
            error_message: Опис помилки
            error_type: Тип помилки
            depth: Глибина URL в графі
            source_url: URL джерело (optional)
        """
        current_time = time.time()

        if url in self.failed_urls:
            # URL вже є в DLQ - оновлюємо інформацію
            failed_url = self.failed_urls[url]
            failed_url.attempt_count += 1
            failed_url.last_failed_at = current_time
            failed_url.error_message = error_message  # Оновлюємо останню помилку
            failed_url.error_type = error_type

            # Перевіряємо чи досягнуто max retries
            if failed_url.attempt_count >= self.max_retries:
                failed_url.is_permanent_failure = True
                failed_url.retry_after = None
                logger.warning(
                    f"URL marked as permanent failure after {failed_url.attempt_count} attempts: {url}"
                )
            else:
                # Розраховуємо exponential backoff для retry
                retry_delay = self._calculate_retry_delay(failed_url.attempt_count)
                failed_url.retry_after = current_time + retry_delay
                logger.info(
                    f"URL retry scheduled after {retry_delay:.1f}s (attempt {failed_url.attempt_count}): {url}"
                )
        else:
            # Новий failed URL
            retry_delay = self._calculate_retry_delay(1)
            failed_url = FailedURL(
                url=url,
                error_message=error_message,
                error_type=error_type,
                attempt_count=1,
                first_failed_at=current_time,
                last_failed_at=current_time,
                depth=depth,
                source_url=source_url,
                retry_after=current_time + retry_delay,
                is_permanent_failure=False,
            )
            self.failed_urls[url] = failed_url
            logger.info(f"New failed URL added to DLQ: {url} (error: {error_type})")

        # Оновлюємо статистику
        self.error_stats[error_type] += 1

    def _calculate_retry_delay(self, attempt_count: int) -> float:
        """
        Розраховує затримку для retry з exponential backoff.

        Args:
            attempt_count: Номер спроби

        Returns:
            Затримка в секундах

        Example:
            Attempt 1: 1 * (2^0) = 1 секунда
            Attempt 2: 1 * (2^1) = 2 секунди
            Attempt 3: 1 * (2^2) = 4 секунди
        """
        delay = self.base_retry_delay * (self.exponential_base ** (attempt_count - 1))
        return delay

    def get_urls_for_retry(self) -> List[FailedURL]:
        """
        Повертає список URLs готових для retry.

        Returns:
            Список FailedURL об'єктів готових для retry

        Критерії:
        - retry_after <= поточний час
        - is_permanent_failure == False
        """
        current_time = time.time()
        urls_for_retry = []

        for failed_url in self.failed_urls.values():
            if (
                not failed_url.is_permanent_failure
                and failed_url.retry_after is not None
                and failed_url.retry_after <= current_time
            ):
                urls_for_retry.append(failed_url)

        logger.info(f"Found {len(urls_for_retry)} URLs ready for retry")
        return urls_for_retry

    def mark_as_success(self, url: str) -> None:
        """
        Видаляє URL з DLQ після успішної retry спроби.

        Args:
            url: URL що успішно завантажено
        """
        if url in self.failed_urls:
            failed_url = self.failed_urls[url]
            logger.info(
                f"URL successfully recovered after {failed_url.attempt_count} attempts: {url}"
            )
            del self.failed_urls[url]

    def get_permanent_failures(self) -> List[FailedURL]:
        """
        Повертає список URLs з permanent failure.

        Returns:
            Список FailedURL об'єктів з is_permanent_failure=True
        """
        return [
            failed_url
            for failed_url in self.failed_urls.values()
            if failed_url.is_permanent_failure
        ]

    def get_statistics(self) -> Dict[str, Any]:
        """
        Повертає статистику DLQ.

        Returns:
            Dict з статистикою:
            - total_failed: загальна кількість failed URLs
            - permanent_failures: кількість permanent failures
            - pending_retry: кількість URLs в очікуванні retry
            - errors_by_type: помилки по типах
            - average_attempts: середня кількість спроб
        """
        total_failed = len(self.failed_urls)
        permanent_failures = sum(
            1 for url in self.failed_urls.values() if url.is_permanent_failure
        )
        pending_retry = total_failed - permanent_failures

        # Середня кількість спроб
        total_attempts = sum(url.attempt_count for url in self.failed_urls.values())
        avg_attempts = total_attempts / total_failed if total_failed > 0 else 0

        return {
            "total_failed": total_failed,
            "permanent_failures": permanent_failures,
            "pending_retry": pending_retry,
            "errors_by_type": dict(self.error_stats),
            "average_attempts": round(avg_attempts, 2),
        }

    def export_to_json(self, filepath: str) -> None:
        """
        Експортує всі failed URLs в JSON файл.

        Args:
            filepath: Шлях до JSON файлу

        Example JSON format:
        {
            "metadata": {
                "exported_at": "2024-11-25T10:30:00",
                "total_failed": 150,
                "permanent_failures": 50
            },
            "failed_urls": [
                {
                    "url": "https://site.com/page",
                    "error_type": "TimeoutError",
                    "attempt_count": 3,
                    ...
                }
            ]
        }
        """
        metadata = {
            "exported_at": datetime.now().isoformat(),
            "statistics": self.get_statistics(),
        }

        failed_urls_list = [
            failed_url.to_dict() for failed_url in self.failed_urls.values()
        ]

        export_data = {"metadata": metadata, "failed_urls": failed_urls_list}

        # Створюємо директорію якщо не існує
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Exported {len(failed_urls_list)} failed URLs to {filepath}")

    def import_from_json(self, filepath: str) -> None:
        """
        Імпортує failed URLs з JSON файлу.

        Args:
            filepath: Шлях до JSON файлу
        """
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        failed_urls_list = data.get("failed_urls", [])

        for failed_url_dict in failed_urls_list:
            failed_url = FailedURL.from_dict(failed_url_dict)
            self.failed_urls[failed_url.url] = failed_url
            self.error_stats[failed_url.error_type] += 1

        logger.info(f"Imported {len(failed_urls_list)} failed URLs from {filepath}")

    def clear(self) -> None:
        """Очищає всі failed URLs з DLQ."""
        count = len(self.failed_urls)
        self.failed_urls.clear()
        self.error_stats.clear()
        logger.info(f"Cleared {count} failed URLs from DLQ")

    def get_summary(self) -> str:
        """
        Повертає текстовий summary DLQ статистики.

        Returns:
            Форматований текст з статистикою
        """
        stats = self.get_statistics()

        summary = []
        summary.append("=" * 60)
        summary.append("Dead Letter Queue Summary")
        summary.append("=" * 60)
        summary.append(f"Total Failed URLs:        {stats['total_failed']}")
        summary.append(f"Permanent Failures:       {stats['permanent_failures']}")
        summary.append(f"Pending Retry:            {stats['pending_retry']}")
        summary.append(f"Average Attempts:         {stats['average_attempts']}")
        summary.append("")
        summary.append("Errors by Type:")
        summary.append("-" * 60)

        for error_type, count in sorted(
            stats["errors_by_type"].items(), key=lambda x: x[1], reverse=True
        ):
            summary.append(f"  {error_type:30s} {count:>5d}")

        summary.append("=" * 60)

        return "\n".join(summary)
