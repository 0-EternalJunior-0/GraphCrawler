"""Goose3 content extractor."""

import logging
from typing import Optional

from graph_crawler.extensions.plugins.node.content_extractors.base import (
    BaseContentExtractor,
    ExtractedArticle,
)

logger = logging.getLogger(__name__)


class Goose3Extractor(BaseContentExtractor):
    """
    Content extractor використовуючи Goose3.

    Goose3 - швидкий екстрактор статей з акцентом на витяг основного тексту.
    Підтримує витяг: title, text, meta_description, top_image.

    Example:
        extractor = Goose3Extractor()
        article = extractor.extract(html, url)
        if article:
            print(article.text)
    """

    def __init__(self):
        """Ініціалізує Goose3Extractor."""
        try:
            from goose3 import Goose

            self._goose = Goose()
            self._available = True
        except ImportError:
            logger.warning("goose3 is not installed. Install with: pip install goose3")
            self._goose = None
            self._available = False

    @property
    def extractor_name(self) -> str:
        """Повертає назву екстрактора."""
        return "goose3"

    def extract(self, html: str, url: str) -> Optional[ExtractedArticle]:
        """
        Витягує статтю використовуючи goose3.

        Args:
            html: HTML контент
            url: URL сторінки

        Returns:
            ExtractedArticle або None
        """
        if not self._available:
            logger.error("goose3 is not available")
            return None

        try:
            # Витягуємо статтю
            article = self._goose.extract(raw_html=html)

            # Створюємо ExtractedArticle
            return ExtractedArticle(
                title=article.title or None,
                text=article.cleaned_text or None,
                summary=article.meta_description or None,
                authors=[],  # Goose3 не витягує авторів
                publish_date=None,  # Goose3 не витягує дату
                keywords=[],
                top_image=article.top_image.src if article.top_image else None,
                images=[],
                videos=(
                    [article.movies[0] if article.movies else None]
                    if article.movies
                    else []
                ),
                extractor_name=self.extractor_name,
            )

        except Exception as e:
            logger.error(f"Error extracting article with goose3: {e}")
            return None
