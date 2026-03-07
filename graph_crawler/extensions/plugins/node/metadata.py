"""Плагін для витягування метаданих з HTML.

Витягує базові метадані:
- title
- description (meta)
- keywords (meta)
- h1

А також SEO метадані важливі для краулерів (Googlebot, Bingbot тощо):
- canonical_url - канонічний URL сторінки
- robots - директиви для краулерів (noindex, nofollow тощо)
- hreflang - альтернативні мовні версії сторінки
- x_robots_tag - X-Robots-Tag з HTTP заголовків (якщо доступно)
"""

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from graph_crawler.extensions.plugins.node.base import (
    BaseNodePlugin,
    NodePluginContext,
    NodePluginType,
)
from graph_crawler.shared.constants import (
    MAX_CANONICAL_URL_LENGTH,
    MAX_DESCRIPTION_LENGTH,
    MAX_H1_LENGTH,
    MAX_HREFLANG_ENTRIES,
    MAX_KEYWORDS_LENGTH,
    MAX_ROBOTS_CONTENT_LENGTH,
    MAX_TITLE_LENGTH,
)

logger = logging.getLogger(__name__)


class MetadataExtractorPlugin(BaseNodePlugin):
    """
    Дефолтний плагін для витягування метаданих з HTML.

    Витягує базові метадані:
    - title
    - description (meta)
    - keywords (meta)
    - h1

    А також SEO метадані важливі для краулерів:
    - canonical_url - канонічний URL сторінки (<link rel="canonical">)
    - robots - директиви для краулерів (noindex, nofollow, noarchive тощо)
    - hreflang - альтернативні мовні версії (<link rel="alternate" hreflang="...">)
    - meta_robots - вміст meta name="robots"
    - googlebot - специфічні директиви для Googlebot
    - bingbot - специфічні директиви для Bingbot

    Цей плагін можна:
    - Підключити (дефолтно увімкнено)
    - Відключити (config={'enabled': False})
    - Замінити на свій власний плагін

    Приклад відключення:
        config = CrawlerConfig(
            url="...",
            node_plugins=[
                MetadataExtractorPlugin(config={'enabled': False})
            ]
        )

    Приклад отримання канонічного URL:
        node = graph.get_node(url)
        canonical = node.get_canonical_url()  # Law of Demeter wrapper
        # або
        canonical = node.metadata.get('canonical_url')

    Приклад перевірки індексації:
        robots = node.metadata.get('robots', {})
        is_indexable = not robots.get('noindex', False)
        is_followable = not robots.get('nofollow', False)
    """

    @property
    def plugin_type(self) -> NodePluginType:
        return NodePluginType.ON_HTML_PARSED

    @property
    def name(self) -> str:
        return "MetadataExtractorPlugin"

    def execute(self, context: NodePluginContext) -> NodePluginContext:
        """Витягує метадані з HTML дерева. Оптимізовано - мінімум DOM операцій."""
        # Перевірка чи не пропущено витягування метаданих
        if context.skip_metadata_extraction:
            logger.debug(f"Skipping metadata extraction for {context.url}")
            return context

        # Перевірка наявності parser
        if not context.parser:
            logger.warning(f"No parser for metadata extraction: {context.url}")
            return context

        try:
            parser = context.parser

            # Збираємо всі meta[name] теги за один прохід
            meta_tags = {}
            for elem in parser.find_all("meta[name]"):
                name = elem.get_attribute("name")
                content = elem.get_attribute("content")
                if name and content:
                    meta_tags[name.lower()] = content

            # Title
            if title_elem := parser.find("title"):
                if title_text := title_elem.text():
                    context.set_metadata(
                        "title", self._sanitize_text(title_text, MAX_TITLE_LENGTH)
                    )

            # Description та Keywords з кешу
            if desc := meta_tags.get("description"):
                context.set_metadata(
                    "description", self._sanitize_text(desc, MAX_DESCRIPTION_LENGTH)
                )
            if keywords := meta_tags.get("keywords"):
                context.set_metadata(
                    "keywords", self._sanitize_text(keywords, MAX_KEYWORDS_LENGTH)
                )

            # H1 - шукаємо в основному контенті, ігноруючи modals/popups/navigation
            h1_text = self._extract_main_h1(parser)
            if h1_text:
                context.set_metadata(
                    "h1", self._sanitize_text(h1_text, MAX_H1_LENGTH)
                )

            # ==================== SEO МЕТАДАНІ ДЛЯ КРАУЛЕРІВ ====================

            # Canonical URL
            canonical_url = self._extract_canonical(parser, context.url)
            if canonical_url:
                context.set_metadata("canonical_url", canonical_url)

            # Robots директиви (meta robots, googlebot, bingbot тощо)
            robots_data = self._extract_robots_directives(meta_tags)
            if robots_data:
                context.set_metadata("robots", robots_data)

            # Hreflang - альтернативні мовні версії
            hreflang_data = self._extract_hreflang(parser, context.url)
            if hreflang_data:
                context.set_metadata("hreflang", hreflang_data)

            # Language - мова сторінки з <html lang="...">
            language = self._extract_language(parser)
            if language:
                context.set_metadata("language", language)

            logger.debug(
                f"Extracted metadata for {context.url}: {list(context.metadata.keys())}"
            )

        except Exception as e:
            logger.error(f"Error extracting metadata for {context.url}: {e}")

        return context

    # CSS селектор для H1 в основному контенті (виключаючи modals/nav/etc)
    # Один селектор - один запит до DOM, максимально швидко
    _H1_MAIN_CONTENT_SELECTOR = (
        'main h1, article h1, [role="main"] h1, '
        '#main-content h1, #main h1, .main-content h1, '
        '.content h1, .page-content h1'
    )

    # H1 що НЕ знаходяться в проблемних контейнерах
    _H1_EXCLUDE_SELECTOR = (
        'h1:not(dialog h1):not(nav h1):not(aside h1):not(header h1):not(footer h1)'
        ':not([role="dialog"] h1):not([role="navigation"] h1):not([role="banner"] h1)'
        ':not(.modal h1):not(.popup h1):not(.cookie h1):not(.consent h1)'
    )

    def _extract_main_h1(self, parser: Any) -> Optional[str]:
        """
        Витягує H1 з основного контенту сторінки.

        Використовує CSS селектори для швидкого пошуку (один запит до DOM).

        Стратегія:
        1. Шукаємо H1 в main/article/[role=main] (пріоритет)
        2. Шукаємо H1 що не в modal/nav/aside (CSS :not())
        3. Fallback - перший H1

        Args:
            parser: Tree adapter

        Returns:
            Текст H1 або None
        """
        try:
            # 1. Пріоритет: H1 в основному контенті
            if h1_elem := parser.find(self._H1_MAIN_CONTENT_SELECTOR):
                if h1_text := h1_elem.text():
                    return h1_text.strip()

            # 2. H1 що не в modal/nav/aside (CSS :not selector)
            if h1_elem := parser.find(self._H1_EXCLUDE_SELECTOR):
                if h1_text := h1_elem.text():
                    return h1_text.strip()

            # 3. Fallback - перший H1
            if h1_elem := parser.find("h1"):
                if h1_text := h1_elem.text():
                    return h1_text.strip()

        except Exception as e:
            logger.debug(f"Error extracting main H1: {e}")

        return None

    def _extract_canonical(self, parser: Any, base_url: str) -> Optional[str]:
        """
        Витягує canonical URL з <link rel="canonical">.

        Args:
            parser: Tree adapter
            base_url: Базовий URL для резолвінгу відносних посилань

        Returns:
            Абсолютний canonical URL або None
        """
        try:
            canonical_elem = parser.find('link[rel="canonical"]')
            if canonical_elem:
                href = canonical_elem.get_attribute("href")
                if href:
                    # Резолвимо відносний URL до абсолютного
                    canonical_url = urljoin(base_url, href.strip())
                    if len(canonical_url) <= MAX_CANONICAL_URL_LENGTH:
                        return canonical_url
                    else:
                        logger.warning(
                            f"Canonical URL too long ({len(canonical_url)} chars): {canonical_url[:100]}..."
                        )
        except Exception as e:
            logger.debug(f"Error extracting canonical URL: {e}")
        return None

    def _extract_robots_directives(self, meta_tags: Dict[str, str]) -> Dict[str, Any]:
        """
        Витягує robots директиви з meta тегів.

        Підтримує:
        - meta name="robots" - загальні директиви
        - meta name="googlebot" - специфічні для Google
        - meta name="bingbot" - специфічні для Bing
        - meta name="googlebot-news" - для Google News

        Args:
            meta_tags: Словник meta тегів {name: content}

        Returns:
            Словник з директивами:
            {
                'content': 'noindex, nofollow',  # оригінальний вміст
                'noindex': True/False,
                'nofollow': True/False,
                'noarchive': True/False,
                'nosnippet': True/False,
                'noimageindex': True/False,
                'googlebot': {...},  # специфічні директиви
                'bingbot': {...}
            }
        """
        robots_data = {}

        # Основні robots директиви
        robots_content = meta_tags.get("robots", "")
        if robots_content:
            robots_data["content"] = self._sanitize_text(
                robots_content, MAX_ROBOTS_CONTENT_LENGTH
            )
            robots_data.update(self._parse_robots_content(robots_content))

        # Googlebot специфічні директиви
        googlebot_content = meta_tags.get("googlebot", "")
        if googlebot_content:
            robots_data["googlebot"] = {
                "content": self._sanitize_text(
                    googlebot_content, MAX_ROBOTS_CONTENT_LENGTH
                ),
                **self._parse_robots_content(googlebot_content)
            }

        # Googlebot-news
        googlebot_news = meta_tags.get("googlebot-news", "")
        if googlebot_news:
            robots_data["googlebot_news"] = {
                "content": self._sanitize_text(
                    googlebot_news, MAX_ROBOTS_CONTENT_LENGTH
                ),
                **self._parse_robots_content(googlebot_news)
            }

        # Bingbot специфічні директиви
        bingbot_content = meta_tags.get("bingbot", "")
        if bingbot_content:
            robots_data["bingbot"] = {
                "content": self._sanitize_text(
                    bingbot_content, MAX_ROBOTS_CONTENT_LENGTH
                ),
                **self._parse_robots_content(bingbot_content)
            }

        return robots_data

    def _parse_robots_content(self, content: str) -> Dict[str, bool]:
        """
        Парсить robots content на окремі директиви.

        Args:
            content: Вміст meta robots, напр. "noindex, nofollow, noarchive"

        Returns:
            Словник директив {directive: True}
        """
        directives = {}

        # Стандартні robots директиви (як позитивні так і негативні)
        known_directives = {
            "index", "noindex", "follow", "nofollow", "none", "all",
            "noarchive", "archive", "nosnippet", "snippet",
            "noimageindex", "imageindex", "nocache", "cache",
            "notranslate", "translate", "noodp", "noydir",
            "unavailable_after", "max-snippet", "max-image-preview",
            "max-video-preview", "indexifembedded"
        }

        # Парсимо директиви розділені комою або пробілом
        parts = content.lower().replace(",", " ").split()

        for part in parts:
            part = part.strip()
            if not part:
                continue

            # Обробка директив з параметрами (напр. max-snippet:50)
            directive_name = part.split(":")[0]

            if directive_name in known_directives:
                directives[directive_name.replace("-", "_")] = True

            # Спеціальний випадок: "none" = noindex + nofollow
            if part == "none":
                directives["noindex"] = True
                directives["nofollow"] = True

            # Спеціальний випадок: "all" = index + follow (дефолт)
            elif part == "all":
                directives["index"] = True
                directives["follow"] = True

        return directives

    def _extract_hreflang(self, parser: Any, base_url: str) -> List[Dict[str, str]]:
        """
        Витягує hreflang альтернативи з <link rel="alternate" hreflang="...">.

        Важливо для багатомовних сайтів та локалізацій.

        Args:
            parser: Tree adapter
            base_url: Базовий URL для резолвінгу відносних посилань

        Returns:
            Список альтернатив:
            [
                {'hreflang': 'en', 'href': 'https://example.com/en/page'},
                {'hreflang': 'uk', 'href': 'https://example.com/uk/page'},
                {'hreflang': 'x-default', 'href': 'https://example.com/page'}
            ]
        """
        hreflang_list = []

        try:
            # Шукаємо всі link[hreflang] (альтернативні версії)
            alternate_links = parser.find_all('link[hreflang]')

            for link in alternate_links:
                hreflang = link.get_attribute("hreflang")
                href = link.get_attribute("href")

                if hreflang and href:
                    # Резолвимо відносний URL
                    absolute_href = urljoin(base_url, href.strip())

                    hreflang_list.append({
                        "hreflang": hreflang.strip().lower(),
                        "href": absolute_href
                    })

                    # Ліміт на кількість записів
                    if len(hreflang_list) >= MAX_HREFLANG_ENTRIES:
                        logger.warning(
                            f"Too many hreflang entries ({len(hreflang_list)}), "
                            f"truncating to {MAX_HREFLANG_ENTRIES}"
                        )
                        break

        except Exception as e:
            logger.debug(f"Error extracting hreflang: {e}")

        return hreflang_list

    def _extract_language(self, parser: Any) -> Optional[str]:
        """
        Витягує мову сторінки з <html lang="...">.

        Args:
            parser: Tree adapter

        Returns:
            Мовний код (напр. "en", "uk", "en-US") або None
        """
        try:
            html_elem = parser.find("html")
            if html_elem:
                lang = html_elem.get_attribute("lang")
                if lang:
                    # Нормалізуємо та обмежуємо довжину (max 10 символів для "en-US" тощо)
                    return lang.strip().lower()[:10]
        except Exception as e:
            logger.debug(f"Error extracting language: {e}")
        return None

    @staticmethod
    def _sanitize_text(text: str, max_length: int) -> str:
        """Санітизує текст: видаляє зайві пробіли та обмежує довжину."""
        if not text:
            return ""

        text = " ".join(text.split())

        if len(text) > max_length:
            text = text[:max_length] + "..."

        return text
