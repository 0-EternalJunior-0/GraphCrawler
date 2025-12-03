"""BeautifulSoup HTML Parser Strategy."""

from typing import Any, Dict, List

from graph_crawler.application.use_cases.crawling.parsers.base import BaseHTMLParser


class HTMLParser(BaseHTMLParser):
    """
    HTML парсер на основі BeautifulSoup4.
    """

    @property
    def name(self) -> str:
        return "beautifulsoup"

    def parse(self, html: str) -> Any:
        """
        Парсить HTML через BeautifulSoup.

        docs: Реалізувати:
        - BeautifulSoup(html, 'html.parser')
        - Обробку помилок
        """
        # docs: from bs4 import BeautifulSoup
        # return BeautifulSoup(html, 'html.parser')
        pass

    def extract_links(self, tree: Any) -> List[str]:
        """
        Витягує всі <a href>.

        docs: Реалізувати:
        - tree.find_all('a', href=True)
        - Витяг href атрибутів
        - Фільтрацію (#, javascript:, mailto:)
        """
        return []

    def extract_metadata(self, tree: Any) -> Dict[str, Any]:
        """
        Витягує метадані.

        docs: Реалізувати витяг:
        - title: tree.find('title')
        - description: tree.find('meta', {'name': 'description'})
        - keywords: tree.find('meta', {'name': 'keywords'})
        - h1: tree.find('h1')
        - og:title, og:description
        """
        return {}

    def extract_text(self, tree: Any) -> str:
        """
        Витягує текст.

        docs: Реалізувати:
        - tree.get_text()
        - Очищення зайвих пробілів
        - Видалення <script>, <style>
        """
        return ""
