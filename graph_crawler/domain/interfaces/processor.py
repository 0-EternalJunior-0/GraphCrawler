"""Protocol для обробника посилань."""

from typing import Protocol



class IProcessor(Protocol):
    """Інтерфейс для обробника посилань."""

    def process_links(self, parent_node, links: list[str]) -> None:
        """Обробляє знайдені посилання."""
        ...
