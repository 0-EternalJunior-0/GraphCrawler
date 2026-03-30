"""SitemapSpider - спеціалізований spider для краулінгу sitemap структури .
- crawl() тепер async
- Внутрішні методи async де потрібно
- Async context manager підтримка
- Підтримка url_rules для фільтрації та пріоритизації

ВИПРАВЛЕННЯ (Лютий 2025):
- P0: Додано захист від циклічних sitemap (_processed_sitemaps set)
- P0: Додано timeout на asyncio.to_thread() виклики (SITEMAP_PARSE_TIMEOUT)
"""

import asyncio
import logging
import re
import time
from typing import Optional, Set
from urllib.parse import urljoin

# Константи для захисту
SITEMAP_PARSE_TIMEOUT = 60  # Таймаут на парсинг одного sitemap (секунди)

from graph_crawler.application.use_cases.crawling.base_spider import (
    BaseSpider,
    CrawlerState,
)
from graph_crawler.application.use_cases.crawling.sitemap_parser import SitemapParser
from graph_crawler.application.use_cases.crawling.sitemap_processor import (
    SitemapProcessor,
)
from graph_crawler.domain.entities.graph import Graph
from graph_crawler.domain.events import CrawlerEvent, EventBus, EventType
from graph_crawler.domain.interfaces.driver import IDriver
from graph_crawler.domain.interfaces.storage import IStorage
from graph_crawler.domain.value_objects.configs import CrawlerConfig
from graph_crawler.domain.value_objects.models import Rule

logger = logging.getLogger(__name__)


class SitemapSpider(BaseSpider):
    """
    Async-First Spider для краулінгу sitemap структури .

    Example:
        >>> async with SitemapSpider(config, driver, storage) as spider:
        ...     graph = await spider.crawl()
        ...     print(f"Sitemaps: {spider.sitemaps_processed}")
    """

    def __init__(
        self,
        config: CrawlerConfig,
        driver: IDriver,
        storage: IStorage,
        event_bus: Optional[EventBus] = None,
        graph: Optional[Graph] = None,
        parser: Optional[SitemapParser] = None,
        processor: Optional[SitemapProcessor] = None,
        include_urls: bool = True,
        max_urls: Optional[int] = None,
        url_rules: Optional[list[Rule]] = None,
        max_sitemaps: Optional[int] = None,
        http_client: str = "requests",
        browser_config: Optional[dict] = None,
    ):
        """
        Ініціалізує SitemapSpider.

        Args:
            config: Конфігурація краулера
            driver: Драйвер для завантаження файлів
            storage: Сховище для графу
            event_bus: EventBus для публікації подій
            graph: Граф для зберігання результатів (optional, створюється автоматично)
            parser: Sitemap parser (optional, створюється автоматично)
            processor: Sitemap processor (optional, створюється автоматично)
            include_urls: Чи додавати кінцеві URL до графу (False = тільки структура sitemap)
            max_urls: Максимальна кількість URL для обробки (None = всі)
            url_rules: Правила для фільтрації та пріоритизації sitemap URLs
            max_sitemaps: Максимальна кількість sitemap файлів для обробки (None = всі)
            http_client: HTTP клієнт для sync запитів:
                - "requests" (default): стандартний requests
                - "cloudscraper": для обходу Cloudflare захисту
            browser_config: Конфігурація браузера для cloudscraper (optional)
        """
        super().__init__(config, driver, storage, event_bus)

        # DI: Graph (fallback якщо не передано)
        self.graph = graph if graph is not None else Graph()
        self.include_urls = include_urls
        self.max_urls = max_urls
        self.url_rules = url_rules or []
        self.max_sitemaps = max_sitemaps
        self.http_client = http_client
        self.browser_config = browser_config

        # DI: Parser (fallback якщо не передано)
        self.parser = (
            parser
            if parser is not None
            else SitemapParser(
                user_agent=config.get_user_agent(),
                http_client=http_client,
                browser_config=browser_config,
            )
        )

        # DI: Processor (fallback якщо не передано)
        self.processor = (
            processor
            if processor is not None
            else SitemapProcessor(
                graph=self.graph, event_bus=self.event_bus, include_urls=include_urls
            )
        )

        # Лічильники
        self.sitemaps_processed = 0
        self.urls_extracted = 0
        self.sitemaps_skipped = 0
        self._max_urls_reached = False  # Прапор для глобальної зупинки при досягненні ліміту

        # Зберігаємо вже оброблені sitemap URLs для детекції циклів
        self._processed_sitemaps: Set[str] = set()

        logger.info(
            f"SitemapSpider (async) initialized: "
            f"graph={'injected' if graph else 'created'}, "
            f"parser={'injected' if parser else 'created'}, "
            f"processor={'injected' if processor else 'created'}, "
            f"url_rules={len(self.url_rules)} rules, "
            f"max_sitemaps={max_sitemaps}, "
            f"http_client={http_client}"
        )

    async def crawl(self, base_graph: Optional[Graph] = None) -> Graph:
        """
        Async запускає процес краулінгу sitemap .

        Args:
            base_graph: Не використовується для sitemap (для сумісності з BaseSpider)

        Returns:
            Побудований граф sitemap структури
        """
        self._state = CrawlerState.RUNNING
        start_time = time.time()

        self.event_bus.publish(
            CrawlerEvent.create(
                EventType.SITEMAP_CRAWL_STARTED,
                data={
                    "url": self.config.url,
                    "include_urls": self.include_urls,
                    "max_urls": self.max_urls,
                },
            )
        )

        logger.info("Starting async sitemap crawl: %s", self.config.url)
        logger.info("Config: include_urls=%s, max_urls=%s", self.include_urls, self.max_urls)

        try:
            # Крок 1: Парсимо robots.txt та отримуємо sitemap URLs
            robots_url = urljoin(self.config.url, "/robots.txt")
            sitemap_data = await self._parse_robots_txt(robots_url)

            # Крок 2: Створюємо Node для robots.txt
            self.processor.create_robots_node(
                url=robots_url,
                sitemap_urls=sitemap_data.get("sitemap_urls", []),
                error=sitemap_data.get("error"),
            )

            # Крок 3: Обробляємо кожен знайдений sitemap
            sitemap_urls = sitemap_data.get("sitemap_urls", [])
            if sitemap_urls:
                # Сортуємо за пріоритетом якщо є url_rules
                if self.url_rules:
                    sitemap_urls = self._sort_sitemaps_by_priority(sitemap_urls)
                    logger.info("Sorted %s sitemaps by priority", len(sitemap_urls))

                # Обробляємо кожен sitemap
                for sitemap_url in sitemap_urls:
                    if self._max_urls_reached:
                        logger.info(
                            f"Stopping crawl: max_urls limit reached. "
                            f"URLs extracted: {self.urls_extracted}"
                        )
                        break
                    if self.max_sitemaps and self.sitemaps_processed >= self.max_sitemaps:
                        logger.info(
                            f"Reached max_sitemaps limit: {self.max_sitemaps}. "
                            f"Processed: {self.sitemaps_processed}, Skipped: {self.sitemaps_skipped}"
                        )
                        break

                    try:
                        await self._process_sitemap(sitemap_url, parent_url=robots_url, depth=1)
                    except asyncio.TimeoutError:
                        logger.warning("Timeout processing sitemap: %s", sitemap_url)
                        continue
                    except asyncio.CancelledError:
                        logger.warning("Cancelled processing sitemap: %s", sitemap_url)
                        continue
                    except Exception as e:
                        logger.warning("Error processing sitemap %s: %s", sitemap_url, e)
                        continue
            else:
                logger.warning(
                    "No sitemaps found in robots.txt. Graph contains only robots.txt node."
                )

            # Завершення
            duration = time.time() - start_time
            stats = self.graph.get_stats()

            logger.info("Sitemap crawl completed in %.2fs", duration)
            logger.info("Stats: %s", stats)
            logger.info("Sitemaps processed: %s", self.sitemaps_processed)
            logger.info("URLs extracted: %s", self.urls_extracted)

            # Подія завершення
            self.event_bus.publish(
                CrawlerEvent.create(
                    EventType.SITEMAP_CRAWL_COMPLETED,
                    data={
                        "total_nodes": stats["total_nodes"],
                        "sitemaps_processed": self.sitemaps_processed,
                        "urls_extracted": self.urls_extracted,
                        "duration": duration,
                    },
                )
            )

            return self.graph

        except Exception as e:
            self._state = CrawlerState.ERROR
            logger.error("Sitemap crawl error: %s", e, exc_info=True)

            # Подія помилки
            self.event_bus.publish(
                CrawlerEvent.create(
                    EventType.ERROR_OCCURRED,
                    data={"error": str(e), "error_type": type(e).__name__},
                )
            )
            raise

        finally:
            if self._state not in [CrawlerState.ERROR, CrawlerState.STOPPED]:
                self._state = CrawlerState.IDLE

    async def _parse_robots_txt(self, robots_url: str) -> dict:
        """
        Async парсить robots.txt та отримує sitemap URLs.

        Args:
            robots_url: URL robots.txt

        Returns:
            Dict з ключами:
            - sitemap_urls: список знайдених sitemap URLs
            - error: повідомлення про помилку (якщо є)
        """
        try:
            logger.info("Parsing robots.txt: %s", robots_url)
            base_url = robots_url.replace("/robots.txt", "")

            # Parser.parse_from_robots використовує requests (sync)
            # В майбутньому можна оптимізувати через aiohttp
            result = await asyncio.to_thread(self.parser.parse_from_robots, base_url)

            return {
                "sitemap_urls": result.get("sitemap_urls", []),
                "error": None,
            }

        except Exception as e:
            logger.error("Failed to parse robots.txt: %s", e)
            return {
                "sitemap_urls": [],
                "error": str(e),
            }

    def _normalize_sitemap_url(self, url: str, base_url: str) -> str:
        """
        Нормалізує sitemap URL - перетворює відносний URL в абсолютний.

        Args:
            url: URL для нормалізації
            base_url: Базовий URL для конструювання абсолютного шляху

        Returns:
            Абсолютний URL або None якщо не вдалося нормалізувати
        """
        if not url:
            return None

        url = url.strip()
        if url.startswith(("http://", "https://")):
            return url

        # Відносний - перетворюємо в абсолютний
        return urljoin(base_url, url)

    def _should_process_sitemap(self, sitemap_url: str) -> tuple[bool, int]:
        """
        Перевіряє чи потрібно обробляти даний sitemap на основі url_rules.

        Args:
            sitemap_url: URL sitemap для перевірки

        Returns:
            Tuple (should_process, priority):
                - should_process: True якщо треба обробляти, False якщо skip
                - priority: пріоритет обробки (вищий = раніше)
        """
        if not self.url_rules:
            return True, 5  # Default: обробляти з нормальним пріоритетом

        should_process = None  # None = не визначено, використати default
        priority = 5  # Default priority

        # Проходимо всі правила
        for rule in self.url_rules:
            try:
                if re.search(rule.pattern, sitemap_url):
                    if rule.should_scan is not None:
                        should_process = rule.should_scan

                    # Оновлюємо пріоритет
                    if rule.priority is not None:
                        priority = max(priority, rule.priority)

                    logger.debug(
                        f"URL rule matched: {rule.pattern} for {sitemap_url} "
                        f"(should_scan={rule.should_scan}, priority={rule.priority})"
                    )

            except re.error as e:
                logger.warning("Invalid regex pattern in rule: %s - %s", rule.pattern, e)
                continue
        if should_process is None:
            should_process = True

        return should_process, priority

    def _sort_sitemaps_by_priority(self, sitemap_urls: list[str]) -> list[str]:
        """
        Сортує sitemap URLs за пріоритетом (від вищого до нижчого).

        Args:
            sitemap_urls: Список sitemap URLs

        Returns:
            Відсортований список sitemap URLs
        """
        if not self.url_rules:
            return sitemap_urls
        url_with_priority = []
        for url in sitemap_urls:
            should_process, priority = self._should_process_sitemap(url)
            url_with_priority.append((url, priority, should_process))

        # Сортуємо: спочаткуті що треба обробляти, потім за пріоритетом (від вищого)
        url_with_priority.sort(key=lambda x: (not x[2], -x[1]))

        # Повертаємо тільки URLs (без пріоритету)
        return [url for url, _, _ in url_with_priority]

    async def _process_sitemap(self, sitemap_url: str, parent_url: str, depth: int = 1):
        """
        Async обробляє один sitemap файл.

        Args:
            sitemap_url: URL sitemap
            parent_url: URL батьківського елементу
            depth: Глибина у графі

        ВИПРАВЛЕННЯ P0:
        - Додано захист від циклічних sitemap (_processed_sitemaps)
        - Додано timeout на asyncio.to_thread() (SITEMAP_PARSE_TIMEOUT)
        """
        # Нормалізуємо URL перед обробкою
        normalized_url = self._normalize_sitemap_url(sitemap_url, parent_url)

        if not normalized_url or not normalized_url.startswith(("http://", "https://")):
            logger.error(
                f"Invalid sitemap URL after normalization: {sitemap_url} -> {normalized_url}"
            )
            # НЕ падаємо - просто логуємо та пропускаємо
            return

        sitemap_url = normalized_url
        if sitemap_url in self._processed_sitemaps:
            logger.warning("Cycle detected! Skipping already processed sitemap: %s", sitemap_url)
            self.sitemaps_skipped += 1
            return

        # Додаємо до множини оброблених ДО обробки (щоб уникнути race condition)
        self._processed_sitemaps.add(sitemap_url)
        should_process, priority = self._should_process_sitemap(sitemap_url)

        if not should_process:
            logger.info("Skipping sitemap (url_rules): %s", sitemap_url)
            self.sitemaps_skipped += 1
            return
        if depth > self.config.max_depth:
            logger.info("Skipping sitemap (max_depth=%s): %s", self.config.max_depth, sitemap_url)
            self.sitemaps_skipped += 1
            return
        if self.max_sitemaps and self.sitemaps_processed >= self.max_sitemaps:
            logger.info("Skipping sitemap (max_sitemaps=%s): %s", self.max_sitemaps, sitemap_url)
            self.sitemaps_skipped += 1
            return

        logger.info("Processing sitemap: %s (depth=%s, priority=%s)", sitemap_url, depth, priority)

        try:
            # Раніше asyncio.to_thread() міг зависати назавжди
            try:
                sitemap_data = await asyncio.wait_for(
                    asyncio.to_thread(self.parser.parse_sitemap, sitemap_url),
                    timeout=SITEMAP_PARSE_TIMEOUT,
                )
            except asyncio.TimeoutError:
                logger.warning("Timeout parsing sitemap (%ss): %s", SITEMAP_PARSE_TIMEOUT, sitemap_url)
                self.processor.create_error_node(
                    url=sitemap_url,
                    parent_url=parent_url,
                    error_message=f"Timeout ({SITEMAP_PARSE_TIMEOUT}s)",
                    depth=depth,
                )
                return
            has_nested_sitemaps = len(sitemap_data.get("sitemap_indexes", [])) > 0
            has_urls = len(sitemap_data.get("urls", [])) > 0

            if not has_nested_sitemaps and not has_urls:
                # Порожній або невалідний sitemap - логуємо але НЕ падаємо
                logger.warning("Empty or invalid sitemap: %s", sitemap_url)
                try:
                    self.processor.create_error_node(
                        url=sitemap_url,
                        parent_url=parent_url,
                        error_message="Empty or invalid sitemap",
                        depth=depth,
                    )
                except Exception as e:
                    logger.warning("Failed to create error node for %s: %s", sitemap_url, e)
                return

            # Випадок 1: Sitemap Index (містить посилання на інші sitemaps)
            if has_nested_sitemaps:
                nested_sitemap_urls = sitemap_data["sitemap_indexes"]
                self.processor.create_sitemap_index_node(
                    url=sitemap_url,
                    parent_url=parent_url,
                    sitemap_urls=nested_sitemap_urls,
                    depth=depth,
                )

                self.sitemaps_processed += 1

                # Сортуємо вкладені sitemaps за пріоритетом якщо є url_rules
                if self.url_rules:
                    nested_sitemap_urls = self._sort_sitemaps_by_priority(nested_sitemap_urls)
                    logger.debug("Sorted %s nested sitemaps by priority", len(nested_sitemap_urls))

                # Рекурсивно обробляємо вкладені sitemaps
                for nested_sitemap_url in nested_sitemap_urls:
                    try:
                        if self._max_urls_reached:
                            logger.info("Stopping nested processing: max_urls limit reached")
                            break
                        if self.max_sitemaps and self.sitemaps_processed >= self.max_sitemaps:
                            logger.info("Reached max_sitemaps limit during nested processing")
                            break

                        await self._process_sitemap(
                            nested_sitemap_url, parent_url=sitemap_url, depth=depth + 1
                        )
                    except Exception as e:
                        logger.error("Error processing nested sitemap %s: %s", nested_sitemap_url, e)
                        # Продовжуємо з наступним, не падаємо

            # Випадок 2: Звичайний Sitemap (містить URLs)
            elif has_urls:
                url_list = sitemap_data["urls"]
                self.processor.create_sitemap_node(
                    url=sitemap_url,
                    parent_url=parent_url,
                    url_list=url_list,
                    depth=depth,
                )

                self.sitemaps_processed += 1
                if self.include_urls:
                    url_nodes = self.processor.create_url_nodes(
                        url_list=url_list,
                        parent_sitemap_url=sitemap_url,
                        depth=depth + 1,
                        max_urls=self.max_urls,
                    )
                    self.urls_extracted += len(url_nodes)
                    if self.max_urls and self.urls_extracted >= self.max_urls:
                        logger.info("Reached max_urls limit: %s. Stopping crawl.", self.max_urls)
                        self._max_urls_reached = True
                        return

        except Exception as e:
            logger.error("Error processing sitemap %s: %s", sitemap_url, e)
            # Ловимо всі винятки та продовжуємо роботу
            try:
                self.processor.create_error_node(
                    url=sitemap_url,
                    parent_url=parent_url,
                    error_message=str(e),
                    depth=depth,
                )
            except Exception as inner_e:
                # Навіть якщо не вдалося створити error node - не падаємо
                logger.error("Failed to create error node: %s", inner_e)

    def get_stats(self) -> dict:
        """
        Повертає статистику краулінгу.

        Returns:
            Dict зі статистикою
        """
        stats = self.graph.get_stats()
        stats["sitemaps_processed"] = self.sitemaps_processed
        stats["sitemaps_skipped"] = self.sitemaps_skipped
        stats["urls_extracted"] = self.urls_extracted
        stats["url_rules_count"] = len(self.url_rules)
        return stats

    async def close(self) -> None:
        """Async закриває ресурси Spider."""
        await self.driver.close()
        logger.info("SitemapSpider closed")
