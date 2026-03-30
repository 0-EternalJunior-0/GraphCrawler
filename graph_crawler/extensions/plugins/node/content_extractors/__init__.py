"""Content extraction plugins for article extraction."""

from graph_crawler.extensions.plugins.node.content_extractors.base import (
    BaseContentExtractor,
    ExtractedArticle,
)
from graph_crawler.extensions.plugins.node.content_extractors.plugin import (
    ContentExtractionPlugin,
)

__all__ = [
    "ExtractedArticle",
    "BaseContentExtractor",
    "ContentExtractionPlugin",
]
