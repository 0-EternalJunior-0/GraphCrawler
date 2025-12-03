"""lxml.html реалізація TreeAdapter.
для кращої ізоляції між шарами.
"""

import logging
from typing import Any, List, Optional

from lxml import html as lxml_html

from graph_crawler.infrastructure.adapters.base import BaseTreeAdapter, TreeElement

logger = logging.getLogger(__name__)


class LxmlAdapter(BaseTreeAdapter):
    """
    lxml.html адаптер (швидкий).

    Переваги:
    - В 5-10 разів швидший за BeautifulSoup
    - Менше споживання пам'яті
    - Підтримка XPath

    Недоліки:
    - Гірше обробляє зламаний HTML

    Рекомендації:
    - Використовуйте для великих обсягів (1000-20000 сторінок)
    - Коли швидкість критична

    Використання:
        >>> adapter = LxmlAdapter()
        >>> adapter.parse('<html><title>Test</title></html>')
        >>> elem = adapter.find('title')
        >>> elem.text()
        'Test'
    """

    def __init__(self):
        """Ініціалізує lxml адаптер."""
        self._tree = None

    @property
    def name(self) -> str:
        """Повертає назву адаптера."""
        return "lxml"

    @property
    def tree(self) -> Any:
        """Повертає оригінальне lxml дерево."""
        return self._tree

    @property
    def text(self) -> str:
        """Повертає весь текст з документа."""
        if self._tree is None:
            return ""
        return self._tree.text_content().strip()

    def parse(self, html: str) -> lxml_html.HtmlElement:
        """Парсить HTML в lxml дерево."""
        self._tree = lxml_html.fromstring(html)
        return self._tree

    def find(self, selector: str) -> Optional[TreeElement]:
        """Знаходить перший елемент."""
        if self._tree is None:
            return None

        try:
            elements = self._tree.cssselect(selector)
        except Exception as e:
            logger.error(f"CSS selector error: {e}")
            return None

        if not elements:
            return None

        return TreeElement.from_adapter(elements[0], self)

    def find_all(self, selector: str) -> List[TreeElement]:
        """Знаходить всі елементи."""
        if self._tree is None:
            return []

        try:
            elements = self._tree.cssselect(selector)
        except Exception as e:
            logger.error(f"CSS selector error: {e}")
            return []

        return [TreeElement.from_adapter(elem, self) for elem in elements]

    def css(self, selector: str) -> List[TreeElement]:
        """CSS селектор (alias для find_all)."""
        return self.find_all(selector)

    def xpath(self, query: str) -> List[TreeElement]:
        """
        XPath запит.

        lxml повністю підтримує XPath 1.0.
        """
        if self._tree is None:
            return []

        try:
            elements = self._tree.xpath(query)
        except Exception as e:
            logger.error(f"XPath query error: {e}")
            return []

        # XPath може повертати не тільки елементи, але й текст/атрибути
        result = []
        for elem in elements:
            if isinstance(elem, lxml_html.HtmlElement):
                result.append(TreeElement.from_adapter(elem, self))

        return result

    # Protected методи для TreeElement

    def _get_element_text(self, element: Any) -> str:
        """Повертає текст елемента."""
        if element is None:
            return ""
        # Використовуємо text_content() для отримання всього тексту включно з дочірніми елементами
        text = element.text_content()
        return text.strip() if text else ""

    def _get_element_attribute(self, element: Any, name: str) -> Optional[str]:
        """Повертає атрибут елемента."""
        if element is None or not hasattr(element, "attrib"):
            return None
        return element.attrib.get(name)

    def _find_in_element(self, element: Any, selector: str) -> Optional[TreeElement]:
        """Знаходить дочірній елемент."""
        if element is None:
            return None

        try:
            children = element.cssselect(selector)
        except Exception as e:
            logger.error(f"CSS selector error: {e}")
            return None

        if not children:
            return None

        return TreeElement.from_adapter(children[0], self)

    def _find_all_in_element(self, element: Any, selector: str) -> List[TreeElement]:
        """Знаходить всі дочірні елементи."""
        if element is None:
            return []

        try:
            children = element.cssselect(selector)
        except Exception as e:
            logger.error(f"CSS selector error: {e}")
            return []

        return [TreeElement.from_adapter(child, self) for child in children]
