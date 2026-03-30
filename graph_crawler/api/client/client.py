"""Високорівневий Async-First API для роботи з GraphCrawler .
- crawl() тепер async
- close() тепер async
- Async context manager
"""

import asyncio
import logging
from typing import TYPE_CHECKING, Any, List, Optional

from graph_crawler.domain.entities.edge import Edge
from graph_crawler.domain.entities.graph import Graph
from graph_crawler.domain.entities.node import Node
from graph_crawler.domain.interfaces.driver import IDriver
from graph_crawler.domain.interfaces.storage import IStorage
from graph_crawler.domain.value_objects.configs import CrawlerConfig
from graph_crawler.domain.value_objects.domain_patterns import AllowedDomains
from graph_crawler.domain.value_objects.models import Rule
from graph_crawler.infrastructure.persistence.graph_repository import GraphRepository

if TYPE_CHECKING:
    from graph_crawler.domain.events.event_bus import EventBus

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
        Async factory метод для створення клієнта.
        """
        from graph_crawler.application.services import create_driver, create_storage
        from graph_crawler.domain.events import EventBus
        from graph_crawler.infrastructure.persistence.graph_repository import GraphRepository

        driver = create_driver(kwargs.get("driver", "async"), kwargs.get("driver_config"))
        storage = create_storage(kwargs.get("storage", "memory"), kwargs.get("storage_config"))
        event_bus = EventBus()
        repository = GraphRepository()  # Використовуємо default директорію

        return cls(
            driver=driver,
            storage=storage,
            event_bus=event_bus,
            repository=repository,
        )

    def __init__(
        self,
        driver: IDriver,
        storage: IStorage,
        event_bus: "EventBus",
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
        from graph_crawler.domain.events.events import EventType

        self.listeners.append(listener)
        # Маппінг методів на EventType
        event_method_map = {
            "on_crawl_started": EventType.CRAWL_STARTED,
            "on_node_scanned": EventType.NODE_SCANNED,
            "on_progress_update": EventType.PROGRESS_UPDATE,
            "on_crawl_completed": EventType.CRAWL_COMPLETED,
            "on_error_occurred": EventType.ERROR_OCCURRED,
        }
        for method_name, event_type in event_method_map.items():
            if hasattr(listener, method_name) and callable(getattr(listener, method_name)):
                self.event_bus.subscribe(event_type, getattr(listener, method_name))

    async def crawl(
        self,
        url: str,
        max_depth: int = 3,
        max_pages: Optional[int] = 100,
        allowed_domains: Optional[List[str]] = None,
        url_rules: Optional[list[Rule]] = None,
        custom_node_class: Optional[type[Node]] = None,
        custom_edge_class: Optional[type[Edge]] = None,
        timeout: Optional[int] = None,
        edge_strategy: str = "all",
        max_in_degree_threshold: int = 100,
        node_plugins: Optional[List[Any]] = None,
        seed_urls: Optional[list[str]] = None,
        base_graph: Optional[Graph] = None,
        follow_links: bool = True,
        # LOW-MEMORY MODE
        low_memory_mode: bool = False,
        evict_threshold: int = 500,
        eviction_storage_path: Optional[str] = None,
        # AI Agent Integration
        crawl_context: Optional[Any] = None,
        control_channel: Optional[Any] = None,
    ) -> Graph:
        """
        Async запускає краулінг веб-сайту з підтримкою множинних seed URLs та incremental crawling.

        Returns:
            Побудований граф
        """
        if self._closed:
            raise RuntimeError("Client is closed. Create a new instance.")

        self.logger.info("Starting async crawl: %s", url)
        if seed_urls:
            self.logger.info("Seed URLs: %s URLs", len(seed_urls))
        if base_graph:
            self.logger.info("Base graph: %s nodes", len(base_graph.nodes))
        if not follow_links:
            self.logger.info("follow_links=False: will scan only specified URLs, no link following")
        if low_memory_mode:
            self.logger.info("LOW-MEMORY MODE: evict_threshold=%s", evict_threshold)

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
            follow_links=follow_links,
            # LOW-MEMORY MODE
            low_memory_mode=low_memory_mode,
            evict_threshold=evict_threshold,
            eviction_storage_path=eviction_storage_path,
        )

        # Публікуємо подію початку
        from graph_crawler.domain.events.events import CrawlerEvent, EventType

        self.event_bus.publish(
            CrawlerEvent.create(
                event_type=EventType.CRAWL_STARTED,
                data={
                    "url": url,
                    "max_depth": max_depth,
                    "max_pages": max_pages,
                    "seed_urls_count": len(seed_urls) if seed_urls else 0,
                    "base_graph_nodes": len(base_graph.nodes) if base_graph else 0,
                    "low_memory_mode": low_memory_mode,
                },
            )
        )

        try:
            # Створюємо async spider з AI Agent Integration
            spider = self._create_spider(
                config,
                crawl_context=crawl_context,
                control_channel=control_channel,
            )

            # Конвертуємо base_graph → GraphDTO якщо передано
            base_graph_dto = None
            if base_graph:
                from graph_crawler.application.dto.mappers import GraphMapper

                base_graph_dto = GraphMapper.to_dto(base_graph)
                self.logger.info("Converted base graph to DTO: %s nodes", len(base_graph.nodes))

            # Spider тепер сам обробляє timeout через Coordinator
            # Це забезпечує коректну зупинку краулінгу без orphan tasks
            graph_dto = await spider.crawl(
                base_graph_dto=base_graph_dto, seed_urls=seed_urls, timeout=timeout
            )

            # Конвертуємо GraphDTO → Domain Graph для backward compatibility публічного API
            from graph_crawler.application.dto.mappers import GraphMapper

            context = {
                "plugin_manager": spider.node_plugin_manager,
                "node_class": custom_node_class,
                "edge_class": custom_edge_class,
            }
            graph = GraphMapper.to_domain(graph_dto, context=context)

            self._last_graph = graph

            # Подія CRAWL_COMPLETED вже публікується в spider.py через progress_tracker
            # Тут тільки логуємо
            self.logger.info("Crawl completed: %s nodes", len(graph.nodes))
            return graph

        except asyncio.TimeoutError:
            self.logger.error("Crawl timeout after %s seconds", timeout)
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
            self.logger.error("Crawl failed: %s", e)
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

        # IStorage.save_graph приймає тільки graph
        result = await self.storage.save_graph(graph_to_save)

        self.logger.info("Graph saved: %s", name)
        return name if result else ""

    async def load_graph(self, name: str) -> Optional[Graph]:
        """
        Async завантажує граф.
        """
        result = await self.storage.load_graph()
        if result:
            # result може бути Graph або GraphDTO залежно від storage
            if isinstance(result, Graph):
                self._last_graph = result
            else:
                # Якщо це не Graph - конвертуємо
                from graph_crawler.application.dto.mappers import GraphMapper

                self._last_graph = GraphMapper.to_domain(result)
            self.logger.info("Graph loaded: %s", name)
        return self._last_graph

    def get_stats(self, graph: Optional[Graph] = None) -> dict[str, int]:
        """Отримує статистику графа (sync - in-memory)."""
        graph_to_check = graph or self._last_graph
        if not graph_to_check:
            raise ValueError("No graph available. Run crawl() first.")
        return graph_to_check.get_stats()

    def _create_spider(
        self,
        config: CrawlerConfig,
        crawl_context: Optional[Any] = None,
        control_channel: Optional[Any] = None,
    ) -> Any:
        """
        Створює async Spider з підтримкою AI Agent Integration.
        """
        from graph_crawler.application.use_cases.crawling.spider import GraphSpider

        spider = GraphSpider(
            config=config,
            driver=self.driver,
            storage=self.storage,
            event_bus=self.event_bus,
            crawl_context=crawl_context,
            control_channel=control_channel,
        )

        self._graph = spider.graph
        self.logger.debug("Spider created: %s", type(spider).__name__)
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
            self.logger.error("Error during client cleanup: %s", e)
            self._closed = True
            raise

    @property
    def is_closed(self) -> bool:
        """Перевіряє чи закритий клієнт."""
        return self._closed
