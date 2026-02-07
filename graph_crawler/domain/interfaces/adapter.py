"""Protocol для HTML адаптерів."""

from typing import Any, List, Optional, Protocol


class ITreeAdapter(Protocol):
    """Інтерфейс для HTML адаптерів."""

    def parse(self, html: str) -> Any:
        """Парсить HTML в дерево."""
        ...

    def find(self, tree: Any, selector: str) -> Optional[Any]:
        """Знаходить перший елемент."""
        ...

    def find_all(self, tree: Any, selector: str) -> List[Any]:
        """Знаходить всі елементи."""
        ...

    def get_text(self, element: Any) -> str:
        """Отримує текст елементу."""
        ...

    def get_attribute(self, element: Any, attr: str) -> Optional[str]:
        """Отримує атрибут елементу."""
        ...
