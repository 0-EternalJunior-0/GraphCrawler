"""Protocol для event bus ."""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class IEventBus(Protocol):
    """
    Async-First інтерфейс для event bus. Async publish() для неблокуючої публікації подій.
    Дозволяє async listeners обробляти події без блокування.
    """

    def subscribe(self, event_type, listener: Any) -> None:
        """
        Підписується на події (sync - in-memory операція).

        Args:
            event_type: Тип події для підписки
            listener: Callback функція або async coroutine
        """
        ...

    async def publish(self, event) -> None:
        """
        Async публікує подію.

        Всі async listeners викликаються паралельно через asyncio.gather().

        Args:
            event: Подія для публікації
        """
        ...

    def unsubscribe(self, event_type, listener: Any) -> None:
        """
        Відписується від подій (sync - in-memory операція).

        Args:
            event_type: Тип події
            listener: Callback функція або async coroutine для видалення
        """
        ...
