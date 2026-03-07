"""Утиліти для роботи з HTML."""

import html
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from graph_crawler.shared.constants import (
    MAX_DESCRIPTION_LENGTH,
    MAX_H1_LENGTH,
    MAX_KEYWORDS_LENGTH,
    MAX_TEXT_LENGTH,
    MAX_TITLE_LENGTH,
)
from graph_crawler.shared.utils.url_utils import URLUtils


class HTMLUtils:
    """Допоміжні функції для парсингу HTML."""

    @staticmethod
    def sanitize_text(
        text: Optional[str], max_length: int = MAX_TEXT_LENGTH
    ) -> Optional[str]:
        """
        Санітизує текст: видаляє HTML entities, обмежує довжину, видаляє небезпечні символи.

        Args:
            text: Текст для санітизації
            max_length: Максимальна довжина тексту

        Returns:
            Санітизований текст або None
        """
        if not text:
            return None

        # HTML escape для безпеки
        text = html.escape(text)

        text = " ".join(text.split())

        if len(text) > max_length:
            text = text[:max_length] + "..."

        return text

    @staticmethod
    def parse_html(html: str) -> BeautifulSoup:
        """
        Парсить HTML у BeautifulSoup об'єкт.
        Використовує lxml якщо доступний (2-3x швидше).

        Args:
            html: HTML контент

        Returns:
            BeautifulSoup об'єкт
        """
        try:
            return BeautifulSoup(html, "lxml")
        except Exception:
            return BeautifulSoup(html, "html.parser")

    @staticmethod
    def extract_links(html: str, base_url: str = None) -> List[str]:
        """
        Витягує всі посилання з HTML.

        Args:
            html: HTML контент
            base_url: Базовий URL для відносних посилань

        Returns:
            Список абсолютних URL
        """
        soup = HTMLUtils.parse_html(html)
        links = []

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]

            # Пропускаємо спеціальні посилання
            if href.startswith(("mailto:", "javascript:", "tel:", "#")):
                continue

            # Конвертуємо відносні URL в абсолютні
            if base_url:
                href = URLUtils.make_absolute(base_url, href)

            # Додаємо тільки валідні URL
            if URLUtils.is_valid_url(href):
                links.append(href)

        return links

    @staticmethod
    def extract_text(html: str) -> str:
        """
        Витягує текст з HTML (без тегів).

        Args:
            html: HTML контент

        Returns:
            Текст без HTML тегів
        """
        soup = HTMLUtils.parse_html(html)
        return soup.get_text(separator=" ", strip=True)

    @staticmethod
    def extract_metadata(html: str) -> Dict[str, Any]:
        """
        Витягує метадані з HTML (title, description, keywords, h1).
        Оптимізовано - meta теги витягуються одним запитом.

        БЕЗПЕКА: Всі метадані санітизуються для запобігання XSS.

        Args:
            html: HTML контент

        Returns:
            Словник з санітизованими метаданими
        """
        soup = HTMLUtils.parse_html(html)

        meta_tags = {
            tag.get("name"): tag.get("content")
            for tag in soup.find_all("meta", attrs={"name": True})
            if tag.get("name") in ("description", "keywords")
        }

        # Title
        title_tag = soup.find("title")
        title_text = title_tag.get_text(strip=True) if title_tag else None

        # H1 - шукаємо в основному контенті, ігноруючи modals/popups
        h1_text = HTMLUtils._extract_main_h1(soup)

        return {
            "title": HTMLUtils.sanitize_text(title_text, max_length=MAX_TITLE_LENGTH),
            "description": HTMLUtils.sanitize_text(
                meta_tags.get("description"), max_length=MAX_DESCRIPTION_LENGTH
            ),
            "keywords": HTMLUtils.sanitize_text(
                meta_tags.get("keywords"), max_length=MAX_KEYWORDS_LENGTH
            ),
            "h1": HTMLUtils.sanitize_text(h1_text, max_length=MAX_H1_LENGTH),
        }

    # CSS селектори (class-level constants)
    _H1_MAIN_SELECTOR = (
        'main h1, article h1, [role="main"] h1, '
        '#main-content h1, #main h1, .main-content h1, .content h1'
    )
    _H1_EXCLUDE_SELECTOR = (
        'h1:not(dialog h1):not(nav h1):not(aside h1):not(header h1):not(footer h1)'
        ':not([role="dialog"] h1):not([role="navigation"] h1)'
        ':not(.modal h1):not(.popup h1):not(.cookie h1)'
    )

    @staticmethod
    def _extract_main_h1(soup: BeautifulSoup) -> Optional[str]:
        """
        Витягує H1 з основного контенту (CSS селектори, один запит до DOM).
        """
        # 1. Пріоритет: H1 в main/article
        if h1 := soup.select_one(HTMLUtils._H1_MAIN_SELECTOR):
            if text := h1.get_text(strip=True):
                return text

        # 2. H1 не в modal/nav (CSS :not)
        if h1 := soup.select_one(HTMLUtils._H1_EXCLUDE_SELECTOR):
            if text := h1.get_text(strip=True):
                return text

        # 3. Fallback
        if h1 := soup.find("h1"):
            return h1.get_text(strip=True)

        return None
