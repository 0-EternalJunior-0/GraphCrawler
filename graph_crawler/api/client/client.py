"""Високорівневий Async-First API для роботи з GraphCrawler .
- crawl() тепер async
- close() тепер async
- Async context manager
"""

import asyncio
import logging
from typing import Any, List, Optional

from graph_crawler.application.use_cases.crawling.filters.domain_patterns import (
    AllowedDomains,
)
from graph_crawler.domain.entities.edge import Edge
from graph_crawler.domain.entities.graph import Graph
from graph_crawler.domain.entities.node import Node
from graph_crawler.domain.interfaces.driver import IDriver
from graph_crawler.domain.interfaces.event_bus import IEventBus
from graph_crawler.domain.interfaces.spider import ISpider
from graph_crawler.domain.interfaces.storage import IStorage
from graph_crawler.domain.value_objects.configs import CrawlerConfig
from graph_crawler.domain.value_objects.models import GraphMetadata, GraphStats, URLRule
from graph_crawler.infrastructure.persistence.graph_repository import GraphRepository

logger = logging.getLogger(__name__)


class GraphCrawlerClient:
    """
    Async-First високорівневий API для GraphCrawler . Всі операції тепер async.

    Приклад:
        >>> async with GraphCrawlerClient.create() as client:
        ...     graph = await client.crawl("https://example.com")
        ...     print(f"Found {len(graph.nodes)} pages")
    """

    @classmethod
    async def create(cls, **kwargs) -> "GraphCrawlerClient":
        """
        Async factory метод через ApplicationContainer.
        """
        from graph_crawler.application.services.application_container import (
            ApplicationContainer,
        )

        container = ApplicationContainer()
        return container.client()

    def __init__(
        self,
        driver: IDriver,
        storage: IStorage,
        event_bus: IEventBus,
        repository: GraphRepository,
        logger_instance: Optional[logging.Logger] = None,
    ):
        """
        Ініціалізація клієнта через Dependency Injection.
        """
        self.driver = driver
        self.storage = storage
        self.event_bus = event_bus
        self.repository = repository
        self.logger = logger_instance or logger

        self._last_graph: Optional[Graph] = None
        self._graph: Optional[Graph] = None
        self.listeners = []
        self._closed = False

        if not self.logger.handlers:
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            )

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
        return False

    def add_listener(self, listener) -> None:
        """Додати event listener."""
        self.listeners.append(listener)
        event_methods = [
            "on_crawl_started",
            "on_node_scanned",
            "on_progress_update",
            "on_crawl_completed",
            "on_error_occurred",
        ]
        for method_name in event_methods:
            if hasattr(listener, method_name) and callable(
                getattr(listener, method_name)
            ):
                event_type = method_name[3:]
                self.event_bus.subscribe(event_type, getattr(listener, method_name))

    async def crawl(
        self,
        url: str,
        max_depth: int = 3,
        max_pages: Optional[int] = 100,
        allowed_domains: Optional[List[str]] = None,
        url_rules: Optional[list[URLRule]] = None,
        custom_node_class: Optional[type[Node]] = None,
        custom_edge_class: Optional[type[Edge]] = None,
        timeout: Optional[int] = None,
        edge_strategy: str = "all",
        max_in_degree_threshold: int = 100,
        node_plugins: Optional[List[Any]] = None,
    ) -> Graph:
        """
        Async запускає краулінг веб-сайту.

        Args:
            url: Початковий URL
            max_depth: Максимальна глибина
            max_pages: Максимальна кількість сторінок
            allowed_domains: Дозволені домени
            url_rules: Правила URL
            custom_node_class: Кастомний клас Node
            timeout: Максимальний час краулінгу
            node_plugins: Список плагінів

        Returns:
            Побудований граф
        """
        if self._closed:
            raise RuntimeError("Client is closed. Create a new instance.")

        self.logger.info(f"Starting async crawl: {url}")

        domains = (
            allowed_domains
            if allowed_domains is not None
            else [AllowedDomains.DOMAIN_WITH_SUB.value]
        )

        config = CrawlerConfig(
            url=url,
            max_depth=max_depth,
            max_pages=max_pages,
            allowed_domains=domains,
            url_rules=url_rules or [],
            custom_node_class=custom_node_class,
            custom_edge_class=custom_edge_class,
            edge_strategy=edge_strategy,
            max_in_degree_threshold=max_in_degree_threshold,
            node_plugins=node_plugins,
        )

        # Публікуємо подію початку
        from graph_crawler.domain.events.events import CrawlerEvent, EventType

        self.event_bus.publish(
            CrawlerEvent.create(
                event_type=EventType.CRAWL_STARTED,
                data={"url": url, "max_depth": max_depth, "max_pages": max_pages},
            )
        )

        try:
            # Створюємо async spider
            spider = self._create_spider(config)

            # Spider повертає GraphDTO (Clean Architecture)
            if timeout:
                graph_dto = await asyncio.wait_for(spider.crawl(), timeout=timeout)
            else:
                graph_dto = await spider.crawl()

            # Конвертуємо GraphDTO → Domain Graph для backward compatibility публічного API
            from graph_crawler.application.dto.mappers import GraphMapper
            
            context = {
                'plugin_manager': spider.node_plugin_manager,
                'node_class': custom_node_class,
                'edge_class': custom_edge_class,
            }
            graph = GraphMapper.to_domain(graph_dto, context=context)

            self._last_graph = graph

            self.event_bus.publish(
                CrawlerEvent.create(
                    event_type=EventType.CRAWL_COMPLETED,
                    data={"total_pages": len(graph.nodes), "stats": graph.get_stats()},
                )
            )

            self.logger.info(f"Crawl completed: {len(graph.nodes)} nodes")
            return graph

        except asyncio.TimeoutError:
            self.logger.error(f"Crawl timeout after {timeout} seconds")
            self.event_bus.publish(
                CrawlerEvent.create(
                    event_type=EventType.ERROR_OCCURRED,
                    data={
                        "error": f"Timeout after {timeout}s",
                        "error_type": "TimeoutError",
                    },
                )
            )
            raise
        except Exception as e:
            self.logger.error(f"Crawl failed: {e}")
            self.event_bus.publish(
                CrawlerEvent.create(
                    event_type=EventType.ERROR_OCCURRED,
                    data={"error": str(e), "error_type": type(e).__name__},
                )
            )
            raise

    async def save_graph(
        self,
        graph: Optional[Graph] = None,
        name: str = "graph",
        description: str = "",
    ) -> str:
        """
        Async зберігає граф.
        """
        graph_to_save = graph or self._last_graph
        if not graph_to_save:
            raise ValueError("No graph to save. Run crawl() first.")

        graph_id = await self.storage.save_graph(
            graph=graph_to_save, name=name, description=description
        )

        self.logger.info(f"Graph saved: {graph_id}")
        return graph_id

    async def load_graph(self, name: str) -> Optional[Graph]:
        """
        Async завантажує граф.
        """
        graph = await self.storage.load_graph(name)
        if graph:
            self._last_graph = graph
            self.logger.info(f"Graph loaded: {name}")
        return graph

    def get_stats(self, graph: Optional[Graph] = None) -> GraphStats:
        """Отримує статистику графа (sync - in-memory)."""
        graph_to_check = graph or self._last_graph
        if not graph_to_check:
            raise ValueError("No graph available. Run crawl() first.")
        return graph_to_check.get_stats()

    def _create_spider(self, config: CrawlerConfig) -> "ISpider":
        """
        Створює async Spider.
        """
        from graph_crawler.application.use_cases.crawling.spider import GraphSpider

        spider = GraphSpider(
            config=config,
            driver=self.driver,
            storage=self.storage,
            event_bus=self.event_bus,
        )

        self._graph = spider.graph
        self.logger.debug(f"Spider created: {type(spider).__name__}")
        return spider

    async def close(self) -> None:
        """
        Async закриває всі ресурси.
        """
        if self._closed:
            self.logger.debug("Client already closed")
            return

        self.logger.info("Closing client resources...")

        try:
            # Async закриваємо driver
            if self.driver:
                await self.driver.close()
                self.logger.debug("Driver closed")

            # Async закриваємо storage
            if self.storage and hasattr(self.storage, "close"):
                await self.storage.close()
                self.logger.debug("Storage closed")

            self.listeners.clear()
            self._last_graph = None
            self._closed = True

            self.logger.info("Client closed successfully")

        except Exception as e:
            self.logger.error(f"Error during client cleanup: {e}")
            self._closed = True
            raise

    @property
    def is_closed(self) -> bool:
        """Перевіряє чи закритий клієнт."""
        return self._closed
