"""Processor для обробки sitemap даних та побудови графу."""

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from graph_crawler.domain.entities.edge import Edge
from graph_crawler.domain.entities.graph import Graph
from graph_crawler.domain.entities.sitemap_node import SitemapNode
from graph_crawler.domain.events import CrawlerEvent, EventBus, EventType

logger = logging.getLogger(__name__)


class SitemapProcessor:
    """
    Обробляє дані з sitemap та будує граф структуру.

    Відповідальності:
    - Створення SitemapNode для різних типів (robots, sitemap, url)
    - Створення Edge між батьківським та дочірнім елементом
    - Розпізнавання типу sitemap (index vs urlset)
    - Обробка помилок (404, invalid XML)
    - Публікація подій через EventBus

    Архітектура (Single Responsibility):
    - SitemapSpider - координує процес краулінгу
    - SitemapProcessor - обробляє дані та будує граф (цей клас)
    - SitemapParser - парсить XML файли
    """

    def __init__(
        self,
        graph: Graph,
        event_bus: Optional[EventBus] = None,
        include_urls: bool = True,
    ):
        """
        Ініціалізує processor.

        Args:
            graph: Граф для додавання вузлів та ребер
            event_bus: EventBus для публікації подій
            include_urls: Чи додавати кінцеві URL до графу (False = тільки структура sitemap)
        """
        self.graph = graph
        self.event_bus = event_bus or EventBus()
        self.include_urls = include_urls

    def create_robots_node(
        self, url: str, sitemap_urls: List[str], error: Optional[str] = None
    ) -> SitemapNode:
        """
        Створює Node для robots.txt.

        Args:
            url: URL robots.txt
            sitemap_urls: Список знайдених sitemap URLs
            error: Повідомлення про помилку (якщо є)

        Returns:
            SitemapNode для robots.txt
        """
        node = SitemapNode(
            url=url,
            node_type="robots_txt",
            urls_count=len(sitemap_urls),
            error_message=error,
            depth=0,
            should_scan=True,
            can_create_edges=True,
        )

        self.graph.add_node(node)
        logger.info(f"Created robots.txt node: {url} ({len(sitemap_urls)} sitemaps)")

        # Публікуємо подію
        self.event_bus.publish(
            CrawlerEvent.create(
                EventType.ROBOTS_TXT_PARSED,
                data={"url": url, "sitemap_count": len(sitemap_urls), "error": error},
            )
        )

        return node

    def create_sitemap_index_node(
        self,
        url: str,
        parent_url: str,
        sitemap_urls: List[str],
        depth: int = 1,
        error: Optional[str] = None,
    ) -> SitemapNode:
        """
        Створює Node для sitemap index (містить посилання на інші sitemaps).

        Args:
            url: URL sitemap index
            parent_url: URL батьківського елементу
            sitemap_urls: Список вкладених sitemap URLs
            depth: Глибина у графі
            error: Повідомлення про помилку (якщо є)

        Returns:
            SitemapNode для sitemap index
        """
        sitemap_type = self._detect_sitemap_type(url)

        node = SitemapNode(
            url=url,
            node_type="sitemap_index",
            sitemap_type=sitemap_type,
            parent_sitemap=parent_url,
            urls_count=len(sitemap_urls),
            error_message=error,
            depth=depth,
            should_scan=True,
            can_create_edges=True,
        )

        self.graph.add_node(node)
        logger.info(
            f"Created sitemap_index node: {url} ({len(sitemap_urls)} nested sitemaps)"
        )

        # Публікуємо подію
        self.event_bus.publish(
            CrawlerEvent.create(
                EventType.SITEMAP_INDEX_FOUND,
                data={
                    "url": url,
                    "parent": parent_url,
                    "nested_count": len(sitemap_urls),
                    "error": error,
                },
            )
        )

        # Створюємо Edge від батьківського елементу
        parent_node = self.graph.get_node_by_url(parent_url)
        if parent_node:
            edge = Edge(source_node_id=parent_node.node_id, target_node_id=node.node_id)
            edge.add_metadata("edge_type", "contains")
            self.graph.add_edge(edge)

        return node

    def create_sitemap_node(
        self,
        url: str,
        parent_url: str,
        url_list: List[str],
        depth: int = 1,
        error: Optional[str] = None,
    ) -> SitemapNode:
        """
        Створює Node для звичайного sitemap (містить URLs).

        Args:
            url: URL sitemap
            parent_url: URL батьківського елементу
            url_list: Список URLs з sitemap
            depth: Глибина у графі
            error: Повідомлення про помилку (якщо є)

        Returns:
            SitemapNode для sitemap
        """
        sitemap_type = self._detect_sitemap_type(url)

        node = SitemapNode(
            url=url,
            node_type="sitemap",
            sitemap_type=sitemap_type,
            parent_sitemap=parent_url,
            urls_count=len(url_list),
            error_message=error,
            depth=depth,
            should_scan=True,
            can_create_edges=True,
        )

        self.graph.add_node(node)
        logger.info(f"Created sitemap node: {url} ({len(url_list)} URLs)")

        # Публікуємо подію
        self.event_bus.publish(
            CrawlerEvent.create(
                EventType.SITEMAP_PARSED,
                data={
                    "url": url,
                    "parent": parent_url,
                    "url_count": len(url_list),
                    "error": error,
                },
            )
        )

        # Створюємо Edge від батьківського елементу
        parent_node = self.graph.get_node_by_url(parent_url)
        if parent_node:
            edge = Edge(source_node_id=parent_node.node_id, target_node_id=node.node_id)
            edge.add_metadata("edge_type", "contains")
            self.graph.add_edge(edge)

        return node

    def create_url_nodes(
        self,
        url_list: List[str],
        parent_sitemap_url: str,
        depth: int = 2,
        max_urls: Optional[int] = None,
    ) -> List[SitemapNode]:
        """
        Створює Node для кожного URL зі sitemap.

        Args:
            url_list: Список URLs
            parent_sitemap_url: URL батьківського sitemap
            depth: Глибина у графі
            max_urls: Максимальна кількість URL для обробки (None = всі)

        Returns:
            Список створених SitemapNode
        """
        if not self.include_urls:
            logger.debug(f"Skipping URL nodes creation (include_urls=False)")
            return []

        # Обмежуємо кількість URL якщо потрібно
        urls_to_process = url_list[:max_urls] if max_urls else url_list

        if max_urls and len(url_list) > max_urls:
            logger.info(f"Limiting URLs: {len(url_list)} → {max_urls}")

        nodes = []
        parent_node = self.graph.get_node_by_url(parent_sitemap_url)

        for url in urls_to_process:
            # Перевіряємо чи вже є такий URL у графі
            existing_node = self.graph.get_node_by_url(url)
            if existing_node:
                logger.debug(f"URL already in graph: {url}")
                continue

            node = SitemapNode(
                url=url,
                node_type="url",
                parent_sitemap=parent_sitemap_url,
                depth=depth,
                should_scan=False,  # URL вузли не сканують (це кінцеві точки)
                can_create_edges=False,
            )

            self.graph.add_node(node)
            nodes.append(node)

            # Створюємо Edge від батьківського sitemap
            if parent_node:
                edge = Edge(
                    source_node_id=parent_node.node_id, target_node_id=node.node_id
                )
                edge.add_metadata("edge_type", "contains")
                self.graph.add_edge(edge)

            # Публікуємо подію для кожного URL
            self.event_bus.publish(
                CrawlerEvent.create(
                    EventType.URL_EXTRACTED,
                    data={"url": url, "parent_sitemap": parent_sitemap_url},
                )
            )

        logger.info(f"Created {len(nodes)} URL nodes from {parent_sitemap_url}")
        return nodes

    def create_error_node(
        self, url: str, parent_url: Optional[str], error_message: str, depth: int = 1
    ) -> SitemapNode:
        """
        Створює Node з помилкою (404, parse error тощо).

        Args:
            url: URL елементу з помилкою
            parent_url: URL батьківського елементу
            error_message: Повідомлення про помилку
            depth: Глибина у графі

        Returns:
            SitemapNode з помилкою
        """
        # Визначаємо тип на основі URL
        if url.endswith("robots.txt"):
            node_type = "robots_txt"
        elif "sitemap" in url.lower():
            node_type = "sitemap"
        else:
            node_type = "url"

        node = SitemapNode(
            url=url,
            node_type=node_type,
            parent_sitemap=parent_url,
            error_message=error_message,
            depth=depth,
            should_scan=False,
            can_create_edges=False,
        )

        self.graph.add_node(node)
        logger.warning(f"Created error node: {url} - {error_message}")

        # Публікуємо подію про помилку
        self.event_bus.publish(
            CrawlerEvent.create(
                EventType.SITEMAP_ERROR,
                data={"url": url, "parent": parent_url, "error": error_message},
            )
        )

        # Створюємо Edge від батьківського елементу якщо є
        if parent_url:
            parent_node = self.graph.get_node_by_url(parent_url)
            if parent_node:
                edge = Edge(
                    source_node_id=parent_node.node_id, target_node_id=node.node_id
                )
                edge.add_metadata("edge_type", "contains")
                self.graph.add_edge(edge)

        return node

    def _detect_sitemap_type(self, url: str) -> str:
        """
        Визначає тип sitemap за URL.

        Args:
            url: URL sitemap

        Returns:
            Тип: "xml.gz", "xml", або "text"
        """
        url_lower = url.lower()

        if url_lower.endswith(".xml.gz") or url_lower.endswith(".gz"):
            return "xml.gz"
        elif url_lower.endswith(".xml"):
            return "xml"
        else:
            return "text"
