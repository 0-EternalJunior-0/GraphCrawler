"""Email address extractor plugin.

Витягує email адреси з HTML з фільтрацією fake domains.
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


class EmailExtractorPlugin(BaseNodePlugin):
    """Витягує email адреси з HTML.

    Features:
    - RFC 5322 compliant regex
    - mailto: links parsing
    - Фільтрація fake emails (example.com, test.com, тощо)
    - Deduplication (lowercase)

    Attributes:
        EMAIL_PATTERN: RFC 5322 compliant regex для email
        FAKE_DOMAINS: Список fake domains для фільтрації
        IMAGE_EXTENSIONS: Розширення файлів (помилково схожі на email)

    Usage:
        plugin = EmailExtractorPlugin()
        context = plugin.execute(context)
        emails = context.user_data['emails']

    Example:
        >>> from graph_crawler.extensions.plugins.node.extractors import EmailExtractorPlugin
        >>> plugin = EmailExtractorPlugin()
        >>> context = plugin.execute(context)
        >>> print(context.user_data['emails'])
        ['info@example.com', 'support@example.com']
    """

    # RFC 5322 compliant email regex
    EMAIL_PATTERN = r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"

    # Fake domains для фільтрації
    FAKE_DOMAINS = [
        "example.com",
        "example.org",
        "example.net",
        "test.com",
        "test.org",
        "test.net",
        "localhost",
        "127.0.0.1",
        "domain.com",
        "email.com",
        "yoursite.com",
        "yourdomain.com",
    ]

    # Image extensions (часто схожі на email)
    IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico"]

    @property
    def name(self) -> str:
        """Назва плагіну."""
        return "EmailExtractorPlugin"

    @property
    def plugin_type(self) -> NodePluginType:
        """Тип плагіну - виконується після парсингу HTML."""
        return NodePluginType.ON_HTML_PARSED

    def execute(self, context: NodePluginContext) -> NodePluginContext:
        """Витягує emails з HTML.

        Args:
            context: NodePluginContext з HTML даними

        Returns:
            Оновлений context з emails у user_data
        """
        if not context.html:
            context.user_data["emails"] = []
            context.user_data["email_count"] = 0
            return context

        emails: Set[str] = set()

        # 1. Шукаємо в HTML тексті
        matches = re.findall(self.EMAIL_PATTERN, context.html, re.IGNORECASE)
        for email in matches:
            normalized = email.lower()
            if self._is_valid_email(normalized):
                emails.add(normalized)

        # 2. Шукаємо в mailto: посиланнях
        if context.html_tree and context.parser:
            try:
                mailto_links = context.parser.select('a[href^="mailto:"]')
                for link in mailto_links:
                    href = link.get("href", "")
                    if href.startswith("mailto:"):
                        # Видаляємо mailto: та query params
                        email = href[7:].split("?")[0].split("&")[0]
                        normalized = email.lower()
                        if self._is_valid_email(normalized):
                            emails.add(normalized)
            except Exception as e:
                logger.debug(f"Error parsing mailto: links: {e}")

        # Зберігаємо в user_data
        context.user_data["emails"] = sorted(list(emails))
        context.user_data["email_count"] = len(emails)

        if emails:
            logger.debug(f"Extracted {len(emails)} emails from {context.url}")

        return context

    def _is_valid_email(self, email: str) -> bool:
        """Перевіряє чи валідний email.

        Args:
            email: Email для перевірки

        Returns:
            True якщо email валідний
        """
        # Перевірка на порожній
        if not email or "@" not in email:
            return False

        # Розбиваємо на username @ domain
        try:
            username, domain = email.rsplit("@", 1)
        except ValueError:
            return False

        # Username не може бути порожнім
        if not username or len(username) < 1:
            return False

        # Domain має містити крапку
        if "." not in domain:
            return False

        # Фільтруємо fake domains
        if domain in self.FAKE_DOMAINS:
            return False

        # Фільтруємо image extensions (помилково схожі на email)
        if any(email.endswith(ext) for ext in self.IMAGE_EXTENSIONS):
            return False

        # TLD має бути >= 2 символів
        tld = domain.split(".")[-1]
        if len(tld) < 2:
            return False

        return True
