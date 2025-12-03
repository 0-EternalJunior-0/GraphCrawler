"""Парсер sitemap для побудови графу з sitemap.xml файлів."""

import logging
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional
from urllib.parse import urljoin

import requests

logger = logging.getLogger(__name__)


class SitemapParser:
    """
    Парсер для sitemap.xml файлів.

    Підтримує:
    - sitemap index (посилання на інші sitemap)
    - urlset (список URL)
    - robots.txt для отримання sitemap URLs

    Приклад використання:
        >>> parser = SitemapParser()
        >>> result = parser.parse_from_robots("https://example.com")
        >>> print(result['sitemap_urls'])
        >>> print(result['urls'])
    """

    # XML namespaces для sitemap
    SITEMAP_NS = {
        "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
        "news": "http://www.google.com/schemas/sitemap-news/0.9",
        "image": "http://www.google.com/schemas/sitemap-image/1.1",
        "video": "http://www.google.com/schemas/sitemap-video/1.1",
    }

    def __init__(self, user_agent: str = "GraphCrawler/2.0"):
        """
        Ініціалізація парсера.

        Args:
            user_agent: User-Agent для HTTP запитів
        """
        self.user_agent = user_agent
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})

    def parse_from_robots(self, base_url: str) -> Dict[str, List[str]]:
        """
        Парсить sitemap URLs з robots.txt та завантажує їх.

        Args:
            base_url: Базовий URL сайту (https://example.com)

        Returns:
            Dict з ключами:
            - 'sitemap_urls': список знайдених sitemap URLs
            - 'urls': всі URL з усіх sitemap
            - 'sitemap_indexes': sitemap index URLs (якщо є)
        """
        from urllib.robotparser import RobotFileParser

        result = {"sitemap_urls": [], "urls": [], "sitemap_indexes": []}

        # Завантажити robots.txt
        robots_url = urljoin(base_url, "/robots.txt")
        parser = RobotFileParser()

        try:
            parser.set_url(robots_url)
            parser.read()

            # Отримати sitemap URLs з robots.txt
            # RobotFileParser зберігає sitemaps в атрибуті
            if hasattr(parser, "site_maps") and parser.site_maps():
                sitemap_urls = list(parser.site_maps())
                result["sitemap_urls"] = sitemap_urls
                logger.info(f"Знайдено {len(sitemap_urls)} sitemap URLs в robots.txt")

                # Парсити кожен sitemap
                for sitemap_url in sitemap_urls:
                    sitemap_data = self.parse_sitemap(sitemap_url)
                    result["urls"].extend(sitemap_data["urls"])
                    result["sitemap_indexes"].extend(sitemap_data["sitemap_indexes"])
            else:
                logger.warning(f"Sitemap не знайдено в {robots_url}")
                # Спробувати типові URL
                default_sitemaps = [
                    urljoin(base_url, "/sitemap.xml"),
                    urljoin(base_url, "/sitemap_index.xml"),
                ]
                for sitemap_url in default_sitemaps:
                    try:
                        sitemap_data = self.parse_sitemap(sitemap_url)
                        if sitemap_data["urls"] or sitemap_data["sitemap_indexes"]:
                            result["sitemap_urls"].append(sitemap_url)
                            result["urls"].extend(sitemap_data["urls"])
                            result["sitemap_indexes"].extend(
                                sitemap_data["sitemap_indexes"]
                            )
                            logger.info(f"Знайдено sitemap на {sitemap_url}")
                            break
                    except Exception as e:
                        logger.debug(f"Не вдалося завантажити {sitemap_url}: {e}")

        except Exception as e:
            logger.error(f"Помилка при читанні robots.txt з {robots_url}: {e}")

        # Видалити дублікати
        result["urls"] = list(set(result["urls"]))
        result["sitemap_indexes"] = list(set(result["sitemap_indexes"]))

        logger.info(f"Всього знайдено {len(result['urls'])} URLs в sitemap")
        return result

    def parse_sitemap(self, sitemap_url: str) -> Dict[str, List[str]]:
        """
        Парсить один sitemap файл.

        Args:
            sitemap_url: URL sitemap файлу

        Returns:
            Dict з ключами:
            - 'urls': список URL з urlset
            - 'sitemap_indexes': список sitemap URLs з sitemapindex
        """
        result = {"urls": [], "sitemap_indexes": []}

        try:
            response = self.session.get(sitemap_url, timeout=30)
            response.raise_for_status()

            # Парсити XML
            root = ET.fromstring(response.content)

            # Визначити тип sitemap
            if root.tag.endswith("sitemapindex"):
                # Це sitemap index - містить посилання на інші sitemap
                result["sitemap_indexes"] = self._parse_sitemap_index(root)
                logger.info(
                    f"Знайдено {len(result['sitemap_indexes'])} sitemap в index {sitemap_url}"
                )

            elif root.tag.endswith("urlset"):
                # Це звичайний sitemap - містить URLs
                result["urls"] = self._parse_urlset(root)
                logger.info(
                    f"Знайдено {len(result['urls'])} URLs в sitemap {sitemap_url}"
                )

            else:
                logger.warning(f"Невідомий тип sitemap: {root.tag}")

        except Exception as e:
            logger.error(f"Помилка при парсингу sitemap {sitemap_url}: {e}")

        return result

    def _parse_sitemap_index(self, root: ET.Element) -> List[str]:
        """
        Парсить sitemap index (посилання на інші sitemap).

        Args:
            root: XML root element

        Returns:
            Список sitemap URLs
        """
        sitemap_urls = []

        # Спробувати з namespace
        sitemaps = root.findall(".//sm:sitemap/sm:loc", self.SITEMAP_NS)
        if not sitemaps:
            # Спробувати без namespace
            sitemaps = root.findall(".//sitemap/loc")

        for sitemap in sitemaps:
            url = sitemap.text
            if url:
                sitemap_urls.append(url.strip())

        return sitemap_urls

    def _parse_urlset(self, root: ET.Element) -> List[str]:
        """
        Парсить urlset (список URLs).

        Args:
            root: XML root element

        Returns:
            Список URLs
        """
        urls = []

        # Спробувати з namespace
        url_elements = root.findall(".//sm:url/sm:loc", self.SITEMAP_NS)
        if not url_elements:
            # Спробувати без namespace
            url_elements = root.findall(".//url/loc")

        for url_elem in url_elements:
            url = url_elem.text
            if url:
                urls.append(url.strip())

        return urls

    def close(self):
        """Закрити сесію."""
        self.session.close()
