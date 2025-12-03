"""Плагін для витягування метаданих з HTML.

Витягує:
- title
- description (meta)
- keywords (meta)
- h1
"""

import logging

from graph_crawler.extensions.plugins.node.base import (
    BaseNodePlugin,
    NodePluginContext,
    NodePluginType,
)
from graph_crawler.shared.constants import (
    MAX_DESCRIPTION_LENGTH,
    MAX_H1_LENGTH,
    MAX_KEYWORDS_LENGTH,
    MAX_TITLE_LENGTH,
)

logger = logging.getLogger(__name__)


class MetadataExtractorPlugin(BaseNodePlugin):
    """
    Дефолтний плагін для витягування метаданих з HTML.

    Витягує:
    - title
    - description (meta)
    - keywords (meta)
    - h1

    Цей плагін можна:
    - Підключити (дефолтно увімкнено)
    - Відключити (config={'enabled': False})
    - Замінити на свій власний плагін

    Приклад відключення:
        config = CrawlerConfig(
            url="...",
            node_plugins=[
                MetadataExtractorPlugin(config={'enabled': False})
            ]
        )
    """

    @property
    def plugin_type(self) -> NodePluginType:
        return NodePluginType.ON_HTML_PARSED

    @property
    def name(self) -> str:
        return "MetadataExtractorPlugin"

    def execute(self, context: NodePluginContext) -> NodePluginContext:
        """Витягує метадані з HTML дерева. Оптимізовано - мінімум DOM операцій."""
        # Перевірка чи не пропущено витягування метаданих
        if context.skip_metadata_extraction:
            logger.debug(f"Skipping metadata extraction for {context.url}")
            return context

        # Перевірка наявності parser
        if not context.parser:
            logger.warning(f"No parser for metadata extraction: {context.url}")
            return context

        try:
            parser = context.parser

            meta_tags = {
                elem.get_attribute("name"): elem.get_attribute("content")
                for elem in parser.find_all("meta[name]")
                if elem.get_attribute("name") in ("description", "keywords")
            }

            # Title
            if title_elem := parser.find("title"):
                if title_text := title_elem.text():
                    context.set_metadata(
                        "title", self._sanitize_text(title_text, MAX_TITLE_LENGTH)
                    )

            # Description та Keywords з кешу
            if desc := meta_tags.get("description"):
                context.set_metadata(
                    "description", self._sanitize_text(desc, MAX_DESCRIPTION_LENGTH)
                )
            if keywords := meta_tags.get("keywords"):
                context.set_metadata(
                    "keywords", self._sanitize_text(keywords, MAX_KEYWORDS_LENGTH)
                )

            # H1
            if h1_elem := parser.find("h1"):
                if h1_text := h1_elem.text():
                    context.set_metadata(
                        "h1", self._sanitize_text(h1_text, MAX_H1_LENGTH)
                    )

            logger.debug(
                f"Extracted metadata for {context.url}: {list(context.metadata.keys())}"
            )

        except Exception as e:
            logger.error(f"Error extracting metadata for {context.url}: {e}")

        return context

    @staticmethod
    def _sanitize_text(text: str, max_length: int) -> str:
        """Санітизує текст: видаляє зайві пробіли та обмежує довжину."""
        if not text:
            return ""

        # Видаляємо зайві пробіли
        text = " ".join(text.split())

        # Обмежуємо довжину
        if len(text) > max_length:
            text = text[:max_length] + "..."

        return text
