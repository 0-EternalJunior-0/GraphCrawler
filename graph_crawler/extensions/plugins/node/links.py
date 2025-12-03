"""Плагін для витягування посилань з HTML.

- Використовує URLUtils.is_special_link() замість локальної функції
- List comprehension для швидшої обробки
- Мінімізація викликів URLUtils методів
"""

import logging
from typing import Any, Dict, List

from graph_crawler.extensions.plugins.node.base import (
    BaseNodePlugin,
    NodePluginContext,
    NodePluginType,
)
from graph_crawler.shared.utils.url_utils import URLUtils

logger = logging.getLogger(__name__)


class LinkExtractorPlugin(BaseNodePlugin):
    """
    Дефолтний плагін для витягування посилань з HTML.

    - Використовує кешовані методи URLUtils
    - List comprehension для швидшої обробки
    - Мінімізовані перевірки

    Цей плагін можна:
    - Підключити (дефолтно увімкнено)
    - Відключити (config={'enabled': False})
    - Налаштувати (config={'extract_images': True})
    """

    @property
    def plugin_type(self) -> NodePluginType:
        return NodePluginType.ON_HTML_PARSED

    @property
    def name(self) -> str:
        return "LinkExtractorPlugin"

    def execute(self, context: NodePluginContext) -> NodePluginContext:
        """Витягує посилання з HTML дерева."""
        # Перевірка чи не пропущено витягування посилань
        if context.skip_link_extraction:
            logger.debug(f"Skipping link extraction for {context.url}")
            return context

        # Перевірка наявності parser
        if not context.parser:
            logger.warning(f"No parser for link extraction: {context.url}")
            return context

        try:
            links = self._extract_all_links(context)
            context.extracted_links = links
            logger.debug(f"Extracted {len(links)} links from {context.url}")

        except Exception as e:
            logger.error(f"Error extracting links for {context.url}: {e}")

        return context

    def _extract_all_links(self, context: NodePluginContext) -> List[str]:
        """
        ОПТИМІЗОВАНО: Витягує всі посилання з HTML дерева.

        Args:
            context: Контекст з parser та URL

        Returns:
            Список абсолютних URL
        """
        links = self._extract_anchor_links(context)

        # Опціонально: витягуємо зображення
        if self.config.get("extract_images", False):
            links.extend(self._extract_image_links(context))

        # Опціонально: витягуємо iframe
        if self.config.get("extract_iframes", False):
            links.extend(self._extract_iframe_links(context))

        return links

    def _extract_anchor_links(self, context: NodePluginContext) -> List[str]:
        """
        ОПТИМІЗОВАНО Витягує посилання з <a href> тегів.

        Оптимізації:
        - Один прохід через list comprehension
        - Використання URLUtils.is_special_link() (кешована)
        - URLUtils.is_valid_url() з кешем

        Args:
            context: Контекст з parser та URL

        Returns:
            Список валідних абсолютних URL
        """
        base_url = context.url
        a_elements = context.parser.find_all("a[href]")

        # List comprehension + walrus operator
        # Один прохід замість кількох циклів
        links = []
        for a_elem in a_elements:
            href = a_elem.get_attribute("href")
            if not href:
                continue
            # Швидка перевірка special links (без urlparse)
            if URLUtils.is_special_link(href):
                continue
            # Конвертуємо в абсолютний URL
            absolute_url = URLUtils.make_absolute(base_url, href)
            # Перевіряємо валідність (кешовано)
            if URLUtils.is_valid_url(absolute_url):
                links.append(absolute_url)

        return links

    def _extract_image_links(self, context: NodePluginContext) -> List[str]:
        """
        Витягує посилання з <img src> тегів.
        """
        base_url = context.url
        return [
            absolute_url
            for img_elem in context.parser.find_all("img[src]")
            if (src := img_elem.get_attribute("src"))
            and (absolute_url := URLUtils.make_absolute(base_url, src))
            and URLUtils.is_valid_url(absolute_url)
        ]

    def _extract_iframe_links(self, context: NodePluginContext) -> List[str]:
        """
        Витягує посилання з <iframe src> тегів.
        """
        base_url = context.url
        return [
            absolute_url
            for iframe_elem in context.parser.find_all("iframe[src]")
            if (src := iframe_elem.get_attribute("src"))
            and (absolute_url := URLUtils.make_absolute(base_url, src))
            and URLUtils.is_valid_url(absolute_url)
        ]
