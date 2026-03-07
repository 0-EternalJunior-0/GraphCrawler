"""Плагін для витягування мікророзмітки (Structured Data)."""

import logging
import time
from typing import Any, Dict, Optional

from graph_crawler.extensions.plugins.node.base import (
    BaseNodePlugin,
    NodePluginContext,
    NodePluginType,
)
from graph_crawler.extensions.plugins.node.structured_data.extractor import StructuredDataExtractor
from graph_crawler.extensions.plugins.node.structured_data.options import StructuredDataOptions
from graph_crawler.extensions.plugins.node.structured_data.result import StructuredDataResult

logger = logging.getLogger(__name__)


class StructuredDataPlugin(BaseNodePlugin):
    """
    Плагін для витягування мікророзмітки (Structured Data).

    Архітектурні принципи:
    - Консистентний з MetadataExtractorPlugin, LinkExtractorPlugin
    - Використовує context.user_data (не metadata!)
    - Graceful degradation при помилках
    - Підтримує конфігурацію через options

    Підтримувані формати:
    - JSON-LD (schema.org) — найвищий пріоритет
    - Open Graph (og:*)
    - Twitter Cards (twitter:*)
    - Microdata (itemscope/itemprop)
    - RDFa (опціонально)

    Example:
        >>> # Базове використання
        >>> graph = crawl("https://example.com", plugins=[StructuredDataPlugin()])
        >>>
        >>> # З налаштуваннями
        >>> options = StructuredDataOptions(
        ...     allowed_types=['Product', 'Article'],
        ...     parse_rdfa=False
        ... )
        >>> graph = crawl("https://example.com", plugins=[StructuredDataPlugin(options)])
    """

    def __init__(
        self,
        options: Optional[StructuredDataOptions] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Ініціалізує плагін.

        Args:
            options: Налаштування витягування
            config: Базова конфігурація плагіна (enabled тощо)
        """
        super().__init__(config=config or {})
        self.options = options or StructuredDataOptions()
        self._extractor: Optional[StructuredDataExtractor] = None

    @property
    def plugin_type(self) -> NodePluginType:
        return NodePluginType.ON_HTML_PARSED

    @property
    def name(self) -> str:
        return "StructuredDataPlugin"

    def setup(self) -> None:
        """
        Ініціалізує extractor.

        Викликається NodePluginManager при реєстрації.
        Lazy initialization — парсери створюються тут.
        """
        self._extractor = StructuredDataExtractor(self.options)
        logger.debug(
            f"{self.name} initialized: "
            f"jsonld={self.options.parse_jsonld}, "
            f"og={self.options.parse_opengraph}, "
            f"twitter={self.options.parse_twitter}, "
            f"microdata={self.options.parse_microdata}, "
            f"rdfa={self.options.parse_rdfa}"
        )

    def teardown(self) -> None:
        """Очищує ресурси."""
        self._extractor = None

    def execute(self, context: NodePluginContext) -> NodePluginContext:
        """
        Витягує мікророзмітку з HTML.

        Args:
            context: Контекст з html та parser

        Returns:
            Контекст з доданим structured_data в user_data
        """
        # Lazy init якщо setup() не викликався
        if self._extractor is None:
            self._extractor = StructuredDataExtractor(self.options)

        # Early exit якщо немає HTML
        if not context.html and not context.parser:
            logger.debug(f"No HTML/parser for {context.url}, skipping structured data")
            context.user_data['structured_data'] = StructuredDataResult.empty()
            return context

        start_time = time.perf_counter()

        try:
            result = self._extractor.extract(
                html=context.html,
                parser=context.parser
            )

            # Записуємо час парсингу
            result.parse_time_ms = (time.perf_counter() - start_time) * 1000

            # Зберігаємо в user_data (НЕ в metadata!)
            context.user_data['structured_data'] = result

            if result.has_data:
                logger.debug(
                    f"Extracted structured data from {context.url}: "
                    f"type={result.primary_type}, "
                    f"jsonld={result.jsonld_count}, "
                    f"microdata={result.microdata_count}, "
                    f"time={result.parse_time_ms:.1f}ms"
                )

        except Exception as e:
            logger.error(
                f"Error extracting structured data from {context.url}: {e}",
                exc_info=True
            )

            if self.options.fail_silently:
                context.user_data['structured_data'] = StructuredDataResult.with_error(str(e))
            else:
                raise

        return context
