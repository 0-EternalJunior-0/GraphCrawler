"""Newspaper3k content extractor."""

import logging
from typing import Optional

from graph_crawler.extensions.plugins.node.content_extractors.base import (
    BaseContentExtractor,
    ExtractedArticle,
)

logger = logging.getLogger(__name__)


class NewspaperExtractor(BaseContentExtractor):
    """
    Content extractor використовуючи newspaper3k.

    Newspaper3k - популярна бібліотека для витягування статей з новинних сайтів.
    Підтримує витяг: title, text, authors, publish_date, summary, images.

    Example:
        extractor = NewspaperExtractor()
        article = extractor.extract(html, url)
        if article:
            print(article.title)
    """

    def __init__(self):
        """Ініціалізує NewspaperExtractor."""
        try:
            import newspaper

            self._newspaper = newspaper
            self._available = True
        except ImportError:
            logger.warning(
                "newspaper3k is not installed. Install with: pip install newspaper3k"
            )
            self._newspaper = None
            self._available = False

    @property
    def extractor_name(self) -> str:
        """Повертає назву екстрактора."""
        return "newspaper3k"

    def extract(self, html: str, url: str) -> Optional[ExtractedArticle]:
        """
        Витягує статтю використовуючи newspaper3k.

        Args:
            html: HTML контент
            url: URL сторінки

        Returns:
            ExtractedArticle або None
        """
        if not self._available:
            logger.error("newspaper3k is not available")
            return None

        try:
            # Створюємо Article об'єкт
            article = self._newspaper.Article(url)

            # Встановлюємо HTML вручну
            article.set_html(html)

            # Парсимо та обробляємо
            article.parse()

            # Пробуємо витягти summary (може викинути помилку)
            summary = None
            try:
                article.nlp()
                summary = article.summary
            except Exception as e:
                logger.debug(f"Could not extract summary: {e}")

            # Створюємо ExtractedArticle
            return ExtractedArticle(
                title=article.title or None,
                text=article.text or None,
                summary=summary,
                authors=list(article.authors) if article.authors else [],
                publish_date=article.publish_date,
                keywords=list(article.keywords) if article.keywords else [],
                top_image=article.top_image or None,
                images=list(article.images) if article.images else [],
                videos=list(article.movies) if article.movies else [],
                extractor_name=self.extractor_name,
            )

        except Exception as e:
            logger.error(f"Error extracting article with newspaper3k: {e}")
            return None
