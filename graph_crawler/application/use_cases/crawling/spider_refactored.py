"""
GraphSpider (Refactored) - головний краулер з дотриманням SRP.

Розділено відповідальності на окремі класи:
- SpiderLifecycleManager - lifecycle hooks
- IncrementalCrawlStrategy - incremental crawling
- CrawlProgressTracker - progress tracking та метрики
- CrawlCoordinator - координація краулінгу
- GraphSpider - ТІЛЬКИ ініціалізація та координація компонентів

Було: 622 рядки, 15+ відповідальностей
Стало: ~150 рядків, 3 відповідальності (ініціалізація, координація, DI)
"""

import logging
import time
from typing import Optional

from graph_crawler.application.use_cases.crawling.base_spider import BaseSpider
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

# Нові компоненти (SRP refactoring)
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


class GraphSpiderRefactored(BaseSpider):
    """
    Рефакторений GraphSpider з дотриманням SRP (Single Responsibility Principle).

    Responsibilities (ТІЛЬКИ 3):
    1. Ініціалізація компонентів (filters, scanner, processor, plugins)
    2. Координація компонентів через Dependency Injection
    3. Управління на високому рівні (crawl method)

    Делегування відповідальностей:
    - SpiderLifecycleManager → lifecycle hooks (BEFORE_CRAWL, AFTER_CRAWL)
    - IncrementalCrawlStrategy → incremental crawling логіка
    - CrawlProgressTracker → progress tracking, metrics, events
    - CrawlCoordinator → координація sequential/batch mode

    ПЕРЕВАГИ рефакторингу:
    - Кожен клас має одну відповідальність (SRP)
    - Легко тестувати кожен компонент окремо
    - Зменшено розмір класу з 622 до ~150 рядків
    - Покращена підтримуваність та читабельність
    - Легше розширювати (нові стратегії, координатори)
    """

    def __init__(
        self,
        config: CrawlerConfig,
        driver: BaseDriver,
        storage: BaseStorage,
        event_bus: Optional[EventBus] = None,
        domain_filter: Optional[DomainFilter] = None,
        path_filter: Optional[PathFilter] = None,
    ):
        """
        Ініціалізує GraphSpider з усіма компонентами.

        Args:
            config: Конфігурація краулера
            driver: Driver для завантаження сторінок
            storage: Storage для збереження графу
            event_bus: Event bus для подій (optional)
            domain_filter: Domain filter (optional, створюється автоматично)
            path_filter: Path filter (optional, створюється автоматично)
        """
        super().__init__(config, driver, storage, event_bus)

        # Граф та scheduler
        self.graph = Graph()
        self.scheduler = CrawlScheduler(
            url_rules=config.url_rules, event_bus=self.event_bus
        )

        # Ініціалізуємо фільтри
        if domain_filter is None or path_filter is None:
            self._init_filters()
            if domain_filter is not None:
                self.domain_filter = domain_filter
            if path_filter is not None:
                self.path_filter = path_filter
        else:
            self.domain_filter = domain_filter
            self.path_filter = path_filter
            logger.info(
                f"Filters injected: domain={type(domain_filter).__name__}, "
                f"path={type(path_filter).__name__}"
            )

        # Ініціалізуємо Node Plugin Manager
        self._init_node_plugins()

        # CORE КОМПОНЕНТИ: Scanner та Processor
        self.scanner = NodeScanner(driver=self.driver)
        self.processor = LinkProcessor(
            graph=self.graph,
            scheduler=self.scheduler,
            domain_filter=self.domain_filter,
            path_filter=self.path_filter,
            custom_node_class=self.config.custom_node_class,
            plugin_manager=self.node_plugin_manager,
        )

        # НОВІ КОМПОНЕНТИ (SRP Refactoring) - ініціалізуємо пізніше в crawl()
        # бо залежать від base_graph
        self.lifecycle_manager: Optional[SpiderLifecycleManager] = None
        self.incremental_strategy: Optional[IncrementalCrawlStrategy] = None
        self.progress_tracker: Optional[CrawlProgressTracker] = None
        self.coordinator: Optional[CrawlCoordinator] = None

    def _init_filters(self):
        """Ініціалізує фільтри для URL."""
        # Path filter - конвертуємо url_rules в патерни
        excluded_patterns = list(self.config.excluded_paths)
        included_patterns = list(self.config.included_paths)

        # Додаємо патерни з url_rules
        # URLRule використовує should_scan замість action
        # ВАЖЛИВО: Тільки should_scan=False додається в excluded_patterns!
        # should_scan=True НЕ додається в included_patterns, бо це перебиває
        # всі інші URL через логіку PathFilter (дозволяє ТІЛЬКИ included)
        for rule in self.config.url_rules:
            # should_scan=False означає exclude - додаємо в excluded_patterns
            if rule.should_scan is False:
                excluded_patterns.append(rule.pattern)
            # should_scan=True обробляється в LinkProcessor, НЕ в PathFilter!

        # Створюємо фільтри
        base_domain = URLUtils.get_domain(self.config.url)

        domain_config = DomainFilterConfig(
            base_domain=base_domain,
            allowed_domains=self.config.allowed_domains,
            blocked_domains=[],
        )
        self.domain_filter = DomainFilter(domain_config, self.event_bus)

        path_config = PathFilterConfig(
            excluded_patterns=excluded_patterns, included_patterns=included_patterns
        )
        self.path_filter = PathFilter(path_config, self.event_bus)

        logger.info(f"Filters initialized: base_domain={base_domain}")
        if self.config.has_url_rules():
            logger.info(f"URL rules active: {self.config.get_url_rules_count()} rules")

    def _init_node_plugins(self):
        """Ініціалізує Node Plugin Manager."""
        from graph_crawler.extensions.plugins.node import (
            NodePluginManager,
            get_default_node_plugins,
        )

        self.node_plugin_manager = NodePluginManager(event_bus=self.event_bus)

        if self.config.node_plugins is not None:
            plugins = self.config.node_plugins
            logger.info(f"Using custom node plugins: {len(plugins)} plugins")
        else:
            plugins = get_default_node_plugins()
            logger.info(f"Using default node plugins: {len(plugins)} plugins")

        for plugin in plugins:
            if plugin.enabled:
                self.node_plugin_manager.register(plugin)
                logger.debug(
                    f"Registered plugin: {plugin.name} "
                    f"(type={plugin.plugin_type.value})"
                )

        logger.info(f"Node plugins initialized: {self.node_plugin_manager}")

    def _init_components(self, base_graph: Optional[Graph]) -> None:
        """
        Ініціалізує компоненти для краулінгу.

        SRP: Кожен компонент має одну відповідальність

        Args:
            base_graph: Базовий граф для incremental mode
        """
        # Lifecycle Manager - управління hooks
        self.lifecycle_manager = SpiderLifecycleManager(
            config=self.config,
            plugin_manager=self.node_plugin_manager,
            graph=self.graph,
        )

        # Incremental Strategy - детекція змін
        self.incremental_strategy = IncrementalCrawlStrategy(
            config=self.config,
            base_graph=base_graph,
            event_bus=self.event_bus,
        )

        # Progress Tracker - метрики та події
        self.progress_tracker = CrawlProgressTracker(
            config=self.config,
            scheduler=self.scheduler,
            event_bus=self.event_bus,
        )

        # Coordinator - координація краулінгу
        self.coordinator = CrawlCoordinator(
            config=self.config,
            driver=self.driver,
            graph=self.graph,
            scheduler=self.scheduler,
            scanner=self.scanner,
            processor=self.processor,
            progress_tracker=self.progress_tracker,
            incremental_strategy=self.incremental_strategy,
        )

    def crawl(self, base_graph: Optional[Graph] = None) -> Graph:
        """
        Запускає процес краулінгу (головний метод).

        РЕФАКТОРИНГ: Тепер тільки координація на високому рівні,
        вся логіка делегована компонентам.

        Args:
            base_graph: Базовий граф для incremental краулінгу

        Returns:
            Граф з результатами краулінгу
        """
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

        logger.info(f"Starting crawl: {self.config.url}")
        logger.info(
            f"Config: max_depth={self.config.max_depth}, "
            f"max_pages={self.config.max_pages}"
        )

        try:
            # ДЕЛЕГУВАННЯ: Lifecycle Manager виконує BEFORE_CRAWL hooks
            self.lifecycle_manager.execute_before_crawl()

            # Створюємо початковий вузол
            node_class = self.config.custom_node_class or Node
            root_node = node_class(
                url=self.config.url, depth=0, plugin_manager=self.node_plugin_manager
            )
            self.graph.add_node(root_node)
            self.scheduler.add_node(root_node)

            # ДЕЛЕГУВАННЯ: Coordinator координує весь процес краулінгу
            result = self.coordinator.coordinate()

            return result

        except Exception as e:
            logger.error(f"Crawl error: {e}", exc_info=True)

            # Подія помилки
            self.event_bus.publish(
                CrawlerEvent.create(
                    EventType.ERROR_OCCURRED,
                    data={"error": str(e), "error_type": type(e).__name__},
                )
            )
            raise

        finally:
            # ДЕЛЕГУВАННЯ: Lifecycle Manager виконує AFTER_CRAWL hooks
            pages_crawled = self.progress_tracker.get_pages_crawled()
            self.lifecycle_manager.execute_after_crawl(pages_crawled)

            # ДЕЛЕГУВАННЯ: Progress Tracker публікує завершення
            self.progress_tracker.publish_crawl_completed()

    def get_stats(self) -> dict:
        """
        Повертає статистику краулінгу.

        Returns:
            Словник зі статистикою графу та краулінгу
        """
        stats = self.graph.get_stats()
        if self.progress_tracker:
            stats["pages_crawled"] = self.progress_tracker.get_pages_crawled()
        return stats
