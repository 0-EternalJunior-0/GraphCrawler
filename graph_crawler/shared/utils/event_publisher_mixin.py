"""EventPublisherMixin - Mixin для спрощення публікації подій."""

import logging
from typing import Any, Dict, Optional

from graph_crawler.domain.events.event_bus import EventBus
from graph_crawler.domain.events.events import CrawlerEvent, EventType

logger = logging.getLogger(__name__)


class EventPublisherMixin:
    """
    Mixin для додавання можливості публікації подій до будь-якого класу.

    Використання:
        class MyClass(EventPublisherMixin):
            def __init__(self, event_bus: Optional[EventBus] = None):
                self.event_bus = event_bus

            def do_something(self):
                # Публікуємо подію
                self.publish_event(
                    EventType.NODE_CREATED,
                    data={'url': 'https://example.com'}
                )

    Переваги:
    - Уніфікований спосіб публікації подій
    - Автоматична перевірка наявності event_bus
    - Зменшення code duplication
    - Легше тестувати (можна мокати методи)
    """

    def publish_event(
        self,
        event_type: EventType,
        data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Публікує подію в event bus (якщо він є).

        Args:
            event_type: Тип події
            data: Дані події (опціонально)
            metadata: Метадані події (опціонально)

        Приклад:
            self.publish_event(
                EventType.FETCH_SUCCESS,
                data={'url': url, 'status': 200},
                metadata={'driver': 'http', 'duration': 1.5}
            )
        """
        if not hasattr(self, "event_bus") or self.event_bus is None:
            # Якщо event_bus не налаштовано - просто пропускаємо
            logger.debug(
                f"No event bus configured for {self.__class__.__name__}, skipping event {event_type}"
            )
            return

        try:
            event = CrawlerEvent.create(
                event_type=event_type, data=data or {}, metadata=metadata or {}
            )
            self.event_bus.publish(event)

        except Exception as e:
            # Помилки публікації подій не повинні ламати основну логіку
            logger.error(
                f"Failed to publish event {event_type} in {self.__class__.__name__}: {e}",
                exc_info=True,
            )

    def publish_event_safe(
        self,
        event_type: EventType,
        data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        context: str = "",
    ) -> bool:
        """
        Безпечна публікація події з додатковим контекстом.
        Повертає True якщо подія успішно опублікована, False якщо ні.

        Args:
            event_type: Тип події
            data: Дані події
            metadata: Метадані події
            context: Додатковий контекст для логування

        Returns:
            True якщо подія опублікована, False якщо ні
        """
        try:
            self.publish_event(event_type, data, metadata)
            return True
        except Exception as e:
            logger.warning(f"Event publishing failed for {event_type} ({context}): {e}")
            return False

    def has_event_bus(self) -> bool:
        """
        Перевіряє чи налаштовано event bus.

        Returns:
            True якщо event bus доступний, False якщо ні
        """
        return hasattr(self, "event_bus") and self.event_bus is not None

    def publish_error_event(
        self,
        error: Exception,
        context: str = "",
        additional_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Спеціальний helper для публікації помилок.

        Args:
            error: Виняток що стався
            context: Контекст помилки
            additional_data: Додаткові дані

        Приклад:
            try:
                self.do_something()
            except Exception as e:
                self.publish_error_event(e, context="fetching URL", additional_data={'url': url})
                raise
        """
        data = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context,
            "class": self.__class__.__name__,
        }

        if additional_data:
            data.update(additional_data)

        self.publish_event(
            EventType.ERROR_OCCURRED, data=data, metadata={"severity": "error"}
        )

    def publish_progress_event(
        self,
        current: int,
        total: int,
        message: str = "",
        additional_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Helper для публікації прогресу.

        Args:
            current: Поточне значення
            total: Загальне значення
            message: Повідомлення прогресу
            additional_data: Додаткові дані
        """
        data = {
            "current": current,
            "total": total,
            "percentage": round((current / total * 100), 2) if total > 0 else 0,
            "message": message,
        }

        if additional_data:
            data.update(additional_data)

        self.publish_event(EventType.PROGRESS_UPDATE, data=data)
