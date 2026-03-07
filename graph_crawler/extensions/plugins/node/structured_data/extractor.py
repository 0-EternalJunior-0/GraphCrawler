"""Екстрактор мікророзмітки."""

import logging
from typing import Any, Dict, List, Optional, Set

from graph_crawler.extensions.plugins.node.structured_data.options import StructuredDataOptions
from graph_crawler.extensions.plugins.node.structured_data.result import StructuredDataResult

logger = logging.getLogger(__name__)


class StructuredDataExtractor:
    """
    Core логіка витягування мікророзмітки.

    Може використовуватись:
    1. Як частина StructuredDataPlugin
    2. Standalone для прямого виклику

    Архітектура:
    - Lazy loading парсерів
    - Ізольована обробка помилок
    - Статистика парсингу
    """

    def __init__(self, options: Optional[StructuredDataOptions] = None):
        self.options = options or StructuredDataOptions()
        self._parsers: Dict[str, Any] = {}
        self._init_parsers()

    def _init_parsers(self) -> None:
        """Lazy ініціалізація парсерів."""
        if self.options.parse_jsonld:
            from graph_crawler.extensions.plugins.node.structured_data.parsers.jsonld import (
                JsonLdParser,
            )
            self._parsers['jsonld'] = JsonLdParser()

        if self.options.parse_opengraph:
            from graph_crawler.extensions.plugins.node.structured_data.parsers.opengraph import (
                OpenGraphParser,
            )
            self._parsers['opengraph'] = OpenGraphParser()

        if self.options.parse_twitter:
            from graph_crawler.extensions.plugins.node.structured_data.parsers.twitter import (
                TwitterCardsParser,
            )
            self._parsers['twitter'] = TwitterCardsParser()

        if self.options.parse_microdata:
            from graph_crawler.extensions.plugins.node.structured_data.parsers.microdata import (
                MicrodataParser,
            )
            self._parsers['microdata'] = MicrodataParser()

        if self.options.parse_rdfa:
            from graph_crawler.extensions.plugins.node.structured_data.parsers.rdfa import (
                RdfaParser,
            )
            self._parsers['rdfa'] = RdfaParser()

    def extract(
        self,
        html: Optional[str] = None,
        parser: Optional[Any] = None
    ) -> StructuredDataResult:
        """
        Витягує мікророзмітку.

        Args:
            html: Raw HTML для JSON-LD
            parser: Tree adapter для OG, Twitter, Microdata

        Returns:
            StructuredDataResult з усіма знайденими даними
        """
        result = StructuredDataResult()

        # JSON-LD (потребує raw HTML)
        if 'jsonld' in self._parsers and html:
            self._parse_jsonld(html, result)

        # Open Graph (потребує parser)
        if 'opengraph' in self._parsers and parser:
            self._parse_opengraph(parser, result)

        # Twitter Cards (потребує parser)
        if 'twitter' in self._parsers and parser:
            self._parse_twitter(parser, result)

        # Microdata (потребує parser)
        if 'microdata' in self._parsers and parser:
            self._parse_microdata(parser, result)

        # RDFa (потребує parser)
        if 'rdfa' in self._parsers and parser:
            self._parse_rdfa(parser, result)

        # Фільтрація за allowed_types
        if self.options.allowed_types:
            self._filter_by_types(result)

        # Визначення primary_type
        result.primary_type = self._determine_primary_type(result)

        return result

    def _parse_jsonld(self, html: str, result: StructuredDataResult) -> None:
        """Парсить JSON-LD блоки."""
        try:
            parsed = self._parsers['jsonld'].parse(html, self.options)
            result.jsonld = parsed[:self.options.max_jsonld_blocks]
            self._extract_types(result.jsonld, result.all_types)
        except Exception as e:
            logger.warning(f"JSON-LD parsing error: {e}")
            result.errors.append(f"jsonld: {str(e)}")

    def _parse_opengraph(self, parser: Any, result: StructuredDataResult) -> None:
        """Парсить Open Graph."""
        try:
            result.opengraph = self._parsers['opengraph'].parse(parser, self.options)
            if og_type := result.opengraph.get('type'):
                result.all_types.add(f"og:{og_type}")
        except Exception as e:
            logger.warning(f"Open Graph parsing error: {e}")
            result.errors.append(f"opengraph: {str(e)}")

    def _parse_twitter(self, parser: Any, result: StructuredDataResult) -> None:
        """Парсить Twitter Cards."""
        try:
            result.twitter = self._parsers['twitter'].parse(parser, self.options)
        except Exception as e:
            logger.warning(f"Twitter Cards parsing error: {e}")
            result.errors.append(f"twitter: {str(e)}")

    def _parse_microdata(self, parser: Any, result: StructuredDataResult) -> None:
        """Парсить Microdata."""
        try:
            parsed = self._parsers['microdata'].parse(parser, self.options)
            result.microdata = parsed[:self.options.max_microdata_items]
            self._extract_types(result.microdata, result.all_types)
        except Exception as e:
            logger.warning(f"Microdata parsing error: {e}")
            result.errors.append(f"microdata: {str(e)}")

    def _parse_rdfa(self, parser: Any, result: StructuredDataResult) -> None:
        """Парсить RDFa."""
        try:
            result.rdfa = self._parsers['rdfa'].parse(parser, self.options)
            self._extract_types(result.rdfa, result.all_types)
        except Exception as e:
            logger.warning(f"RDFa parsing error: {e}")
            result.errors.append(f"rdfa: {str(e)}")

    def _extract_types(self, items: List[Dict], types_set: Set[str]) -> None:
        """Витягує @type з об'єктів."""
        for item in items:
            item_type = item.get('@type') or item.get('type')
            if item_type:
                if isinstance(item_type, list):
                    types_set.update(item_type)
                else:
                    # Нормалізація: "https://schema.org/Product" -> "Product"
                    if self.options.normalize_types and '/' in str(item_type):
                        item_type = str(item_type).split('/')[-1]
                    types_set.add(item_type)

    def _filter_by_types(self, result: StructuredDataResult) -> None:
        """Фільтрує за allowed_types."""
        allowed = set(self.options.allowed_types)

        result.jsonld = [
            item for item in result.jsonld
            if self._type_matches(item, allowed)
        ]

        result.microdata = [
            item for item in result.microdata
            if self._type_matches(item, allowed)
        ]

        result.all_types &= allowed

    def _type_matches(self, item: Dict, allowed: Set[str]) -> bool:
        """Перевіряє чи тип в allowed."""
        item_type = item.get('@type') or item.get('type')
        if item_type is None:
            return False
        if isinstance(item_type, list):
            return bool(set(item_type) & allowed)
        return item_type in allowed

    def _determine_primary_type(self, result: StructuredDataResult) -> Optional[str]:
        """Визначає primary_type."""
        # Пріоритет: JSON-LD > Microdata > Open Graph
        if result.jsonld:
            item_type = result.jsonld[0].get('@type')
            if isinstance(item_type, str):
                return item_type
            if isinstance(item_type, list) and item_type:
                return item_type[0]

        if result.microdata:
            return result.microdata[0].get('@type') or result.microdata[0].get('type')

        if og_type := result.opengraph.get('type'):
            return f"og:{og_type}"

        return None
