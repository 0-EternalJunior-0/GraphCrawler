"""SitemapSpider - спеціалізований spider для краулінгу sitemap структури .
- crawl() тепер async
- Внутрішні методи async де потрібно
- Async context manager підтримка
"""

import asyncio
import logging
import time
from typing import Optional
from urllib.parse import urljoin

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
from graph_crawler.domain.value_objects.configs import CrawlerConfig
from graph_crawler.infrastructure.persistence.base import BaseStorage
from graph_crawler.infrastructure.transport.base import BaseDriver

logger = logging.getLogger(__name__)


class SitemapSpider(BaseSpider):
    """
    Async-First Spider для краулінгу sitemap структури .

    Responsibilities:
    - Координує процес краулінгу sitemap
    - Використовує SitemapParser для парсингу XML
    - Делегує обробку даних до SitemapProcessor
    - Публікує події через EventBus

    Архітектура (Single Responsibility):
    - SitemapSpider - координує процес
    - SitemapParser - парсить XML файли
    - SitemapProcessor - будує граф
    - EventBus - публікація подій

    Граф структура:
        robots.txt (root)
            ↓
        sitemap_index.xml
            ↓
         sitemap-posts.xml (URLs: 100)
         sitemap-pages.xml (URLs: 50)
         sitemap-products.xml (URLs: 200)

    Example:
        >>> async with SitemapSpider(config, driver, storage) as spider:
        ...     graph = await spider.crawl()
        ...     print(f"Sitemaps: {spider.sitemaps_processed}")
    """

    def __init__(
        self,
        config: CrawlerConfig,
        driver: BaseDriver,
        storage: BaseStorage,
        event_bus: Optional[EventBus] = None,
        graph: Optional[Graph] = None,
        parser: Optional[SitemapParser] = None,
        processor: Optional[SitemapProcessor] = None,
        include_urls: bool = True,
        max_urls: Optional[int] = None,
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
        """
        super().__init__(config, driver, storage, event_bus)

        # DI: Graph (fallback якщо не передано)
        self.graph = graph if graph is not None else Graph()
        self.include_urls = include_urls
        self.max_urls = max_urls

        # DI: Parser (fallback якщо не передано)
        self.parser = (
            parser
            if parser is not None
            else SitemapParser(user_agent=config.get_user_agent())
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

        logger.info(
            f"SitemapSpider (async) initialized: "
            f"graph={'injected' if graph else 'created'}, "
            f"parser={'injected' if parser else 'created'}, "
            f"processor={'injected' if processor else 'created'}"
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

        # Подія початку краулінгу
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

        logger.info(f"Starting async sitemap crawl: {self.config.url}")
        logger.info(
            f"Config: include_urls={self.include_urls}, max_urls={self.max_urls}"
        )

        try:
            # Крок 1: Парсимо robots.txt та отримуємо sitemap URLs
            robots_url = urljoin(self.config.url, "/robots.txt")
            sitemap_data = await self._parse_robots_txt(robots_url)

            # Крок 2: Створюємо Node для robots.txt
            robots_node = self.processor.create_robots_node(
                url=robots_url,
                sitemap_urls=sitemap_data.get("sitemap_urls", []),
                error=sitemap_data.get("error"),
            )

            # Крок 3: Обробляємо кожен знайдений sitemap
            sitemap_urls = sitemap_data.get("sitemap_urls", [])
            if sitemap_urls:
                for sitemap_url in sitemap_urls:
                    await self._process_sitemap(
                        sitemap_url, parent_url=robots_url, depth=1
                    )
            else:
                logger.warning(
                    f"No sitemaps found in robots.txt. Graph contains only robots.txt node."
                )

            # Завершення
            duration = time.time() - start_time
            stats = self.graph.get_stats()

            logger.info(f"Sitemap crawl completed in {duration:.2f}s")
            logger.info(f"Stats: {stats}")
            logger.info(f"Sitemaps processed: {self.sitemaps_processed}")
            logger.info(f"URLs extracted: {self.urls_extracted}")

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
            logger.error(f"Sitemap crawl error: {e}", exc_info=True)

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
            logger.info(f"Parsing robots.txt: {robots_url}")
            base_url = robots_url.replace("/robots.txt", "")

            # Parser.parse_from_robots використовує requests (sync)
            # В майбутньому можна оптимізувати через aiohttp
            result = await asyncio.to_thread(self.parser.parse_from_robots, base_url)

            return {
                "sitemap_urls": result.get("sitemap_urls", []),
                "error": None,
            }

        except Exception as e:
            logger.error(f"Failed to parse robots.txt: {e}")
            return {
                "sitemap_urls": [],
                "error": str(e),
            }

    async def _process_sitemap(self, sitemap_url: str, parent_url: str, depth: int = 1):
        """
        Async обробляє один sitemap файл.

        Args:
            sitemap_url: URL sitemap
            parent_url: URL батьківського елементу
            depth: Глибина у графі
        """
        logger.info(f"Processing sitemap: {sitemap_url}")

        try:
            # Парсимо sitemap (sync операція в thread)
            sitemap_data = await asyncio.to_thread(
                self.parser.parse_sitemap, sitemap_url
            )

            # Перевіряємо що знайдено
            has_nested_sitemaps = len(sitemap_data.get("sitemap_indexes", [])) > 0
            has_urls = len(sitemap_data.get("urls", [])) > 0

            if not has_nested_sitemaps and not has_urls:
                # Порожній або невалідний sitemap
                logger.warning(f"Empty or invalid sitemap: {sitemap_url}")
                self.processor.create_error_node(
                    url=sitemap_url,
                    parent_url=parent_url,
                    error_message="Empty or invalid sitemap",
                    depth=depth,
                )
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

                # Рекурсивно обробляємо вкладені sitemaps
                for nested_sitemap_url in nested_sitemap_urls:
                    await self._process_sitemap(
                        nested_sitemap_url, parent_url=sitemap_url, depth=depth + 1
                    )

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

                # Створюємо Node для кожного URL (якщо include_urls=True)
                if self.include_urls:
                    url_nodes = self.processor.create_url_nodes(
                        url_list=url_list,
                        parent_sitemap_url=sitemap_url,
                        depth=depth + 1,
                        max_urls=self.max_urls,
                    )
                    self.urls_extracted += len(url_nodes)

                    # Перевіряємо ліміт URL
                    if self.max_urls and self.urls_extracted >= self.max_urls:
                        logger.info(f"Reached max_urls limit: {self.max_urls}")
                        return

        except Exception as e:
            logger.error(f"Error processing sitemap {sitemap_url}: {e}")
            self.processor.create_error_node(
                url=sitemap_url,
                parent_url=parent_url,
                error_message=str(e),
                depth=depth,
            )

    def get_stats(self) -> dict:
        """
        Повертає статистику краулінгу.

        Returns:
            Dict зі статистикою
        """
        stats = self.graph.get_stats()
        stats["sitemaps_processed"] = self.sitemaps_processed
        stats["urls_extracted"] = self.urls_extracted
        return stats

    async def close(self) -> None:
        """Async закриває ресурси Spider."""
        await self.driver.close()
        logger.info("SitemapSpider closed")
