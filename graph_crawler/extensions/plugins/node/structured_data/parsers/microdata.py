"""Парсер Microdata мікророзмітки."""

import logging
from typing import Any, Dict, List, Union

from graph_crawler.extensions.plugins.node.structured_data.options import StructuredDataOptions
from graph_crawler.extensions.plugins.node.structured_data.exceptions import ParserError

logger = logging.getLogger(__name__)


class MicrodataParser:
    """
    Парсер Microdata (HTML атрибути) мікророзмітки.
    
    Витягує itemscope/itemprop атрибути з HTML.
    Поширеність ~30% сайтів.
    """
    
    @property
    def name(self) -> str:
        return "microdata"
    
    def can_parse(self, source: Union[str, Any]) -> bool:
        """Перевіряє чи джерело є parser adapter."""
        return hasattr(source, 'find_all')
    
    def parse(
        self, 
        source: Union[str, Any],
        options: StructuredDataOptions
    ) -> List[Dict[str, Any]]:
        """
        Парсить Microdata елементи.
        
        Args:
            source: Parser adapter (context.parser)
            options: Налаштування
            
        Returns:
            Список Microdata об'єктів
        """
        if not hasattr(source, 'find_all'):
            raise ParserError(self.name, "Source must be parser adapter")
        
        results = []
        
        try:
            # Шукаємо елементи з itemscope (top-level)
            itemscopes = source.find_all('[itemscope]:not([itemprop])')
            
            for elem in itemscopes[:options.max_microdata_items]:
                item = self._extract_item(elem, options, depth=0)
                if item:
                    results.append(item)
                    
        except Exception as e:
            logger.warning(f"Error parsing Microdata: {e}")
        
        return results
    
    def _extract_item(self, elem: Any, options: StructuredDataOptions, depth: int = 0) -> Dict[str, Any]:
        """Рекурсивно витягує item з елемента."""
        if depth > options.max_nesting_depth:
            return {}
        
        item = {}
        
        # Тип
        itemtype = elem.get_attribute('itemtype')
        if itemtype:
            # Нормалізація: "https://schema.org/Product" -> "Product"
            if options.normalize_types and '/' in itemtype:
                item['@type'] = itemtype.split('/')[-1]
            else:
                item['@type'] = itemtype
        
        # Властивості
        try:
            props = elem.find_all('[itemprop]')
            for prop_elem in props:
                prop_name = prop_elem.get_attribute('itemprop')
                if not prop_name:
                    continue
                
                # Вкладений itemscope
                if prop_elem.get_attribute('itemscope') is not None:
                    if options.include_nested:
                        value = self._extract_item(prop_elem, options, depth + 1)
                    else:
                        continue
                else:
                    # Значення: content атрибут має пріоритет
                    value = (
                        prop_elem.get_attribute('content') or
                        prop_elem.get_attribute('href') or
                        prop_elem.get_attribute('src') or
                        prop_elem.text() or
                        ''
                    )
                    value = self._sanitize_value(str(value))
                
                if value:
                    item[prop_name] = value
                    
        except Exception as e:
            logger.warning(f"Error extracting microdata properties: {e}")
        
        return item
    
    def _sanitize_value(self, value: str, max_length: int = 10000) -> str:
        """Санітизація значень."""
        if not value:
            return ""
        value = " ".join(value.split())
        if len(value) > max_length:
            value = value[:max_length] + "..."
        return value
