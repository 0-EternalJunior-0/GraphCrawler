"""
GraphSpider - головний краулер з дотриманням Clean Architecture.

BREAKING CHANGE (Фаза 6): Тепер використовує DTO для ізоляції Domain Layer.

Responsibilities:
- Координація краулінгу через компоненти (DI)
- Управління життєвим циклом краулінгу
- Повернення GraphDTO (не Domain Graph!)

Features:
- Async-first design
- Domain entities використовуються ТІЛЬКИ внутрішньо (приватно)
- Публічний API через DTO (GraphDTO)
- Автоматична конвертація Domain → DTO через GraphMapper
"""

import logging
from typing import Optional

from graph_crawler.application.dto import GraphDTO, GraphSummaryDTO
from graph_crawler.application.dto.mappers import GraphMapper
from graph_crawler.application.use_cases.crawling.base_spider import (
    BaseSpider,
    CrawlerState,
)
from graph_crawler.application.use_cases.crawling.checkpoint import CheckpointManager
from graph_crawler.application.use_cases.crawling.crawl_coordinator import (
    CrawlCoordinator,
)
from graph_crawler.application.use_cases.crawling.filters.domain_filter import (
    DomainFilter,
)
from graph_crawler.application.use_cases.crawling.filters.path_filter import PathFilter
from graph_crawler.application.use_cases.crawling.incremental_strategy import (
    IncrementalCrawlStrategy,
)
from graph_crawler.application.use_cases.crawling.link_processor import LinkProcessor
from graph_crawler.application.use_cases.crawling.node_scanner import NodeScanner
from graph_crawler.application.use_cases.crawling.progress_tracker import (
    CrawlProgressTracker,
)
from graph_crawler.application.use_cases.crawling.scheduler import CrawlScheduler
from graph_crawler.application.use_cases.crawling.spider_lifecycle import (
    SpiderLifecycleManager,
)
from graph_crawler.domain.entities.graph import Graph
from graph_crawler.domain.entities.node import Node
from graph_crawler.domain.events import CrawlerEvent, EventBus, EventType
from graph_crawler.domain.value_objects.configs import CrawlerConfig
from graph_crawler.domain.value_objects.models import (
    DomainFilterConfig,
    PathFilterConfig,
)
from graph_crawler.infrastructure.persistence.base import BaseStorage
from graph_crawler.infrastructure.transport.base import BaseDriver
from graph_crawler.shared.utils.url_utils import URLUtils

logger = logging.getLogger(__name__)


class GraphSpider(BaseSpider):
    """
    GraphSpider з Clean Architecture - всі операції через DTO.

    BREAKING CHANGE (Фаза 6): Повний перехід на DTO для ізоляції Domain Layer.

    Архітектурні принципи:
    1. Domain entities (Graph, Node, Edge) - ТІЛЬКИ внутрішня реалізація (приватні поля)
    2. Публічний API - ТІЛЬКИ через DTO (GraphDTO, NodeDTO, EdgeDTO)
    3. Конвертація Domain ↔ DTO - через Mappers
    4. Dependency Injection - всі компоненти через конструктор

    Responsibilities:
    1. Ініціалізація компонентів через DI
    2. Координація краулінгу (делегування до CrawlCoordinator)
    3. Повернення результату як GraphDTO

    Example:
        >>> async with GraphSpider(config, driver, storage) as spider:
        ...     graph_dto = await spider.crawl()  # ✅ Повертає GraphDTO!
        ...     print(f"Found {graph_dto.stats.total_nodes} pages")
        ...
        ... # Якщо потрібен Domain Graph для внутрішньої логіки:
        ... graph = GraphMapper.to_domain(graph_dto, context={...})
    """

    def __init__(
        self,
        config: CrawlerConfig,
        driver: BaseDriver,
        storage: BaseStorage,
        event_bus: Optional[EventBus] = None,
        graph: Optional[Graph] = None,
        scheduler: Optional[CrawlScheduler] = None,
        domain_filter: Optional[DomainFilter] = None,
        path_filter: Optional[PathFilter] = None,
        scanner: Optional[NodeScanner] = None,
        processor: Optional[LinkProcessor] = None,
        plugin_manager=None,
        checkpoint_manager: Optional[CheckpointManager] = None,
    ):
        """
        Ініціалізує GraphSpider з усіма компонентами через DI.

        Args:
            config: Конфігурація краулінгу
            driver: Driver для HTTP запитів
            storage: Storage для збереження результатів
            event_bus: EventBus для публікації подій (опціонально)
            graph: Domain Graph (внутрішнє використання, опціонально)
            scheduler: CrawlScheduler (опціонально)
            domain_filter: Фільтр доменів (опціонально)
            path_filter: Фільтр шляхів (опціонально)
            scanner: NodeScanner (опціонально)
            processor: LinkProcessor (опціонально)
            plugin_manager: Plugin manager для нод (опціонально)
            checkpoint_manager: Checkpoint manager (опціонально)

        Note:
            Domain Graph використовується ТІЛЬКИ внутрішньо для краулінгу.
            Публічний API повертає GraphDTO через метод crawl().
        """
        super().__init__(config, driver, storage, event_bus)

        # DI: Graph (ПРИВАТНЕ поле - внутрішнє використання)
        # Domain entity НЕ виходить за межі Spider
        self._graph = graph if graph is not None else Graph()

        # DI: Scheduler
        self._scheduler = (
            scheduler
            if scheduler is not None
            else CrawlScheduler(url_rules=config.url_rules, event_bus=self.event_bus)
        )

        # DI: Domain filter
        if domain_filter is None:
            # Використовуємо get_root_domain() для коректної роботи з субдоменами
            # www.ciklum.com -> ciklum.com, тоді jobs.ciklum.com буде субдоменом
            base_domain = URLUtils.get_root_domain(self.config.url)
            domain_config = DomainFilterConfig(
                base_domain=base_domain,
                allowed_domains=self.config.allowed_domains,
                blocked_domains=[],
            )
            self.domain_filter = DomainFilter(domain_config, self.event_bus)
        else:
            self.domain_filter = domain_filter

        # DI: Path filter
        if path_filter is None:
            excluded_patterns = list(self.config.excluded_paths)
            included_patterns = list(self.config.included_paths)
            for rule in self.config.url_rules:
                if rule.should_scan is False:
                    excluded_patterns.append(rule.pattern)
            path_config = PathFilterConfig(
                excluded_patterns=excluded_patterns, included_patterns=included_patterns
            )
            self.path_filter = PathFilter(path_config, self.event_bus)
        else:
            self.path_filter = path_filter

        # DI: Plugin Manager
        if plugin_manager is None:
            from graph_crawler.extensions.plugins.node import (
                NodePluginManager,
                get_default_node_plugins,
            )

            self.node_plugin_manager = NodePluginManager(event_bus=self.event_bus)
            for plugin in get_default_node_plugins():
                self.node_plugin_manager.register(plugin)
        else:
            self.node_plugin_manager = plugin_manager

        # Custom plugins
        node_plugins = None
        if isinstance(config, dict):
            node_plugins = config.get("node_plugins")
        elif hasattr(config, "node_plugins"):
            node_plugins = config.node_plugins

        if node_plugins:
            for plugin in node_plugins:
                self.node_plugin_manager.register(plugin)

        # DI: Scanner
        self.scanner = (
            scanner if scanner is not None else NodeScanner(driver=self.driver)
        )

        # DI: Processor
        if processor is None:
            self._processor = LinkProcessor(
                graph=self._graph,
                scheduler=self._scheduler,
                domain_filter=self.domain_filter,
                path_filter=self.path_filter,
                url_rules=self.config.url_rules,
                custom_node_class=self.config.custom_node_class,
                plugin_manager=self.node_plugin_manager,
                edge_strategy=self.config.edge_strategy,
                max_in_degree_threshold=self.config.max_in_degree_threshold,
            )
        else:
            self._processor = processor

        # DI: Checkpoint Manager
        self.checkpoint_manager = checkpoint_manager

        # Компоненти SRP - ініціалізуються в crawl()
        # ПРИВАТНІ поля - внутрішня реалізація
        self._lifecycle_manager: Optional[SpiderLifecycleManager] = None
        self._incremental_strategy: Optional[IncrementalCrawlStrategy] = None
        self._progress_tracker: Optional[CrawlProgressTracker] = None
        self._coordinator: Optional[CrawlCoordinator] = None

        logger.info("GraphSpider initialized (DTO-based, Clean Architecture)")

    def _init_components(self, base_graph: Optional[Graph]) -> None:
        """
        Ініціалізує внутрішні компоненти для краулінгу.

        Args:
            base_graph: Базовий граф для incremental краулінгу (Domain entity)

        Note:
            Всі компоненти працюють з Domain entities внутрішньо.
            Тільки публічний API Spider повертає DTO.
        """
        # Lifecycle Manager
        self._lifecycle_manager = SpiderLifecycleManager(
            config=self.config,
            plugin_manager=self.node_plugin_manager,
            graph=self._graph,
        )

        # Incremental Strategy
        self._incremental_strategy = IncrementalCrawlStrategy(
            config=self.config,
            base_graph=base_graph,
            event_bus=self.event_bus,
        )

        # Progress Tracker
        self._progress_tracker = CrawlProgressTracker(
            config=self.config,
            scheduler=self._scheduler,
            event_bus=self.event_bus,
        )

        # Coordinator
        self._coordinator = CrawlCoordinator(
            config=self.config,
            driver=self.driver,
            graph=self._graph,
            scheduler=self._scheduler,
            scanner=self.scanner,
            processor=self._processor,
            progress_tracker=self._progress_tracker,
            incremental_strategy=self._incremental_strategy,
            checkpoint_manager=self.checkpoint_manager,
        )

    async def crawl(self, base_graph_dto: Optional[GraphDTO] = None) -> GraphDTO:
        """
        Async запускає процес краулінгу через DTO (Clean Architecture).

        BREAKING CHANGE (Фаза 6): Тепер приймає та повертає GraphDTO замість Graph.

        Внутрішній процес:
        1. Конвертація GraphDTO → Domain Graph (якщо передано base_graph_dto)
        2. Виконання краулінгу з Domain entities (внутрішня логіка)
        3. Конвертація Domain Graph → GraphDTO (повернення результату)

        Args:
            base_graph_dto: Базовий GraphDTO для incremental краулінгу (опціонально)

        Returns:
            GraphDTO з результатами краулінгу

        Raises:
            Exception: При помилках краулінгу

        Example:
            >>> async with GraphSpider(config, driver, storage) as spider:
            ...     # Incremental crawl з базовим графом
            ...     base_dto = await storage.load_graph()
            ...     result_dto = await spider.crawl(base_graph_dto=base_dto)
            ...     print(f"Crawled {result_dto.stats.total_nodes} pages")
        """
        # Встановлюємо стан RUNNING
        self._state = CrawlerState.RUNNING

        # Конвертуємо GraphDTO → Domain Graph якщо передано (для incremental crawl)
        base_graph = None
        if base_graph_dto is not None:
            logger.debug("Converting base GraphDTO to Domain Graph for incremental crawl")
            # Використовуємо context з plugin_manager для правильного відновлення залежностей
            context = {
                'plugin_manager': self.node_plugin_manager,
                'tree_parser': None,  # Tree parser буде доданий під час сканування
            }
            base_graph = GraphMapper.to_domain(base_graph_dto, context=context)

        # Ініціалізуємо компоненти
        self._init_components(base_graph)

        # Подія початку краулінгу
        self.event_bus.publish(
            CrawlerEvent.create(
                EventType.CRAWL_STARTED,
                data={
                    "url": self.config.url,
                    "max_pages": self.config.max_pages,
                    "max_depth": self.config.max_depth,
                },
            )
        )

        logger.info(f"Starting async crawl: {self.config.url}")
        logger.info(
            f"Config: max_depth={self.config.max_depth}, "
            f"max_pages={self.config.max_pages}"
        )

        try:
            # ДЕЛЕГУВАННЯ: Lifecycle Manager виконує BEFORE_CRAWL hooks
            self._lifecycle_manager.execute_before_crawl()

            # Створюємо початковий вузол (Domain entity - внутрішнє використання)
            node_class = self.config.custom_node_class or Node
            root_node = node_class(
                url=self.config.url, depth=0, plugin_manager=self.node_plugin_manager
            )
            self._graph.add_node(root_node)
            self._scheduler.add_node(root_node)

            # ASYNC ДЕЛЕГУВАННЯ: Coordinator координує весь процес краулінгу
            # Повертає Domain Graph (внутрішня логіка)
            result_graph = await self._coordinator.coordinate(spider=self)

            # ✅ КОНВЕРТАЦІЯ: Domain Graph → GraphDTO для повернення
            logger.debug("Converting Domain Graph to GraphDTO for return")
            result_dto = GraphMapper.to_dto(result_graph)

            logger.info(
                f"Crawl completed: {result_dto.stats.total_nodes} nodes, "
                f"{result_dto.stats.total_edges} edges"
            )

            return result_dto

        except Exception as e:
            self._state = CrawlerState.ERROR
            logger.error(f"Crawl error: {e}", exc_info=True)

            self.event_bus.publish(
                CrawlerEvent.create(
                    EventType.ERROR_OCCURRED,
                    data={"error": str(e), "error_type": type(e).__name__},
                )
            )
            raise

        finally:
            # ДЕЛЕГУВАННЯ: Lifecycle Manager виконує AFTER_CRAWL hooks
            pages_crawled = self._progress_tracker.get_pages_crawled()
            self._lifecycle_manager.execute_after_crawl(pages_crawled)

            # ДЕЛЕГУВАННЯ: Progress Tracker публікує завершення
            self._progress_tracker.publish_crawl_completed()

            # Встановлюємо стан IDLE (якщо не ERROR/STOPPED)
            if self._state not in [CrawlerState.ERROR, CrawlerState.STOPPED]:
                self._state = CrawlerState.IDLE

    def get_stats(self) -> dict:
        """
        Повертає статистику краулінгу як словник (backward compatibility).

        Реалізація абстрактного методу з BaseSpider.

        Returns:
            dict з статистикою краулінгу

        Example:
            >>> stats = spider.get_stats()
            >>> print(f"Total nodes: {stats['total_nodes']}")
        """
        return self._graph.get_stats()

    def get_stats_dto(self) -> GraphSummaryDTO:
        """
        Повертає статистику краулінгу через DTO.

        BREAKING CHANGE (Фаза 6): Тепер повертає GraphSummaryDTO замість dict.

        Returns:
            GraphSummaryDTO з статистикою краулінгу

        Example:
            >>> summary = spider.get_stats_dto()
            >>> print(f"Total nodes: {summary.total_nodes}")
            >>> print(f"Completed: {summary.crawl_completed}")
        """
        # Отримуємо статистику з Domain Graph
        domain_stats = self._graph.get_stats()

        # Визначаємо чи краулінг завершено
        crawl_completed = self._state == CrawlerState.IDLE

        # Створюємо GraphSummaryDTO
        return GraphSummaryDTO(
            total_nodes=domain_stats.get("total_nodes", 0),
            total_edges=domain_stats.get("total_edges", 0),
            root_url=self.config.url,
            crawl_completed=crawl_completed,
        )

    async def restore_from_checkpoint(
        self, checkpoint_path: Optional[str] = None
    ) -> bool:
        """
        Async відновлює стан краулінгу з checkpoint.

        Note:
            Checkpoint manager працює з Domain entities внутрішньо.
            Публічний API Spider залишається через DTO.

        Args:
            checkpoint_path: Шлях до checkpoint файлу (опціонально)

        Returns:
            True якщо відновлення успішне, False інакше

        Example:
            >>> await spider.restore_from_checkpoint()
            >>> graph_dto = await spider.crawl()  # Продовжує з checkpoint
        """
        if not self.checkpoint_manager:
            logger.warning("Checkpoint manager not available")
            return False

        try:
            if checkpoint_path:
                checkpoint_data = self.checkpoint_manager.load_checkpoint(
                    checkpoint_path
                )
            else:
                checkpoint_data = self.checkpoint_manager.load_latest_checkpoint()

            if not checkpoint_data:
                logger.warning("No checkpoint found to restore")
                return False

            # Відновлюємо Domain entities з checkpoint
            restored_graph, queue_urls, seen_urls = (
                self.checkpoint_manager.restore_from_checkpoint(checkpoint_data)
            )

            # Оновлюємо внутрішній стан (Domain entities)
            self._graph = restored_graph
            self._scheduler.seen_urls = seen_urls
            self._scheduler.queue = []
            self._scheduler.counter = 0

            # Відновлюємо чергу
            for url in queue_urls:
                node = self._graph.get_node_by_url(url)
                if node:
                    self._scheduler.add_node(node)

            logger.info(
                f"Restored from checkpoint: "
                f"{len(restored_graph.nodes)} nodes, "
                f"{len(queue_urls)} URLs in queue"
            )

            return True

        except Exception as e:
            logger.error(f"Failed to restore from checkpoint: {e}", exc_info=True)
            return False

    # ═══════════════════════════════════════════════════════════════════
    # Публічні властивості для сумісності з внутрішніми компонентами
    # ═══════════════════════════════════════════════════════════════════

    @property
    def graph(self) -> Graph:
        """
        Доступ до внутрішнього Domain Graph.

        УВАГА: Використовувати ТІЛЬКИ для внутрішніх компонентів (Coordinator, тощо).
        Публічний API повинен працювати з GraphDTO через crawl().

        Returns:
            Domain Graph (внутрішня реалізація)
        """
        return self._graph

    @property
    def scheduler(self) -> CrawlScheduler:
        """
        Доступ до внутрішнього Scheduler.

        Returns:
            CrawlScheduler (внутрішня реалізація)
        """
        return self._scheduler

    @property
    def processor(self) -> LinkProcessor:
        """
        Доступ до внутрішнього LinkProcessor.

        Returns:
            LinkProcessor (внутрішня реалізація)
        """
        return self._processor

    @property
    def progress_tracker(self) -> Optional[CrawlProgressTracker]:
        """
        Доступ до внутрішнього Progress Tracker.

        Returns:
            CrawlProgressTracker або None
        """
        return self._progress_tracker

    @property
    def lifecycle_manager(self) -> Optional[SpiderLifecycleManager]:
        """
        Доступ до внутрішнього Lifecycle Manager.

        Returns:
            SpiderLifecycleManager або None
        """
        return self._lifecycle_manager

    @property
    def coordinator(self) -> Optional[CrawlCoordinator]:
        """
        Доступ до внутрішнього Coordinator.

        Returns:
            CrawlCoordinator або None
        """
        return self._coordinator

    # ═══════════════════════════════════════════════════════════════════
    # Lifecycle Methods
    # ═══════════════════════════════════════════════════════════════════

    async def close(self) -> None:
        """
        Async закриває всі ресурси Spider.

        Example:
            >>> async with GraphSpider(config, driver, storage) as spider:
            ...     graph_dto = await spider.crawl()
            ... # Автоматично викликається close() через context manager
        """
        await self.driver.close()
        logger.info("GraphSpider closed")
