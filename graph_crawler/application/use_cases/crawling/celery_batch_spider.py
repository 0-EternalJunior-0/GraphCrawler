"""CeleryBatchSpider - ефективний distributed краулер з batch tasks.

Це оновлена версія CelerySpider, яка використовує batch tasks
для максимальної ефективності AsyncDriver.

Порівняння:

           CelerySpider vs CeleryBatchSpider

  CelerySpider (стара архітектура):
  - 1 task = 1 URL
  - AsyncDriver.max_concurrent=24 НЕ використовується
  - Ефективність: ~4% (prefetch=4, але 1 URL per fetch)

  CeleryBatchSpider (нова архітектура):
  - 1 task = N URLs (N = driver.max_concurrent)
  - AsyncDriver.fetch_many() повністю задіяний
  - Ефективність: ~100%

  РЕЗУЛЬТАТ: до 24x швидше!

Використання:
```python
from graph_crawler.application.use_cases.crawling.celery_batch_spider import CeleryBatchSpider

spider = CeleryBatchSpider(config, driver, storage)
graph = spider.crawl()
```
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from celery import group

from graph_crawler.application.use_cases.crawling.serialization_mixin import (
    ConfigSerializationMixin,
)
from graph_crawler.application.use_cases.crawling.spider import GraphSpider
from graph_crawler.domain.entities.edge import Edge
from graph_crawler.domain.entities.graph import Graph
from graph_crawler.domain.entities.node import Node
from graph_crawler.domain.value_objects.configs import CrawlerConfig
from graph_crawler.infrastructure.persistence.base import BaseStorage
from graph_crawler.infrastructure.transport.base import BaseDriver
from graph_crawler.shared.constants import (
    DEFAULT_CELERY_RESULTS_TIMEOUT,
    DEFAULT_MAX_CONCURRENT_REQUESTS,
)
from graph_crawler.shared.utils.url_utils import URLUtils

logger = logging.getLogger(__name__)

# Константи для прогрес-логування
PROGRESS_LOG_INTERVAL = 5  # секунд


class CeleryBatchSpider(ConfigSerializationMixin):
    """
    Ефективний distributed краулер з batch tasks.

    Ключова інновація: драйвер визначає batch size!
    - AsyncDriver: batch_size = max_concurrent (default 24)
    - PlaywrightDriver: batch_size = browsers × tabs (наприклад 3×5=15)
    - HTTPDriver: batch_size = 1 (sync драйвер)

    Архітектура:
    ```

                       CeleryBatchSpider


      1. Визначаємо batch_size з драйвера


      2. Групуємо URLs в batches по batch_size


      3. Кожен batch → окрема Celery task


      4. Worker обробляє batch через driver.fetch_many()


      5. Результати збираються та об'єднуються


    ```
    """

    def __init__(
        self,
        config: CrawlerConfig,
        driver: BaseDriver,
        storage: BaseStorage,
        batch_size: Optional[int] = None,
        timeout: Optional[int] = None,
    ):
        """
        Ініціалізує CeleryBatchSpider.

        Args:
            config: Конфігурація краулера (включає celery конфігурацію)
            driver: Драйвер для завантаження сторінок
            storage: Storage для зберігання графу
            batch_size: Розмір batch (якщо None - визначається з драйвера)
            timeout: Загальний timeout для краулінгу в секундах (опціонально)
        """
        self.config = config
        self.driver = driver
        self.storage = storage
        self.timeout = timeout
        self.start_time: Optional[float] = None

        # Визначаємо batch_size з драйвера
        self.batch_size = batch_size or self._get_driver_batch_size()

        # Ініціалізуємо Celery app
        self._init_celery_app()

        # Локальний граф (для збірки результатів)
        self.graph = Graph()
        self.pages_crawled = 0
        self.visited_urls = set()

        # Статистика для прогресу
        self.total_batches_sent = 0
        self.total_batches_completed = 0
        self.total_urls_processed = 0
        self.last_progress_log = 0.0

        self._shutdown_requested = False
        self._pending_results = None
        self._setup_signal_handlers()

        logger.info(
            f"CeleryBatchSpider initialized: "
            f"batch_size={self.batch_size}, "
            f"broker={self._get_celery_broker_url()}"
            + (f", timeout={timeout}s" if timeout else "")
        )

    def _get_driver_batch_size(self) -> int:
        """
        Визначає оптимальний batch_size з драйвера.

        Логіка:
        - AsyncDriver: max_concurrent (default 24)
        - PooledPlaywrightDriver: browsers × tabs_per_browser
        - PlaywrightDriver: 1 (один браузер)
        - HTTPDriver/RequestsDriver: 1 (sync)

        Returns:
            Оптимальний batch size для драйвера
        """
        driver_class = self.driver.__class__.__name__

        # AsyncDriver - використовуємо max_concurrent
        if hasattr(self.driver, "max_concurrent"):
            batch_size = self.driver.max_concurrent
            logger.info(f"Batch size from {driver_class}.max_concurrent: {batch_size}")
            return batch_size

        # PooledPlaywrightDriver - browsers × tabs
        if hasattr(self.driver, "max_browsers") and hasattr(
            self.driver, "max_tabs_per_browser"
        ):
            batch_size = self.driver.max_browsers * self.driver.max_tabs_per_browser
            logger.info(f"Batch size from {driver_class} pool: {batch_size}")
            return batch_size

        # Sync драйвери - batch size 1
        if (
            "Sync" in driver_class
            or "Requests" in driver_class
            or "HTTP" in driver_class
        ):
            logger.info(f"Sync driver {driver_class}: batch_size=1")
            return 1

        # Default fallback
        logger.info(f"Using default batch_size for {driver_class}")
        return DEFAULT_MAX_CONCURRENT_REQUESTS

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

    def _init_celery_app(self):
        """Ініціалізує Celery app для batch tasks."""
        import os

        from graph_crawler.infrastructure.messaging.celery_unified import (
            celery,
            crawl_batch_task,
        )

        self.celery_app = celery
        self.crawl_batch_task = crawl_batch_task

        # Встановлюємо environment variables
        celery_config = self.config.celery
        os.environ["CELERY_BROKER_URL"] = celery_config.broker_url
        os.environ["CELERY_RESULT_BACKEND"] = celery_config.backend_url

        if celery_config.broker_url != celery.conf.broker_url:
            celery.conf.update(
                broker_url=celery_config.broker_url,
                result_backend=celery_config.backend_url,
            )

        logger.info("Celery unified app initialized")

    def _check_workers(self) -> Dict[str, Any]:
        """
        Перевіряє стан Celery воркерів.

        Returns:
            Dict з інформацією про воркерів
        """
        try:
            inspect = self.celery_app.control.inspect()

            # Отримуємо активних воркерів (timeout 2 секунди)
            active = inspect.active() or {}
            stats = inspect.stats() or {}

            worker_count = len(stats)
            active_tasks = sum(len(tasks) for tasks in active.values())

            return {
                "workers": worker_count,
                "active_tasks": active_tasks,
                "worker_names": list(stats.keys()),
                "online": worker_count > 0,
            }
        except Exception as e:
            logger.warning(f" Could not check workers: {e}")
            return {
                "workers": 0,
                "active_tasks": 0,
                "worker_names": [],
                "online": False,
            }

    def _log_progress(self, force: bool = False):
        """
        Логує прогрес краулінгу (кожні PROGRESS_LOG_INTERVAL секунд).

        Args:
            force: Примусово залогувати (ігноруючи інтервал)
        """
        now = time.time()
        if not force and (now - self.last_progress_log) < PROGRESS_LOG_INTERVAL:
            return

        self.last_progress_log = now
        elapsed = now - self.start_time if self.start_time else 0

        # Формуємо статистику
        remaining = ""
        if self.timeout:
            time_left = self.timeout - elapsed
            remaining = (
                f", залишилось {time_left:.0f}s" if time_left > 0 else ", timeout!"
            )

        logger.info(
            f" Прогрес: {self.pages_crawled} сторінок | "
            f"{self.total_batches_completed}/{self.total_batches_sent} batches | "
            f"{elapsed:.1f}s{remaining}"
        )

    def _get_remaining_timeout(self) -> Optional[float]:
        """
        Обчислює залишковий timeout.

        Returns:
            Залишковий час в секундах або None якщо timeout не встановлено
        """
        if not self.timeout or not self.start_time:
            return None

        elapsed = time.time() - self.start_time
        remaining = self.timeout - elapsed

        return max(remaining, 0.1)  # Мінімум 0.1 секунди

    def _is_timeout_reached(self) -> bool:
        """
        Перевіряє чи досягнуто timeout.

        Returns:
            True якщо timeout досягнуто
        """
        if not self.timeout or not self.start_time:
            return False

        return (time.time() - self.start_time) >= self.timeout

    def _setup_signal_handlers(self):
        """

        Обробляє SIGINT (Ctrl+C) та SIGTERM для коректного завершення:
        - Зупиняє відправку нових batch tasks
        - Відміняє pending tasks
        - Зберігає частковий граф
        """
        import signal

        def handle_shutdown(signum, frame):
            signal_name = "SIGINT" if signum == signal.SIGINT else "SIGTERM"
            logger.warning(
                f" Shutdown signal received ({signal_name}), stopping gracefully..."
            )
            self._shutdown_requested = True

            # Відміняємо pending tasks
            if self._pending_results:
                try:
                    logger.info("Revoking pending tasks...")
                    self._pending_results.revoke(terminate=True)
                except Exception as e:
                    logger.warning(f"Error revoking tasks: {e}")

        # Встановлюємо handlers тільки в main thread
        try:
            signal.signal(signal.SIGINT, handle_shutdown)
            signal.signal(signal.SIGTERM, handle_shutdown)
            logger.debug("Signal handlers installed for graceful shutdown")
        except ValueError:
            # signal.signal може викинути ValueError якщо не в main thread
            logger.debug("Cannot install signal handlers (not in main thread)")

    def _should_stop(self) -> bool:
        """
        Перевіряє чи потрібно зупинити crawl.

        Returns:
            True якщо shutdown requested або timeout reached
        """
        if self._shutdown_requested:
            return True
        if self._is_timeout_reached():
            return True
        return False

    def crawl(self) -> Graph:
        """
        Запускає ефективний розподілений краулінг з batch tasks (sync версія).

        Алгоритм:
        1. Ініціалізація - створюємо кореневий вузол
        2. Збираємо URLs в batches по batch_size
        3. Кожен batch → окрема Celery task
        4. Обробляємо результати, збираємо нові URLs
        5. Повторюємо поки є URLs та не досягнуто ліміту

        Returns:
            Побудований граф
        """
        import asyncio

        return asyncio.run(self.crawl_async())

    async def crawl_async(self) -> Graph:
        """
        Async версія crawl для підтримки timeout через asyncio.wait_for().

        Returns:
            Побудований граф
        """
        self.start_time = time.time()

        logger.info(f" Starting CeleryBatchSpider crawl: {self._get_start_url()}")
        logger.info(
            f"Config: batch_size={self.batch_size}, "
            f"max_depth={self._get_max_depth()}, "
            f"max_pages={self._get_max_pages()}"
            + (f", timeout={self.timeout}s" if self.timeout else "")
        )

        # Перевіряємо воркерів на старті
        worker_info = self._check_workers()
        if worker_info["online"]:
            logger.info(
                f" Workers online: {worker_info['workers']} ({', '.join(worker_info['worker_names'][:3])}{'...' if len(worker_info['worker_names']) > 3 else ''})"
            )
        else:
            logger.warning(
                " No workers detected! Tasks will be queued but may not execute until workers start."
            )

        # Крок 1: Ініціалізація
        urls_to_process = self._initialize_crawl()
        config_dict = self._serialize_config()

        # Додаємо timeout info в config для воркерів
        if self.timeout:
            config_dict["_crawl_timeout"] = self.timeout
            config_dict["_crawl_start_time"] = self.start_time

        round_num = 0
        while urls_to_process and self._should_continue():
            if self._should_stop():
                if self._shutdown_requested:
                    logger.warning(" Shutdown requested, stopping crawl gracefully")
                else:
                    logger.warning(
                        f"⏱ Timeout reached ({self.timeout}s), stopping crawl"
                    )
                break

            round_num += 1

            # Крок 2: Групуємо URLs в batches
            batches = self._create_batches(urls_to_process)
            self.total_batches_sent += len(batches)

            logger.info(
                f" Round {round_num}: {len(urls_to_process)} URLs → "
                f"{len(batches)} batches (batch_size={self.batch_size})"
            )

            # Крок 3: Виконуємо batch tasks з timeout
            results = self._execute_batch_tasks(batches, config_dict)
            self.total_batches_completed += len([r for r in results if r])

            # Крок 4: Обробляємо результати
            urls_to_process = self._process_batch_results(results)

            # Логуємо прогрес
            self._log_progress()

            logger.info(
                f" Round {round_num} completed: "
                f"pages={self.pages_crawled}, queue={len(urls_to_process)}"
            )

            # Yield control для можливості timeout
            await asyncio.sleep(0)

        # Фінальний лог
        self._log_progress(force=True)
        elapsed = time.time() - self.start_time
        logger.info(f" Crawl finished: {self.pages_crawled} pages in {elapsed:.1f}s")
        stats = self.graph.get_stats()
        logger.info(f"Graph stats: {stats}")

        return self.graph

    def get_partial_graph(self) -> Graph:
        """
        Повертає частковий граф (для випадку timeout).

        Returns:
            Поточний стан графу
        """
        return self.graph

    def _create_batches(
        self, urls_to_process: List[Tuple[str, int]]
    ) -> List[List[Tuple[str, int]]]:
        """
        Групує URLs в batches відповідно до batch_size драйвера.

        Args:
            urls_to_process: Список (url, depth) для обробки

        Returns:
            Список batches, кожен batch = список (url, depth)
        """
        batches = []
        for i in range(0, len(urls_to_process), self.batch_size):
            batch = urls_to_process[i : i + self.batch_size]
            batches.append(batch)
        return batches

    def _execute_batch_tasks(
        self, batches: List[List[Tuple[str, int]]], config_dict: dict
    ) -> List[Dict]:
        """
        Виконує Celery batch tasks.

        Args:
            batches: Список batches URLs
            config_dict: Серіалізована конфігурація

        Returns:
            Список результатів від воркерів
        """
        from celery.exceptions import TimeoutError as CeleryTimeoutError

        # Перевірка shutdown перед відправкою
        if self._shutdown_requested:
            logger.warning("Shutdown requested, skipping batch execution")
            return []

        # Створюємо tasks
        tasks = []
        for batch in batches:
            task = self.crawl_batch_task.s(batch, config_dict, self.batch_size)
            tasks.append(task)

        # Запускаємо паралельно
        job = group(tasks)
        result_group = job.apply_async()

        self._pending_results = result_group

        logger.info(f" Sent {len(tasks)} batch tasks to workers")

        # Визначаємо timeout для очікування результатів
        remaining_timeout = self._get_remaining_timeout()
        if remaining_timeout is not None:
            # Використовуємо залишковий timeout, але не більше дефолтного
            wait_timeout = min(remaining_timeout, DEFAULT_CELERY_RESULTS_TIMEOUT)
        else:
            wait_timeout = DEFAULT_CELERY_RESULTS_TIMEOUT

        logger.info(f"⏳ Waiting for results (timeout={wait_timeout:.1f}s)...")

        # Чекаємо результати - простий підхід без polling
        try:
            results = result_group.get(timeout=wait_timeout)
            self._pending_results = None  # Очищаємо після успішного отримання
            logger.info(f" Received {len(results)} batch results")
            return results

        except CeleryTimeoutError:
            logger.warning(
                f"⏱ Celery timeout ({wait_timeout:.1f}s), trying to get partial results..."
            )

            # Намагаємось отримати часткові результати
            partial_results = []
            for async_result in result_group.results:
                try:
                    if async_result.ready():
                        result = async_result.get(timeout=1)
                        partial_results.append(result)
                except Exception:
                    pass

            if partial_results:
                logger.info(f" Got {len(partial_results)} partial results")
                return partial_results

            # Відміняємо незавершені tasks
            try:
                result_group.revoke(terminate=True)
            except Exception:
                pass

            return []

        except Exception as e:
            logger.error(f" Error waiting for batch results: {type(e).__name__}: {e}")
            return []

    def _process_batch_results(
        self, batch_results: List[Dict]
    ) -> List[Tuple[str, int]]:
        """
        Обробляє результати від batch tasks.

        Args:
            batch_results: Список результатів від batch tasks

        Returns:
            Нові URLs для наступного раунду
        """
        urls_to_process = []

        logger.debug(f"Processing {len(batch_results)} batch results")

        for batch_idx, batch_result in enumerate(batch_results):
            if not batch_result:
                logger.warning(f"Batch {batch_idx}: empty result")
                continue

            results = batch_result.get("results", [])
            logger.debug(
                f"Batch {batch_idx}: {len(results)} results, success={batch_result.get('success_count', 0)}"
            )

            for result in results:
                if not result.get("success"):
                    continue

                node_data = result.get("node_data")
                edges_data = result.get("edges_data", [])
                new_urls = result.get("new_urls", [])

                if node_data:
                    # Додаємо вузол в граф
                    node = self._deserialize_node(node_data)
                    if node.url not in self.graph.nodes:
                        self.graph.add_node(node)
                        self.pages_crawled += 1

                        # Перевіряємо ліміт
                        if not self._should_continue():
                            logger.info(f"Limit reached at {self.pages_crawled} pages")
                            break

                # Додаємо ребра
                for edge_data in edges_data:
                    edge = Edge(**edge_data)
                    self.graph.add_edge(edge)

                # Збираємо нові URLs
                for url, depth in new_urls:
                    if url not in self.visited_urls and depth <= self._get_max_depth():
                        urls_to_process.append((url, depth))
                        self.visited_urls.add(url)

            if not self._should_continue():
                break

        logger.debug(
            f"Processed: pages_crawled={self.pages_crawled}, new_urls={len(urls_to_process)}"
        )

        return urls_to_process

    def _initialize_crawl(self) -> List[Tuple[str, int]]:
        """Ініціалізує краулінг - створює кореневий вузол."""
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

    # тепер наслідуються з ConfigSerializationMixin

    def _create_temp_spider(self) -> GraphSpider:
        """Створює тимчасовий spider."""
        return GraphSpider(self.config, self.driver, self.storage)

    def _deserialize_node(self, node_data: dict) -> Node:
        """Десеріалізує вузол."""
        node_class = self._get_custom_node_class()
        temp_spider = self._create_temp_spider()

        node = node_class.model_validate(node_data)
        node.plugin_manager = temp_spider.node_plugin_manager

        return node

    def _should_continue(self) -> bool:
        """Перевіряє чи треба продовжувати."""
        # Перевірка max_pages
        max_pages = self._get_max_pages()
        if max_pages and self.pages_crawled >= max_pages:
            logger.info(f"Reached max_pages limit: {max_pages}")
            return False

        # Перевірка timeout
        if self._is_timeout_reached():
            logger.info(f"Reached timeout limit: {self.timeout}s")
            return False

        return True

    def get_stats(self) -> dict:
        """Повертає статистику краулінгу."""
        stats = self.graph.get_stats()
        stats["pages_crawled"] = self.pages_crawled
        stats["batch_size"] = self.batch_size
        stats["mode"] = "celery_batch"
        stats["total_batches_sent"] = self.total_batches_sent
        stats["total_batches_completed"] = self.total_batches_completed

        # Час роботи
        if self.start_time:
            stats["elapsed_time"] = time.time() - self.start_time
            if self.timeout:
                stats["timeout"] = self.timeout
                stats["timeout_reached"] = self._is_timeout_reached()

        return stats
