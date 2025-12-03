"""Node Plugins - плагіни для обробки контенту веб-сторінок.

Node плагіни працюють з HTML контентом після завантаження сторінки:
- Витягування метаданих (title, description, h1)
- Витягування посилань
- Витягування тексту
- Кастомна обробка контенту

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
    ...     get_default_node_plugins,
    ... )
    >>>
    >>> manager = NodePluginManager()
    >>> for plugin in get_default_node_plugins():
    ...     manager.register(plugin)
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

# Built-in plugins
from graph_crawler.extensions.plugins.node.metadata import MetadataExtractorPlugin
from graph_crawler.extensions.plugins.node.text import TextExtractorPlugin

__all__ = [
    # Base classes
    "BaseNodePlugin",
    "NodePluginType",
    "NodePluginContext",
    "NodePluginManager",
    # Built-in plugins
    "MetadataExtractorPlugin",
    "LinkExtractorPlugin",
    "TextExtractorPlugin",
    # Defaults
    "get_default_node_plugins",
]
