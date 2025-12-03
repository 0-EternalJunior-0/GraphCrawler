"""Protocol для обробника посилань."""

from typing import List, Protocol


class IProcessor(Protocol):
    """Інтерфейс для обробника посилань."""

    def process_links(self, parent_node, links: List[str]) -> None:
        """Обробляє знайдені посилання."""
        ...
