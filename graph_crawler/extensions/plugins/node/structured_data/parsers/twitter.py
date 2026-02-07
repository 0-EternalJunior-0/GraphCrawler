"""Парсер Twitter Cards мікророзмітки."""

import logging
from typing import Any, Dict, Union

from graph_crawler.extensions.plugins.node.structured_data.options import StructuredDataOptions
from graph_crawler.extensions.plugins.node.structured_data.exceptions import ParserError

logger = logging.getLogger(__name__)


class TwitterCardsParser:
    """
    Парсер Twitter Cards мікророзмітки.
    
    Витягує мета-теги з name="twitter:*".
    Поширеність ~70% сайтів.
    """
    
    @property
    def name(self) -> str:
        return "twitter"
    
    def can_parse(self, source: Union[str, Any]) -> bool:
        """Перевіряє чи джерело є parser adapter."""
        return hasattr(source, 'find_all')
    
    def parse(
        self, 
        source: Union[str, Any],
        options: StructuredDataOptions
    ) -> Dict[str, str]:
        """
        Парсить Twitter Cards теги.
        
        Args:
            source: Parser adapter (context.parser)
            options: Налаштування
            
        Returns:
            Dict з Twitter властивостями (без "twitter:" префіксу)
        """
        if not hasattr(source, 'find_all'):
            raise ParserError(self.name, "Source must be parser adapter")
        
        result = {}
        
        try:
            # Шукаємо всі meta теги з name="twitter:*"
            for elem in source.find_all('meta[name^="twitter:"]'):
                name = elem.get_attribute('name')
                content = elem.get_attribute('content')
                
                if name and content:
                    # Видаляємо "twitter:" префікс
                    key = name.replace('twitter:', '')
                    result[key] = self._sanitize_value(content)
                    
        except Exception as e:
            logger.warning(f"Error parsing Twitter Cards: {e}")
        
        return result
    
    def _sanitize_value(self, value: str, max_length: int = 10000) -> str:
        """Санітизація значень."""
        if not value:
            return ""
        value = " ".join(value.split())
        if len(value) > max_length:
            value = value[:max_length] + "..."
        return value
