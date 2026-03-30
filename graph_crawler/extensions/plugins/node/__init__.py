"""Node Plugins - плагіни для обробки контенту веб-сторінок.

Node плагіни працюють з HTML контентом після завантаження сторінки:
"""

# Base classes
from graph_crawler.extensions.plugins.node.base import (
    BaseNodePlugin,
    NodePluginContext,
    NodePluginManager,
    NodePluginType,
)

# Defaults
from graph_crawler.extensions.plugins.node.defaults import get_default_node_plugins
from graph_crawler.extensions.plugins.node.links import LinkExtractorPlugin

# Built-in Plugins
from graph_crawler.extensions.plugins.node.metadata import MetadataExtractorPlugin

# ML Smart Page Finder Plugin
from graph_crawler.extensions.plugins.node.smart_page_finder import (
    RelevanceLevel,
    SmartFinderNode,
    SmartPageFinderPlugin,
    create_smart_finder_node_class,
)

# Structured Data Plugin (Microdata)
from graph_crawler.extensions.plugins.node.structured_data import (
    SchemaType,
    StructuredDataExtractor,
    StructuredDataOptions,
    StructuredDataPlugin,
    StructuredDataResult,
)
from graph_crawler.extensions.plugins.node.text import TextExtractorPlugin

__all__ = [
    # Base classes
    "BaseNodePlugin",
    "NodePluginType",
    "NodePluginContext",
    "NodePluginManager",
    # Built-in Plugins
    "MetadataExtractorPlugin",
    "LinkExtractorPlugin",
    "TextExtractorPlugin",
    # ML Smart Page Finder
    "SmartPageFinderPlugin",
    "SmartFinderNode",
    "RelevanceLevel",
    "create_smart_finder_node_class",
    # Structured Data Plugin
    "StructuredDataPlugin",
    "StructuredDataOptions",
    "StructuredDataResult",
    "StructuredDataExtractor",
    "SchemaType",
    # Defaults
    "get_default_node_plugins",
]
