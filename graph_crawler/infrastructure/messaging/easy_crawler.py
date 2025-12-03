"""Простий API для distributed crawling.

Цей модуль надає EasyDistributedCrawler - wrapper над CeleryBatchSpider
для зручного запуску розподіленого краулінгу через YAML конфіг.
для 24x кращої продуктивності.
"""

import logging
from typing import List, Optional

from graph_crawler.application.use_cases.crawling.celery_batch_spider import (
    CeleryBatchSpider,
)
from graph_crawler.domain.entities.graph import Graph
from graph_crawler.domain.value_objects.configs import (
    CeleryConfig,
    CrawlerConfig,
    DriverConfig,
)
from graph_crawler.infrastructure.messaging.config import (
    DistributedCrawlConfig,
    load_config,
)
from graph_crawler.infrastructure.persistence.memory_storage import MemoryStorage
from graph_crawler.infrastructure.persistence.mongodb_storage import MongoDBStorage
from graph_crawler.infrastructure.persistence.postgresql_storage import (
    PostgreSQLStorage,
)
from graph_crawler.infrastructure.transport.sync import RequestsDriver as HTTPDriver
from graph_crawler.shared.utils.celery_config import validate_distributed_setup
from graph_crawler.shared.utils.celery_helpers import import_plugin

logger = logging.getLogger(__name__)


class EasyDistributedCrawler:
    """Простий wrapper над CeleryBatchSpider для distributed crawling.
    для 24x кращої продуктивності.

    Дозволяє запустити розподілений краулінг через простий YAML конфіг
    без необхідності вручну налаштовувати всі компоненти.

    Architecture:
        Master (Local) → Redis Broker → Workers (Servers 1-N) → Storage

    Storage Types:
        - memory: Зберігання в RAM (для малих сайтів <1000 сторінок)
        - mongodb: MongoDB база даних (для великих проектів)
        - postgresql: PostgreSQL база даних (для великих проектів)

    Attributes:
        config: Конфігурація distributed crawling
        _spider: Внутрішній CeleryBatchSpider instance

    Example:
        # Memory storage (локально, без БД)
        crawler = EasyDistributedCrawler.from_dict({
            "broker": {"type": "redis", "host": "server.com", "port": 6379},
            "database": {"type": "memory"},
            "crawl_task": {
                "urls": ["https://example.com"],
                "extractors": ["phones", "emails"]
            }
        })
        results = crawler.crawl()

        # MongoDB storage
        crawler = EasyDistributedCrawler.from_dict({
            "broker": {"type": "redis", "host": "server.com"},
            "database": {
                "type": "mongodb",
                "host": "server.com",
                "port": 27017,
                "database": "results"
            },
            "crawl_task": {"urls": ["https://example.com"]}
        })
    """

    @classmethod
    def from_yaml(cls, yaml_path: str) -> "EasyDistributedCrawler":
        """Створити з YAML конфігу.

        Args:
            yaml_path: Шлях до YAML файлу

        Returns:
            EasyDistributedCrawler instance

        Example:
            crawler = EasyDistributedCrawler.from_yaml("config.yaml")
            graph = crawler.crawl()
        """
        config = load_config(yaml_path)
        return cls(config)

    @classmethod
    def from_dict(cls, config_dict: dict) -> "EasyDistributedCrawler":
        """Створити з dict конфігу.

        Args:
            config_dict: Словник з конфігурацією

        Returns:
            EasyDistributedCrawler instance

        Example:
            # Memory storage (без БД)
            config = {
                "broker": {"type": "redis", "host": "localhost"},
                "database": {"type": "memory"},
                "crawl_task": {"urls": ["https://example.com"]}
            }
            crawler = EasyDistributedCrawler.from_dict(config)

            # MongoDB storage
            config = {
                "broker": {"type": "redis", "host": "localhost"},
                "database": {
                    "type": "mongodb",
                    "host": "localhost",
                    "port": 27017,
                    "database": "test"
                },
                "crawl_task": {"urls": ["https://example.com"]}
            }
            crawler = EasyDistributedCrawler.from_dict(config)
        """
        config = DistributedCrawlConfig(**config_dict)
        return cls(config)

    def __init__(self, config: DistributedCrawlConfig):
        """Ініціалізація з конфігом.

        Args:
            config: DistributedCrawlConfig об'єкт
        """
        self.config = config
        self._spider: Optional[CeleryBatchSpider] = None
        self._setup()

    def _setup(self):
        """Налаштування CelerySpider з конфігу."""

        # 1. Створюємо CrawlerConfig
        crawler_config = CrawlerConfig(
            url=self.config.crawl_task.urls[0],  # Primary URL
            max_depth=self.config.crawl_task.max_depth,
            max_pages=self.config.crawl_task.max_pages,
            driver=DriverConfig(),
            celery=CeleryConfig(
                enabled=True,
                broker_url=self.config.broker.url,
                backend_url=self.config.broker.url.replace("/0", "/1"),
                workers=self.config.workers,
                task_time_limit=self.config.task_time_limit,
                worker_prefetch_multiplier=self.config.worker_prefetch_multiplier,
            ),
        )

        # 2. Створюємо Driver
        driver = HTTPDriver(crawler_config.get_driver_params())

        # 3. Створюємо Storage
        storage = self._create_storage()

        # 4. Додаємо extractors як plugins
        plugins = self._create_extractors()
        crawler_config.node_plugins = plugins

        # 5. Створюємо CeleryBatchSpider
        self._spider = CeleryBatchSpider(crawler_config, driver, storage)

        logger.info(f"EasyDistributedCrawler initialized")
        logger.info(f"Broker: {self.config.broker.url}")
        logger.info(
            f"Database: {self.config.database.type}"
            + (
                f" at {self.config.database.host}"
                if self.config.database.host
                else " (local RAM)"
            )
        )
        logger.info(f"Workers: {self.config.workers}")

    def _create_storage(self):
        """Створити storage з конфігу.

        Returns:
            BaseStorage instance (Memory, MongoDB або PostgreSQL)
        """
        db_config = self.config.database

        if db_config.type == "memory":
            logger.info("Using MemoryStorage (local RAM, max 1000 nodes)")
            return MemoryStorage()
        elif db_config.type == "mongodb":
            return MongoDBStorage(
                {
                    "connection_string": db_config.connection_string,
                    "database": db_config.database,
                }
            )
        elif db_config.type == "postgresql":
            return PostgreSQLStorage(
                {
                    "connection_string": db_config.connection_string,
                }
            )
        else:
            raise ValueError(f"Unsupported database type: {db_config.type}")

    def _create_extractors(self) -> list:
        """Створити extractors з конфігу.

        Конвертує shortcut aliases в повні import paths і
        створює інстанси плагінів через dynamic import.

        Returns:
            Список BaseNodePlugin instances
        """
        # Mapping aliases -> import paths (визначається тут, не в ядрі!)
        EXTRACTOR_ALIASES = {
            "phones": "graph_crawler.plugins.node.extractors.PhoneExtractorPlugin",
            "emails": "graph_crawler.plugins.node.extractors.EmailExtractorPlugin",
            "prices": "graph_crawler.plugins.node.extractors.PriceExtractorPlugin",
        }

        # Збираємо всі import paths
        plugin_paths = []

        # Конвертуємо aliases в import paths
        for alias in self.config.crawl_task.extractors:
            if alias in EXTRACTOR_ALIASES:
                plugin_paths.append(EXTRACTOR_ALIASES[alias])

        # Додаємо явно вказані plugins
        plugin_paths.extend(self.config.crawl_task.plugins)

        # Dynamic import всіх плагінів
        plugins = []
        for plugin_path in plugin_paths:
            plugin = import_plugin(plugin_path)  # Використовуємо спільну функцію
            if plugin:
                plugins.append(plugin)

        return plugins

    def _get_plugin_paths(self) -> List[str]:
        """
        Повертає список import paths всіх плагінів.

        Використовується для передачі через Celery (тільки strings).

        Returns:
            Список import paths
        """
        EXTRACTOR_ALIASES = {
            "phones": "graph_crawler.plugins.node.extractors.PhoneExtractorPlugin",
            "emails": "graph_crawler.plugins.node.extractors.EmailExtractorPlugin",
            "prices": "graph_crawler.plugins.node.extractors.PriceExtractorPlugin",
        }

        paths = []
        for alias in self.config.crawl_task.extractors:
            if alias in EXTRACTOR_ALIASES:
                paths.append(EXTRACTOR_ALIASES[alias])
        paths.extend(self.config.crawl_task.plugins)

        return paths

    def crawl(self, validate: bool = True, skip_worker_check: bool = False) -> Graph:
        """Запустити distributed crawling.

        Args:
            validate: Чи виконувати валідацію перед стартом (default: True)
            skip_worker_check: Пропустити перевірку воркерів (для тестів)

        Returns:
            Graph з результатами краулінгу

        Raises:
            RuntimeError: Якщо валідація не пройшла (Redis недоступний або немає воркерів)

        Example:
            crawler = EasyDistributedCrawler.from_yaml("config.yaml")
            graph = crawler.crawl()

            # Аналіз результатів
            stats = graph.get_stats()
            print(f"Nodes: {stats['total_nodes']}")
            print(f"Edges: {stats['total_edges']}")

            # Extractors результати
            for node in graph.nodes.values():
                phones = node.user_data.get('phones', [])
                emails = node.user_data.get('emails', [])
                if phones:
                    print(f"{node.url}: {phones}")
        """
        if not self._spider:
            raise RuntimeError("Spider not initialized. Call _setup() first.")

        if validate:
            from graph_crawler.infrastructure.messaging.celery_unified import celery

            check_workers = not skip_worker_check
            ok, errors = validate_distributed_setup(
                celery_app=celery if check_workers else None,
                check_workers=check_workers,
            )

            if not ok:
                error_msg = "Distributed setup validation failed:\n"
                for err in errors:
                    error_msg += f"   {err}\n"
                error_msg += "\nTo fix:\n"
                error_msg += (
                    "  1. Start Redis: docker run -d -p 6379:6379 redis:alpine\n"
                )
                error_msg += "  2. Start workers: celery -A graph_crawler.celery_unified worker --loglevel=info\n"
                error_msg += (
                    "\nOr pass validate=False to skip validation (not recommended)"
                )
                raise RuntimeError(error_msg)

        logger.info(
            f"Starting distributed crawl for {len(self.config.crawl_task.urls)} URLs"
        )

        # Запускаємо CelerySpider
        graph = self._spider.crawl()

        logger.info(f"Crawl completed: {len(graph.nodes)} nodes")
        return graph

    def get_stats(self) -> dict:
        """Отримати статистику краулінгу.

        Returns:
            Словник зі статистикою

        Example:
            stats = crawler.get_stats()
            print(f"Pages crawled: {stats['pages_crawled']}")
            print(f"Workers: {stats['celery_workers']}")
        """
        if not self._spider:
            return {}
        return self._spider.get_stats()
