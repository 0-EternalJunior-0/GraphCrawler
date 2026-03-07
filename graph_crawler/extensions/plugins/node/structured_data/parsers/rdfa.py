"""Парсер RDFa мікророзмітки."""

import logging
from typing import Any, Dict, List, Union

from graph_crawler.extensions.plugins.node.structured_data.exceptions import ParserError
from graph_crawler.extensions.plugins.node.structured_data.options import StructuredDataOptions

logger = logging.getLogger(__name__)


class RdfaParser:
    """
    Парсер RDFa (семантичний веб) мікророзмітки.

    Найскладніший формат, рідко використовується (~10% сайтів).
    Вимкнено за замовчуванням.
    """

    @property
    def name(self) -> str:
        return "rdfa"

    def can_parse(self, source: Union[str, Any]) -> bool:
        """Перевіряє чи джерело є parser adapter."""
        return hasattr(source, 'find_all')

    def parse(
        self,
        source: Union[str, Any],
        options: StructuredDataOptions
    ) -> List[Dict[str, Any]]:
        """
        Парсить RDFa елементи.

        Args:
            source: Parser adapter (context.parser)
            options: Налаштування

        Returns:
            Список RDFa об'єктів
        """
        if not hasattr(source, 'find_all'):
            raise ParserError(self.name, "Source must be parser adapter")

        results = []

        try:
            # Шукаємо елементи з typeof (RDFa root)
            type_elems = source.find_all('[typeof]')

            for elem in type_elems[:options.max_microdata_items]:
                item = self._extract_rdfa_item(elem, options, depth=0)
                if item:
                    results.append(item)

        except Exception as e:
            logger.warning(f"Error parsing RDFa: {e}")

        return results

    def _extract_rdfa_item(self, elem: Any, options: StructuredDataOptions, depth: int = 0) -> Dict[str, Any]:
        """Витягує RDFa item з елемента."""
        if depth > options.max_nesting_depth:
            return {}

        item = {}

        # Тип
        typeof = elem.get_attribute('typeof')
        if typeof:
            # Нормалізація
            if options.normalize_types and '/' in typeof:
                item['@type'] = typeof.split('/')[-1]
            else:
                item['@type'] = typeof

        # Vocab
        vocab = elem.get_attribute('vocab')
        if vocab:
            item['@context'] = vocab

        # Властивості (property атрибут)
        try:
            props = elem.find_all('[property]')
            for prop_elem in props:
                prop_name = prop_elem.get_attribute('property')
                if not prop_name:
                    continue

                # Вкладений typeof
                if prop_elem.get_attribute('typeof') is not None:
                    if options.include_nested:
                        value = self._extract_rdfa_item(prop_elem, options, depth + 1)
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
            logger.warning(f"Error extracting RDFa properties: {e}")

        return item

    def _sanitize_value(self, value: str, max_length: int = 10000) -> str:
        """Санітизація значень."""
        if not value:
            return ""
        value = " ".join(value.split())
        if len(value) > max_length:
            value = value[:max_length] + "..."
        return value
