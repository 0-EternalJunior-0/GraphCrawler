"""Спрощений Application Container для GraphCrawler.

Замість dependency-injector використовуємо простий Python клас.

Цей контейнер забезпечує:
- Ліниву ініціалізацію компонентів
- Управління конфігурацією
- Створення драйверів та сховищ

Використання:
    container = ApplicationContainer()
    container.config.from_pydantic(config)
    driver = container.driver.http_driver()
    storage = container.storage.memory_storage()
"""

import logging
from typing import Any, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ConfigProvider:
    """Провайдер конфігурації."""

    def __init__(self):
        self._config: Optional[BaseModel] = None

    def from_pydantic(self, config: BaseModel) -> None:
        """Встановити конфігурацію з Pydantic моделі."""
        self._config = config

    def get(self) -> Optional[BaseModel]:
        """Отримати поточну конфігурацію."""
        return self._config


class DriverProvider:
    """Провайдер драйверів."""

    def __init__(self, config_provider: ConfigProvider):
        self._config = config_provider
        self._driver_instance = None

    def http_driver(self, config: Optional[dict] = None):
        """Створити HTTP драйвер."""
        from graph_crawler.application.services.driver_factory import create_driver

        driver_config = config or {}
        if self._config.get():
            cfg = self._config.get()
            if hasattr(cfg, "driver") and cfg.driver:
                driver_config = {
                    "timeout": getattr(cfg.driver, "timeout", 30),
                    "request_delay": getattr(cfg.driver, "request_delay", 0.5),
                }

        self._driver_instance = create_driver("http", driver_config)
        return self._driver_instance

    def async_driver(self, config: Optional[dict] = None):
        """Створити Async драйвер."""
        from graph_crawler.application.services.driver_factory import create_driver

        driver_config = config or {}
        self._driver_instance = create_driver("async", driver_config)
        return self._driver_instance

    def playwright_driver(self, config: Optional[dict] = None):
        """Створити Playwright драйвер."""
        from graph_crawler.application.services.driver_factory import create_driver

        driver_config = config or {}
        self._driver_instance = create_driver("playwright", driver_config)
        return self._driver_instance


class StorageProvider:
    """Провайдер сховищ."""

    def __init__(self, config_provider: ConfigProvider):
        self._config = config_provider
        self._storage_instance = None

    def memory_storage(self):
        """Створити Memory Storage."""
        from graph_crawler.infrastructure.persistence.memory_storage import (
            MemoryStorage,
        )

        self._storage_instance = MemoryStorage()
        return self._storage_instance

    def json_storage(self, filepath: str = "graph.json"):
        """Створити JSON Storage."""
        from graph_crawler.infrastructure.persistence.json.json_storage import (
            JSONStorage,
        )

        self._storage_instance = JSONStorage(filepath)
        return self._storage_instance

    def sqlite_storage(self, db_path: str = "graph.db"):
        """Створити SQLite Storage."""
        from graph_crawler.infrastructure.persistence.sqlite.sqlite_storage import (
            SQLiteStorage,
        )

        self._storage_instance = SQLiteStorage(db_path)
        return self._storage_instance


class CoreProvider:
    """Провайдер core компонентів."""

    def __init__(self):
        self._event_bus = None

    def event_bus(self):
        """Створити EventBus."""
        if self._event_bus is None:
            from graph_crawler.domain.events.event_bus import EventBus

            self._event_bus = EventBus()
        return self._event_bus


class ApplicationContainer:
    """
    Спрощений DI контейнер для GraphCrawler.

    використовуємо простий Python клас з lazy initialization.

    Використання:
        container = ApplicationContainer()
        container.config.from_pydantic(my_config)

        driver = container.driver.http_driver()
        storage = container.storage.memory_storage()
        event_bus = container.core.event_bus()
    """

    def __init__(self):
        self._config = ConfigProvider()
        self._driver = DriverProvider(self._config)
        self._storage = StorageProvider(self._config)
        self._core = CoreProvider()
        self._repository = None

    @property
    def config(self) -> ConfigProvider:
        """Провайдер конфігурації."""
        return self._config

    @property
    def driver(self) -> DriverProvider:
        """Провайдер драйверів."""
        return self._driver

    @property
    def storage(self) -> StorageProvider:
        """Провайдер сховищ."""
        return self._storage

    @property
    def core(self) -> CoreProvider:
        """Провайдер core компонентів."""
        return self._core

    def repository(self):
        """Створити репозиторій для графа."""
        if self._repository is None:
            from graph_crawler.domain.entities.graph import Graph

            # Простий репозиторій - повертаємо новий Graph
            self._repository = Graph()
        return self._repository

    async def shutdown_resources_async(self):
        """Async закриття ресурсів."""
        try:
            if self._driver._driver_instance:
                driver = self._driver._driver_instance
                if hasattr(driver, "close"):
                    if callable(getattr(driver, "close", None)):
                        import asyncio
                        import inspect

                        if inspect.iscoroutinefunction(driver.close):
                            await driver.close()
                        else:
                            driver.close()

            if self._storage._storage_instance:
                storage = self._storage._storage_instance
                if hasattr(storage, "close"):
                    import asyncio
                    import inspect

                    if inspect.iscoroutinefunction(storage.close):
                        await storage.close()
                    else:
                        storage.close()

            logger.debug("ApplicationContainer resources shutdown complete")
        except Exception as e:
            logger.warning(f"Error during shutdown: {e}")


# Експорт
__all__ = ["ApplicationContainer"]
