"""Error Recovery Middleware - обробка та відновлення після критичних помилок.

Team 3: Reliability & DevOps
Task 3.3: Error Recovery (P0)
Week 2
"""

import logging
import traceback
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from graph_crawler.extensions.middleware.base import (
    BaseMiddleware,
    MiddlewareContext,
    MiddlewareType,
)

logger = logging.getLogger(__name__)


class ErrorRecoveryMiddleware(BaseMiddleware):
    """
    Middleware для обробки та відновлення після критичних помилок.

    Функціонал:
    - Обробка різних типів помилок (network, driver, parsing)
    - Graceful degradation (продовження роботи при помилках)
    - Error logging та детальне reporting
    - Fallback strategies (альтернативні шляхи при помилках)
    - Error metrics tracking
    - Automatic error notification (callback)

    Підтримувані типи помилок:
    - Network errors (timeout, connection, DNS)
    - Driver errors (browser crash, resource exhaustion)
    - Parsing errors (malformed HTML, encoding issues)
    - Storage errors (disk full, write failures)
    - Unknown errors (unexpected exceptions)

    Конфіг:
        log_errors: Логувати помилки (default: True)
        log_traceback: Логувати stack trace (default: True)
        continue_on_error: Продовжувати при помилках (default: True)
        max_consecutive_errors: Макс послідовних помилок перед зупинкою (default: 10)
        error_callback: Callback функція для повідомлень про помилки (optional)
        fallback_strategies: Dict з fallback стратегіями для типів помилок (optional)
    """

    # Типи помилок
    ERROR_TYPE_NETWORK = "network"
    ERROR_TYPE_DRIVER = "driver"
    ERROR_TYPE_PARSING = "parsing"
    ERROR_TYPE_STORAGE = "storage"
    ERROR_TYPE_UNKNOWN = "unknown"

    def __init__(self, config: dict = None):
        super().__init__(config)

        # Metrics
        self.total_errors = 0
        self.errors_by_type: Dict[str, int] = {}
        self.errors_by_url: Dict[str, int] = {}
        self.consecutive_errors = 0
        self.last_successful_url: Optional[str] = None

        # Error history для аналізу
        self.error_history: list = []

        # Fallback strategies
        self.fallback_strategies: Dict[str, Callable] = self.config.get(
            "fallback_strategies", {}
        )

    @property
    def middleware_type(self) -> MiddlewareType:
        return MiddlewareType.ON_ERROR

    @property
    def name(self) -> str:
        return "error_recovery"

    def _classify_error(self, error_msg, context: MiddlewareContext) -> str:
        """
        Класифікує тип помилки на основі повідомлення та контексту.

        Args:
            error_msg: Повідомлення про помилку (str або Exception)
            context: Контекст middleware

        Returns:
            Тип помилки (ERROR_TYPE_*)
        """
        # Конвертуємо Exception в str якщо потрібно
        if isinstance(error_msg, Exception):
            error_msg = str(error_msg)
        error_lower = error_msg.lower()

        # Network errors
        network_keywords = [
            "timeout",
            "connection",
            "dns",
            "network",
            "unreachable",
            "refused",
            "reset",
            "timed out",
        ]
        if any(keyword in error_lower for keyword in network_keywords):
            return self.ERROR_TYPE_NETWORK

        # Driver errors
        driver_keywords = [
            "driver",
            "browser",
            "playwright",
            "selenium",
            "webdriver",
            "crash",
            "terminated",
        ]
        if any(keyword in error_lower for keyword in driver_keywords):
            return self.ERROR_TYPE_DRIVER

        # Parsing errors
        parsing_keywords = [
            "parse",
            "html",
            "decode",
            "encoding",
            "malformed",
            "invalid markup",
            "beautifulsoup",
        ]
        if any(keyword in error_lower for keyword in parsing_keywords):
            return self.ERROR_TYPE_PARSING

        # Storage errors
        storage_keywords = [
            "storage",
            "disk",
            "write",
            "save",
            "database",
            "sqlite",
            "mongodb",
            "no space",
        ]
        if any(keyword in error_lower for keyword in storage_keywords):
            return self.ERROR_TYPE_STORAGE

        return self.ERROR_TYPE_UNKNOWN

    def _log_error(
        self, url: str, error_msg, error_type: str, traceback_str: Optional[str] = None
    ):
        """
        Логує помилку з детальною інформацією.

        Args:
            url: URL де сталась помилка
            error_msg: Повідомлення про помилку (str або Exception)
            error_type: Тип помилки
            traceback_str: Stack trace (optional)
        """
        log_errors = self.config.get("log_errors", True)
        log_traceback = self.config.get("log_traceback", True)

        if not log_errors:
            return

        # Конвертуємо Exception в str якщо потрібно
        if isinstance(error_msg, Exception):
            error_msg = str(error_msg)

        logger.error(
            f"[{error_type.upper()}] Error for {url}: {error_msg} "
            f"(consecutive: {self.consecutive_errors})"
        )

        if log_traceback and traceback_str:
            logger.debug(f"Traceback:\n{traceback_str}")

    def _record_error(self, url: str, error_msg, error_type: str):
        """
        Записує помилку в історію та метрики.

        Args:
            url: URL де сталась помилка
            error_msg: Повідомлення про помилку (str або Exception)
            error_type: Тип помилки
        """
        # Конвертуємо Exception в str якщо потрібно
        if isinstance(error_msg, Exception):
            error_msg = str(error_msg)

        # Оновлюємо метрики
        self.total_errors += 1
        self.errors_by_type[error_type] = self.errors_by_type.get(error_type, 0) + 1
        self.errors_by_url[url] = self.errors_by_url.get(url, 0) + 1
        self.consecutive_errors += 1

        # Додаємо в історію
        error_record = {
            "timestamp": datetime.now().isoformat(),
            "url": url,
            "error_msg": error_msg,
            "error_type": error_type,
            "consecutive": self.consecutive_errors,
        }
        self.error_history.append(error_record)

        # Обмежуємо розмір історії
        max_history = self.config.get("max_error_history", 1000)
        if len(self.error_history) > max_history:
            self.error_history = self.error_history[-max_history:]

    def _apply_fallback(
        self, error_type: str, context: MiddlewareContext
    ) -> Optional[MiddlewareContext]:
        """
        Застосовує fallback стратегію для типу помилки.

        Args:
            error_type: Тип помилки
            context: Контекст middleware

        Returns:
            Оновлений контекст або None
        """
        if error_type not in self.fallback_strategies:
            return None

        try:
            fallback_func = self.fallback_strategies[error_type]
            return fallback_func(context)
        except Exception as e:
            logger.error(f"Fallback strategy failed for {error_type}: {e}")
            return None

    def _notify_error(self, url: str, error_msg, error_type: str):
        """
        Відправляє повідомлення про помилку через callback.

        Args:
            url: URL де сталась помилка
            error_msg: Повідомлення про помилку (str або Exception)
            error_type: Тип помилки
        """
        error_callback = self.config.get("error_callback")
        if not error_callback:
            return

        # Конвертуємо Exception в str якщо потрібно
        if isinstance(error_msg, Exception):
            error_msg = str(error_msg)

        try:
            error_callback(
                {
                    "url": url,
                    "error_msg": error_msg,
                    "error_type": error_type,
                    "timestamp": datetime.now().isoformat(),
                    "consecutive_errors": self.consecutive_errors,
                    "total_errors": self.total_errors,
                }
            )
        except Exception as e:
            logger.error(f"Error callback failed: {e}")

    def _check_error_threshold(self) -> bool:
        """
        Перевіряє чи не перевищено ліміт послідовних помилок.

        Returns:
            True якщо треба зупинити краулінг, False якщо продовжувати
        """
        max_consecutive = self.config.get("max_consecutive_errors", 10)

        if self.consecutive_errors >= max_consecutive:
            logger.critical(
                f"Critical: {self.consecutive_errors} consecutive errors detected! "
                f"Last successful: {self.last_successful_url}"
            )
            return True

        return False

    def get_metrics(self) -> dict:
        """
        Повертає метрики помилок.

        Returns:
            dict: Словник з метриками
        """
        return {
            "total_errors": self.total_errors,
            "errors_by_type": dict(self.errors_by_type),
            "consecutive_errors": self.consecutive_errors,
            "last_successful_url": self.last_successful_url,
            "top_failing_urls": sorted(
                self.errors_by_url.items(), key=lambda x: x[1], reverse=True
            )[:10],
            "recent_errors": self.error_history[-10:] if self.error_history else [],
        }

    def get_error_rate(self, total_requests: int) -> float:
        """
        Розраховує відсоток помилок.

        Args:
            total_requests: Загальна кількість запитів

        Returns:
            Відсоток помилок (0.0 - 1.0)
        """
        if total_requests == 0:
            return 0.0
        return self.total_errors / total_requests

    async def process(self, context: MiddlewareContext) -> MiddlewareContext:
        """
        Async обробляє помилки та застосовує recovery стратегії .

        Args:
            context: Контекст з помилкою

        Returns:
            Оновлений контекст
        """
        url = context.url
        continue_on_error = self.config.get("continue_on_error", True)

        # Якщо немає помилки - скидаємо лічильник послідовних помилок
        if not context.error:
            self.consecutive_errors = 0
            self.last_successful_url = url
            return context

        # Класифікуємо помилку
        error_type = self._classify_error(context.error, context)

        # Публікуємо подію про виявлення помилки (якщо є event_bus)
        if self.event_bus:
            from graph_crawler.domain.events.events import CrawlerEvent, EventType

            self.event_bus.publish(
                CrawlerEvent.create(
                    EventType.ERROR_DETECTED,
                    data={
                        "url": url,
                        "error": str(context.error),
                        "error_type": error_type,
                        "consecutive_errors": self.consecutive_errors + 1,
                        "total_errors": self.total_errors + 1,
                    },
                )
            )

        # Отримуємо traceback якщо доступний
        traceback_str = None
        if hasattr(context, "exception") and context.exception:
            traceback_str = "".join(
                traceback.format_exception(
                    type(context.exception),
                    context.exception,
                    context.exception.__traceback__,
                )
            )

        # Логуємо помилку
        self._log_error(url, context.error, error_type, traceback_str)

        # Записуємо в метрики
        self._record_error(url, context.error, error_type)

        # Відправляємо повідомлення
        self._notify_error(url, context.error, error_type)

        # Перевіряємо ліміт послідовних помилок
        if self._check_error_threshold():
            logger.critical("Stopping crawler due to consecutive errors")

            # Публікуємо подію про досягнення порогу помилок (якщо є event_bus)
            if self.event_bus:
                from graph_crawler.domain.events.events import CrawlerEvent, EventType

                self.event_bus.publish(
                    CrawlerEvent.create(
                        EventType.ERROR_THRESHOLD_REACHED,
                        data={
                            "consecutive_errors": self.consecutive_errors,
                            "max_consecutive_errors": self.config.get(
                                "max_consecutive_errors", 10
                            ),
                            "total_errors": self.total_errors,
                            "last_successful_url": self.last_successful_url,
                        },
                    )
                )

            context.should_stop = True
            return context

        # Публікуємо подію про початок recovery (якщо є event_bus)
        if self.event_bus:
            from graph_crawler.domain.events.events import CrawlerEvent, EventType

            self.event_bus.publish(
                CrawlerEvent.create(
                    EventType.ERROR_RECOVERY_STARTED,
                    data={
                        "url": url,
                        "error_type": error_type,
                        "has_fallback": error_type in self.fallback_strategies,
                        "continue_on_error": continue_on_error,
                    },
                )
            )

        # Застосовуємо fallback стратегію
        fallback_context = self._apply_fallback(error_type, context)
        if fallback_context:
            logger.info(f"Applied fallback strategy for {error_type}")

            # Публікуємо подію про успішний recovery (якщо є event_bus)
            if self.event_bus:
                from graph_crawler.domain.events.events import CrawlerEvent, EventType

                self.event_bus.publish(
                    CrawlerEvent.create(
                        EventType.ERROR_RECOVERY_SUCCESS,
                        data={
                            "url": url,
                            "error_type": error_type,
                            "recovery_method": "fallback_strategy",
                        },
                    )
                )

            return fallback_context

        # Якщо continue_on_error=True, продовжуємо краулінг
        if continue_on_error:
            logger.warning(f"Continuing despite error for {url} (graceful degradation)")

            # Публікуємо подію про успішний recovery через graceful degradation (якщо є event_bus)
            if self.event_bus:
                from graph_crawler.domain.events.events import CrawlerEvent, EventType

                self.event_bus.publish(
                    CrawlerEvent.create(
                        EventType.ERROR_RECOVERY_SUCCESS,
                        data={
                            "url": url,
                            "error_type": error_type,
                            "recovery_method": "graceful_degradation",
                        },
                    )
                )
        else:
            logger.error(f"Stopping due to error for {url}")

            # Публікуємо подію про невдалий recovery (якщо є event_bus)
            if self.event_bus:
                from graph_crawler.domain.events.events import CrawlerEvent, EventType

                self.event_bus.publish(
                    CrawlerEvent.create(
                        EventType.ERROR_RECOVERY_FAILED,
                        data={
                            "url": url,
                            "error_type": error_type,
                            "reason": "continue_on_error=False",
                        },
                    )
                )

            context.should_stop = True

        return context
