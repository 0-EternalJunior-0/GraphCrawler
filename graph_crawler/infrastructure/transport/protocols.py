"""Protocol-based інтерфейси для драйверів.

Використовує Python Protocol (PEP 544) для structural subtyping:
- Драйвер НЕ обов'язково наслідувати базовий клас
- Достатньо реалізувати методи з Protocol
- Це дозволяє легко мокати та тестувати

v4.0: Повна реорганізація архітектури драйверів

Note: FetchResponse залишається в domain/value_objects/models.py
      (правильне місце для value objects в Clean Architecture)
"""

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from graph_crawler.domain.value_objects.models import FetchResponse


@runtime_checkable
class IAsyncDriver(Protocol):
    """
    Protocol для async драйверів.

    Будь-який клас що реалізує ці методи - валідний async драйвер.
    Не потрібно наслідувати BaseDriver!

    Example:
        >>> class MyCustomDriver:
        ...     async def fetch(self, url: str) -> FetchResponse:
        ...         ...
        ...     async def fetch_many(self, urls: List[str]) -> List[FetchResponse]:
        ...         ...
        ...     async def close(self) -> None:
        ...         ...
        >>>
        >>> # Перевірка type:
        >>> assert isinstance(MyCustomDriver(), IAsyncDriver)
    """

    async def fetch(self, url: str) -> FetchResponse:
        """Async завантажує одну сторінку."""
        ...

    async def fetch_many(self, urls: List[str]) -> List[FetchResponse]:
        """Async паралельне завантаження."""
        ...

    async def close(self) -> None:
        """Закриває ресурси."""
        ...


@runtime_checkable
class ISyncDriver(Protocol):
    """
    Protocol для sync драйверів (legacy або специфічні провайдери).

    Для випадків коли async неможливий:
    - Legacy бібліотеки (Selenium WebDriver)
    - Специфічні API що блокують
    - CLI інструменти
    """

    def fetch(self, url: str) -> FetchResponse:
        """Sync завантажує одну сторінку."""
        ...

    def fetch_many(self, urls: List[str]) -> List[FetchResponse]:
        """Sync послідовне завантаження."""
        ...

    def close(self) -> None:
        """Закриває ресурси."""
        ...


@runtime_checkable
class IDriverWithPlugins(Protocol):
    """
    Protocol для драйверів з підтримкою плагінів.

    Опціональний - не всі драйвери потребують плагіни.
    """

    @property
    def plugin_manager(self) -> Any:
        """Повертає plugin manager."""
        ...

    def register_plugin(self, plugin: Any) -> None:
        """Реєструє плагін."""
        ...


@runtime_checkable
class IBrowserDriver(Protocol):
    """
    Protocol для браузерних драйверів.

    Розширює async драйвер специфічними browser методами.
    """

    async def fetch(self, url: str) -> FetchResponse:
        """Async завантажує сторінку в браузері."""
        ...

    async def screenshot(self, url: str, path: str) -> str:
        """Робить скріншот сторінки."""
        ...

    async def execute_script(self, script: str) -> Any:
        """Виконує JavaScript."""
        ...

    async def close(self) -> None:
        """Закриває браузер."""
        ...
