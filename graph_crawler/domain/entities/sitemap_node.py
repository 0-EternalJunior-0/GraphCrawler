"""Спеціалізований Node для sitemap структури."""

import logging
from typing import Literal, Optional

from pydantic import Field

from graph_crawler.domain.entities.node import Node

logger = logging.getLogger(__name__)


class SitemapNode(Node):
    """
    Спеціалізований Node для представлення елементів sitemap структури.

    Розширює базовий Node додатковими полями специфічними для sitemap:
    - Тип вузла (robots.txt, sitemap index, sitemap, URL)
    - Тип файлу (xml, xml.gz, text)
    - Інформація про батьківський sitemap
    - Кількість URL у sitemap
    - Повідомлення про помилки

    Приклад використання:
        >>> # Robots.txt node
        >>> robots = SitemapNode(
        ...     url="https://example.com/robots.txt",
        ...     node_type="robots_txt"
        ... )
        >>>
        >>> # Sitemap index node
        >>> sitemap_index = SitemapNode(
        ...     url="https://example.com/sitemap.xml",
        ...     node_type="sitemap_index",
        ...     urls_count=6,
        ...     parent_sitemap="https://example.com/robots.txt"
        ... )
        >>>
        >>> # Regular sitemap node
        >>> sitemap = SitemapNode(
        ...     url="https://example.com/sitemap-posts.xml",
        ...     node_type="sitemap",
        ...     sitemap_type="xml",
        ...     urls_count=150,
        ...     parent_sitemap="https://example.com/sitemap.xml"
        ... )
        >>>
        >>> # URL node
        >>> url_node = SitemapNode(
        ...     url="https://example.com/post/123",
        ...     node_type="url",
        ...     parent_sitemap="https://example.com/sitemap-posts.xml"
        ... )
        >>>
        >>> # Error node (404 sitemap)
        >>> error_sitemap = SitemapNode(
        ...     url="https://example.com/missing.xml",
        ...     node_type="sitemap",
        ...     error_message="404 Not Found"
        ... )
    """

    # Тип вузла в sitemap ієрархії
    node_type: Literal["robots_txt", "sitemap_index", "sitemap", "url"] = Field(
        default="url", description="Тип вузла в sitemap структурі"
    )

    # Тип sitemap файлу (якщо це sitemap)
    sitemap_type: Optional[Literal["xml", "xml.gz", "text"]] = Field(
        default=None, description="Тип sitemap файлу (xml, xml.gz, text)"
    )

    # URL батьківського sitemap
    parent_sitemap: Optional[str] = Field(
        default=None, description="URL батьківського sitemap або robots.txt"
    )

    # Кількість URL у sitemap (якщо це sitemap або sitemap_index)
    urls_count: Optional[int] = Field(
        default=None, ge=0, description="Кількість URL у цьому sitemap"
    )

    # Повідомлення про помилку (якщо є)
    error_message: Optional[str] = Field(
        default=None, description="Повідомлення про помилку (404, parse error тощо)"
    )

    def is_robots_txt(self) -> bool:
        """Перевіряє чи це robots.txt."""
        return self.node_type == "robots_txt"

    def is_sitemap_index(self) -> bool:
        """Перевіряє чи це sitemap index (містить посилання на інші sitemaps)."""
        return self.node_type == "sitemap_index"

    def is_sitemap(self) -> bool:
        """Перевіряє чи це звичайний sitemap (містить URLs)."""
        return self.node_type == "sitemap"

    def is_url(self) -> bool:
        """Перевіряє чи це кінцевий URL зі sitemap."""
        return self.node_type == "url"

    def has_error(self) -> bool:
        """Перевіряє чи є помилка."""
        return self.error_message is not None

    def is_gzipped(self) -> bool:
        """Перевіряє чи це gzip sitemap."""
        return self.sitemap_type == "xml.gz" or (self.url and self.url.endswith(".gz"))

    def __repr__(self):
        parts = [f"url={self.url}"]
        parts.append(f"type={self.node_type}")

        if self.urls_count is not None:
            parts.append(f"urls={self.urls_count}")

        if self.error_message:
            parts.append(f"error='{self.error_message}'")

        return f"SitemapNode({', '.join(parts)})"
