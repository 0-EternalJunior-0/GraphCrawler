"""Strategy Pattern для HTML парсерів."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class BaseHTMLParser(ABC):
    """
    Базова стратегія для HTML парсингу.

    Strategy Pattern дозволяє легко змінювати парсер.

    Приклади стратегій:
    - BeautifulSoupParser - BeautifulSoup4
    - LxmlParser - lxml
    - SelectolibParser - Scrapy selectors
    - CustomParser - кастомна логіка
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Назва парсера."""
        pass

    @abstractmethod
    def parse(self, html: str) -> Any:
        """
        Парсить HTML.

        Args:
            html: HTML контент

        Returns:
            Парсер tree object
        """
        pass

    @abstractmethod
    def extract_links(self, tree: Any) -> List[str]:
        """
        Витягує всі посилання.

        Args:
            tree: Парсер tree

        Returns:
            Список URL
        """
        pass

    @abstractmethod
    def extract_metadata(self, tree: Any) -> Dict[str, Any]:
        """
        Витягує метадані зі сторінки.

        Args:
            tree: Парсер tree

        Returns:
            Словник з метаданими (title, description, keywords, h1)
        """
        pass

    @abstractmethod
    def extract_text(self, tree: Any) -> str:
        """
        Витягує текстовий контент (без HTML тегів).

        Args:
            tree: Парсер tree

        Returns:
            Текстовий контент
        """
        pass
