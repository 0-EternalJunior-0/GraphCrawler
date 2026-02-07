"""Парсери мікророзмітки.

Експортує всі доступні парсери:
- JsonLdParser - JSON-LD (найпоширеніший)
- OpenGraphParser - Open Graph (Facebook)
- TwitterCardsParser - Twitter Cards
- MicrodataParser - HTML Microdata
- RdfaParser - RDFa (опціонально)
"""

from graph_crawler.extensions.plugins.node.structured_data.parsers.base import BaseParser
from graph_crawler.extensions.plugins.node.structured_data.parsers.jsonld import JsonLdParser
from graph_crawler.extensions.plugins.node.structured_data.parsers.opengraph import OpenGraphParser
from graph_crawler.extensions.plugins.node.structured_data.parsers.twitter import TwitterCardsParser
from graph_crawler.extensions.plugins.node.structured_data.parsers.microdata import MicrodataParser
from graph_crawler.extensions.plugins.node.structured_data.parsers.rdfa import RdfaParser

__all__ = [
    "BaseParser",
    "JsonLdParser",
    "OpenGraphParser",
    "TwitterCardsParser",
    "MicrodataParser",
    "RdfaParser",
]
