"""Module: shared - Спільні утиліти та константи

Містить:
- Constants: Константи проекту
- Exceptions: Кастомні винятки
- Error Handling: Обробка помилок
- Utils: Допоміжні утиліти
"""

# Винесемо найбільш використовувані речі тут
from graph_crawler.shared.error_handling.error_handler import (
    ErrorCategory,
    ErrorHandler,
    ErrorHandlerBuilder,
    ErrorSeverity,
)

__all__ = [
    "ErrorCategory",
    "ErrorHandler",
    "ErrorHandlerBuilder",
    "ErrorSeverity",
]
