"""Внутрішня реалізація async краулінгу.

Використовуються інтерфейси IDriver, IStorage замість конкретних класів.
Dependency Injection через параметри функції, фабрики винесені окремо.
"""

import asyncio
import logging
from typing import Any, Optional

# Auto-bootstrap при імпорті модуля
from graph_crawler.application.bootstrap import bootstrap

bootstrap()

# Використовуємо uvloop якщо доступний для швидшого event loop
_uvloop_enabled = False
try:
    import uvloop  # type: ignore[import-not-found]

    # Тільки встановлюємо policy якщо event loop ще не запущений
    # Це запобігає RuntimeError при імпорті з вже запущеного async контексту
    try:
        loop = asyncio.get_running_loop()
        # Event loop вже запущений - не змінюємо policy
    except RuntimeError:
        # Немає запущеного event loop - безпечно встановити policy
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        _uvloop_enabled = True
except ImportError:
    pass  # uvloop не встановлено, використовуємо стандартний event loop
except Exception:
    # Інші помилки (RuntimeError, тощо) - ігноруємо і використовуємо стандартний
    pass

from graph_crawler.api._shared import DriverType, EventCallback, StorageType
from graph_crawler.domain.entities.edge import Edge
from graph_crawler.domain.entities.graph import Graph
from graph_crawler.domain.entities.node import Node
from graph_crawler.domain.value_objects.models import Rule

logger = logging.getLogger(__name__)

if _uvloop_enabled:
    logger.info(" uvloop enabled for faster event loop")


async def async_crawl_impl(
    url: Optional[str] = None,
    *,
    seed_urls: Optional[list[str]] = None,
    base_graph: Optional[Graph] = None,
    max_depth: int = 3,
    max_pages: Optional[int] = 100,
    same_domain: bool = True,
    allowed_domains: Optional[list[str]] = None,
    timeout: Optional[int] = None,
    request_delay: float = 0.5,
    driver: Optional[DriverType] = None,
    driver_config: Optional[dict[str, Any]] = None,
    storage: Optional[StorageType] = None,
    storage_config: Optional[dict[str, Any]] = None,
    plugins: Optional[list] = None,
    node_class: Optional[type[Node]] = None,
    edge_class: Optional[type[Edge]] = None,
    url_rules: Optional[list[Rule]] = None,
    on_progress: Optional[EventCallback] = None,
    on_node_scanned: Optional[EventCallback] = None,
    on_error: Optional[EventCallback] = None,
    on_completed: Optional[EventCallback] = None,
    edge_strategy: str = "all",
    follow_links: bool = True,
    # LOW-MEMORY MODE
    low_memory_mode: bool = False,
    evict_threshold: int = 500,
    eviction_storage_path: Optional[str] = None,
    # AI Agent Integration
    crawl_context: Optional[Any] = None,
    control_channel: Optional[Any] = None,
) -> Graph:
    """Внутрішня async реалізація crawl з підтримкою множинних seed URLs та incremental crawling.

    Використовуємо інтерфейси IDriver, IStorage для іньєкції залежностей.
    Returns:
        Graph об'єкт з результатами краулінгу
    """
    from graph_crawler.api.client.client import GraphCrawlerClient
    from graph_crawler.application.services.driver_factory import create_driver
    from graph_crawler.application.services.storage_factory import create_storage
    from graph_crawler.domain.events.event_bus import EventBus
    from graph_crawler.domain.events.events import EventType
    from graph_crawler.infrastructure.persistence.graph_repository import (
        GraphRepository,
    )

    actual_driver = None

    try:
        # Визначаємо початковий URL для конфігурації
        # Пріоритет: url > seed_urls[0] > base_graph.nodes[0].url
        base_url = url
        if base_url is None and seed_urls:
            base_url = seed_urls[0]
        elif base_url is None and base_graph:
            # Беремо перший URL з графу (streaming через iter_nodes)
            first_node = next(base_graph.iter_nodes(), None)
            if first_node:
                base_url = first_node.url

        if base_url is None:
            raise ValueError("Не вдалося визначити base URL для краулінгу")

        # Якщо передано allowed_domains напряму - використовуємо їх
        domains = allowed_domains

        # Якщо allowed_domains не передано, визначаємо за same_domain
        if domains is None and same_domain:
            from graph_crawler.domain.value_objects.domain_patterns import AllowedDomains
            from graph_crawler.shared.utils.url_utils import URLUtils

            domains = []

            # При множинних seed_urls - дозволяємо всі їх домени
            if seed_urls and len(seed_urls) > 1:
                for seed_url in seed_urls:
                    root_domain = URLUtils.get_root_domain(seed_url)
                    if root_domain and root_domain not in domains:
                        domains.append(root_domain)
                        logger.info("Added allowed domain from seed_urls: %s", root_domain)

            # При base_graph - витягуємо всі унікальні домени з графу (streaming)
            if base_graph and base_graph.nodes:
                for node in base_graph.iter_nodes():
                    root_domain = URLUtils.get_root_domain(node.url)
                    if root_domain and root_domain not in domains:
                        domains.append(root_domain)
                        logger.info("Added allowed domain from base_graph: %s", root_domain)

            # Якщо не знайдено жодного домену - стандартна поведінка
            if not domains:
                domains = [AllowedDomains.DOMAIN_WITH_SUB.value]

        if driver is not None:
            actual_driver = create_driver(driver, driver_config or {})
            logger.info("Created driver: %s", type(actual_driver).__name__)
        else:
            actual_driver = create_driver("http", {})

        if storage is not None:
            storage_instance = create_storage(storage, storage_config or {})
        else:
            storage_instance = create_storage("memory", {})

        event_bus = EventBus()
        repository = GraphRepository()

        if on_progress:
            event_bus.subscribe(EventType.PROGRESS_UPDATE, lambda e: on_progress(e.data))
        if on_node_scanned:
            event_bus.subscribe(EventType.NODE_SCANNED, lambda e: on_node_scanned(e.data))
        if on_error:
            event_bus.subscribe(EventType.ERROR_OCCURRED, lambda e: on_error(e.data))
        if on_completed:
            event_bus.subscribe(EventType.CRAWL_COMPLETED, lambda e: on_completed(e.data))

        client = GraphCrawlerClient(
            driver=actual_driver,
            storage=storage_instance,
            event_bus=event_bus,
            repository=repository,
        )

        # Timeout тепер обробляється всередині client.crawl() та spider через CrawlCoordinator
        # Це забезпечує коректну зупинку краулінгу без orphan browser tasks
        graph = await client.crawl(
            url=base_url,
            seed_urls=seed_urls,
            base_graph=base_graph,
            max_depth=max_depth,
            max_pages=max_pages,
            allowed_domains=domains,
            url_rules=url_rules,
            custom_node_class=node_class,
            custom_edge_class=edge_class,
            edge_strategy=edge_strategy,
            node_plugins=plugins,
            timeout=timeout,
            follow_links=follow_links,
            # LOW-MEMORY MODE
            low_memory_mode=low_memory_mode,
            evict_threshold=evict_threshold,
            eviction_storage_path=eviction_storage_path,
            # AI Agent Integration
            crawl_context=crawl_context,
            control_channel=control_channel,
        )

        logger.info(
            f"Crawl completed: {len(graph.nodes)} nodes, {sum(1 for _ in graph.iter_edges())} edges"
        )
        return graph

    finally:
        try:
            if actual_driver and hasattr(actual_driver, "close"):
                await actual_driver.close()
                logger.debug("Driver closed successfully")
        except Exception as e:
            logger.warning("Error shutting down resources: %s", e)


__all__ = ["async_crawl_impl"]
