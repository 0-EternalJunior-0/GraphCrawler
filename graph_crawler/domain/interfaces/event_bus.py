"""Protocol для event bus."""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class IEventBus(Protocol):
    """
    Інтерфейс для event bus. Підтримує як sync, так і async publish.
    """

    def subscribe(self, event_type, callback: Any) -> None:
        """
        Підписується на події (sync - in-memory операція).

        Args:
            event_type: Тип події для підписки
            callback: Callback функція або async coroutine
        """
        ...

    def publish(self, event, fail_fast: bool = False) -> None:
        """
        Sync публікує подію.

        Args:
            event: Подія для публікації
            fail_fast: Якщо True - пробрасывает виняток при помилці
        """
        ...

    def unsubscribe(self, event_type, callback: Any) -> None:
        """
        Відписується від подій (sync - in-memory операція).

        Args:
            event_type: Тип події
            callback: Callback функція або async coroutine для видалення
        """
        ...
