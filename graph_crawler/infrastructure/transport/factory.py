"""Factory для створення драйверів.

Єдина точка входу для створення будь-яких драйверів.
Підтримує:
- Створення за типом (http, async, playwright)
- Автоматичний вибір оптимального драйвера
- Конфігурація через dict або dataclass

v4.0: Нова архітектура
"""

import logging
from enum import Enum
from typing import Any, Dict, List, Optional, Type, Union

logger = logging.getLogger(__name__)


class DriverType(str, Enum):
    """Типи драйверів."""

    # Async HTTP драйвери (рекомендовані)
    AIOHTTP = "aiohttp"  # Async HTTP через aiohttp
    ASYNC = "async"  # Alias для AIOHTTP
    HTTP = "http"  # Legacy alias для AIOHTTP

    # Browser драйвери
    PLAYWRIGHT = "playwright"  # Async Playwright

    # Sync драйвери (для legacy)
    REQUESTS = "requests"  # Sync HTTP через requests
    SYNC = "sync"  # Alias для REQUESTS

    # Auto-select
    AUTO = "auto"  # Автоматичний вибір


class DriverFactory:
    """
    Factory для створення драйверів.

    Приклади використання:

        >>> # 1. Простий async драйвер
        >>> driver = DriverFactory.create(DriverType.AIOHTTP)
        >>>
        >>> # 2. Playwright з конфігурацією
        >>> driver = DriverFactory.create(
        ...     DriverType.PLAYWRIGHT,
        ...     config={'headless': True, 'timeout': 30}
        ... )
        >>>
        >>> # 3. Автоматичний вибір
        >>> driver = DriverFactory.create(DriverType.AUTO)
        >>>
        >>> # 4. За string типом
        >>> driver = DriverFactory.create('aiohttp')
    """

    # Реєстр драйверів: type -> (module_path, class_name)
    _registry: Dict[DriverType, tuple] = {
        DriverType.AIOHTTP: ("graph_crawler.drivers.async_http.driver", "AsyncDriver"),
        DriverType.HTTP: ("graph_crawler.drivers.async_http.driver", "AsyncDriver"),
        DriverType.ASYNC: ("graph_crawler.drivers.async_http.driver", "AsyncDriver"),
        DriverType.PLAYWRIGHT: (
            "graph_crawler.drivers.playwright.driver",
            "PlaywrightDriver",
        ),
        DriverType.REQUESTS: (
            "graph_crawler.drivers.sync.requests_driver",
            "RequestsDriver",
        ),
        DriverType.SYNC: (
            "graph_crawler.drivers.sync.requests_driver",
            "RequestsDriver",
        ),
    }

    @classmethod
    def create(
        cls,
        driver_type: Union[DriverType, str] = DriverType.AIOHTTP,
        config: Optional[Dict[str, Any]] = None,
        event_bus: Optional[Any] = None,
        plugins: Optional[List[Any]] = None,
    ) -> Any:
        """
        Створює драйвер за типом.

        Args:
            driver_type: Тип драйвера (DriverType або string)
            config: Конфігурація драйвера
            event_bus: EventBus для подій
            plugins: Список плагінів

        Returns:
            Інстанс драйвера

        Raises:
            ValueError: Якщо тип невідомий
            ImportError: Якщо драйвер недоступний
        """
        # Конвертуємо string в DriverType
        if isinstance(driver_type, str):
            try:
                driver_type = DriverType(driver_type.lower())
            except ValueError:
                raise ValueError(
                    f"Unknown driver type: {driver_type}. "
                    f"Available: {[t.value for t in DriverType]}"
                )

        # AUTO: вибираємо оптимальний
        if driver_type == DriverType.AUTO:
            driver_type = cls._auto_select(config)
            logger.info(f"Auto-selected driver: {driver_type.value}")

        # Отримуємо module та class
        if driver_type not in cls._registry:
            raise ValueError(f"Driver type not registered: {driver_type}")

        module_path, class_name = cls._registry[driver_type]

        # Lazy import
        try:
            import importlib

            module = importlib.import_module(module_path)
            driver_class = getattr(module, class_name)
        except ImportError as e:
            raise ImportError(
                f"Cannot import driver {class_name} from {module_path}: {e}. "
                f"Install required dependencies."
            )

        # Створюємо драйвер
        kwargs = {"config": config or {}}
        if event_bus:
            kwargs["event_bus"] = event_bus
        if plugins:
            kwargs["plugins"] = plugins

        return driver_class(**kwargs)

    @classmethod
    def _auto_select(cls, config: Optional[Dict[str, Any]] = None) -> DriverType:
        """
        Автоматично вибирає оптимальний драйвер.

        Логіка:
        1. Якщо потрібен JS рендеринг -> PLAYWRIGHT
        2. Інакше -> AIOHTTP (найшвидший)
        """
        if config:
            # Якщо є browser-специфічні налаштування
            browser_keys = {"headless", "browser", "scroll_page", "wait_selector"}
            if browser_keys & set(config.keys()):
                return DriverType.PLAYWRIGHT

        # Default: async HTTP
        return DriverType.AIOHTTP

    @classmethod
    def register(
        cls, driver_type: DriverType, module_path: str, class_name: str
    ) -> None:
        """
        Реєструє новий тип драйвера.

        Для додавання власних драйверів:

            >>> DriverFactory.register(
            ...     DriverType.CUSTOM,
            ...     'my_package.drivers.custom',
            ...     'CustomDriver'
            ... )
        """
        cls._registry[driver_type] = (module_path, class_name)
        logger.info(
            f"Registered driver: {driver_type.value} -> {module_path}.{class_name}"
        )

    @classmethod
    def available_drivers(cls) -> List[str]:
        """
        Повертає список доступних драйверів.

        Returns:
            Список типів драйверів
        """
        available = []

        for driver_type, (module_path, class_name) in cls._registry.items():
            try:
                import importlib

                importlib.import_module(module_path)
                available.append(driver_type.value)
            except ImportError:
                pass

        return available


# Shortcut функція
def create_driver(driver_type: Union[DriverType, str] = "aiohttp", **kwargs) -> Any:
    """
    Shortcut для DriverFactory.create().

    Example:
        >>> driver = create_driver('playwright', headless=True)
    """
    config = {k: v for k, v in kwargs.items() if k not in ("event_bus", "plugins")}

    return DriverFactory.create(
        driver_type=driver_type,
        config=config,
        event_bus=kwargs.get("event_bus"),
        plugins=kwargs.get("plugins"),
    )
