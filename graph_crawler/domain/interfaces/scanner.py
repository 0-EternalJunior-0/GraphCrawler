"""Protocol для сканера сторінок ."""

from typing import List, Protocol, Tuple, runtime_checkable


@runtime_checkable
class IScanner(Protocol):
    """
    Async-First інтерфейс для сканера сторінок. Повністю async інтерфейс для неблокуючого сканування.
    Підтримує як одиночне, так і batch сканування.
    """

    async def scan_node(self, node) -> List[str]:
        """
        Async сканування однієї ноди.

        Args:
            node: Node для сканування

        Returns:
            Список знайдених URL посилань
        """
        ...

    async def scan_batch(self, nodes: List) -> List[Tuple]:
        """
        Async batch сканування нод.

        Всі ноди сканують паралельно для максимальної швидкості.

        Args:
            nodes: Список нод для сканування

        Returns:
            Список кортежів (node, links)
        """
        ...
