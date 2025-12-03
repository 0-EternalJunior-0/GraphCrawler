"""Спільні helper функції для Celery модулів.

Винесено в спільний модуль для DRY принципу.

Цей модуль містить:
- _import_plugin: Dynamic import плагіна
- _import_class: Dynamic import класу
- _create_driver_from_config: Створення драйвера з конфігурації
"""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def import_plugin(import_path: str) -> Optional[Any]:
    """
    Dynamic import плагіна за import path з валідацією.

    Args:
        import_path: Повний шлях імпорту (напр. "myapp.plugins.MyPlugin")

    Returns:
        Інстанс плагіна або None при помилці

    Example:
        plugin = import_plugin("graph_crawler.plugins.node.extractors.PhoneExtractorPlugin")
        if plugin:
            plugins.append(plugin)
    """
    import importlib

    try:
        module_path, class_name = import_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        plugin_class = getattr(module, class_name)
        return plugin_class()
    except ModuleNotFoundError as e:
        logger.error(
            f" Модуль плагіна не знайдено: {import_path}\n"
            f"Помилка: {e}\n"
            f"Встановіть плагін: pip install <package_name>"
        )
        return None
    except AttributeError as e:
        logger.error(
            f" Клас плагіна не знайдено в модулі: {import_path}\n" f"Помилка: {e}"
        )
        return None
    except Exception as e:
        logger.error(f" Не вдалося імпортувати плагін {import_path}: {e}")
        return None


def import_class(import_path: str) -> Optional[type]:
    """
    Dynamic import класу за import path.

    Args:
        import_path: Повний шлях імпорту класу

    Returns:
        Клас або None при помилці

    Example:
        node_class = import_class("myapp.models.CustomNode")
        if node_class:
            node = node_class(url="https://example.com")
    """
    import importlib

    try:
        module_path, class_name = import_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        return getattr(module, class_name)
    except Exception as e:
        logger.error(f"Failed to import class {import_path}: {e}")
        return None


def create_driver_from_config(driver_config: dict) -> Any:
    """
    Створює драйвер з конфігурації.

    Підтримує як вбудовані драйвери так і кастомні.

    Args:
        driver_config: Dict з:
            - driver_class: Import path драйвера
            - config: Конфігурація драйвера
            - plugins: Список плагінів драйвера (опціонально)

    Returns:
        Інстанс драйвера

    Example:
        config = {
            "driver_class": "graph_crawler.drivers.async_http.driver.AsyncDriver",
            "config": {"timeout": 30},
            "plugins": []
        }
        driver = create_driver_from_config(config)
    """
    import importlib

    driver_class_path = driver_config.get("driver_class")
    config = driver_config.get("config", {})
    plugin_paths = driver_config.get("plugins", [])

    # Імпортуємо клас драйвера
    try:
        module_path, class_name = driver_class_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        driver_class = getattr(module, class_name)
    except Exception as e:
        logger.error(f"Failed to import driver {driver_class_path}: {e}")
        # Fallback на AsyncDriver або RequestsDriver
        return _get_fallback_driver()

    # Імпортуємо плагіни драйвера
    driver_plugins = []
    for plugin_path in plugin_paths:
        plugin = import_plugin(plugin_path)
        if plugin:
            driver_plugins.append(plugin)

    # Створюємо драйвер з плагінами
    try:
        if driver_plugins:
            return driver_class(config=config, plugins=driver_plugins)
        else:
            return driver_class(config=config)
    except Exception as e:
        logger.error(f"Failed to create driver: {e}")
        return _get_fallback_driver()


def _get_fallback_driver() -> Any:
    """
    Повертає fallback драйвер при помилках.

    Спочатку пробує AsyncDriver, потім RequestsDriver.

    Returns:
        Інстанс драйвера
    """
    try:
        from graph_crawler.infrastructure.transport.async_http.driver import AsyncDriver

        logger.info("Fallback to AsyncDriver")
        return AsyncDriver({})
    except ImportError:
        from graph_crawler.infrastructure.transport.sync.requests_driver import (
            RequestsDriver,
        )

        logger.info("Fallback to RequestsDriver")
        return RequestsDriver({})


# Експортуємо для використання в інших модулях
__all__ = [
    "import_plugin",
    "import_class",
    "create_driver_from_config",
]
