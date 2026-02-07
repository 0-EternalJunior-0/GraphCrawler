"""Protocol для фільтрів URL."""

from typing import Protocol


class IDomainFilter(Protocol):
    """Інтерфейс для фільтрації доменів."""

    def is_allowed(self, url: str) -> bool:
        """Перевіряє чи дозволений URL за доменом."""
        ...


class IPathFilter(Protocol):
    """Інтерфейс для фільтрації URL шляхів."""

    def is_allowed(self, url: str) -> bool:
        """Перевіряє чи дозволений URL за патерном."""
        ...
