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
DriverFactory = Callable[[dict], Any]  # Can return IDriver or sync driver

# DRIVER REGISTRY (OCP)
# Registry pattern дозволяє додавати нові драйвери без зміни коду factory

_DRIVER_REGISTRY: Dict[str, DriverFactory] = {}


def _register_builtin_drivers():
    """Реєструє вбудовані драйвери."""

    def http_factory(config: dict) -> "IDriver":
        from graph_crawler.infrastructure.transport import HTTPDriver

        return HTTPDriver(config)  # type: ignore[return-value]

    def async_factory(config: dict) -> "IDriver":
        try:
            from graph_crawler.infrastructure.transport.async_http import AsyncDriver
            from graph_crawler.infrastructure.transport.async_http.plugins.http_cache import (
                AsyncHTTPCachePlugin,
            )
            
            # Автоматично додаємо HTTP Cache plugin якщо увімкнено
            plugins = config.pop("plugins", []) if isinstance(config, dict) else []
            
            http_cache_enabled = config.pop("http_cache_enabled", True) if isinstance(config, dict) else True
            if http_cache_enabled:
                cache_config = AsyncHTTPCachePlugin.create_config(
                    enabled=True,
                    max_cache_size=config.pop("http_cache_max_size", 10000) if isinstance(config, dict) else 10000,
                    store_content=config.pop("http_cache_store_content", False) if isinstance(config, dict) else False,
                    max_age_seconds=config.pop("http_cache_max_age", 3600) if isinstance(config, dict) else 3600,
                )
                plugins.append(AsyncHTTPCachePlugin(cache_config))
            
            return AsyncDriver(config, plugins=plugins if plugins else None)  # type: ignore[return-value]
        except ImportError:
            raise ImportError("AsyncDriver requires aiohttp. Install with: pip install aiohttp")

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
            from graph_crawler.infrastructure.transport.async_http.plugins.stealth_driver import (
                StealthHTTPDriver,
            )

            return StealthHTTPDriver(config)
        except ImportError:
            raise ImportError(
                "StealthHTTPDriver requires curl_cffi. Install with: pip install curl_cffi"
            )

    def cloudscraper_factory(config: dict) -> "IDriver":
        try:
            from graph_crawler.infrastructure.transport.sync.cloudscraper_driver import (
                CloudscraperDriver,
            )

            return CloudscraperDriver(config)  # type: ignore[return-value]
        except ImportError:
            raise ImportError(
                "CloudscraperDriver requires cloudscraper. Install with: pip install cloudscraper"
            )

    # Реєструємо вбудовані драйвери
    _DRIVER_REGISTRY["http"] = http_factory
    _DRIVER_REGISTRY["async"] = async_factory
    _DRIVER_REGISTRY["playwright"] = playwright_factory
    _DRIVER_REGISTRY["stealth"] = stealth_factory
    _DRIVER_REGISTRY["cloudscraper"] = cloudscraper_factory


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
        logger.warning("Overwriting existing driver registration: %s", name)
    _DRIVER_REGISTRY[name] = factory
    logger.debug("Registered driver: %s", name)


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


def create_driver(driver: DriverType = None, config: Optional[dict[str, Any]] = None) -> "IDriver":
    """
    Створює драйвер з string або повертає instance.

    Returns:
        IDriver: Готовий до використання драйвер
    Raises:
        ValueError: Якщо невідомий тип драйвера
    Examples:
        Простий HTTP драйвер:
        >>> driver = create_driver("http")
        >>> response = driver.fetch("https://example.com")
    """
    config = config or {}

    # Якщо передали готовий драйвер (instance) - повертаємо як є
    if driver is not None and not isinstance(driver, (str, type)):
        # Перевіряємо чи це схоже на драйвер (має метод fetch)
        if hasattr(driver, "fetch"):
            logger.debug("Using custom driver instance: %s", type(driver).__name__)
            return driver
        else:
            raise ValueError(
                f"Invalid driver instance: {type(driver).__name__}. "
                f"Driver must have 'fetch' method."
            )

    # Якщо передали клас драйвера - створюємо instance
    if driver is not None and isinstance(driver, type):
        logger.debug("Creating driver from class: %s", driver.__name__)
        return driver(config)

    # String shortcuts - використовуємо registry (OCP)
    driver_type = driver or "http"
    driver_type = driver_type.lower()

    # Перевіряємо registry
    if driver_type in _DRIVER_REGISTRY:
        factory = _DRIVER_REGISTRY[driver_type]
        logger.debug("Creating %s driver from registry", driver_type)
        return factory(config)
    else:
        available = ", ".join(f"'{d}'" for d in get_available_drivers())
        raise ValueError(
            f"Unknown driver type: '{driver}'. "
            f"Available: {available} "
            f"or provide IDriver instance. "
            f"Use register_driver() to add custom drivers."
        )
