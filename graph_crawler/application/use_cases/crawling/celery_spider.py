"""CelerySpider - розподілений краулер з підтримкою Celery для масштабування між серверами.

 DEPRECATED: Використовуйте CeleryBatchSpider для 24x кращої продуктивності!

Цей клас обробляє 1 URL per Celery task, що НЕ використовує
AsyncDriver.max_concurrent ефективно.

Migration:
    # Старий код (неефективний):
    from graph_crawler.application.use_cases.crawling.celery_spider import CelerySpider
    spider = CelerySpider(config, driver, storage)

    # Новий код (24x швидше):
    from graph_crawler.application.use_cases.crawling.celery_batch_spider import CeleryBatchSpider
    spider = CeleryBatchSpider(config, driver, storage)

Документація: docs/deployment/BATCH_TASKS.md
"""

import logging
import warnings
from typing import Any, Dict, List, Optional, Tuple

from celery import Celery, group  # type: ignore[import-not-found]

from graph_crawler.application.use_cases.crawling.serialization_mixin import (
    ConfigSerializationMixin,
)
from graph_crawler.application.use_cases.crawling.spider import GraphSpider
from graph_crawler.domain.entities.edge import Edge
from graph_crawler.domain.entities.graph import Graph
from graph_crawler.domain.entities.node import Node
from graph_crawler.domain.interfaces.distributed_spider import IDistributedSpider
from graph_crawler.domain.interfaces.driver import IDriver
from graph_crawler.domain.interfaces.storage import IStorage
from graph_crawler.domain.value_objects.configs import CrawlerConfig
from graph_crawler.shared.constants import (
    DEFAULT_CELERY_RESULTS_TIMEOUT,
)
from graph_crawler.shared.utils.url_utils import URLUtils

logger = logging.getLogger(__name__)


class CelerySpider(ConfigSerializationMixin, IDistributedSpider):
    """
    DEPRECATED: Використовуйте CeleryBatchSpider для 24x кращої продуктивності!

    """

    def __init__(self, config: CrawlerConfig, driver: IDriver, storage: IStorage):
        """
        Ініціалізує CelerySpider.

         DEPRECATED: Використовуйте CeleryBatchSpider для 24x кращої продуктивності!

        Args:
            config: Конфігурація краулера (включає celery конфігурацію)
            driver: Драйвер для завантаження сторінок
            storage: Storage для зберігання графу
        """
        warnings.warn(
            "CelerySpider is deprecated and will be removed in future versions. "
            "Use CeleryBatchSpider for 24x better performance. "
            "See docs/deployment/BATCH_TASKS.md for migration guide.",
            DeprecationWarning,
            stacklevel=2,
        )

        self.config = config
        self.driver = driver
        self.storage = storage

        # Ініціалізуємо Celery app
        self.celery_app = self._init_celery_app()

        # Локальний граф (для збірки результатів)
        self.graph = Graph()
        self.pages_crawled = 0
        self.visited_urls = set()

        logger.info("CelerySpider initialized with broker: %s", self._get_celery_broker_url())
        logger.info("Celery workers: %s", self._get_celery_workers())

    def _get_celery_workers(self) -> int:
        """Повертає кількість Celery воркерів."""
        return self.config.celery.workers

    def _get_celery_broker_url(self) -> str:
        """Повертає URL брокера Celery."""
        return self.config.celery.broker_url

    def _get_max_depth(self) -> int:
        """Повертає максимальну глибину краулінгу."""
        return self.config.max_depth

    def _get_max_pages(self) -> Optional[int]:
        """Повертає максимальну кількість сторінок."""
        return self.config.max_pages

    def _get_custom_node_class(self):
        """Повертає кастомний клас Node або дефолтний."""
        return self.config.custom_node_class if self.config.custom_node_class else Node

    def _get_start_url(self) -> str:
        """Повертає початковий URL."""
        return self.config.url

    def _init_celery_app(self) -> Celery:
        """
        Ініціалізує Celery application з конфігурації.

        Використовує глобальний celery app з celery_app.py,
        що дозволяє воркерам бачити зареєстровані таски.

        Returns:
            Налаштований Celery app
        """
        import os

        from graph_crawler.infrastructure.messaging.celery_app import (
            celery,
            crawl_page_task,
        )

        # Зберігаємо посилання на глобальний task
        self.crawl_page_task = crawl_page_task

        # Оновлюємо broker URL якщо відрізняється від default
        celery_config = self.config.celery

        # Встановлюємо environment variables для воркерів
        os.environ["CELERY_BROKER_URL"] = celery_config.broker_url
        os.environ["CELERY_RESULT_BACKEND"] = celery_config.backend_url
        logger.info("Set CELERY_BROKER_URL to: %s", celery_config.broker_url)
        logger.info("Set CELERY_RESULT_BACKEND to: %s", celery_config.backend_url)

        if celery_config.broker_url != celery.conf.broker_url:
            celery.conf.update(
                broker_url=celery_config.broker_url,
                result_backend=celery_config.backend_url,
            )

        logger.info("Celery app initialized (using global celery_app)")
        return celery

    # _register_tasks видалено - використовуємо глобальні таски з celery_app.py

    def _setup_worker_spider(self, config_dict: dict) -> GraphSpider:
        """
        Створює локальний spider для Celery воркера.

        Плагіни десеріалізуються з import paths через dynamic import.

        Args:
            config_dict: Серіалізована конфігурація

        Returns:
            Налаштований GraphSpider
        """
        import importlib

        from graph_crawler.domain.value_objects.configs import CrawlerConfig
        from graph_crawler.infrastructure.persistence.memory_storage import (
            MemoryStorage,
        )
        from graph_crawler.infrastructure.transport.http import HTTPDriver

        # Витягуємо plugin paths перед створенням конфігу
        plugin_paths = config_dict.pop("_plugin_paths", [])

        config = CrawlerConfig(**config_dict)

        # Десеріалізуємо плагіни через dynamic import
        plugins = []
        for plugin_path in plugin_paths:
            try:
                module_path, class_name = plugin_path.rsplit(".", 1)
                module = importlib.import_module(module_path)
                plugin_class = getattr(module, class_name)
                plugins.append(plugin_class())
            except Exception as e:
                logger.warning("Failed to import plugin %s: %s", plugin_path, e)

        config.node_plugins = plugins if plugins else None

        # LAW OF DEMETER: використовуємо config.get_driver_params()
        driver_params = config.get_driver_params()
        driver = HTTPDriver(driver_params)

        storage = MemoryStorage()

        return GraphSpider(config, driver, storage)

    def _scan_node_in_worker(
        self, spider: GraphSpider, url: str, depth: int
    ) -> Tuple[Node, List[str]]:
        """
        Скануює вузол в контексті Celery воркера.

        Args:
            spider: Налаштований spider
            url: URL для сканування
            depth: Глибина вузла

        Returns:
            Tuple (node, links)
        """
        node_class = spider.config.custom_node_class if spider.config.custom_node_class else Node
        node = node_class(url=url, depth=depth, plugin_manager=spider.node_plugin_manager)
        links = spider.scanner.scan_node(node)
        return node, links

    def _process_scan_results(
        self, spider: GraphSpider, node: Node, links: List[str], depth: int
    ) -> Dict[str, Any]:
        """
        Обробляє результати сканування - фільтрує посилання та створює ребра.

        Args:
            spider: Spider з налаштованими фільтрами
            node: Просканована нода
            links: Знайдені посилання
            depth: Поточна глибина

        Returns:
            Dict з результатами для повернення в Celery
        """
        node_data = node.model_dump()
        edges_data = []
        new_urls = []

        if links:
            for link_url in links:
                if not spider.domain_filter.is_allowed(link_url):
                    continue
                if not spider.path_filter.is_allowed(link_url):
                    continue

                normalized_url = URLUtils.normalize_url(link_url)

                edge = Edge(source_node_id=node.node_id, target_node_id=normalized_url)
                edges_data.append(edge.model_dump())

                # Додаємо новий URL
                new_urls.append((normalized_url, depth + 1))

        return {
            "node_data": node_data,
            "edges_data": edges_data,
            "new_urls": new_urls,
            "success": True,
        }

    def crawl(self) -> Graph:
        """
                Запускає розподілений краулінг через Celery.

        Розбито на підметоди для покращення читабельності.

                Returns:
                    Побудований граф
        """
        logger.info("Starting Celery crawl: %s", self._get_start_url())
        logger.info(
            f"Celery workers: {self._get_celery_workers()}, "
            f"max_depth: {self._get_max_depth()}, max_pages: {self._get_max_pages()}"
        )

        # Крок 1: Ініціалізація
        urls_to_process = self._initialize_crawl()
        config_dict = self._serialize_config()

        # Крок 2: Основний цикл
        while urls_to_process and self._should_continue():
            logger.info("Processing %s URLs via Celery", len(urls_to_process))

            # Крок 3: Виконання задач
            results = self._execute_celery_tasks(urls_to_process, config_dict)

            # Крок 4: Обробка результатів
            urls_to_process = self._process_celery_results(results)

            logger.info(
                f"Celery round completed. Total pages: {self.pages_crawled}, "
                f"URLs in queue: {len(urls_to_process)}"
            )

        logger.info("Celery crawl finished: %s pages scanned", self.pages_crawled)
        stats = self.graph.get_stats()
        logger.info("Graph stats: %s", stats)

        return self.graph

    # тепер наслідуються з ConfigSerializationMixin

    def _initialize_crawl(self) -> List[Tuple[str, int]]:
        """
        Ініціалізує краулінг - створює кореневий вузол.

        Returns:
            Список URL для обробки [(url, depth)]
        """
        temp_spider = self._create_temp_spider()

        node_class = self._get_custom_node_class()
        root_node = node_class(
            url=self._get_start_url(),
            depth=0,
            plugin_manager=temp_spider.node_plugin_manager,
        )
        self.graph.add_node(root_node)
        self.visited_urls.add(root_node.url)

        return [(root_node.url, 0)]

    def _execute_celery_tasks(
        self, urls_to_process: List[Tuple[str, int]], config_dict: dict
    ) -> List[Dict]:
        """
        Виконує Celery задачі для списку URL.

        Args:
            urls_to_process: Список (url, depth) для обробки
            config_dict: Серіалізована конфігурація

        Returns:
            Список результатів від воркерів
        """
        # Створюємо задачі для Celery
        tasks = []
        for url, depth in urls_to_process:
            task = self.crawl_page_task.s(url, depth, config_dict)
            tasks.append(task)

        # Запускаємо задачі паралельно
        job = group(tasks)
        result_group = job.apply_async()

        # Чекаємо на завершення всіх задач
        return result_group.get(timeout=DEFAULT_CELERY_RESULTS_TIMEOUT)

    def _process_celery_results(self, results: List[Dict]) -> List[Tuple[str, int]]:
        """
        Обробляє результати від Celery воркерів.

        Args:
            results: Список результатів від воркерів

        Returns:
            Нові URL для наступного раунду
        """
        urls_to_process = []

        for result in results:
            if not result or not result.get("success"):
                continue

            node_data = result["node_data"]
            edges_data = result["edges_data"]
            new_urls = result["new_urls"]

            # Додаємо вузол в граф
            node = self._deserialize_node(node_data)
            if node.url not in self.graph.nodes:
                self.graph.add_node(node)
                self.pages_crawled += 1

            # Додаємо ребра
            for edge_data in edges_data:
                edge = Edge(**edge_data)
                self.graph.add_edge(edge)

            # Збираємо нові URL для наступного раунду
            for url, depth in new_urls:
                if url not in self.visited_urls and depth <= self._get_max_depth():
                    urls_to_process.append((url, depth))
                    self.visited_urls.add(url)

        return urls_to_process

    def _create_temp_spider(self) -> GraphSpider:
        """Створює тимчасовий spider для ініціалізації."""
        return GraphSpider(self.config, self.driver, self.storage)

    def _deserialize_node(self, node_data: dict) -> Node:
        """
        Десеріалізує вузол з словника.

        Args:
            node_data: Серіалізовані дані вузла

        Returns:
            Відновлений Node об'єкт
        """
        node_class = self._get_custom_node_class()

        # Створюємо временний spider для plugin_manager
        temp_spider = self._create_temp_spider()

        # Відновлюємо вузол
        node = node_class.model_validate(node_data)
        node.plugin_manager = temp_spider.node_plugin_manager

        return node

    def _should_continue(self) -> bool:
        """
        Перевіряє чи треба продовжувати краулінг.

        Returns:
            True якщо можна продовжувати
        """
        max_pages = self._get_max_pages()
        if max_pages and self.pages_crawled >= max_pages:
            logger.info("Reached max_pages limit: %s", max_pages)
            return False
        return True

    def get_stats(self) -> Dict[str, Any]:
        """
        Повертає статистику краулінгу.

        Returns:
            Словник зі статистикою
        """
        stats: Dict[str, Any] = self.graph.get_stats()
        stats["pages_crawled"] = self.pages_crawled
        stats["celery_workers"] = self._get_celery_workers()
        stats["mode"] = "celery"
        return stats

    def get_partial_graph(self) -> Graph:
        """
        Повертає частковий граф (для випадку timeout/shutdown).

        Returns:
            Поточний стан графу
        """
        return self.graph
