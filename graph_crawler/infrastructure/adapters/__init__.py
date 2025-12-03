"""Модуль для абстракції HTML парсерів.

- get_default_parser() - singleton для BeautifulSoupAdapter
- Уникає створення нового об'єкта на кожну сторінку
"""

from graph_crawler.infrastructure.adapters.base import BaseTreeAdapter, TreeElement

# Singleton для default parser
_default_parser_instance = None


def get_default_parser() -> BaseTreeAdapter:
    """
    Повертає singleton BeautifulSoupAdapter.

    - Уникає створення нового об'єкта на кожну сторінку
    - Lazy initialization при першому виклику
    - Thread-safe (GIL захищає)

    Returns:
        BeautifulSoupAdapter instance
    """
    global _default_parser_instance
    if _default_parser_instance is None:
        from graph_crawler.infrastructure.adapters.beautifulsoup_adapter import (
            BeautifulSoupAdapter,
        )

        _default_parser_instance = BeautifulSoupAdapter()
    return _default_parser_instance


__all__ = [
    "BaseTreeAdapter",
    "TreeElement",
    "get_default_parser",
]
