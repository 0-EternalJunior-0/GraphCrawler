"""Protocol для краулерів ."""

from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class ISpider(Protocol):
    """
    Async-First інтерфейс для краулерів. Повністю async інтерфейс для неблокуючого краулінгу.
    Підтримує pause/resume/stop контроль через async методи.
    """

    async def crawl(self, base_graph=None):
        """
        Async запуск процесу краулінгу.

        Args:
            base_graph: Базовий граф для incremental краулінгу (optional)

        Returns:
            Graph з результатами краулінгу
        """
        ...

    async def pause(self) -> None:
        """
        Async призупинення краулінгу.

        Краулер переходить в стан PAUSED та чекає resume().
        """
        ...

    async def resume(self) -> None:
        """
        Async відновлення краулінгу.

        Краулер переходить зі стану PAUSED в RUNNING.
        """
        ...

    async def stop(self) -> None:
        """
        Async зупинка краулінгу.

        Краулер переходить в стан STOPPED та завершує роботу.
        """
        ...

    def get_stats(self) -> dict:
        """Повертає статистику краулінгу (sync - in-memory операція)."""
        ...

    def is_paused(self) -> bool:
        """Перевіряє чи краулер призупинено."""
        ...

    def is_stopped(self) -> bool:
        """Перевіряє чи краулер зупинено."""
        ...

    def is_running(self) -> bool:
        """Перевіряє чи краулер працює."""
        ...
