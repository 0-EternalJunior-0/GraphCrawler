"""Price/Salary extractor plugin.

Витягує ціни та зарплати з HTML з підтримкою різних валют.
"""

import logging
import re
from typing import Dict, List, Set

from graph_crawler.extensions.plugins.node.base import (
    BaseNodePlugin,
    NodePluginContext,
    NodePluginType,
)

logger = logging.getLogger(__name__)


class PriceExtractorPlugin(BaseNodePlugin):
    """Extract prices and salaries from HTML with multi-currency support.

    Supported currencies: USD, EUR, UAH with range detection.

    Example:
        >>> from graph_crawler.extensions.plugins.node.extractors import PriceExtractorPlugin
        >>> plugin = PriceExtractorPlugin()
        >>> context = plugin.execute(context)
        >>> print(context.user_data['prices'])
        [{'value': '$1000', 'currency': 'USD', 'original': '$1,000'}]
    """

    PRICE_PATTERNS = [
        # USD
        (r"\$\s?\d{1,3}(?:,\d{3})*(?:\.\d{2})?", "USD"),
        (r"\$\s?\d+(?:\.\d+)?[kKmMbB]", "USD"),  # $1.5k, $2M
        (r"\d+(?:\.\d+)?\s?USD", "USD"),
        # EUR
        (r"€\s?\d{1,3}(?:,\d{3})*(?:\.\d{2})?", "EUR"),
        (r"\d{1,3}(?:,\d{3})*(?:\.\d{2})?\s?€", "EUR"),
        (r"\d+\s?EUR", "EUR"),
        # UAH
        (r"₴\s?\d{1,3}(?:,\d{3})*", "UAH"),
        (r"\d{1,3}(?:\s?\d{3})*\s?(?:грн|гривень|гривні)", "UAH"),
        # Salary ranges (Ukrainian)
        (r"від\s+\d+(?:\s?\d{3})*\s?(?:грн|гривень)", "UAH_RANGE"),
        (r"до\s+\d+(?:\s?\d{3})*\s?(?:грн|гривень)", "UAH_RANGE"),
        # Salary ranges (English)
        (r"\$\s?\d+[kK]?\s*[-–—]\s*\$?\s?\d+[kK]?", "USD_RANGE"),
        (r"\d+[kK]?\s*[-–—]\s*\d+[kK]?\s*(?:USD|dollars?)", "USD_RANGE"),
    ]

    @property
    def name(self) -> str:
        """Назва плагіну."""
        return "PriceExtractorPlugin"

    @property
    def plugin_type(self) -> NodePluginType:
        """Тип плагіну - виконується після парсингу HTML."""
        return NodePluginType.ON_HTML_PARSED

    def execute(self, context: NodePluginContext) -> NodePluginContext:
        """Витягує ціни з HTML.

        Args:
            context: NodePluginContext з HTML даними

        Returns:
            Оновлений context з prices у user_data
        """
        if not context.html:
            context.user_data["prices"] = []
            context.user_data["price_count"] = 0
            return context

        prices: List[Dict[str, str]] = []
        seen: Set[str] = set()

        # Шукаємо всі паттерни
        for pattern, currency_type in self.PRICE_PATTERNS:
            matches = re.findall(pattern, context.html, re.IGNORECASE)
            for match in matches:
                # Нормалізуємо
                normalized = self._normalize_price(match)

                # Deduplicate
                if normalized in seen:
                    continue
                seen.add(normalized)

                # Валідація
                if self._is_valid_price(normalized):
                    prices.append(
                        {
                            "value": normalized,
                            "currency": currency_type,
                            "original": match,
                        }
                    )

        context.user_data["prices"] = prices
        context.user_data["price_count"] = len(prices)

        if prices:
            logger.debug("Extracted %s prices from %s", len(prices), context.url)

        return context

    def _normalize_price(self, price: str) -> str:
        """Нормалізує ціну (видаляє зайві символи).

        Args:
            price: Ціна для нормалізації

        Returns:
            Нормалізована ціна
        """
        normalized = re.sub(r"\s+", " ", price.strip())
        return normalized

    def _is_valid_price(self, price: str) -> bool:
        """Перевіряє чи валідна ціна.

        Args:
            price: Ціна для перевірки

        Returns:
            True якщо ціна валідна
        """
        # Має містити хоча б одну цифру
        if not re.search(r"\d", price):
            return False

        # Не може бути надто коротким
        if len(price) < 2:
            return False

        return True
