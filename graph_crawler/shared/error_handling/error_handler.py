"""
Error Handler - Централізована обробка помилок краулінгу

Обробляє всі типи помилок і координує з DeadLetterQueue для retry логіки.

"""

import logging
from enum import Enum
from typing import Any, Callable, Optional, Type

logger = logging.getLogger(__name__)


class ErrorSeverity(str, Enum):
    """Рівні серйозності помилок."""

    LOW = "low"  # Можна ігнорувати (404 на зображеннях)
    MEDIUM = "medium"  # Варто retry (timeout, connection error)
    HIGH = "high"  # Критична помилка (authentication, rate limit)
    CRITICAL = "critical"  # Фатальна помилка (invalid config)


class ErrorCategory(str, Enum):
    """Категорії помилок для класифікації."""

    NETWORK = "network"  # Connection errors, timeouts
    HTTP = "http"  # HTTP status errors (4xx, 5xx)
    PARSING = "parsing"  # HTML parsing errors
    VALIDATION = "validation"  # Data validation errors
    AUTHENTICATION = "authentication"  # Auth errors
    RATE_LIMIT = "rate_limit"  # Rate limiting errors
    DRIVER = "driver"  # Driver-specific errors
    UNKNOWN = "unknown"  # Невідомі помилки


class ErrorHandler:
    """
    Централізований обробник помилок краулінгу.

    Функціонал:
    - Класифікація помилок по типу та severity
    - Визначення чи можна робити retry
    - Логування помилок з контекстом
    - Інтеграція з DeadLetterQueue
    - Callbacks для custom обробки помилок

    Example:
        >>> from graph_crawler.application.use_cases.crawling.dead_letter_queue import DeadLetterQueue
        >>>
        >>> dlq = DeadLetterQueue()
        >>> error_handler = ErrorHandler(dead_letter_queue=dlq)
        >>>
        >>> # Обробка помилки
        >>> try:
        ...     # краулінг код
        ...     pass
        ... except Exception as e:
        ...     error_handler.handle_error(
        ...         error=e,
        ...         url="https://site.com/page",
        ...         context={"depth": 2, "source": "https://site.com"}
        ...     )
    """

    def __init__(
        self,
        dead_letter_queue: Optional["DeadLetterQueue"] = None,
        on_error_callback: Optional[Callable[[Exception, str, dict], None]] = None,
    ):
        """
        Ініціалізує ErrorHandler.

        Args:
            dead_letter_queue: DLQ для зберігання failed URLs (optional)
            on_error_callback: Callback функція для custom обробки помилок (optional)
                             Signature: (error: Exception, url: str, context: dict) -> None
        """
        self.dead_letter_queue = dead_letter_queue
        self.on_error_callback = on_error_callback

        # Статистика помилок
        self.error_count = 0
        self.errors_by_category = {}
        self.errors_by_severity = {}

        logger.info(
            f"ErrorHandler initialized with DLQ: {dead_letter_queue is not None}"
        )

    def handle_error(
        self, error: Exception, url: str, context: Optional[dict] = None
    ) -> None:
        """
        Обробляє помилку краулінгу.

        Args:
            error: Exception об'єкт
            url: URL де сталась помилка
            context: Додатковий контекст (depth, source_url, тощо)
        """
        context = context or {}

        # Класифікація помилки
        error_type = type(error).__name__
        category = self._classify_error(error)
        severity = self._determine_severity(error, category)
        is_retryable = self._is_retryable(error, category)

        # Оновлення статистики
        self.error_count += 1
        self.errors_by_category[category.value] = (
            self.errors_by_category.get(category.value, 0) + 1
        )
        self.errors_by_severity[severity.value] = (
            self.errors_by_severity.get(severity.value, 0) + 1
        )

        # Логування з відповідним рівнем
        log_message = (
            f"Error handling URL: {url}\n"
            f"  Type: {error_type}\n"
            f"  Category: {category.value}\n"
            f"  Severity: {severity.value}\n"
            f"  Retryable: {is_retryable}\n"
            f"  Message: {str(error)}\n"
            f"  Context: {context}"
        )

        if severity == ErrorSeverity.CRITICAL:
            logger.critical(log_message, exc_info=True)
        elif severity == ErrorSeverity.HIGH:
            logger.error(log_message, exc_info=True)
        elif severity == ErrorSeverity.MEDIUM:
            logger.warning(log_message)
        else:
            logger.info(log_message)

        # Додаємо в DLQ якщо можна робити retry
        if is_retryable and self.dead_letter_queue:
            self.dead_letter_queue.add_failed_url(
                url=url,
                error_message=str(error),
                error_type=error_type,
                depth=context.get("depth", 0),
                source_url=context.get("source_url"),
            )

        # Викликаємо custom callback якщо є
        if self.on_error_callback:
            try:
                self.on_error_callback(error, url, context)
            except Exception as callback_error:
                logger.error(
                    f"Error in error callback: {callback_error}", exc_info=True
                )

    def _classify_error(self, error: Exception) -> ErrorCategory:
        """
        Класифікує помилку по категорії.

        Args:
            error: Exception об'єкт

        Returns:
            ErrorCategory
        """
        error_type = type(error).__name__.lower()
        error_message = str(error).lower()

        # Network errors
        if any(
            keyword in error_type for keyword in ["connection", "timeout", "network"]
        ):
            return ErrorCategory.NETWORK

        if any(
            keyword in error_message for keyword in ["connection", "timeout", "network"]
        ):
            return ErrorCategory.NETWORK

        # HTTP errors
        if "http" in error_type or "status" in error_type:
            return ErrorCategory.HTTP

        if any(keyword in error_message for keyword in ["404", "500", "502", "503"]):
            return ErrorCategory.HTTP

        # Parsing errors
        if any(keyword in error_type for keyword in ["parse", "decode", "encoding"]):
            return ErrorCategory.PARSING

        # Validation errors
        if "validation" in error_type or "invalid" in error_type:
            return ErrorCategory.VALIDATION

        # Authentication errors
        if any(
            keyword in error_type for keyword in ["auth", "permission", "forbidden"]
        ):
            return ErrorCategory.AUTHENTICATION

        if any(
            keyword in error_message
            for keyword in ["401", "403", "unauthorized", "forbidden"]
        ):
            return ErrorCategory.AUTHENTICATION

        # Rate limit errors
        if "rate" in error_message or "429" in error_message:
            return ErrorCategory.RATE_LIMIT

        # Driver errors
        if (
            "driver" in error_type
            or "playwright" in error_type
            or "selenium" in error_type
        ):
            return ErrorCategory.DRIVER

        return ErrorCategory.UNKNOWN

    def _determine_severity(
        self, error: Exception, category: ErrorCategory
    ) -> ErrorSeverity:
        """
        Визначає severity помилки.

        Args:
            error: Exception об'єкт
            category: ErrorCategory

        Returns:
            ErrorSeverity
        """
        error_message = str(error).lower()

        # CRITICAL - фатальні помилки
        if category == ErrorCategory.VALIDATION:
            return ErrorSeverity.CRITICAL

        if "fatal" in error_message or "critical" in error_message:
            return ErrorSeverity.CRITICAL

        # HIGH - серйозні помилки
        if category in [ErrorCategory.AUTHENTICATION, ErrorCategory.RATE_LIMIT]:
            return ErrorSeverity.HIGH

        if "500" in error_message or "502" in error_message or "503" in error_message:
            return ErrorSeverity.HIGH

        # MEDIUM - помилки які варто retry
        if category in [ErrorCategory.NETWORK, ErrorCategory.DRIVER]:
            return ErrorSeverity.MEDIUM

        if "timeout" in error_message:
            return ErrorSeverity.MEDIUM

        # LOW - можна ігнорувати
        if "404" in error_message:
            return ErrorSeverity.LOW

        return ErrorSeverity.MEDIUM

    def _is_retryable(self, error: Exception, category: ErrorCategory) -> bool:
        """
        Визначає чи можна робити retry для цієї помилки.

        Args:
            error: Exception об'єкт
            category: ErrorCategory

        Returns:
            True якщо можна retry, False якщо ні
        """
        error_message = str(error).lower()

        # НЕ робимо retry для цих випадків
        non_retryable_conditions = [
            category == ErrorCategory.VALIDATION,  # Помилки валідації
            category == ErrorCategory.AUTHENTICATION,  # Auth помилки
            "404" in error_message,  # Page not found
            "401" in error_message,  # Unauthorized
            "403" in error_message,  # Forbidden
            "invalid" in error_message and "url" in error_message,  # Invalid URL
        ]

        if any(non_retryable_conditions):
            return False

        # Робимо retry для цих категорій
        retryable_categories = [
            ErrorCategory.NETWORK,
            ErrorCategory.HTTP,  # 5xx errors
            ErrorCategory.DRIVER,
            ErrorCategory.RATE_LIMIT,  # Після backoff
            ErrorCategory.PARSING,  # Можливо тимчасова проблема
        ]

        return category in retryable_categories

    def get_statistics(self) -> dict:
        """
        Повертає статистику помилок.

        Returns:
            Dict з статистикою
        """
        return {
            "total_errors": self.error_count,
            "errors_by_category": self.errors_by_category,
            "errors_by_severity": self.errors_by_severity,
        }

    def reset_statistics(self) -> None:
        """Скидає статистику помилок."""
        self.error_count = 0
        self.errors_by_category.clear()
        self.errors_by_severity.clear()
        logger.info("Error statistics reset")


class ErrorHandlerBuilder:
    """
    Builder для створення ErrorHandler з різними конфігураціями.

    Example:
        >>> from graph_crawler.application.use_cases.crawling.dead_letter_queue import DeadLetterQueue
        >>>
        >>> dlq = DeadLetterQueue(max_retries=3)
        >>>
        >>> error_handler = (
        ...     ErrorHandlerBuilder()
        ...     .with_dead_letter_queue(dlq)
        ...     .with_error_callback(my_custom_callback)
        ...     .build()
        ... )
    """

    def __init__(self):
        self._dlq = None
        self._callback = None

    def with_dead_letter_queue(self, dlq: "DeadLetterQueue") -> "ErrorHandlerBuilder":
        """Додає DeadLetterQueue."""
        self._dlq = dlq
        return self

    def with_error_callback(
        self, callback: Callable[[Exception, str, dict], None]
    ) -> "ErrorHandlerBuilder":
        """Додає custom error callback."""
        self._callback = callback
        return self

    def build(self) -> ErrorHandler:
        """Створює ErrorHandler."""
        return ErrorHandler(
            dead_letter_queue=self._dlq, on_error_callback=self._callback
        )
