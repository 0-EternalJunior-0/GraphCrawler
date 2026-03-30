"""Structured Data Plugin - плагін мікророзмітки.

Витягує структуровані дані з HTML сторінок:
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
