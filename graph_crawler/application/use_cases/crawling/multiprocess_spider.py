"""MultiprocessSpider - розподілений краулер з підтримкою множинних процесів."""

import logging
from multiprocessing import Lock, Manager, Pool
from typing import List, Optional, Tuple

from graph_crawler.application.use_cases.crawling.scheduler import CrawlScheduler
from graph_crawler.application.use_cases.crawling.spider import GraphSpider
from graph_crawler.domain.entities.graph import Graph
from graph_crawler.domain.entities.node import Node
from graph_crawler.domain.value_objects.configs import CrawlerConfig
from graph_crawler.infrastructure.persistence.base import BaseStorage
from graph_crawler.infrastructure.transport.base import BaseDriver
from graph_crawler.shared.utils.url_utils import URLUtils

logger = logging.getLogger(__name__)


# Глобальна функція для multiprocessing (має бути поза класом для pickle)
def _process_batch_global(batch_data: Tuple) -> Tuple[List, List, List]:
    """
    Глобальна функція для обробки батча (pickle-able).

    Args:
        batch_data: (urls, config_dict, visited_urls_snapshot)

    Returns:
        (nodes_data, edges_data, new_urls)
    """
    urls, config_dict, visited_urls_snapshot = batch_data

    # Створюємо локальний spider
    from graph_crawler.domain.value_objects.configs import CrawlerConfig
    from graph_crawler.infrastructure.persistence.memory_storage import MemoryStorage
    from graph_crawler.infrastructure.transport.http import HTTPDriver

    config = CrawlerConfig(**config_dict)

    # Прямі імпорти замість Factory
    driver_params = config.get_driver_config_dict()
    driver = HTTPDriver(driver_params)

    # Створюємо storage
    storage = MemoryStorage()

    # Створюємо spider
    spider = GraphSpider(config, driver, storage)

    nodes_data = []
    edges_data = []
    new_urls = []

    # Обробляємо кожен URL
    for url, depth in urls:
        try:
            node_class = config.custom_node_class if config.custom_node_class else Node
            node = node_class(
                url=url, depth=depth, plugin_manager=spider.node_plugin_manager
            )

            links = spider.scanner.scan_node(node)
            nodes_data.append(node.model_dump())

            if links:
                for link_url in links:
                    if not spider.domain_filter.is_allowed(link_url):
                        continue
                    if not spider.path_filter.is_allowed(link_url):
                        continue

                    normalized_url = URLUtils.normalize_url(link_url)

                    from graph_crawler.domain.entities.edge import Edge

                    edge = Edge(source_node_id=node.id, target_node_id=normalized_url)
                    edges_data.append(edge.model_dump())

                    if normalized_url not in visited_urls_snapshot:
                        new_urls.append((normalized_url, depth + 1))

        except Exception as e:
            logger.error(f"Error processing {url}: {e}")
            continue

    return nodes_data, edges_data, new_urls


class MultiprocessSpider:
    """
    Розподілений краулер з підтримкою множинних процесів.

    Архітектура:
    - Головний процес управляє scheduler та координує роботу
    - Воркери (worker processes) паралельно обробляють батчі URL
    - Shared state через Manager для синхронізації між процесами
    - Кожен воркер має свій екземпляр driver та scanner

    Використання:
    ```python
    spider = MultiprocessSpider(config, driver, storage, workers=10)
    graph = spider.crawl()
    ```

    Локальна паралельна обробка:
    - Множинні локальні процеси для паралельної обробки
    - Підходить для середніх/великих сайтів (>1000 сторінок)
    - Значно швидше ніж sequential режим

    Переваги:
    - Паралельна обробка множини сторінок
    - Використання всіх ядер CPU
    - Значне прискорення для великих сайтів
    - Простота налаштування (тільки параметр workers)

    Обмеження:
    -  Тільки локальні процеси (не розподілено між машинами)
    -  Потребує достатньо RAM для всіх воркерів
    """

    def __init__(
        self,
        config: CrawlerConfig,
        driver: BaseDriver,
        storage: BaseStorage,
        workers: int = 10,
        event_bus=None,
    ):
        """
        Ініціалізує MultiprocessSpider.

        Args:
            config: Конфігурація краулера
            driver: Драйвер для завантаження сторінок
            storage: Storage для зберігання графу
            workers: Кількість паралельних процесів
            event_bus: EventBus для публікації подій (опціонально)
        """
        self.config = config
        self.driver = driver
        self.storage = storage
        self.workers = workers
        self.event_bus = event_bus

        # Створюємо Manager для shared state
        self.manager = Manager()
        self.shared_graph_data = self._get_manager_dict()
        self.shared_visited_urls = self._get_manager_list()
        self.shared_lock = self._get_manager_lock()

        # Локальний граф (для збірки результатів)
        self.graph = Graph()
        self.pages_crawled = 0

        logger.info(f"MultiprocessSpider initialized with {workers} workers")

    def _get_manager_dict(self):
        """Повертає shared dict від Manager."""
        return self.manager.dict()

    def _get_manager_list(self):
        """Повертає shared list від Manager."""
        return self.manager.list()

    def _get_manager_lock(self):
        """Повертає shared lock від Manager."""
        return self.manager.Lock()

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

    def crawl(self) -> Graph:
        """
        Запускає розподілений краулінг.

        Алгоритм:
        1. Створити початковий вузол
        2. Розподілити URL між воркерами батчами
        3. Кожен воркер обробляє свій батч паралельно
        4. Зібрати результати та об'єднати графи
        5. Повторювати поки є непроскановані вузли

        Returns:
            Побудований граф
        """
        logger.info(f"Starting multiprocess crawl: {self._get_start_url()}")
        logger.info(
            f"Workers: {self.workers}, max_depth: {self._get_max_depth()}, max_pages: {self._get_max_pages()}"
        )

        # Ініціалізуємо краулінг
        urls_to_process = self._initialize_crawl()

        # Основний цикл краулінгу
        while urls_to_process and self._should_continue():
            urls_to_process = self._process_crawl_batch(urls_to_process)

        self._log_crawl_completion()
        return self.graph

    def _initialize_crawl(self) -> List[Tuple[str, int]]:
        """
        Ініціалізує краулінг - створює початковий вузол.

        Returns:
            Список URL для обробки [(url, depth)]
        """
        temp_spider = self._create_worker_spider()

        node_class = (
            self.config.custom_node_class if self.config.custom_node_class else Node
        )
        root_node = node_class(
            url=self.config.url, depth=0, plugin_manager=temp_spider.node_plugin_manager
        )
        self.graph.add_node(root_node)

        # Додаємо в список для обробки
        self.shared_visited_urls.append(root_node.url)
        return [(root_node.url, 0)]

    def _process_crawl_batch(
        self, urls_to_process: List[Tuple[str, int]]
    ) -> List[Tuple[str, int]]:
        """
        Обробляє батч URL паралельно.

        Args:
            urls_to_process: Список URL для обробки [(url, depth)]

        Returns:
            Новий список URL для наступної ітерації
        """
        # Розбиваємо на батчі
        batches = self._split_into_batches(urls_to_process, self.workers)
        if not batches:
            return []

        logger.info(f"Processing {len(urls_to_process)} URLs in {len(batches)} batches")

        # Паралельна обробка батчів
        batch_results = self._execute_parallel_batches(batches)

        # Обробка результатів
        new_urls = self._merge_batch_results(batch_results)

        logger.info(
            f"Processed batch. Total pages: {self.pages_crawled}, URLs in queue: {len(new_urls)}"
        )
        return new_urls

    def _execute_parallel_batches(self, batches: List) -> List:
        """
        Виконує паралельну обробку батчів.

        Args:
            batches: Список батчів для обробки

        Returns:
            Результати обробки батчів
        """
        with Pool(processes=self.workers) as pool:
            return pool.map(_process_batch_global, batches)

    def _merge_batch_results(self, batch_results: List) -> List[Tuple[str, int]]:
        """
        Об'єднує результати батчів в граф.

        Args:
            batch_results: Результати від воркерів

        Returns:
            Список нових URL для наступної ітерації
        """
        new_urls = []

        for batch_result in batch_results:
            nodes, edges, urls = batch_result

            # Додаємо вузли в граф
            self._add_nodes_to_graph(nodes)

            # Додаємо ребра в граф
            self._add_edges_to_graph(edges)

            # Збираємо нові URL
            new_urls.extend(self._collect_new_urls(urls))

        return new_urls

    def _add_nodes_to_graph(self, nodes_data: List):
        """Додає вузли в граф."""
        for node_data in nodes_data:
            node = self._deserialize_node(node_data)
            if node.url not in self.graph.nodes:
                self.graph.add_node(node)
                self.pages_crawled += 1

    def _add_edges_to_graph(self, edges_data: List):
        """Додає ребра в граф."""
        from graph_crawler.domain.entities.edge import Edge

        for edge_data in edges_data:
            edge = Edge(**edge_data)
            self.graph.add_edge(edge)

    def _collect_new_urls(self, urls: List[Tuple[str, int]]) -> List[Tuple[str, int]]:
        """
        Збирає нові URL для наступного раунду.

        Args:
            urls: Список URL з результатів воркера

        Returns:
            Фільтрований список нових URL
        """
        new_urls = []
        for url, depth in urls:
            if url not in self.shared_visited_urls and depth <= self.config.max_depth:
                new_urls.append((url, depth))
                self.shared_visited_urls.append(url)
        return new_urls

    def _log_crawl_completion(self):
        """Логує завершення краулінгу."""
        logger.info(f"Multiprocess crawl finished: {self.pages_crawled} pages scanned")
        stats = self.graph.get_stats()
        logger.info(f"Graph stats: {stats}")

    def _process_batch_wrapper(self, batch_data: Tuple) -> Tuple[List, List, List]:
        """
        Wrapper для обробки батча (для Pool.map).

        Args:
            batch_data: Кортеж (urls, config_dict, visited_urls_snapshot)

        Returns:
            Tuple: (nodes, edges, new_urls)
        """
        urls, config_dict, visited_urls_snapshot = batch_data
        return self._process_batch(urls, config_dict, visited_urls_snapshot)

    def _process_batch(
        self, urls: List[Tuple[str, int]], config_dict: dict, visited_urls_snapshot: set
    ) -> Tuple[List, List, List]:
        """
        Обробляє батч URL в окремому процесі.

        Args:
            urls: Список кортежів (url, depth)
            config_dict: Словник з конфігурацією
            visited_urls_snapshot: Snapshot відвіданих URL (звичайний set, не Manager)

        Returns:
            Tuple: (nodes_data, edges_data, new_urls)
        """
        # Створюємо локальний spider для цього воркера
        from graph_crawler.domain.value_objects.configs import CrawlerConfig

        config = CrawlerConfig(**config_dict)
        spider = self._create_worker_spider_from_config(config)

        nodes_data = []
        edges_data = []
        new_urls = []

        # Обробляємо кожен URL в батчі
        for url, depth in urls:
            try:
                # Створюємо вузол
                node_class = (
                    config.custom_node_class if config.custom_node_class else Node
                )
                node = node_class(
                    url=url, depth=depth, plugin_manager=spider.node_plugin_manager
                )

                # Скануємо вузол
                links = spider.scanner.scan_node(node)

                # Серіалізуємо вузол
                nodes_data.append(node.model_dump())

                # Обробляємо знайдені посилання
                if links:
                    for link_url in links:
                        # Перевіряємо фільтри
                        if not spider.domain_filter.is_allowed(link_url):
                            continue
                        if not spider.path_filter.is_allowed(link_url):
                            continue

                        # Нормалізуємо URL
                        normalized_url = URLUtils.normalize_url(link_url)

                        # Створюємо ребро
                        from graph_crawler.domain.entities.edge import Edge

                        edge = Edge(
                            source_node_id=node.id, target_node_id=normalized_url
                        )
                        edges_data.append(edge.model_dump())

                        # Додаємо новий URL для обробки (використовуємо snapshot замість Manager)
                        if normalized_url not in visited_urls_snapshot:
                            new_urls.append((normalized_url, depth + 1))

            except Exception as e:
                logger.error(f"Error processing {url}: {e}")
                continue

        return nodes_data, edges_data, new_urls

    def _create_worker_spider(self) -> GraphSpider:
        """Створює екземпляр GraphSpider для воркера."""
        return GraphSpider(self.config, self.driver, self.storage)

    def _create_worker_spider_from_config(self, config: CrawlerConfig) -> GraphSpider:
        """Створює екземпляр GraphSpider з конфігурації.

        Alpha 2.0: Використовуємо прямі імпорти замість Factory.
        """
        from graph_crawler.infrastructure.persistence.memory_storage import (
            MemoryStorage,
        )
        from graph_crawler.infrastructure.transport.http import HTTPDriver

        # Прямі імпорти замість Factory
        driver_params = config.get_driver_config_dict()
        driver = HTTPDriver(driver_params)

        # Створюємо storage для воркера
        storage = MemoryStorage()

        return GraphSpider(config, driver, storage)

    def _deserialize_node(self, node_data: dict) -> Node:
        """Десеріалізує вузол з словника."""
        node_class = (
            self.config.custom_node_class if self.config.custom_node_class else Node
        )

        # Створюємо временний spider для plugin_manager
        temp_spider = self._create_worker_spider()

        # Відновлюємо вузол
        node = node_class.model_validate(node_data)
        node.plugin_manager = temp_spider.node_plugin_manager

        return node

    def _split_into_batches(
        self, urls: List[Tuple[str, int]], num_batches: int
    ) -> List[Tuple]:
        """
        Розбиває список URL на батчі для воркерів.

        Args:
            urls: Список кортежів (url, depth)
            num_batches: Кількість батчів

        Returns:
            Список батчів для обробки (batch_urls, config_dict, visited_urls_snapshot)
        """
        if not urls:
            return []

        batch_size = max(1, len(urls) // num_batches)
        batches = []

        # Серіалізуємо конфігурацію в JSON-сумісний формат (уникаємо Manager об'єктів)
        try:
            config_dict = self.config.model_dump(mode="json")
        except Exception:
            # Fallback - ручна серіалізація базових параметрів
            config_dict = {
                "url": self.config.url,
                "max_depth": self.config.max_depth,
                "max_pages": self.config.max_pages,
                "allowed_domains": self.config.allowed_domains,
                "driver": (
                    self.config.get_driver_config_dict() if self.config.driver else {}
                ),
                "storage": (
                    self.config.get_storage_config_dict() if self.config.storage else {}
                ),
            }

        # Створюємо snapshot відвіданих URL як звичайний set (можна серіалізувати)
        visited_urls_snapshot = set(self.shared_visited_urls)

        for i in range(0, len(urls), batch_size):
            batch_urls = urls[i : i + batch_size]
            batches.append((batch_urls, config_dict, visited_urls_snapshot))

        return batches

    def _should_continue(self) -> bool:
        """Перевіряє чи треба продовжувати краулінг."""
        if self.config.max_pages and self.pages_crawled >= self.config.max_pages:
            logger.info(f"Reached max_pages limit: {self.config.max_pages}")
            return False
        return True

    def get_stats(self) -> dict:
        """Повертає статистику краулінгу."""
        stats = self.graph.get_stats()
        stats["pages_crawled"] = self.pages_crawled
        stats["workers"] = self.workers
        return stats
