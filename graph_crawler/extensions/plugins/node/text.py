"""Плагін для витягування текстового контенту з HTML.

Витягує весь текст без HTML тегів для:
- Векторизації
- Пошуку по ключових словах
- Аналізу контенту
"""

import logging
from typing import Any, Dict

from graph_crawler.extensions.plugins.node.base import (
    BaseNodePlugin,
    NodePluginContext,
    NodePluginType,
)
from graph_crawler.shared.constants import MAX_TEXT_LENGTH

logger = logging.getLogger(__name__)


class TextExtractorPlugin(BaseNodePlugin):
    """
    Плагін для витягування текстового контенту з HTML.

    Витягує весь текст без HTML тегів для:
    - Векторизації
    - Пошуку по ключових словах
    - Аналізу контенту

    За замовчуванням ВІДКЛЮЧЕНИЙ (не потрібен для базового краулінгу).

    Приклад використання:
        config = CrawlerConfig(
            url="...",
            node_plugins=[
                TextExtractorPlugin(config={'enabled': True, 'max_length': 100000})
            ]
        )
    """

    def __init__(self, config: Dict[str, Any] = None):
        """Ініціалізує TextExtractorPlugin."""
        super().__init__(config)
        # За замовчуванням ВІДКЛЮЧЕНИЙ
        self.enabled = config.get("enabled", False) if config else False

    @property
    def plugin_type(self) -> NodePluginType:
        return NodePluginType.ON_HTML_PARSED

    @property
    def name(self) -> str:
        return "TextExtractorPlugin"

    def execute(self, context: NodePluginContext) -> NodePluginContext:
        """Витягує текстовий контент."""
        if not context.parser:
            return context

        try:
            parser = context.parser
            text = parser.text  # Використовуємо property adapter.text

            # Обмежуємо довжину
            max_length = self.config.get("max_length", MAX_TEXT_LENGTH)
            if len(text) > max_length:
                text = text[:max_length]

            context.user_data["text_content"] = text
            logger.debug(f"Extracted {len(text)} characters of text from {context.url}")

        except Exception as e:
            logger.error(f"Error extracting text for {context.url}: {e}")

        return context
