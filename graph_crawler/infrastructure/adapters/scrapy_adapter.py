"""Scrapy Selector реалізація TreeAdapter."""

import logging
from typing import Any, List, Optional

try:
    from scrapy.selector import Selector  # type: ignore[import-not-found]
except ImportError:
    Selector = None  # type: ignore[misc,assignment]

from graph_crawler.infrastructure.adapters.base import BaseTreeAdapter, TreeElement

logger = logging.getLogger(__name__)


class ScrapyAdapter(BaseTreeAdapter):
    """
    Scrapy Selector адаптер.

    """

    def __init__(self):
        """Ініціалізує Scrapy адаптер."""
        self._tree = None

    @property
    def name(self) -> str:
        """Повертає назву адаптера."""
        return "scrapy"

    @property
    def tree(self) -> Any:
        """Повертає оригінальний Scrapy Selector."""
        return self._tree

    @property
    def text(self) -> str:
        """Повертає весь текст з документа."""
        if not self._tree:
            return ""
        return " ".join(self._tree.css("*::text").getall()).strip()

    def parse(self, html: str) -> "Selector":  # type: ignore[name-defined]
        """Парсить HTML в Scrapy Selector."""
        self._tree = Selector(text=html)  # type: ignore[misc]
        return self._tree

    def find(self, selector: str) -> Optional[TreeElement]:
        """Знаходить перший елемент."""
        if not self._tree:
            return None

        try:
            elements = self._tree.css(selector)
        except Exception as e:
            logger.error("CSS selector error: %s", e)
            return None

        if not elements:
            return None

        return TreeElement(elements[0], self)

    def find_all(self, selector: str) -> List[TreeElement]:
        """Знаходить всі елементи."""
        if not self._tree:
            return []

        try:
            elements = self._tree.css(selector)
        except Exception as e:
            logger.error("CSS selector error: %s", e)
            return []

        return [TreeElement(elem, self) for elem in elements]

    def css(self, selector: str) -> List[TreeElement]:
        """CSS селектор (alias для find_all)."""
        return self.find_all(selector)

    def xpath(self, query: str) -> List[TreeElement]:
        """
        XPath запит.

        Scrapy повністю підтримує XPath 1.0.
        """
        if not self._tree:
            return []

        try:
            elements = self._tree.xpath(query)
        except Exception as e:
            logger.error("XPath query error: %s", e)
            return []

        return [TreeElement(elem, self) for elem in elements]

    # Protected методи для TreeElement

    def _get_element_text(self, element: Any) -> str:
        """Повертає текст елемента."""
        if not element:
            return ""
        try:
            return element.get().strip() if element.get() else ""
        except (AttributeError, TypeError):
            return ""
        except Exception:
            return ""  # Fallback для невідомих помилок

    def _get_element_attribute(self, element: Any, name: str) -> Optional[str]:
        """Повертає атрибут елемента."""
        if not element:
            return None
        try:
            return element.xpath(f"@{name}").get()
        except (AttributeError, TypeError):
            return None
        except Exception:
            return None  # Fallback для невідомих помилок

    def _find_in_element(self, element: Any, selector: str) -> Optional[TreeElement]:
        """Знаходить дочірній елемент."""
        if not element:
            return None

        try:
            children = element.css(selector)
        except Exception as e:
            logger.error("CSS selector error: %s", e)
            return None

        if not children:
            return None

        return TreeElement(children[0], self)

    def _find_all_in_element(self, element: Any, selector: str) -> List[TreeElement]:
        """Знаходить всі дочірні елементи."""
        if not element:
            return []

        try:
            children = element.css(selector)
        except Exception as e:
            logger.error("CSS selector error: %s", e)
            return []

        return [TreeElement(child, self) for child in children]
