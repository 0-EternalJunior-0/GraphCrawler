"""Factory для створення драйверів.

Створює драйвер з string або повертає готовий instance.

для дотримання Open/Closed Principle.

Приклади:
    >>> driver = create_driver("http")
    >>> driver = create_driver("playwright", {"headless": True})
    >>> driver = create_driver(CustomDriver())

    # Реєстрація кастомного драйвера
    >>> register_driver("mydriver", MyDriverClass)
    >>> driver = create_driver("mydriver")
"""

import logging
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Union

if TYPE_CHECKING:
    from graph_crawler.domain.interfaces.driver import IDriver

logger = logging.getLogger(__name__)

# Type aliases
DriverType = Union[str, "IDriver", None]
DriverFactory = Callable[[dict], "IDriver"]

# =====================================
# DRIVER REGISTRY (OCP)
# =====================================
# Registry pattern дозволяє додавати нові драйвери без зміни коду factory

_DRIVER_REGISTRY: Dict[str, DriverFactory] = {}


def _register_builtin_drivers():
    """Реєструє вбудовані драйвери."""

    def http_factory(config: dict) -> "IDriver":
        from graph_crawler.infrastructure.transport import HTTPDriver

        return HTTPDriver(config)

    def async_factory(config: dict) -> "IDriver":
        try:
            from graph_crawler.infrastructure.transport.async_http import AsyncDriver

            return AsyncDriver(config)
        except ImportError:
            raise ImportError(
                "AsyncDriver requires aiohttp. " "Install with: pip install aiohttp"
            )

    def playwright_factory(config: dict) -> "IDriver":
        try:
            from graph_crawler.infrastructure.transport.playwright import (
                PlaywrightDriver,
            )

            return PlaywrightDriver(config)
        except ImportError:
            raise ImportError(
                "PlaywrightDriver requires playwright. "
                "Install with: pip install playwright && playwright install"
            )

    def stealth_factory(config: dict) -> "IDriver":
        try:
            from graph_crawler.infrastructure.transport.stealth_driver import (
                StealthDriver,
            )

            return StealthDriver(config)
        except ImportError:
            raise ImportError(
                "StealthDriver requires playwright. "
                "Install with: pip install playwright && playwright install"
            )

    # Реєструємо вбудовані драйвери
    _DRIVER_REGISTRY["http"] = http_factory
    _DRIVER_REGISTRY["async"] = async_factory
    _DRIVER_REGISTRY["playwright"] = playwright_factory
    _DRIVER_REGISTRY["stealth"] = stealth_factory


# Ініціалізуємо вбудовані драйвери
_register_builtin_drivers()


def register_driver(name: str, factory: DriverFactory) -> None:
    """
    Реєструє новий тип драйвера (Open/Closed Principle).

    Дозволяє додавати нові драйвери без зміни коду factory.

    Args:
        name: Назва драйвера (lowercase)
        factory: Функція-фабрика яка приймає config і повертає IDriver

    Example:
        def my_driver_factory(config: dict) -> IDriver:
            return MyCustomDriver(config)

        register_driver("mydriver", my_driver_factory)
        driver = create_driver("mydriver", {"option": "value"})
    """
    name = name.lower()
    if name in _DRIVER_REGISTRY:
        logger.warning(f"Overwriting existing driver registration: {name}")
    _DRIVER_REGISTRY[name] = factory
    logger.debug(f"Registered driver: {name}")


def get_available_drivers() -> list[str]:
    """
    Повертає список доступних типів драйверів.

    Returns:
        Список назв зареєстрованих драйверів

    Example:
        >>> get_available_drivers()
        ['http', 'async', 'playwright', 'stealth']
    """
    return list(_DRIVER_REGISTRY.keys())


def create_driver(
    driver: DriverType = None, config: Optional[dict[str, Any]] = None
) -> "IDriver":
    """
    Створює драйвер з string або повертає instance.

    Factory pattern для простого створення драйверів.
    Дозволяє використовувати string shortcuts замість імпортування класів.

    Args:
        driver: Тип драйвера або готовий instance
            - "http" (default): Синхронний HTTP драйвер (requests)
            - "async": Асинхронний HTTP драйвер (aiohttp)
            - "playwright": Браузерний драйвер з JS рендерингом
            - "stealth": Stealth драйвер для обходу блокувань
            - IDriver instance: Повертається як є
        config: Конфігурація драйвера (опціонально)
            - timeout: int - таймаут запиту
            - user_agent: str - User-Agent заголовок
            - headless: bool - для playwright (default: True)
            - max_retries: int - кількість повторів

    Returns:
        IDriver: Готовий до використання драйвер

    Raises:
        ValueError: Якщо невідомий тип драйвера

    Examples:
        Простий HTTP драйвер:
        >>> driver = create_driver("http")
        >>> response = driver.fetch("https://example.com")

        Playwright з налаштуваннями:
        >>> driver = create_driver("playwright", {
        ...     "headless": True,
        ...     "timeout": 60
        ... })

        Кастомний драйвер:
        >>> class MyDriver:
        ...     def fetch(self, url): ...
        ...     def close(self): ...
        >>>
        >>> driver = create_driver(MyDriver())
    """
    config = config or {}

    # Якщо передали готовий драйвер (instance) - повертаємо як є
    if driver is not None and not isinstance(driver, (str, type)):
        # Перевіряємо чи це схоже на драйвер (має метод fetch)
        if hasattr(driver, "fetch"):
            logger.debug(f"Using custom driver instance: {type(driver).__name__}")
            return driver
        else:
            raise ValueError(
                f"Invalid driver instance: {type(driver).__name__}. "
                f"Driver must have 'fetch' method."
            )

    # Якщо передали клас драйвера - створюємо instance
    if driver is not None and isinstance(driver, type):
        logger.debug(f"Creating driver from class: {driver.__name__}")
        return driver(config)

    # String shortcuts - використовуємо registry (OCP)
    driver_type = driver or "http"
    driver_type = driver_type.lower()

    # Перевіряємо registry
    if driver_type in _DRIVER_REGISTRY:
        factory = _DRIVER_REGISTRY[driver_type]
        logger.debug(f"Creating {driver_type} driver from registry")
        return factory(config)
    else:
        available = ", ".join(f"'{d}'" for d in get_available_drivers())
        raise ValueError(
            f"Unknown driver type: '{driver}'. "
            f"Available: {available} "
            f"or provide IDriver instance. "
            f"Use register_driver() to add custom drivers."
        )
