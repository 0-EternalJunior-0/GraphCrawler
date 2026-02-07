"""Дефолтна конфігурація Node плагінів.

Функції для отримання стандартного набору плагінів для обробки Node.
"""

from graph_crawler.extensions.plugins.node.links import LinkExtractorPlugin
from graph_crawler.extensions.plugins.node.metadata import MetadataExtractorPlugin


def get_default_node_plugins():
    """
    Повертає список дефолтних плагінів для обробки Node.

    Дефолтно увімкнені:
    - MetadataExtractorPlugin (title, h1, description, keywords)
    - LinkExtractorPlugin (витягування <a href>)

    Дефолтно вимкнені:
    - TextExtractorPlugin (потрібен тільки для векторизації)

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
        # TextExtractorPlugin залишається вимкненим за замовчуванням
    ]
