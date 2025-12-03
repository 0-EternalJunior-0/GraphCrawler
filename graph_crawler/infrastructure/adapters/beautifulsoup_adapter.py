"""BeautifulSoup реалізація TreeAdapter.
для кращої ізоляції між шарами.

ОПТИМІЗОВАНО: Автоматично використовує lxml якщо доступний (2-3x швидше).
"""

import logging
from typing import Any, List, Optional

from bs4 import BeautifulSoup

from graph_crawler.infrastructure.adapters.base import BaseTreeAdapter, TreeElement

logger = logging.getLogger(__name__)


# Визначаємо найкращий доступний парсер
def _get_best_parser() -> str:
    """Повертає найкращий доступний парсер (lxml > html.parser)."""
    try:
        import lxml

        return "lxml"
    except ImportError:
        return "html.parser"


_DEFAULT_PARSER = _get_best_parser()


class BeautifulSoupAdapter(BaseTreeAdapter):
    """
    BeautifulSoup адаптер (дефолтний).

    Переваги:
    - Найпростіший API
    - Добре обробляє зламаний HTML
    - Багато документації

    Недоліки:
    - Повільніший за lxml
    - Більше споживання пам'яті

    Використання:
        >>> adapter = BeautifulSoupAdapter()
        >>> adapter.parse('<html><title>Test</title></html>')
        >>> elem = adapter.find('title')
        >>> elem.text()
        'Test'

    Args:
        parser_backend: 'html.parser' (дефолт), 'lxml', або 'html5lib'
    """

    def __init__(self, parser_backend: str = None):
        """
        Ініціалізує BeautifulSoup адаптер.

        Args:
            parser_backend: Backend парсер для BeautifulSoup.
                           Можливі значення:
                           - 'html.parser' (стандартний Python)
                           - 'lxml' (швидший, 2-3x)
                           - 'html5lib' (найтолерантніший)
                           - None (автовибір найкращого)
        """
        self.parser_backend = parser_backend or _DEFAULT_PARSER
        self._tree = None

        if parser_backend is None:
            logger.debug(f"Auto-selected parser backend: {self.parser_backend}")

    @property
    def name(self) -> str:
        """Повертає назву адаптера."""
        return f"beautifulsoup-{self.parser_backend}"

    @property
    def tree(self) -> Any:
        """Повертає оригінальне BeautifulSoup дерево."""
        return self._tree

    @property
    def text(self) -> str:
        """Повертає весь текст з документа."""
        if not self._tree:
            return ""
        return self._tree.get_text(separator=" ", strip=True)

    def parse(self, html: str) -> BeautifulSoup:
        """
        Парсить HTML в BeautifulSoup дерево.

        Args:
            html: HTML string

        Returns:
            BeautifulSoup об'єкт
        """
        self._tree = BeautifulSoup(html, self.parser_backend)
        return self._tree

    def find(self, selector: str) -> Optional[TreeElement]:
        """Знаходить перший елемент."""
        if not self._tree:
            return None

        element = self._tree.select_one(selector)
        if not element:
            return None

        return TreeElement.from_adapter(element, self)

    def find_all(self, selector: str) -> List[TreeElement]:
        """Знаходить всі елементи."""
        if not self._tree:
            return []

        elements = self._tree.select(selector)
        return [TreeElement.from_adapter(elem, self) for elem in elements]

    def css(self, selector: str) -> List[TreeElement]:
        """CSS селектор (alias для find_all)."""
        return self.find_all(selector)

    def xpath(self, query: str) -> List[TreeElement]:
        """
        XPath запит (не підтримується BeautifulSoup).

        Note:
            BeautifulSoup не підтримує XPath.
            Цей метод повертає порожній список.
            Використовуйте lxml або Scrapy для XPath.
        """
        logger.warning(
            "BeautifulSoup does not support XPath. Use lxml or Scrapy adapter."
        )
        return []

    # Protected методи для TreeElement

    def _get_element_text(self, element: Any) -> str:
        """Повертає текст елемента."""
        return element.get_text(strip=True) if element else ""

    def _get_element_attribute(self, element: Any, name: str) -> Optional[str]:
        """Повертає атрибут елемента."""
        if not element or not hasattr(element, "attrs"):
            return None
        return element.attrs.get(name)

    def _find_in_element(self, element: Any, selector: str) -> Optional[TreeElement]:
        """Знаходить дочірній елемент."""
        if not element:
            return None

        child = element.select_one(selector)
        if not child:
            return None

        return TreeElement.from_adapter(child, self)

    def _find_all_in_element(self, element: Any, selector: str) -> List[TreeElement]:
        """Знаходить всі дочірні елементи."""
        if not element:
            return []

        children = element.select(selector)
        return [TreeElement.from_adapter(child, self) for child in children]
