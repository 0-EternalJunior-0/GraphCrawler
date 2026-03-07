"""Парсер Open Graph мікророзмітки."""

import logging
from typing import Any, Dict, Union

from graph_crawler.extensions.plugins.node.structured_data.exceptions import ParserError
from graph_crawler.extensions.plugins.node.structured_data.options import StructuredDataOptions

logger = logging.getLogger(__name__)


class OpenGraphParser:
    """
    Парсер Open Graph (Facebook) мікророзмітки.

    Витягує мета-теги з property="og:*".
    Практично на кожному сайті (95% поширеність).
    """

    @property
    def name(self) -> str:
        return "opengraph"

    def can_parse(self, source: Union[str, Any]) -> bool:
        """Перевіряє чи джерело є parser adapter."""
        return hasattr(source, 'find_all')

    def parse(
        self,
        source: Union[str, Any],
        options: StructuredDataOptions
    ) -> Dict[str, str]:
        """
        Парсить Open Graph теги.

        Args:
            source: Parser adapter (context.parser)
            options: Налаштування

        Returns:
            Dict з OG властивостями (без "og:" префіксу)
        """
        if not hasattr(source, 'find_all'):
            raise ParserError(self.name, "Source must be parser adapter")

        result = {}

        try:
            # Шукаємо всі meta теги з property="og:*"
            for elem in source.find_all('meta[property^="og:"]'):
                prop = elem.get_attribute('property')
                content = elem.get_attribute('content')

                if prop and content:
                    # Видаляємо "og:" префікс
                    key = prop.replace('og:', '')
                    result[key] = self._sanitize_value(content)

        except Exception as e:
            logger.warning(f"Error parsing Open Graph: {e}")

        return result

    def _sanitize_value(self, value: str, max_length: int = 10000) -> str:
        """Санітизація значень."""
        if not value:
            return ""
        value = " ".join(value.split())  # Нормалізація пробілів
        if len(value) > max_length:
            value = value[:max_length] + "..."
        return value
