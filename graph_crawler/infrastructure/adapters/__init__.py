"""Модуль для абстракції HTML парсерів.


Пріоритет: selectolax (5-10x) > lxml (2-3x) > html.parser

- get_default_parser() - singleton для найшвидшого доступного адаптера
- get_parser(name) - отримати конкретний парсер по імені
- Уникає створення нового об'єкта на кожну сторінку
"""

import logging
from typing import Optional

from graph_crawler.infrastructure.adapters.base import BaseTreeAdapter, TreeElement

logger = logging.getLogger(__name__)

# Singleton для default parser
_default_parser_instance: Optional[BaseTreeAdapter] = None
_parser_type_used: Optional[str] = None


def _detect_best_parser() -> str:
    """
    Визначає найшвидший доступний парсер.

    Пріоритет:
    1. selectolax - 5-10x швидше за lxml (C-based Modest)
    2. lxml - 2-3x швидше за html.parser
    3. html.parser - стандартний fallback

    Returns:
        Назва найшвидшого парсера
    """
    # Пробуємо selectolax (найшвидший)
    try:
        from selectolax.parser import HTMLParser
        logger.info("✅ Selectolax detected - using FASTEST HTML parser (+40% speed)")
        return "selectolax"
    except ImportError:
        pass

    # Пробуємо lxml
    try:
        import lxml
        logger.info("✅ lxml detected - using fast HTML parser")
        return "lxml"
    except ImportError:
        pass

    # Fallback на html.parser
    logger.info("Using standard html.parser (consider installing selectolax for +40% speed)")
    return "html.parser"


def get_default_parser() -> BaseTreeAdapter:
    """
    Повертає singleton найшвидшого доступного адаптера.

    ⚠️ УВАГА: Цей метод повертає SINGLETON!
    НЕ використовуйте для паралельного парсингу - буде race condition!
    Для паралельного парсингу використовуйте create_parser_instance().

    Пріоритет:
    1. selectolax - +40% швидкості (5-10x vs lxml)
    2. lxml - швидкий стандарт
    3. html.parser - завжди доступний

    - Lazy initialization при першому виклику
    - Thread-safe (GIL захищає)

    Returns:
        BaseTreeAdapter instance (найшвидший доступний)
    """
    global _default_parser_instance, _parser_type_used

    if _default_parser_instance is None:
        parser_type = _detect_best_parser()
        _parser_type_used = parser_type

        if parser_type == "selectolax":
            from graph_crawler.infrastructure.adapters.selectolax_adapter import (
                SelectolaxAdapter,
            )
            _default_parser_instance = SelectolaxAdapter()
        else:
            # BeautifulSoup з lxml або html.parser backend
            from graph_crawler.infrastructure.adapters.beautifulsoup_adapter import (
                BeautifulSoupAdapter,
            )
            _default_parser_instance = BeautifulSoupAdapter(parser_backend=parser_type)

    return _default_parser_instance


def create_parser_instance() -> BaseTreeAdapter:
    """
    Створює НОВИЙ instance парсера для thread-safe паралельного парсингу.

    🔒 THREAD-SAFE: Кожен виклик створює новий незалежний instance.
    Використовуйте цей метод замість get_default_parser() при:
    - Паралельному парсингу в ThreadPoolExecutor
    - Async краулінгу з asyncio.gather()
    - Будь-якому concurrent доступі до парсера

    Це вирішує race condition коли кілька threads/tasks одночасно
    викликають parser.parse() і перезаписують self._tree один одному.

    Returns:
        НОВИЙ BaseTreeAdapter instance (thread-safe)

    Example:
        >>> # В ThreadPoolExecutor
        >>> def parse_html(html):
        ...     parser = create_parser_instance()  # Новий instance!
        ...     tree = parser.parse(html)
        ...     return parser.find('title').text()
        >>>
        >>> with ThreadPoolExecutor() as executor:
        ...     results = executor.map(parse_html, html_list)
    """
    global _parser_type_used

    # Визначаємо тип парсера якщо ще не визначено
    if _parser_type_used is None:
        _parser_type_used = _detect_best_parser()

    parser_type = _parser_type_used

    if parser_type == "selectolax":
        from graph_crawler.infrastructure.adapters.selectolax_adapter import (
            SelectolaxAdapter,
        )
        return SelectolaxAdapter()
    else:
        # BeautifulSoup з lxml або html.parser backend
        from graph_crawler.infrastructure.adapters.beautifulsoup_adapter import (
            BeautifulSoupAdapter,
        )
        return BeautifulSoupAdapter(parser_backend=parser_type)


def get_parser(name: str = "auto") -> BaseTreeAdapter:
    """
    Повертає парсер за іменем.

    Args:
        name: Ім'я парсера:
            - "auto" - найшвидший доступний (default)
            - "selectolax" - найшвидший (якщо встановлено)
            - "lxml" - швидкий стандарт
            - "beautifulsoup" або "html.parser" - стандартний

    Returns:
        BaseTreeAdapter instance

    Raises:
        ImportError: Якщо запитаний парсер не встановлено

    Example:
        >>> parser = get_parser("selectolax")  # Явно selectolax
        >>> parser = get_parser()  # Автовибір найшвидшого
    """
    if name == "auto":
        return get_default_parser()

    if name == "selectolax":
        from graph_crawler.infrastructure.adapters.selectolax_adapter import (
            SelectolaxAdapter,
        )
        return SelectolaxAdapter()

    if name in ("beautifulsoup", "html.parser", "lxml"):
        from graph_crawler.infrastructure.adapters.beautifulsoup_adapter import (
            BeautifulSoupAdapter,
        )
        backend = "lxml" if name == "lxml" else "html.parser"
        return BeautifulSoupAdapter(parser_backend=backend)

    raise ValueError(f"Unknown parser: {name}. Use: auto, selectolax, lxml, beautifulsoup")


def get_current_parser_type() -> Optional[str]:
    """
    Повертає тип поточного default парсера.

    Returns:
        "selectolax", "lxml", "html.parser" або None якщо ще не ініціалізовано
    """
    return _parser_type_used


__all__ = [
    "BaseTreeAdapter",
    "TreeElement",
    "get_default_parser",
    "get_parser",
    "get_current_parser_type",
    "create_parser_instance",
]
