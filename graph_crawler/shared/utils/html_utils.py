"""Утиліти для роботи з HTML."""

import html
import re
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

        # Видаляємо зайві пробіли
        text = " ".join(text.split())

        # Обмежуємо довжину
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

        # H1
        h1_tag = soup.find("h1")
        h1_text = h1_tag.get_text(strip=True) if h1_tag else None

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
