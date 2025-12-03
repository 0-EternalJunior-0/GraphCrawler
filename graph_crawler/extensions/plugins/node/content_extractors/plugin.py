"""Content Extraction Plugin для Node."""

import logging
from typing import Any, Dict, Optional

from graph_crawler.extensions.plugins.node.base import (
    BaseNodePlugin,
    NodePluginContext,
    NodePluginType,
)
from graph_crawler.extensions.plugins.node.content_extractors.base import (
    BaseContentExtractor,
)
from graph_crawler.extensions.plugins.node.content_extractors.goose3_extractor import (
    Goose3Extractor,
)
from graph_crawler.extensions.plugins.node.content_extractors.newspaper_extractor import (
    NewspaperExtractor,
)
from graph_crawler.extensions.plugins.node.content_extractors.readability_extractor import (
    ReadabilityExtractor,
)

logger = logging.getLogger(__name__)


class ContentExtractionPlugin(BaseNodePlugin):
    """
    Плагін для витягування контенту статей з HTML.

    Підтримує різні екстрактори:
    - newspaper3k (дефолт) - найкраще для новинних статей
    - goose3 - швидкий екстрактор основного контенту
    - readability - простий але ефективний

    Приклад використання:
        plugin = ContentExtractionPlugin(config={
            'extractor': 'newspaper',  # або 'goose3', 'readability'
            'enabled': True
        })

    Результат зберігається в:
    - context.user_data['article'] - повний об'єкт ExtractedArticle
    - context.metadata['article_title'] - заголовок
    - context.metadata['article_text'] - текст (перші 1000 символів)
    """

    def __init__(self, config: Dict[str, Any] = None):
        """Ініціалізує ContentExtractionPlugin."""
        super().__init__(config)

        # Визначаємо який екстрактор використовувати
        extractor_name = self.config.get("extractor", "newspaper")

        self.extractor: Optional[BaseContentExtractor] = None

        if extractor_name == "newspaper":
            self.extractor = NewspaperExtractor()
        elif extractor_name == "goose3":
            self.extractor = Goose3Extractor()
        elif extractor_name == "readability":
            self.extractor = ReadabilityExtractor()
        else:
            logger.error(f"Unknown extractor: {extractor_name}")
            self.enabled = False

    @property
    def plugin_type(self) -> NodePluginType:
        """Тип плагіну - виконується після парсингу HTML."""
        return NodePluginType.ON_HTML_PARSED

    @property
    def name(self) -> str:
        """Назва плагіну."""
        return "ContentExtractionPlugin"

    def execute(self, context: NodePluginContext) -> NodePluginContext:
        """
        Витягує статтю з HTML використовуючи вибраний екстрактор.

        Args:
            context: Контекст з HTML та метаданими

        Returns:
            Оновлений контекст з витягнутою статтею
        """
        if not self.enabled:
            return context

        if not self.extractor:
            logger.warning("No extractor available")
            return context

        if not context.html:
            logger.warning("No HTML for content extraction")
            return context

        try:
            # Витягуємо статтю
            article = self.extractor.extract(context.html, context.url)

            if article:
                # Зберігаємо повний об'єкт в user_data
                context.user_data["article"] = article.model_dump()

                # Зберігаємо ключові поля в metadata для зручності
                if article.title:
                    context.set_metadata("article_title", article.title)

                if article.text:
                    # Обмежуємо текст до 1000 символів для metadata
                    text_preview = (
                        article.text[:1000] + "..."
                        if len(article.text) > 1000
                        else article.text
                    )
                    context.set_metadata("article_text", text_preview)

                if article.authors:
                    context.set_metadata("article_authors", article.authors)

                if article.publish_date:
                    context.set_metadata(
                        "article_publish_date", article.publish_date.isoformat()
                    )

                logger.debug(
                    f"Extracted article from {context.url} using {self.extractor.extractor_name}"
                )
            else:
                logger.warning(f"Could not extract article from {context.url}")

        except Exception as e:
            logger.error(f"Error in ContentExtractionPlugin for {context.url}: {e}")

        return context
