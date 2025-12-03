"""Внутрішня реалізація async краулінгу.

Використовуються інтерфейси IDriver, IStorage замість конкретних класів.
Dependency Injection через параметри функції, фабрики винесені окремо.
"""

import asyncio
import logging
from typing import Any, Optional

# ОПТИМІЗАЦІЯ: Використовуємо uvloop якщо доступний для швидшого event loop
_uvloop_enabled = False
try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    _uvloop_enabled = True
except ImportError:
    pass  # uvloop не встановлено, використовуємо стандартний event loop

from graph_crawler.api._shared import DriverType, EventCallback, StorageType
from graph_crawler.domain.entities.edge import Edge
from graph_crawler.domain.entities.graph import Graph
from graph_crawler.domain.entities.node import Node
from graph_crawler.domain.value_objects.models import URLRule

logger = logging.getLogger(__name__)

if _uvloop_enabled:
    logger.info("✅ uvloop enabled for faster event loop")


async def async_crawl_impl(
    url: str,
    *,
    max_depth: int = 3,
    max_pages: Optional[int] = 100,
    same_domain: bool = True,
    timeout: Optional[int] = None,
    request_delay: float = 0.5,
    driver: Optional[DriverType] = None,
    driver_config: Optional[dict[str, Any]] = None,
    storage: Optional[StorageType] = None,
    storage_config: Optional[dict[str, Any]] = None,
    plugins: Optional[list] = None,
    node_class: Optional[type[Node]] = None,
    edge_class: Optional[type[Edge]] = None,
    url_rules: Optional[list[URLRule]] = None,
    on_progress: Optional[EventCallback] = None,
    on_node_scanned: Optional[EventCallback] = None,
    on_error: Optional[EventCallback] = None,
    on_completed: Optional[EventCallback] = None,
    edge_strategy: str = "all",
) -> Graph:
    """Внутрішня async реалізація crawl.

    Використовуємо інтерфейси IDriver, IStorage для іньєкції залежностей.
    Фабрики викликаються через окремі функції.

    Args:
        url: URL для краулінгу
        max_depth: Максимальна глибина краулінгу
        max_pages: Максимальна кількість сторінок
        same_domain: Краулити тільки в межах домену
        timeout: Timeout для краулінгу (секунди)
        request_delay: Затримка між запитами
        driver: Тип драйвера або IDriver об'єкт
        driver_config: Конфігурація драйвера
        storage: Тип storage або IStorage об'єкт
        storage_config: Конфігурація storage
        plugins: Список плагінів
        node_class: Кастомний клас Node
        edge_class: Кастомний клас Edge
        url_rules: Правила для URL
        on_progress: Callback для прогресу
        on_node_scanned: Callback після сканування ноди
        on_error: Callback при помилці
        on_completed: Callback після завершення
        edge_strategy: Стратегія створення edges

    Returns:
        Graph об'єкт з результатами краулінгу
    """
    from graph_crawler.api.client.client import GraphCrawlerClient
    from graph_crawler.application.services.driver_factory import create_driver
    from graph_crawler.application.services.storage_factory import create_storage
    from graph_crawler.domain.events.event_bus import EventBus
    from graph_crawler.domain.events.events import EventType
    from graph_crawler.domain.value_objects.configs import CrawlerConfig, DriverConfig
    from graph_crawler.infrastructure.persistence.graph_repository import (
        GraphRepository,
    )

    actual_driver = None

    try:
        domains = None
        if same_domain:
            from graph_crawler.application.use_cases.crawling.filters.domain_patterns import (
                AllowedDomains,
            )

            domains = [AllowedDomains.DOMAIN_WITH_SUB.value]

        if driver is not None:
            actual_driver = create_driver(driver, driver_config or {})
            logger.info(f"Created driver: {type(actual_driver).__name__}")
        else:
            actual_driver = create_driver("http", {})

        if storage is not None:
            storage_instance = create_storage(storage, storage_config or {})
        else:
            storage_instance = create_storage("memory", {})

        event_bus = EventBus()
        repository = GraphRepository()

        if on_progress:
            event_bus.subscribe(
                EventType.PROGRESS_UPDATE, lambda e: on_progress(e.data)
            )
        if on_node_scanned:
            event_bus.subscribe(
                EventType.NODE_SCANNED, lambda e: on_node_scanned(e.data)
            )
        if on_error:
            event_bus.subscribe(EventType.ERROR_OCCURRED, lambda e: on_error(e.data))
        if on_completed:
            event_bus.subscribe(
                EventType.CRAWL_COMPLETED, lambda e: on_completed(e.data)
            )

        client = GraphCrawlerClient(
            driver=actual_driver,
            storage=storage_instance,
            event_bus=event_bus,
            repository=repository,
        )

        if timeout:
            graph = await asyncio.wait_for(
                client.crawl(
                    url=url,
                    max_depth=max_depth,
                    max_pages=max_pages,
                    allowed_domains=domains,
                    url_rules=url_rules,
                    custom_node_class=node_class,
                    custom_edge_class=edge_class,
                    edge_strategy=edge_strategy,
                    node_plugins=plugins,
                ),
                timeout=timeout,
            )
        else:
            graph = await client.crawl(
                url=url,
                max_depth=max_depth,
                max_pages=max_pages,
                allowed_domains=domains,
                url_rules=url_rules,
                custom_node_class=node_class,
                custom_edge_class=edge_class,
                edge_strategy=edge_strategy,
                node_plugins=plugins,
            )

        logger.info(
            f"Crawl completed: {len(graph.nodes)} nodes, {len(graph.edges)} edges"
        )
        return graph

    finally:
        try:
            if actual_driver and hasattr(actual_driver, "close"):
                await actual_driver.close()
                logger.debug("Driver closed successfully")
        except Exception as e:
            logger.warning(f"Error shutting down resources: {e}")


__all__ = ["async_crawl_impl"]
