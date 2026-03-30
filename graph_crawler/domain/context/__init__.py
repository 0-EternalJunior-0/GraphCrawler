"""Domain Context - глобальний контекст для краулінгу.

Phase 1: AI Agent Integration
"""

from graph_crawler.domain.context.crawl_context import (
    CrawlContext,
    PydanticResultAggregator,
)

__all__ = [
    "CrawlContext",
    "PydanticResultAggregator",
]
