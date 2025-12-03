"""Phone number extractor plugin.

Витягує телефонні номери з HTML з підтримкою різних форматів.
"""

import logging
import re
from typing import Set

from graph_crawler.extensions.plugins.node.base import (
    BaseNodePlugin,
    NodePluginContext,
    NodePluginType,
)

logger = logging.getLogger(__name__)


class PhoneExtractorPlugin(BaseNodePlugin):
    """Витягує телефонні номери з HTML.

    Підтримувані формати:
    - UA: +380XXXXXXXXX, 380XXXXXXXXX, 0XXXXXXXXX, (0XX) XXX-XX-XX
    - RU: +7XXXXXXXXXX, 7XXXXXXXXXX
    - US: +1XXXXXXXXXX, (XXX) XXX-XXXX
    - International: +XXXXXXXXXXXX
    - tel: links

    Attributes:
        PHONE_PATTERNS: Список regex patterns для різних форматів

    Usage:
        plugin = PhoneExtractorPlugin()
        context = plugin.execute(context)
        phones = context.user_data['phones']

    Example:
        >>> from graph_crawler.extensions.plugins.node.extractors import PhoneExtractorPlugin
        >>> plugin = PhoneExtractorPlugin()
        >>> # context містить HTML з телефонами
        >>> context = plugin.execute(context)
        >>> print(context.user_data['phones'])
        ['+380501234567', '+380441234567']
    """

    # Regex patterns для різних форматів
    PHONE_PATTERNS = [
        # Ukraine
        r"\+?3?8?\s?\(?\d{3}\)?\s?\d{3}[-\s]?\d{2}[-\s]?\d{2}",
        # Russia
        r"\+?7?\s?\(?\d{3}\)?\s?\d{3}[-\s]?\d{2}[-\s]?\d{2}",
        # US
        r"\+?1?\s?\(?\d{3}\)?\s?\d{3}[-\s]?\d{4}",
        # International
        r"\+\d{1,3}\s?\(?\d{1,4}\)?\s?\d{1,4}[-\s]?\d{1,4}[-\s]?\d{1,9}",
        # tel: links
        r"tel:\+?\d+",
    ]

    @property
    def name(self) -> str:
        """Назва плагіну."""
        return "PhoneExtractorPlugin"

    @property
    def plugin_type(self) -> NodePluginType:
        """Тип плагіну - виконується після парсингу HTML."""
        return NodePluginType.ON_HTML_PARSED

    def execute(self, context: NodePluginContext) -> NodePluginContext:
        """Витягує телефони з HTML.

        Args:
            context: NodePluginContext з HTML даними

        Returns:
            Оновлений context з phones у user_data
        """
        if not context.html:
            context.user_data["phones"] = []
            context.user_data["phone_count"] = 0
            return context

        phones: Set[str] = set()

        # 1. Шукаємо в HTML тексті
        for pattern in self.PHONE_PATTERNS:
            matches = re.findall(pattern, context.html, re.IGNORECASE)
            for match in matches:
                normalized = self._normalize_phone(match)
                if normalized and self._is_valid_phone(normalized):
                    phones.add(normalized)

        # 2. Шукаємо в tel: посиланнях
        if context.html_tree and context.parser:
            try:
                tel_links = context.parser.select('a[href^="tel:"]')
                for link in tel_links:
                    href = link.get("href", "")
                    if href.startswith("tel:"):
                        phone = href[4:]
                        normalized = self._normalize_phone(phone)
                        if normalized and self._is_valid_phone(normalized):
                            phones.add(normalized)
            except Exception as e:
                logger.debug(f"Error parsing tel: links: {e}")

        # Зберігаємо в user_data
        context.user_data["phones"] = sorted(list(phones))
        context.user_data["phone_count"] = len(phones)

        if phones:
            logger.debug(f"Extracted {len(phones)} phones from {context.url}")

        return context

    def _normalize_phone(self, phone: str) -> str:
        """Нормалізує телефонний номер (видаляє пробіли, дужки тощо).

        Args:
            phone: Телефон для нормалізації

        Returns:
            Нормалізований телефон (тільки цифри і +)
        """
        # Видаляємо tel: prefix
        phone = phone.replace("tel:", "")
        # Видаляємо всі символи крім цифр і +
        normalized = re.sub(r"[^\d+]", "", phone)
        return normalized

    def _is_valid_phone(self, phone: str) -> bool:
        """Перевіряє чи валідний телефон.

        Args:
            phone: Нормалізований телефон

        Returns:
            True якщо телефон валідний
        """
        # Мінімум 10 цифр (без +)
        digits = phone.replace("+", "")
        if len(digits) < 10:
            return False

        # Максимум 15 цифр (international standard)
        if len(digits) > 15:
            return False

        # Не може бути тільки з нулів або одиниць
        if digits == "0" * len(digits) or digits == "1" * len(digits):
            return False

        return True
