"""Protocol для планувальника URL."""

from typing import Optional, Protocol


class IScheduler(Protocol):
    """Інтерфейс для планувальника URL."""

    def add_node(self, node) -> None:
        """Додає ноду в чергу."""
        ...

    def get_next(self):
        """Отримує наступну ноду для сканування."""
        ...

    def is_empty(self) -> bool:
        """Перевіряє чи черга порожня."""
        ...

    def size(self) -> int:
        """Повертає розмір черги."""
        ...
