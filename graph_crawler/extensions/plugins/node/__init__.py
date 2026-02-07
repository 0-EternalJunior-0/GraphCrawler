"""Node Plugins - плагіни для обробки контенту веб-сторінок.

Node плагіни працюють з HTML контентом після завантаження сторінки:
- Витягування метаданих (title, description, h1)
- Витягування посилань
- Витягування тексту
- Кастомна обробка контенту
- ML-пошук потрібних сторінок (SmartPageFinderPlugin)

Lifecycle Hooks (NodePluginType):
- ON_NODE_CREATED: після створення Node
- ON_HTML_PARSED: після парсингу HTML
- ON_LINKS_EXTRACTED: після витягування посилань
- ON_AFTER_SCAN: після завершення сканування

Example:
    >>> from graph_crawler.extensions.plugins.node import (
    ...     BaseNodePlugin,
    ...     NodePluginManager,
    ...     NodePluginType,
    ...     MetadataExtractorPlugin,
    ...     LinkExtractorPlugin,
    ...     SmartPageFinderPlugin,
    ...     get_default_node_plugins,
    ... )
    >>>
    >>> # ML пошук сторінок
    >>> finder = SmartPageFinderPlugin(
    ...     search_prompt="Автомобілі BMW X5 2024 року"
    ... )
    >>> graph = gc.crawl(url, plugins=[finder])
    >>> 
    >>> # Знайдені сторінки
    >>> targets = [n for n in graph if n.user_data.get('is_target_page')]
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

# Built-in CustomPlugins
from graph_crawler.extensions.plugins.node.metadata import MetadataExtractorPlugin
from graph_crawler.extensions.plugins.node.text import TextExtractorPlugin

# ML Smart Page Finder Plugin
from graph_crawler.extensions.plugins.node.smart_page_finder import (
    SmartPageFinderPlugin,
    SmartFinderNode,
    RelevanceLevel,
    create_smart_finder_node_class,
)

# Structured Data Plugin (Microdata)
from graph_crawler.extensions.plugins.node.structured_data import (
    StructuredDataPlugin,
    StructuredDataOptions,
    StructuredDataResult,
    StructuredDataExtractor,
    SchemaType,
)

__all__ = [
    # Base classes
    "BaseNodePlugin",
    "NodePluginType",
    "NodePluginContext",
    "NodePluginManager",
    # Built-in CustomPlugins
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
