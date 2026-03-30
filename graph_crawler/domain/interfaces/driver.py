"""Protocol для драйверів завантаження сторінок ."""

from typing import Any, List, Optional, Protocol, runtime_checkable

from graph_crawler.domain.value_objects.models import FetchResponse


@runtime_checkable
class IDriver(Protocol):
    """Async-First інтерфейс для драйвера завантаження сторінок."""

    async def fetch(self, url: str) -> FetchResponse:
        """
        Async завантаження сторінки за URL.

        Args:
            url: URL сторінки для завантаження

        Returns:
            FetchResponse з HTML або помилкою
        """
        ...

    async def fetch_many(self, urls: List[str]) -> List[FetchResponse]:
        """
        Async batch завантаження множини URL.

        Всі запити виконуються паралельно для максимальної швидкості.

        Args:
            urls: Список URL

        Returns:
            Список FetchResponse
        """
        ...

    async def close(self) -> None:
        """Async закриття драйвера та вивільнення ресурсів."""
        ...

    def supports_batch_fetching(self) -> bool:
        """Чи підтримує драйвер batch завантаження ."""
        ...

    async def __aenter__(self) -> "IDriver":
        """Async context manager entry."""
        ...

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Optional[bool]:
        """Async context manager exit - автоматично закриває драйвер."""
        ...
