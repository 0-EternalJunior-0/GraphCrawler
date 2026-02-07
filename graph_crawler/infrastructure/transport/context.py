"""Контексти для драйверів та плагінів.

Контекст передається між плагінами і містить:
- URL та параметри запиту
- Внутрішні об'єкти драйвера (session, page, browser)
- Відповідь та результати
- Дані для комунікації між плагінами
- Систему подій
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class EventPriority(int, Enum):
    """Пріоритети виконання плагінів."""

    HIGHEST = 1
    HIGH = 10
    NORMAL = 50
    LOW = 75
    LOWEST = 100


@dataclass
class DriverContext:
    """
    Базовий контекст для всіх драйверів.

    Використовується для передачі даних між драйвером та плагінами.
    Кожен драйвер створює свій специфічний контекст, наслідуючи цей клас.

    Attributes:
        url: URL що обробляється
        data: Словник для передачі даних між плагінами
        events: Словник event handlers для комунікації між плагінами
        errors: Список помилок що виникли
        cancelled: Чи скасовано виконання
    """

    url: str
    data: Dict[str, Any] = field(default_factory=dict)
    events: Dict[str, List[Callable]] = field(default_factory=dict)
    errors: List[Exception] = field(default_factory=list)
    cancelled: bool = False

    def emit(self, event_name: str, **event_data):
        """
        Публікує подію для інших плагінів.

        Приклад:
            ctx.emit('captcha_detected', captcha_type='recaptcha')

        Args:
            event_name: Назва події
            **event_data: Дані події
        """
        handlers = self.events.get(event_name, [])

        if not handlers:
            logger.debug(f"No handlers for event '{event_name}'")
            return

        logger.debug(f"Emitting event '{event_name}' to {len(handlers)} handlers")

        for handler in handlers:
            try:
                handler(self, **event_data)
            except Exception as e:
                logger.error(f"Error in event handler for '{event_name}': {e}")
                self.errors.append(e)

    def subscribe(self, event_name: str, handler: Callable):
        """
        Підписується на подію від іншого плагіна.

        Приклад:
            ctx.subscribe('captcha_detected', self.on_captcha_detected)

        Args:
            event_name: Назва події
            handler: Функція-обробник
        """
        if event_name not in self.events:
            self.events[event_name] = []

        self.events[event_name].append(handler)
        logger.debug(f"Subscribed to event '{event_name}'")

    def cancel(self, reason: str = "Cancelled by plugin"):
        """
        Скасовує подальше виконання.

        Використовується плагінами для припинення обробки в межах поточної сесії.

        Args:
            reason: Причина скасування
        """
        self.cancelled = True
        logger.info(f"Execution cancelled: {reason}")
        self.data["cancellation_reason"] = reason

    def has_error(self) -> bool:
        """Перевіряє чи є помилки."""
        return len(self.errors) > 0

    def get_last_error(self) -> Optional[Exception]:
        """Повертає останню помилку."""
        return self.errors[-1] if self.errors else None
