"""Readability-lxml content extractor."""

import logging
from typing import Optional

from graph_crawler.extensions.plugins.node.content_extractors.base import (
    BaseContentExtractor,
    ExtractedArticle,
)

logger = logging.getLogger(__name__)


class ReadabilityExtractor(BaseContentExtractor):
    """
    Content extractor використовуючи readability-lxml.

    Readability - простий але ефективний екстрактор основного контенту.
    Підтримує витяг: title, cleaned text.

    Example:
        extractor = ReadabilityExtractor()
        article = extractor.extract(html, url)
        if article:
            print(article.text)
    """

    def __init__(self):
        """Ініціалізує ReadabilityExtractor."""
        try:
            from readability import Document

            self._Document = Document
            self._available = True
        except ImportError:
            logger.warning(
                "readability-lxml is not installed. Install with: pip install readability-lxml"
            )
            self._Document = None
            self._available = False

    @property
    def extractor_name(self) -> str:
        """Повертає назву екстрактора."""
        return "readability"

    def extract(self, html: str, url: str) -> Optional[ExtractedArticle]:
        """
        Витягує статтю використовуючи readability-lxml.

        Args:
            html: HTML контент
            url: URL сторінки

        Returns:
            ExtractedArticle або None
        """
        if not self._available:
            logger.error("readability-lxml is not available")
            return None

        try:
            # Створюємо Document
            doc = self._Document(html)

            # Витягуємо title та cleaned HTML
            title = doc.title()
            summary_html = doc.summary()

            # Конвертуємо HTML в текст
            from lxml.html import fromstring

            text_tree = fromstring(summary_html)
            text = text_tree.text_content()

            # Створюємо ExtractedArticle
            return ExtractedArticle(
                title=title or None,
                text=text or None,
                summary=None,
                authors=[],
                publish_date=None,
                keywords=[],
                top_image=None,
                images=[],
                videos=[],
                extractor_name=self.extractor_name,
            )

        except Exception as e:
            logger.error(f"Error extracting article with readability: {e}")
            return None
