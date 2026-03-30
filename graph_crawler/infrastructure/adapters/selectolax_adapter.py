"""Selectolax реалізація TreeAdapter - НАЙШВИДШИЙ ПАРСЕР!

Selectolax базується на Modest (C бібліотека) і є в 5-10x швидшим за lxml.
Рекомендований для high-performance краулінгу.

Benchmark (1000 сторінок):
- selectolax: ~0.5 сек
- lxml: ~2.5 сек
- html.parser: ~8 сек

"""

import logging
from typing import Any, List, Optional

from graph_crawler.infrastructure.adapters.base import BaseTreeAdapter, TreeElement

logger = logging.getLogger(__name__)

_selectolax_available = None


def _check_selectolax() -> bool:
    """Перевіряє чи selectolax доступний."""
    global _selectolax_available
    if _selectolax_available is None:
        try:
            from selectolax.parser import HTMLParser

            _selectolax_available = True
            logger.info(" Selectolax available - using fastest HTML parser!")
        except ImportError:
            _selectolax_available = False
            logger.debug("Selectolax not installed. Install with: pip install selectolax")
    return _selectolax_available


class SelectolaxAdapter(BaseTreeAdapter):
    """
    Selectolax адаптер - НАЙШВИДШИЙ HTML парсер для Python!

    """

    def __init__(self):
        """Ініціалізує Selectolax адаптер."""
        if not _check_selectolax():
            raise ImportError("Selectolax not installed. Install with: pip install selectolax")

        from selectolax.parser import HTMLParser

        self._parser_class = HTMLParser
        self._tree = None

        logger.debug("SelectolaxAdapter initialized")

    @property
    def name(self) -> str:
        """Повертає назву адаптера."""
        return "selectolax"

    @property
    def tree(self) -> Any:
        """Повертає оригінальне selectolax дерево."""
        return self._tree

    @property
    def text(self) -> str:
        """
        Повертає весь текст з документа БЕЗ script/style/noscript.

        ВАЖЛИВО: Видаляємо script, style, noscript, svg перед витяганням тексту,
        інакше CSS/JS код потрапляє в text_content і псує SimHash.
        """
        if not self._tree:
            return ""

        # Клонуємо дерево щоб не модифікувати оригінал
        # (важливо для plugins що можуть викликати text кілька разів)
        from selectolax.parser import HTMLParser

        html_copy = self._tree.html
        tree_copy = HTMLParser(html_copy)

        # Видаляємо теги що містять код/стилі, а не контент
        tags_to_remove = ["script", "style", "noscript", "svg", "head"]
        for tag in tags_to_remove:
            for element in tree_copy.css(tag):
                element.decompose()

        return tree_copy.text(separator=" ", strip=True) or ""

    def parse(self, html: str) -> Any:
        """
        Парсить HTML в selectolax дерево.

        ОПТИМІЗОВАНО: В 5-10x швидше за lxml!

        Args:
            html: HTML string

        Returns:
            HTMLParser об'єкт
        """
        self._tree = self._parser_class(html)
        return self._tree

    def find(self, selector: str) -> Optional[TreeElement]:
        """Знаходить перший елемент за CSS селектором."""
        if not self._tree:
            return None

        element = self._tree.css_first(selector)
        if not element:
            return None

        return TreeElement.from_adapter(element, self)

    def find_all(self, selector: str) -> List[TreeElement]:
        """
        Знаходить всі елементи за CSS селектором.

        ОПТИМІЗОВАНО: selectolax.css() в 5-10x швидший за BS4.select()!
        """
        if not self._tree:
            return []

        elements = self._tree.css(selector)
        return [TreeElement.from_adapter(elem, self) for elem in elements]

    def css(self, selector: str) -> List[TreeElement]:
        """CSS селектор (alias для find_all)."""
        return self.find_all(selector)

    def xpath(self, query: str) -> List[TreeElement]:
        """
        XPath запит (не підтримується selectolax).

        Note:
            Selectolax підтримує тільки CSS селектори.
            Для XPath використовуйте lxml adapter.
        """
        logger.warning("Selectolax does not support XPath. Use lxml adapter or convert to CSS.")
        return []

    # Protected методи для TreeElement

    def _get_element_text(self, element: Any) -> str:
        """Повертає текст елемента."""
        if not element:
            return ""
        return element.text(strip=True) or ""

    def _get_element_attribute(self, element: Any, name: str) -> Optional[str]:
        """Повертає атрибут елемента."""
        if not element:
            return None
        return element.attributes.get(name)

    def _find_in_element(self, element: Any, selector: str) -> Optional[TreeElement]:
        """Знаходить дочірній елемент."""
        if not element:
            return None

        child = element.css_first(selector)
        if not child:
            return None

        return TreeElement.from_adapter(child, self)

    def _find_all_in_element(self, element: Any, selector: str) -> List[TreeElement]:
        """Знаходить всі дочірні елементи."""
        if not element:
            return []

        children = element.css(selector)
        return [TreeElement.from_adapter(child, self) for child in children]


def is_selectolax_available() -> bool:
    """
    Перевіряє чи selectolax доступний.

    Returns:
        True якщо selectolax встановлено

    Example:
        >>> if is_selectolax_available():
        ...     adapter = SelectolaxAdapter()
        ... else:
        ...     adapter = BeautifulSoupAdapter()
    """
    return _check_selectolax()
