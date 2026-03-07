"""Event Bus - Observer Pattern для подій.

Підтримує timeout для async callbacks та fail_fast опцію для критичних сценаріїв.
"""

import asyncio
import logging
from typing import Callable, Dict, List

from graph_crawler.domain.events.events import CrawlerEvent, EventType
from graph_crawler.shared.constants import DEFAULT_EVENT_HISTORY_SIZE

logger = logging.getLogger(__name__)

# Default timeout для callbacks
# 5 секунд достатньо для більшості операцій (logging, metrics)
DEFAULT_CALLBACK_TIMEOUT = 5.0


class EventBus:
    """
    Event Bus для Observer Pattern .

    Дозволяє компонентам підписуватися на події та реагувати на них. Підтримує як sync, так і async callbacks.

    Переваги:
    - Loose coupling між компонентами
    - Легко додавати нових observers
    - Централізоване управління подіями
    - Логування, моніторинг, analytics
    - Async callbacks для неблокуючої обробки

    Приклад:
        bus = EventBus()

        # Підписка на події
        def on_node_created(event: CrawlerEvent):
            print(f"Node created: {event.data['url']}")

        bus.subscribe(EventType.NODE_CREATED, on_node_created)

        # Публікація події
        event = CrawlerEvent.create(
            EventType.NODE_CREATED,
            data={'url': 'https://example.com'}
        )
        bus.publish(event)

        # Async publish для async callbacks
        await bus.publish_async(event)
    """

    def __init__(self):
        self._subscribers: Dict[EventType, List[Callable]] = {}
        self._history: List[CrawlerEvent] = []
        self._history_enabled = False

    def subscribe(
        self, event_type: EventType, callback: Callable[[CrawlerEvent], None]
    ):
        """
        Підписується на події певного типу.

        Args:
            event_type: Тип події
            callback: Функція для виклику при події

        Приклад:
            def my_handler(event):
                print(event.data)

            bus.subscribe(EventType.NODE_CREATED, my_handler)
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []

        self._subscribers[event_type].append(callback)

    def unsubscribe(
        self, event_type: EventType, callback: Callable[[CrawlerEvent], None]
    ):
        """
        Відписується від події.

        Args:
            event_type: Тип події
            callback: Функція для видалення
        """
        if event_type in self._subscribers:
            # Перевірка існування callback перед видаленням
            if callback in self._subscribers[event_type]:
                self._subscribers[event_type].remove(callback)
            else:
                logger.warning(f"Callback not found for event type {event_type}")

    def unsubscribe_all(self, callback: Callable[[CrawlerEvent], None]):
        """
        Відписується від всіх типів подій.

        Args:
            callback: Функція для видалення з усіх підписок
        """
        removed_count = 0
        for event_type in list(self._subscribers.keys()):
            if callback in self._subscribers[event_type]:
                self._subscribers[event_type].remove(callback)
                removed_count += 1

        logger.debug(f"Unsubscribed callback from {removed_count} event types")

    def clear_subscribers(self, event_type: EventType = None):
        """
        Очищає підписників.

        Args:
            event_type: Тип події для очищення. Якщо None - очищує всі підписки
        """
        if event_type is None:
            # Очищуємо всі підписки
            self._subscribers.clear()
            logger.debug("Cleared all subscribers")
        elif event_type in self._subscribers:
            # Очищуємо підписки для конкретного типу
            del self._subscribers[event_type]
            logger.debug(f"Cleared subscribers for {event_type}")

    def publish(self, event: CrawlerEvent, fail_fast: bool = False):
        """
        Публікує подію всім підписникам (sync версія).

        Args:
            event: Подія для публікації
            fail_fast: Якщо True - пробрасывает виняток при помилці в callback.
                      Якщо False (default) - логує помилку і продовжує.
        """
        # Історія
        if self._history_enabled:
            self._history.append(event)
            # Обрізати історію якщо перевищено ліміт
            max_size = getattr(self, "_max_history_size", DEFAULT_EVENT_HISTORY_SIZE)
            if len(self._history) > max_size:
                self._history.pop(0)

        # Виклик підписників
        subscribers = self._subscribers.get(event.event_type, [])
        for callback in subscribers:
            try:
                callback(event)
            except Exception as e:
                if fail_fast:
                    raise
                logger.error(
                    f"Error in event handler for {event.event_type}: {e}",
                    exc_info=True,
                    extra={"event": event.to_dict()},
                )

    async def publish_async(
        self,
        event: CrawlerEvent,
        timeout: float = DEFAULT_CALLBACK_TIMEOUT,
        fail_fast: bool = False
    ):
        """
        Async публікує подію всім підписникам.

        Підтримує timeout для async callbacks та fail_fast опцію.
        Підтримує як sync, так і async callbacks.

        Args:
            event: Подія для публікації
            timeout: Максимальний час очікування для async callback (default: 5.0 секунд)
            fail_fast: Якщо True - пробрасывает виняток при помилці/timeout.
                      Якщо False (default) - логує помилку і продовжує.
        """

        # Історія
        if self._history_enabled:
            self._history.append(event)
            max_size = getattr(self, "_max_history_size", DEFAULT_EVENT_HISTORY_SIZE)
            if len(self._history) > max_size:
                self._history.pop(0)

        # Виклик підписників
        subscribers = self._subscribers.get(event.event_type, [])
        for callback in subscribers:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await asyncio.wait_for(callback(event), timeout=timeout)
                else:
                    callback(event)
            except asyncio.TimeoutError:
                error_msg = f"Callback timeout ({timeout}s) for {event.event_type}: {callback.__name__ if hasattr(callback, '__name__') else callback}"
                if fail_fast:
                    raise asyncio.TimeoutError(error_msg)
                logger.error(error_msg, extra={"event": event.to_dict()})
            except Exception as e:
                if fail_fast:
                    raise
                logger.error(
                    f"Error in event handler for {event.event_type}: {e}",
                    exc_info=True,
                    extra={"event": event.to_dict()},
                )

    def enable_history(self, max_size: int = DEFAULT_EVENT_HISTORY_SIZE):
        """Включає збереження історії подій."""
        self._history_enabled = True
        self._max_history_size = max_size

    def get_history(self, event_type: EventType = None) -> List[CrawlerEvent]:
        """
        Повертає історію подій.

        Args:
            event_type: Фільтр за типом (опціонально)

        Returns:
            Список подій
        """
        if event_type:
            return [e for e in self._history if e.event_type == event_type]
        return self._history

    def clear_history(self):
        """Очищує історію подій."""
        self._history.clear()

    def get_subscriber_count(self, event_type: EventType = None) -> int:
        """Повертає кількість підписників."""
        if event_type:
            return len(self._subscribers.get(event_type, []))
        return sum(len(subs) for subs in self._subscribers.values())
