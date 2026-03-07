"""Дефолтна конфігурація Node плагінів.

Функції для отримання стандартного набору плагінів для обробки Node.
"""

from graph_crawler.extensions.plugins.node.links import LinkExtractorPlugin
from graph_crawler.extensions.plugins.node.metadata import MetadataExtractorPlugin
from graph_crawler.extensions.plugins.node.text import TextExtractorPlugin


def get_default_node_plugins():
    """
    Повертає список дефолтних плагінів для обробки Node.

    Дефолтно увімкнені:
    - MetadataExtractorPlugin (title, h1, description, keywords)
    - LinkExtractorPlugin (витягування <a href>)
    - TextExtractorPlugin (витягування тексту для SimHash)

    Користувач може:
    - Відключити дефолтні плагіни
    - Додати власні плагіни
    - Налаштувати параметри

    Returns:
        Список дефолтних плагінів
    """
    return [
        MetadataExtractorPlugin(config={"enabled": True}),
        LinkExtractorPlugin(config={"enabled": True}),
        TextExtractorPlugin(config={"enabled": True}),  # Потрібен для SimHash!
    ]
