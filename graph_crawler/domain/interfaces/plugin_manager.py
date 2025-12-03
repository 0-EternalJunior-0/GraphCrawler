"""Protocol для менеджера плагінів ."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class IPluginManager(Protocol):
    """
    Async-First інтерфейс для менеджера плагінів. Async execute() для неблокуючого виконання плагінів.
    Плагіни можуть виконувати async операції (HTTP запити, AI виклики тощо).
    """

    def register(self, plugin) -> None:
        """
        Реєструє плагін (sync - in-memory операція).

        Args:
            plugin: Плагін для реєстрації
        """
        ...

    async def execute(self, plugin_type, context):
        """
        Async виконує плагіни вказаного типу.

        Args:
            plugin_type: Тип плагіна для виконання
            context: Контекст виконання

        Returns:
            Оновлений контекст після виконання всіх плагінів
        """
        ...

    def has_plugins(self, plugin_type) -> bool:
        """
        Перевіряє наявність плагінів (sync - in-memory операція).

        Args:
            plugin_type: Тип плагіна

        Returns:
            True якщо є плагіни даного типу
        """
        ...

    async def teardown_all(self) -> None:
        """
        Async закриває всі плагіни.

        Викликає cleanup для кожного плагіна асинхронно.
        """
        ...
