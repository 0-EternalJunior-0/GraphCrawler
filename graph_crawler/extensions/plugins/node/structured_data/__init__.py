"""Structured Data Plugin - плагін мікророзмітки.

Витягує структуровані дані з HTML сторінок:
- JSON-LD (schema.org) - найпоширеніший, рекомендований Google
- Open Graph (og:*) - Facebook метатеги
- Twitter Cards (twitter:*) - Twitter метатеги
- Microdata (itemscope/itemprop) - HTML атрибути
- RDFa (опціонально) - семантичний веб

Бізнес-цінність:
- E-commerce: структуровані Product/Offer замість regex
- Job aggregation: JobPosting з salary, location
- News: Article з author, datePublished
- SEO audit: автоматична валідація schema

Example:
    >>> from graph_crawler import crawl
    >>> from graph_crawler.extensions.plugins.node.structured_data import (
    ...     StructuredDataPlugin,
    ...     StructuredDataOptions,
    ... )
    >>>
    >>> # Базове використання
    >>> graph = crawl("https://example.com", plugins=[StructuredDataPlugin()])
    >>> for node in graph.nodes:
    ...     sd = node.user_data.get('structured_data')
    ...     if sd and sd.has_data:
    ...         print(f"Type: {sd.get_type()}, Title: {sd.get_property('name')}")
    >>>
    >>> # E-commerce
    >>> options = StructuredDataOptions(allowed_types=['Product', 'Offer'])
    >>> graph = crawl("https://shop.com", plugins=[StructuredDataPlugin(options)])
"""

# Main plugin
# Exceptions
from graph_crawler.extensions.plugins.node.structured_data.exceptions import (
    ParserError,
    StructuredDataError,
)

# Extractor (для standalone використання)
from graph_crawler.extensions.plugins.node.structured_data.extractor import StructuredDataExtractor

# Options & Result
from graph_crawler.extensions.plugins.node.structured_data.options import StructuredDataOptions

# Parsers
from graph_crawler.extensions.plugins.node.structured_data.parsers import (
    BaseParser,
    JsonLdParser,
    MicrodataParser,
    OpenGraphParser,
    RdfaParser,
    TwitterCardsParser,
)
from graph_crawler.extensions.plugins.node.structured_data.plugin import StructuredDataPlugin
from graph_crawler.extensions.plugins.node.structured_data.result import (
    SchemaType,
    StructuredDataResult,
)

__all__ = [
    # Main
    "StructuredDataPlugin",
    "StructuredDataOptions",
    "StructuredDataResult",
    "StructuredDataExtractor",
    "SchemaType",
    # Exceptions
    "StructuredDataError",
    "ParserError",
    # Parsers
    "BaseParser",
    "JsonLdParser",
    "OpenGraphParser",
    "TwitterCardsParser",
    "MicrodataParser",
    "RdfaParser",
]
