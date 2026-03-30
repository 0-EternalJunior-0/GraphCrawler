"""Парсер JSON-LD мікророзмітки."""

import json
import logging
from typing import Any, Dict, List, Union

from graph_crawler.extensions.plugins.node.structured_data.constants import (
    JSONLD_PATTERN,
)
from graph_crawler.extensions.plugins.node.structured_data.exceptions import ParserError
from graph_crawler.extensions.plugins.node.structured_data.options import StructuredDataOptions

logger = logging.getLogger(__name__)


class JsonLdParser:
    """
    Парсер JSON-LD мікророзмітки.

    JSON-LD (рекомендовано Google) - найпоширеніший формат.
    Знаходиться в <script type="application/ld+json"> тегах.
    """

    @property
    def name(self) -> str:
        return "jsonld"

    def can_parse(self, source: Union[str, Any]) -> bool:
        """Перевіряє чи джерело є HTML строкою."""
        return isinstance(source, str) and "application/ld+json" in source.lower()

    def parse(
        self, source: Union[str, Any], options: StructuredDataOptions
    ) -> List[Dict[str, Any]]:
        """
        Парсить JSON-LD блоки з HTML.

        Args:
            source: HTML string
            options: Налаштування

        Returns:
            Список JSON-LD об'єктів
        """
        if not isinstance(source, str):
            raise ParserError(self.name, "Source must be HTML string")

        results = []
        blocks = JSONLD_PATTERN.findall(source)

        for i, block in enumerate(blocks[: options.max_jsonld_blocks]):
            # Ліміт на розмір
            if len(block) > options.max_jsonld_size:
                logger.warning("JSON-LD block %s exceeds size limit, skipping", i)
                continue

            try:
                # Очищення від можливих коментарів та пробілів
                block = block.strip()
                if not block:
                    continue

                data = json.loads(block)

                # Захист від глибоко вкладених структур
                if self._check_depth(data, options.max_nesting_depth):
                    results.append(data)
                else:
                    logger.warning("JSON-LD block %s exceeds nesting depth limit", i)

            except json.JSONDecodeError as e:
                logger.warning("Invalid JSON in block %s: %s", i, e)
                continue

        return results

    def _check_depth(self, obj: Any, max_depth: int, current: int = 0) -> bool:
        """Перевіряє глибину вкладеності."""
        if current > max_depth:
            return False
        if isinstance(obj, dict):
            return all(self._check_depth(v, max_depth, current + 1) for v in obj.values())
        if isinstance(obj, list):
            return all(self._check_depth(v, max_depth, current + 1) for v in obj)
        return True
