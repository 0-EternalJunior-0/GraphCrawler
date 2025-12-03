"""Mixin для серіалізації конфігурації Celery spiders.

Створено спільний mixin для CelerySpider та CeleryBatchSpider.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ConfigSerializationMixin:
    """
    Mixin для серіалізації конфігурації Celery spiders.

    для CelerySpider та CeleryBatchSpider.

    Вимагає щоб клас мав атрибути:
    - self.config: CrawlerConfig
    - self.driver: BaseDriver

    Використання:
        class CelerySpider(ConfigSerializationMixin):
            def crawl(self):
                config_dict = self._serialize_config()
                # ...
    """

    def _serialize_config(self) -> dict:
        """
        Серіалізує конфігурацію для передачі через Celery.

         МОДУЛЬНА АРХІТЕКТУРА:
        - Плагіни → import paths
        - Custom Node класи → import paths
        - Драйвери → config dict + import path
        - Все динамічно завантажується на воркері

        Returns:
            Серіалізований словник конфігурації
        """
        # Серіалізуємо конфіг, виключаючи non-serializable об'єкти
        config_dict = self.config.model_dump(
            exclude={"node_plugins", "custom_node_class", "custom_edge_class", "driver"}
        )

        # ========== СЕРІАЛІЗАЦІЯ ПЛАГІНІВ ==========
        config_dict["_plugin_paths"] = self._serialize_plugins()

        # ========== СЕРІАЛІЗАЦІЯ CUSTOM NODE CLASS ==========
        if self.config.custom_node_class:
            config_dict["_custom_node_class"] = self._get_class_import_path(
                self.config.custom_node_class
            )

        # ========== СЕРІАЛІЗАЦІЯ ДРАЙВЕРА ==========
        driver_config = self._serialize_driver(self.driver)
        if driver_config:
            config_dict["_driver_config"] = driver_config

        return config_dict

    def _serialize_plugins(self) -> List[str]:
        """
        Серіалізує плагіни в список import paths.

        Returns:
            Список import paths для плагінів
        """
        plugin_paths = []
        if hasattr(self.config, "node_plugins") and self.config.node_plugins:
            for plugin in self.config.node_plugins:
                plugin_paths.append(self._get_instance_import_path(plugin))
        return plugin_paths

    def _serialize_driver(self, driver) -> Optional[Dict[str, Any]]:
        """
        Серіалізує драйвер для передачі через Celery.

        Args:
            driver: Інстанс драйвера

        Returns:
            Dict з конфігурацією драйвера або None
        """
        if not driver:
            return None

        try:
            driver_class_path = self._get_instance_import_path(driver)

            # Отримуємо конфігурацію драйвера
            driver_config = self._extract_driver_config(driver)

            # Плагіни драйвера
            driver_plugin_paths = self._serialize_driver_plugins(driver)

            return {
                "driver_class": driver_class_path,
                "config": driver_config,
                "plugins": driver_plugin_paths,
            }
        except Exception as e:
            logger.warning(f"Failed to serialize driver: {e}")
            return None

    def _extract_driver_config(self, driver) -> dict:
        """
        Витягує конфігурацію з драйвера.

        Args:
            driver: Інстанс драйвера

        Returns:
            Dict з конфігурацією
        """
        if not hasattr(driver, "config"):
            return {}

        if isinstance(driver.config, dict):
            return driver.config
        elif hasattr(driver.config, "model_dump"):
            return driver.config.model_dump()
        else:
            return {}

    def _serialize_driver_plugins(self, driver) -> List[str]:
        """
        Серіалізує плагіни драйвера.

        Args:
            driver: Інстанс драйвера

        Returns:
            Список import paths для плагінів драйвера
        """
        plugin_paths = []
        if hasattr(driver, "plugins") and driver.plugins:
            for plugin in driver.plugins:
                plugin_paths.append(self._get_instance_import_path(plugin))
        return plugin_paths

    @staticmethod
    def _get_instance_import_path(instance) -> str:
        """
        Отримує import path для інстансу об'єкта.

        Args:
            instance: Об'єкт

        Returns:
            Import path у форматі 'module.ClassName'
        """
        module = instance.__class__.__module__
        class_name = instance.__class__.__name__
        return f"{module}.{class_name}"

    @staticmethod
    def _get_class_import_path(cls) -> str:
        """
        Отримує import path для класу.

        Args:
            cls: Клас

        Returns:
            Import path у форматі 'module.ClassName'
        """
        return f"{cls.__module__}.{cls.__name__}"


# Функції-хелпери для десеріалізації (використовуються на воркерах)


def import_class_from_path(import_path: str):
    """
    Імпортує клас за import path.

    Args:
        import_path: Шлях у форматі 'module.ClassName'

    Returns:
        Клас або None при помилці
    """
    try:
        import importlib

        module_path, class_name = import_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        return getattr(module, class_name)
    except Exception as e:
        logger.error(f"Failed to import class {import_path}: {e}")
        return None


def create_instance_from_path(import_path: str, *args, **kwargs):
    """
    Створює інстанс класу за import path.

    Args:
        import_path: Шлях у форматі 'module.ClassName'
        *args: Позиційні аргументи для конструктора
        **kwargs: Іменовані аргументи для конструктора

    Returns:
        Інстанс класу або None при помилці
    """
    cls = import_class_from_path(import_path)
    if cls is None:
        return None
    try:
        return cls(*args, **kwargs)
    except Exception as e:
        logger.error(f"Failed to create instance of {import_path}: {e}")
        return None


__all__ = [
    "ConfigSerializationMixin",
    "import_class_from_path",
    "create_instance_from_path",
]
