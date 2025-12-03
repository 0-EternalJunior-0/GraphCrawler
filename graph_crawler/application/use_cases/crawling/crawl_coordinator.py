"""
Crawl Coordinator - координація режимів краулінгу.

Features:
- Async методи
- Використовує asyncio.sleep() замість time.sleep()
- Використовує async scanner.scan_node() та scan_batch()
"""

import asyncio
import logging
import time
from typing import List, Optional

from graph_crawler.application.use_cases.crawling.checkpoint import CheckpointManager
from graph_crawler.application.use_cases.crawling.incremental_strategy import (
    IncrementalCrawlStrategy,
)
from graph_crawler.application.use_cases.crawling.link_processor import LinkProcessor
from graph_crawler.application.use_cases.crawling.node_scanner import NodeScanner
from graph_crawler.application.use_cases.crawling.progress_tracker import (
    CrawlProgressTracker,
)
from graph_crawler.application.use_cases.crawling.scheduler import CrawlScheduler
from graph_crawler.domain.entities.graph import Graph
from graph_crawler.domain.entities.node import Node
from graph_crawler.domain.value_objects.configs import CrawlerConfig
from graph_crawler.infrastructure.transport.base import BaseDriver
from graph_crawler.observability.decorators.timing import measure_time
from graph_crawler.shared.constants import DEFAULT_BATCH_SIZE, MAX_PAGES_LIMIT

logger = logging.getLogger(__name__)


class CrawlCoordinator:
    """
    Async-First координатор краулінгу .

    Responsibilities:
    - Визначення режиму краулінгу (sequential vs batch)
    - Async координація sequential mode краулінгу
    - Async координація batch mode краулінгу
    - Перевірка лімітів (max_pages, max_depth)
    - Делегування сканування та обробки Всі затримки тепер NON-BLOCKING через asyncio.sleep()
    """

    def __init__(
        self,
        config: CrawlerConfig,
        driver: BaseDriver,
        graph: Graph,
        scheduler: CrawlScheduler,
        scanner: NodeScanner,
        processor: LinkProcessor,
        progress_tracker: CrawlProgressTracker,
        incremental_strategy: IncrementalCrawlStrategy,
        checkpoint_manager: Optional[CheckpointManager] = None,
        post_scan_hooks: Optional[List] = None,
    ):
        """
        Ініціалізує Crawl Coordinator.

         Підтримка post_scan_hooks для зовнішніх модулів!

        Args:
            post_scan_hooks: Список async функцій для обробки між scan та process
                            Кожна функція отримує (node, links) і повертає модифіковані links
                            Приклад: async def ml_hook(node, links): return filtered_links
        """
        self.config = config
        self.driver = driver
        self.graph = graph
        self.scheduler = scheduler
        self.scanner = scanner
        self.processor = processor
        self.progress_tracker = progress_tracker
        self.incremental_strategy = incremental_strategy
        self.checkpoint_manager = checkpoint_manager
        self.spider = None

        self.post_scan_hooks = post_scan_hooks or []
        if self.post_scan_hooks:
            logger.info(f"Initialized with {len(self.post_scan_hooks)} post-scan hooks")

    async def coordinate(self, spider=None) -> Graph:
        """
        Async координує краулінг (головний метод).

        Визначає режим (sequential vs batch) та запускає відповідний метод.

        Args:
            spider: BaseSpider instance для перевірки стану (optional)

        Returns:
            Граф з результатами краулінгу
        """
        self.spider = spider

        use_batch_mode = self.driver.supports_batch_fetching()

        if use_batch_mode:
            logger.info("Using BATCH MODE for faster parallel crawling")
            result = await self._crawl_batch_mode()
        else:
            logger.info("Using SEQUENTIAL MODE (one page at a time)")
            result = await self._crawl_sequential_mode()

        return result

    async def _crawl_sequential_mode(self) -> Graph:
        """
        Async послідовний режим краулінгу. Всі затримки NON-BLOCKING!

        Returns:
            Граф з результатами
        """
        while not self.scheduler.is_empty():
            # Перевіряємо стан crawler
            if self.spider and not await self._check_crawler_state():
                break

            if not self._should_continue():
                pages = self.progress_tracker.get_pages_crawled()
                logger.info(f"Stopping crawl: reached limit ({pages} pages)")
                break

            node = self.scheduler.get_next()
            if not node or not node.should_scan:
                continue

            if node.depth > self.config.max_depth:
                logger.debug(f"Skipping node (depth={node.depth}): {node.url}")
                continue

            # Публікуємо подію перед сканом
            self.progress_tracker.publish_node_scan_started(node.url, node.depth)

            # Вимірюємо час завантаження
            fetch_start = time.time()

            # ASYNC ДЕЛЕГУВАННЯ: Scanner сканує ноду та повертає redirect info
            links, fetch_response = await self.scanner.scan_node(node)
            self.progress_tracker.increment_pages()

            # REDIRECT HANDLING: Якщо сторінка редіректить - оновлюємо граф
            # Граф завжди відображає РЕАЛЬНИЙ стан сайту!
            actual_node = node
            if fetch_response and fetch_response.is_redirect:
                actual_node = self._handle_redirect_after_scan(
                    node, fetch_response.final_url, fetch_response.redirect_chain
                )
                if actual_node is None:
                    # Редірект обробити не вдалось - пропускаємо ноду
                    continue

            # Публікуємо подію після скану
            fetch_time = time.time() - fetch_start
            self.progress_tracker.publish_node_scanned(
                url=actual_node.url,  # Використовуємо actual URL (може бути змінений після редіректу)
                depth=actual_node.depth,
                title=actual_node.get_title(),
                links_found=len(links) if links else 0,
                fetch_time=fetch_time,
            )

            # Дозволяє плагінам (ML, SEO, Analytics) обробляти результати сканування
            if links and self.post_scan_hooks:
                for hook in self.post_scan_hooks:
                    try:
                        links = await hook(
                            actual_node, links
                        )  # Використовуємо actual_node
                        logger.debug(
                            f"Post-scan hook executed for {actual_node.url}, links={len(links) if links else 0}"
                        )
                    except Exception as e:
                        logger.error(
                            f"Post-scan hook error for {actual_node.url}: {e}",
                            exc_info=True,
                        )

            # INCREMENTAL: Перевіряємо чи змінилась сторінка
            should_process_links = self.incremental_strategy.should_process_node_links(
                actual_node
            )

            # ДЕЛЕГУВАННЯ: Processor обробляє посилання (якщо потрібно)
            # Передаємо fetch_response з redirect info
            if links and should_process_links:
                await self.processor.process_links_async(
                    actual_node, links, fetch_response=fetch_response
                )

            # CHECKPOINT: Зберігаємо стан після кожної сторінки
            if self.checkpoint_manager:
                self.checkpoint_manager.increment_page_count()
                if self.checkpoint_manager.should_checkpoint():
                    self._save_checkpoint()

            # Progress update
            if self.progress_tracker.should_publish_progress():
                self.progress_tracker.publish_progress_event()

            request_delay = self.config.get_request_delay()
            if request_delay > 0:
                await asyncio.sleep(request_delay)  # NON-BLOCKING!

        pages = self.progress_tracker.get_pages_crawled()
        logger.info(f"Crawl finished: {pages} pages scanned")
        stats = self.graph.get_stats()
        logger.info(f"Graph stats: {stats}")

        return self.graph

    async def _crawl_batch_mode(self) -> Graph:
        """
        Async batch режим краулінгу. Всі затримки NON-BLOCKING!

        Returns:
            Граф з результатами
        """
        batch_size = getattr(self.driver, "max_concurrent", DEFAULT_BATCH_SIZE)
        logger.info(f"Batch size: {batch_size}")

        while not self.scheduler.is_empty():
            # Перевіряємо стан crawler
            if self.spider and not await self._check_crawler_state():
                break

            if not self._should_continue():
                pages = self.progress_tracker.get_pages_crawled()
                logger.info(f"Stopping crawl: reached limit ({pages} pages)")
                break

            # Збираємо батч вузлів
            batch_nodes = self._collect_batch(batch_size)

            if not batch_nodes:
                break

            # ASYNC ДЕЛЕГУВАННЯ: Scanner сканує батч та повертає redirect info
            batch_start = time.time()
            scan_results = await self.scanner.scan_batch(batch_nodes)
            self.progress_tracker.increment_pages(len(scan_results))

            # ДЕЛЕГУВАННЯ: Processor обробляє посилання для кожної ноди
            for node, links, fetch_response in scan_results:
                # REDIRECT HANDLING: Якщо сторінка редіректить - оновлюємо граф
                actual_node = node
                if fetch_response and fetch_response.is_redirect:
                    actual_node = self._handle_redirect_after_scan(
                        node, fetch_response.final_url, fetch_response.redirect_chain
                    )
                    if actual_node is None:
                        # Редірект обробити не вдалось - пропускаємо ноду
                        continue

                if links:
                    if self.post_scan_hooks:
                        for hook in self.post_scan_hooks:
                            try:
                                links = await hook(actual_node, links)
                                logger.debug(
                                    f"Post-scan hook executed for {actual_node.url} (batch), links={len(links) if links else 0}"
                                )
                            except Exception as e:
                                logger.error(
                                    f"Post-scan hook error for {actual_node.url} (batch): {e}",
                                    exc_info=True,
                                )

                    # Перевіряємо через incremental strategy
                    should_process = (
                        self.incremental_strategy.should_process_node_links(actual_node)
                    )
                    if should_process:
                        # Передаємо fetch_response з redirect info
                        await self.processor.process_links_async(
                            actual_node, links, fetch_response=fetch_response
                        )

            # CHECKPOINT: Зберігаємо стан після кожного батчу
            if self.checkpoint_manager:
                for _ in range(len(scan_results)):
                    self.checkpoint_manager.increment_page_count()
                if self.checkpoint_manager.should_checkpoint():
                    self._save_checkpoint()

            # Публікуємо подію після обробки batch
            batch_time = time.time() - batch_start
            self.progress_tracker.publish_batch_completed(
                batch_size=len(scan_results),
                batch_time=batch_time,
            )

            request_delay = self.config.get_request_delay()
            if request_delay > 0:
                await asyncio.sleep(request_delay)  # NON-BLOCKING!

        pages = self.progress_tracker.get_pages_crawled()
        logger.info(f"Crawl finished: {pages} pages scanned")
        stats = self.graph.get_stats()
        logger.info(f"Graph stats: {stats}")

        return self.graph

    def _collect_batch(self, batch_size: int) -> List[Node]:
        """
        Збирає батч вузлів для обробки з врахуванням max_pages.
        """
        batch_nodes = []

        # Враховуємо скільки ще можемо відсканувати
        pages_crawled = self.progress_tracker.get_pages_crawled()
        remaining_pages = None
        if self.config.max_pages:
            remaining_pages = self.config.max_pages - pages_crawled
            if remaining_pages <= 0:
                return batch_nodes

        # Обмежуємо batch_size залишком сторінок
        effective_batch_size = batch_size
        if remaining_pages is not None:
            effective_batch_size = min(batch_size, remaining_pages)

        while len(batch_nodes) < effective_batch_size and not self.scheduler.is_empty():
            node = self.scheduler.get_next()
            if not node or not node.should_scan:
                continue

            if node.depth > self.config.max_depth:
                continue

            batch_nodes.append(node)

        return batch_nodes

    def _should_continue(self) -> bool:
        """
        Перевіряє чи треба продовжувати краулінг.
        """
        pages_crawled = self.progress_tracker.get_pages_crawled()

        # Системний ліміт
        if MAX_PAGES_LIMIT is not None and pages_crawled >= MAX_PAGES_LIMIT:
            logger.warning(f"Reached system limit: {MAX_PAGES_LIMIT} pages")
            return False

        # Користувацький ліміт
        if self.config.max_pages and pages_crawled >= self.config.max_pages:
            logger.info(f"Reached user limit: {self.config.max_pages} pages")
            return False

        return True

    async def _check_crawler_state(self) -> bool:
        """
        Async перевіряє стан crawler для підтримки pause/resume/stop. NON-BLOCKING очікування!

        Returns:
            True якщо можна продовжувати краулінг, False якщо треба зупинитись
        """
        if not self.spider:
            return True

        # Якщо зупинено - припиняємо краулінг
        if self.spider.is_stopped():
            logger.info("Crawler stopped by user request")
            return False

        # Якщо призупинено - чекаємо поки не відновиться (NON-BLOCKING!)
        while self.spider.is_paused():
            logger.info("Crawler paused, waiting for resume...")
            await asyncio.sleep(1)  # NON-BLOCKING!

            # Перевіряємо чи не зупинили під час паузи
            if self.spider.is_stopped():
                logger.info("Crawler stopped while paused")
                return False

        return True

    def _save_checkpoint(self) -> None:
        """
        Зберігає checkpoint з поточним станом краулінгу.
        """
        if not self.checkpoint_manager:
            return

        try:
            # Збираємо URLs з черги
            queue_urls = [node.url for _, _, node in self.scheduler.queue]

            # Збираємо метадані
            metadata = {
                "pages_crawled": self.progress_tracker.get_pages_crawled(),
                "config": {
                    "url": self.config.url,
                    "max_depth": self.config.max_depth,
                    "max_pages": self.config.max_pages,
                },
            }

            # Зберігаємо checkpoint
            self.checkpoint_manager.save_checkpoint(
                graph=self.graph,
                queue_urls=queue_urls,
                seen_urls=self.scheduler.seen_urls,
                metadata=metadata,
            )
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}", exc_info=True)

    def _handle_redirect_after_scan(
        self, original_node: Node, final_url: str, redirect_chain: list[str] = None
    ) -> Optional[Node]:
        """
        Обробляє редірект після сканування ноди.

        Коли сторінка /page1 редіректить на /404:
        - Граф оновлюється: всі edges що вели на /page1 тепер ведуть на /404
        - Створюється один вузол /404 (якщо ще не існує)
        - В metadata edges зберігається original_url

        Args:
            original_node: Нода яка була просканована і виявила редірект
            final_url: Фінальний URL після редіректу
            redirect_chain: Ланцюжок проміжних редіректів

        Returns:
            Node: Вузол для final_url (для подальшої обробки посилань)
            None: Якщо обробка не вдалась

        Examples:
            >>> # /old-page редіректить на /new-page
            >>> actual_node = self._handle_redirect_after_scan(
            ...     original_node,
            ...     "https://site.com/new-page",
            ...     ["https://site.com/old-page", "https://site.com/temp"]
            ... )
            >>> # actual_node.url == "https://site.com/new-page"
        """
        if not final_url:
            logger.warning(f"Cannot handle redirect: final_url is empty")
            return original_node

        # Делегуємо обробку редіректу до Graph
        result_node = self.graph.handle_redirect(
            original_node=original_node,
            final_url=final_url,
            redirect_chain=redirect_chain or [],
        )

        if result_node is None:
            logger.warning(
                f"Redirect handling failed for {original_node.url} -> {final_url}"
            )
            return None

        # Якщо final_url ще не в seen_urls - додаємо
        if final_url not in self.scheduler.seen_urls:
            self.scheduler.seen_urls.add(final_url)

        # Якщо original_url був в seen_urls і він != final_url, він там залишається
        # Це запобігає повторному додаванню original_url в чергу

        logger.info(f"Redirect processed: {original_node.url} -> {final_url}")
        return result_node
