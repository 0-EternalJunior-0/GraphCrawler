"""Парсер sitemap для побудови графу з sitemap.xml файлів.

ОПТИМІЗОВАНО для Python 3.14:
- Async HTTP через aiohttp замість синхронного requests
- Паралельне завантаження sitemap через asyncio.gather()
- ThreadPoolExecutor для CPU-bound XML парсингу
- Збережено sync версію для зворотної сумісності

ВИПРАВЛЕННЯ (Лютий 2025):
- P0: Додано підтримку gzip sitemap (автоматична декомпресія)
- P0: Додано ліміт розміру sitemap (MAX_SITEMAP_SIZE = 50MB)
- P1: Додано валідацію Content-Type
- P1: Instance-level ThreadPoolExecutor замість глобального
"""

import asyncio
import gzip
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse
from xml.etree.ElementTree import (
    Element,  # Тип Element для type hints (defusedxml не має цього атрибуту)
)

import defusedxml.ElementTree as ET  # Безпечний XML парсер (захист від XXE атак)

logger = logging.getLogger(__name__)

MAX_SITEMAP_SIZE = 50 * 1024 * 1024  # 50 MB

ALLOWED_CONTENT_TYPES = [
    "text/xml",
    "application/xml",
    "application/x-gzip",
    "application/gzip",
    "text/plain",  # Деякі сервери віддають sitemap як text/plain
]

# ThreadPoolExecutor для CPU-bound XML парсингу (Python 3.14 free-threading optimized)
# ПРИМІТКА: Це дефолтний глобальний executor, але кожен SitemapParser
# створює власний instance-level executor для уникнення race conditions
_xml_workers = (os.cpu_count() or 4) * 2
_xml_executor = ThreadPoolExecutor(max_workers=_xml_workers, thread_name_prefix="xml_parser_")


class SitemapParser:
    """
    Async парсер для sitemap.xml файлів.

    """

    # XML namespaces для sitemap
    SITEMAP_NS = {
        "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
        "news": "http://www.google.com/schemas/sitemap-news/0.9",
        "image": "http://www.google.com/schemas/sitemap-image/1.1",
        "video": "http://www.google.com/schemas/sitemap-video/1.1",
    }

    def __init__(
        self,
        user_agent: str = "GraphCrawler/2.0",
        timeout: int = 30,
        http_client: str = "requests",
        browser_config: Optional[dict] = None,
    ):
        """
        Ініціалізація парсера.

        Args:
            user_agent: User-Agent для HTTP запитів
            timeout: Timeout для HTTP запитів (секунди)
            http_client: HTTP клієнт для sync запитів:
                - "requests" (default): стандартний requests
                - "cloudscraper": для обходу Cloudflare захисту
            browser_config: Конфігурація браузера для cloudscraper:
                - browser: "chrome" (default), "firefox"
                - platform: "windows" (default), "linux", "darwin"
                - mobile: False (default), True
        """
        self.user_agent = user_agent
        self.timeout = timeout
        self.http_client_type = http_client
        self.browser_config = browser_config or {
            "browser": "chrome",
            "platform": "windows",
            "mobile": False,
        }
        self._session = None  # Lazy initialization для aiohttp
        self._sync_session = None  # Lazy initialization для sync HTTP клієнта

        # Замість глобального executor, кожен SitemapParser має свій
        # Це запобігає race conditions при паралельному використанні
        self._xml_executor = ThreadPoolExecutor(
            max_workers=4, thread_name_prefix=f"xml_parser_{id(self)}_"
        )

    def _get_sync_session(self):
        """
        Lazy initialization для sync HTTP клієнта.

        Підтримує:
        - requests (стандартний)
        - cloudscraper (для обходу Cloudflare)

        ВИПРАВЛЕННЯ (Лютий 2025):
        1. НЕ перезаписуємо User-Agent для cloudscraper!
           cloudscraper використовує власний User-Agent для обходу Cloudflare.
        2. Якщо browser_config не вказано явно - дозволяємо cloudscraper
           самому визначити найкращу конфігурацію (auto-detect).
        """
        if self._sync_session is None:
            if self.http_client_type == "cloudscraper":
                try:
                    import cloudscraper

                    # Інакше - дозволяємо cloudscraper auto-detect (найкращий результат)
                    default_browser_config = {
                        "browser": "chrome",
                        "platform": "windows",
                        "mobile": False,
                    }

                    if self.browser_config and self.browser_config != default_browser_config:
                        # Явно вказана конфігурація
                        self._sync_session = cloudscraper.create_scraper(
                            browser=self.browser_config,
                            delay=0,
                        )
                        logger.info(
                            f"Using CloudScraper with explicit browser config: {self.browser_config}"
                        )
                    else:
                        # Auto-detect - cloudscraper сам визначить найкращу конфігурацію
                        # Це працює КРАЩЕ ніж явно вказана конфігурація!
                        self._sync_session = cloudscraper.create_scraper()
                        logger.info(
                            "Using CloudScraper with auto-detect browser config (recommended)"
                        )

                    # НЕ встановлюємо User-Agent для cloudscraper!
                    # cloudscraper має власний User-Agent який імітує браузер

                except ImportError:
                    logger.warning(
                        "cloudscraper not installed, falling back to requests. "
                        "Install with: pip install cloudscraper"
                    )
                    import requests as sync_requests

                    self._sync_session = sync_requests.Session()
                    # Для fallback requests - встановлюємо User-Agent
                    self._sync_session.headers.update({"User-Agent": self.user_agent})
            else:
                import requests as sync_requests

                self._sync_session = sync_requests.Session()
                self._sync_session.headers.update({"User-Agent": self.user_agent})

        return self._sync_session

    async def _get_session(self):
        """Lazy initialization для aiohttp ClientSession."""
        if self._session is None or self._session.closed:
            import aiohttp

            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self._session = aiohttp.ClientSession(
                headers={"User-Agent": self.user_agent}, timeout=timeout
            )
        return self._session

    def _normalize_url(self, url: str, base_url: str) -> str:
        """
        Нормалізує URL - перетворює відносний URL в абсолютний.

        Args:
            url: URL для нормалізації (може бути відносний)
            base_url: Базовий URL сайту

        Returns:
            Абсолютний URL
        """
        if not url:
            return url

        url = url.strip()
        if url.startswith(("http://", "https://")):
            return url

        # Відносний URL - перетворюємо в абсолютний
        return urljoin(base_url, url)

    async def parse_from_robots_async(self, base_url: str) -> Dict[str, List[str]]:
        """
        Async парсить sitemap URLs з robots.txt та завантажує їх.

        ОПТИМІЗОВАНО: Паралельне завантаження sitemap через asyncio.gather()!

        Args:
            base_url: Базовий URL сайту (https://example.com)

        Returns:
            Dict з ключами:
            - 'sitemap_urls': список знайдених sitemap URLs
            - 'urls': всі URL з усіх sitemap
            - 'sitemap_indexes': sitemap index URLs (якщо є)
        """
        result = {"sitemap_urls": [], "urls": [], "sitemap_indexes": []}

        try:
            # Завантажуємо robots.txt
            robots_url = urljoin(base_url, "/robots.txt")
            session = await self._get_session()

            async with session.get(robots_url) as response:
                if response.status != 200:
                    logger.warning("robots.txt not found at %s", robots_url)
                    return await self._try_default_sitemaps_async(base_url, result)

                robots_content = await response.text()

            # Парсимо robots.txt для знаходження sitemap URLs
            sitemap_urls = self._parse_robots_txt(robots_content, base_url)

            if sitemap_urls:
                result["sitemap_urls"] = sitemap_urls
                logger.info("Знайдено %s sitemap URLs в robots.txt", len(sitemap_urls))

                # Паралельне завантаження всіх sitemap!
                sitemap_results = await asyncio.gather(
                    *[self.parse_sitemap_async(url) for url in sitemap_urls], return_exceptions=True
                )

                for sitemap_data in sitemap_results:
                    if isinstance(sitemap_data, Exception):
                        logger.warning("Sitemap parse error: %s", sitemap_data)
                        continue
                    if isinstance(sitemap_data, dict):
                        result["urls"].extend(sitemap_data.get("urls", []))
                        result["sitemap_indexes"].extend(sitemap_data.get("sitemap_indexes", []))
            else:
                logger.warning("Sitemap не знайдено в %s", robots_url)
                result = await self._try_default_sitemaps_async(base_url, result)

        except Exception as e:
            logger.error("Помилка при читанні robots.txt з %s: %s", base_url, e)
            result = await self._try_default_sitemaps_async(base_url, result)

        # Видалити дублікати
        result["urls"] = list(set(result["urls"]))
        result["sitemap_indexes"] = list(set(result["sitemap_indexes"]))

        logger.info("Всього знайдено %s URLs в sitemap", len(result['urls']))
        return result

    async def _try_default_sitemaps_async(self, base_url: str, result: Dict) -> Dict:
        """Спробувати типові URL для sitemap (async версія)."""
        default_sitemaps = [
            urljoin(base_url, "/sitemap.xml"),
            urljoin(base_url, "/sitemap_index.xml"),
        ]

        for sitemap_url in default_sitemaps:
            try:
                sitemap_data = await self.parse_sitemap_async(sitemap_url)
                if sitemap_data["urls"] or sitemap_data["sitemap_indexes"]:
                    result["sitemap_urls"].append(sitemap_url)
                    result["urls"].extend(sitemap_data["urls"])
                    result["sitemap_indexes"].extend(sitemap_data["sitemap_indexes"])
                    logger.info("Знайдено sitemap на %s", sitemap_url)
                    break
            except Exception as e:
                logger.debug("Не вдалося завантажити %s: %s", sitemap_url, e)

        return result

    async def parse_sitemap_async(self, sitemap_url: str) -> Dict[str, List[str]]:
        """
        Async парсить один sitemap файл.

        ОПТИМІЗОВАНО:
        - Async HTTP через aiohttp
        - XML парсинг в ThreadPoolExecutor (CPU-bound)

        ВИПРАВЛЕННЯ P0/P1:
        - Підтримка gzip sitemap (автоматична декомпресія)
        - Ліміт розміру (MAX_SITEMAP_SIZE)
        - Валідація Content-Type

        Args:
            sitemap_url: URL sitemap файлу

        Returns:
            Dict з ключами:
            - 'urls': список URL з urlset
            - 'sitemap_indexes': список sitemap URLs з sitemapindex
        """
        result = {"urls": [], "sitemap_indexes": []}
        if not sitemap_url.startswith(("http://", "https://")):
            logger.error("Invalid sitemap URL: %s", sitemap_url)
            return result

        try:
            session = await self._get_session()

            async with session.get(sitemap_url, allow_redirects=True) as response:
                if response.status not in (200, 301, 302):
                    logger.warning("Sitemap not found: %s (status=%s)", sitemap_url, response.status)
                    return result

                content_type = response.headers.get("content-type", "").lower()
                if content_type and not any(t in content_type for t in ALLOWED_CONTENT_TYPES):
                    logger.warning(
                        f"Invalid content-type for sitemap: {content_type} ({sitemap_url})"
                    )
                    # Продовжуємо - деякі сервери не встановлюють правильний Content-Type

                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > MAX_SITEMAP_SIZE:
                    logger.error(
                        f"Sitemap too large: {content_length} bytes (max: {MAX_SITEMAP_SIZE}) - {sitemap_url}"
                    )
                    return result

                content = await response.content.read(MAX_SITEMAP_SIZE)
                if not response.content.at_eof():
                    logger.error(
                        f"Sitemap truncated (exceeded {MAX_SITEMAP_SIZE} bytes): {sitemap_url}"
                    )
                    # Продовжуємо з тим що є - може бути корисним

            # XML парсинг в ThreadPoolExecutor (CPU-bound операція)
            loop = asyncio.get_event_loop()
            parsed_result = await loop.run_in_executor(
                self._xml_executor, self._parse_sitemap_content_sync, content, sitemap_url
            )

            return parsed_result

        except Exception as e:
            error_type = type(e).__name__
            logger.warning("Error (%s) parsing sitemap %s: %s", error_type, sitemap_url, e)
            return result

    def _parse_sitemap_content_sync(self, content: bytes, sitemap_url: str) -> Dict[str, List[str]]:
        """
        Синхронний парсинг XML контенту sitemap.

        Виконується в ThreadPoolExecutor для не блокування event loop.

        ВИПРАВЛЕННЯ P0: Автоматична декомпресія gzip sitemap

        Args:
            content: XML контент (може бути gzip стиснутий)
            sitemap_url: URL sitemap для base URL нормалізації

        Returns:
            Dict з URLs та sitemap indexes
        """
        result = {"urls": [], "sitemap_indexes": []}

        try:
            # ВИПРАВЛЕННЯ: Перевіряємо чи файл справді gzip за magic bytes, не лише за розширенням
            # Деякі сервери віддають звичайний XML з .gz розширенням
            is_actually_gzip = len(content) >= 2 and content[:2] == b"\x1f\x8b"

            if is_actually_gzip:
                try:
                    content = gzip.decompress(content)
                    logger.debug("Decompressed gzip sitemap: %s", sitemap_url)
                except gzip.BadGzipFile as e:
                    logger.warning("Failed to decompress gzip sitemap %s: %s", sitemap_url, e)
                    # Продовжуємо - можливо це звичайний XML з .gz розширенням
                except Exception as e:
                    logger.warning("Gzip decompression error for %s: %s", sitemap_url, e)
                    # Продовжуємо - спробуємо парсити як XML
            elif sitemap_url.endswith(".gz"):
                # URL має .gz розширення, але контент не є gzip
                logger.info(
                    f"URL ends with .gz but content is not gzip-compressed (starts with {content[:2]!r}), parsing as plain XML: {sitemap_url}"
                )

            root = ET.fromstring(content)
            parsed = urlparse(sitemap_url)
            base_url = f"{parsed.scheme}://{parsed.netloc}"

            # Визначити тип sitemap
            if root.tag.endswith("sitemapindex"):
                raw_indexes = self._parse_sitemap_index(root)
                result["sitemap_indexes"] = [self._normalize_url(u, base_url) for u in raw_indexes]
                logger.info(
                    f"Знайдено {len(result['sitemap_indexes'])} sitemap в index {sitemap_url}"
                )

            elif root.tag.endswith("urlset"):
                raw_urls = self._parse_urlset(root)
                result["urls"] = [self._normalize_url(u, base_url) for u in raw_urls]
                logger.info("Знайдено %s URLs в sitemap %s", len(result['urls']), sitemap_url)

            else:
                logger.warning("Невідомий тип sitemap: %s", root.tag)

        except ET.ParseError as e:
            logger.error("XML parse error for %s: %s", sitemap_url, e)
        except Exception as e:
            logger.error("Error parsing sitemap content %s: %s", sitemap_url, e)

        return result

    def _parse_robots_txt(self, content: str, base_url: str) -> List[str]:
        """
        Парсить robots.txt для знаходження sitemap URLs.

        Args:
            content: Вміст robots.txt
            base_url: Базовий URL для нормалізації

        Returns:
            Список sitemap URLs
        """
        sitemap_urls = []

        for line in content.splitlines():
            line = line.strip()
            if line.lower().startswith("sitemap:"):
                url = line[8:].strip()
                if url:
                    normalized = self._normalize_url(url, base_url)
                    sitemap_urls.append(normalized)

        return sitemap_urls

    def parse_from_robots(self, base_url: str) -> Dict[str, List[str]]:
        """
        Sync версія parse_from_robots для зворотної сумісності.

        ПРИМІТКА: Для краулінгу використовуйте parse_from_robots_async().
        Sync версія використовує requests або cloudscraper для HTTP запитів.

        Args:
            base_url: Базовий URL сайту

        Returns:
            Dict з sitemap URLs та URL списком
        """
        session = self._get_sync_session()
        result = {"sitemap_urls": [], "urls": [], "sitemap_indexes": []}

        try:
            # Завантажуємо robots.txt
            robots_url = urljoin(base_url, "/robots.txt")
            response = session.get(robots_url, timeout=self.timeout)

            if response.status_code != 200:
                logger.warning("robots.txt not found at %s", robots_url)
                return self._try_default_sitemaps_sync(base_url, result)

            # Парсимо robots.txt для знаходження sitemap URLs
            sitemap_urls = self._parse_robots_txt(response.text, base_url)

            if sitemap_urls:
                result["sitemap_urls"] = sitemap_urls
                logger.info("Знайдено %s sitemap URLs в robots.txt", len(sitemap_urls))

                # Завантажуємо кожен sitemap послідовно
                for url in sitemap_urls:
                    try:
                        sitemap_data = self.parse_sitemap(url)
                        result["urls"].extend(sitemap_data.get("urls", []))
                        result["sitemap_indexes"].extend(sitemap_data.get("sitemap_indexes", []))
                    except Exception as e:
                        logger.warning("Error parsing sitemap %s: %s", url, e)
            else:
                logger.warning("Sitemap не знайдено в %s", robots_url)
                result = self._try_default_sitemaps_sync(base_url, result)

        except Exception as e:
            logger.error("Помилка при читанні robots.txt з %s: %s", base_url, e)
            result = self._try_default_sitemaps_sync(base_url, result)

        # Видалити дублікати
        result["urls"] = list(set(result["urls"]))
        result["sitemap_indexes"] = list(set(result["sitemap_indexes"]))

        logger.info("Всього знайдено %s URLs в sitemap", len(result['urls']))
        return result

    def _try_default_sitemaps_sync(self, base_url: str, result: Dict) -> Dict:
        """Спробувати типові URL для sitemap (sync версія)."""
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
                    result["sitemap_indexes"].extend(sitemap_data["sitemap_indexes"])
                    logger.info("Знайдено sitemap на %s", sitemap_url)
                    break
            except Exception as e:
                logger.debug("Не вдалося завантажити %s: %s", sitemap_url, e)

        return result

    def parse_sitemap(self, sitemap_url: str) -> Dict[str, List[str]]:
        """
        Sync версія parse_sitemap для зворотної сумісності.

        ПРИМІТКА: Для краулінгу використовуйте parse_sitemap_async().
        Sync версія використовує requests або cloudscraper для HTTP запитів.
        """
        session = self._get_sync_session()
        result = {"urls": [], "sitemap_indexes": []}
        if not sitemap_url.startswith(("http://", "https://")):
            logger.error("Invalid sitemap URL: %s", sitemap_url)
            return result

        try:
            logger.debug("Fetching sitemap with %s: %s", self.http_client_type, sitemap_url)
            response = session.get(sitemap_url, timeout=self.timeout)
            logger.debug(
                f"Response status: {response.status_code}, content-type: {response.headers.get('content-type', 'unknown')}"
            )

            if response.status_code != 200:
                content_preview = response.text[:100] if response.text else ""
                if "Just a moment" in content_preview or "Cloudflare" in content_preview:
                    logger.warning(
                        f"Cloudflare challenge detected for {sitemap_url} - cloudscraper may need update"
                    )
                else:
                    logger.warning(
                        f"Sitemap not found: {sitemap_url} (status={response.status_code})"
                    )
                return result

            return self._parse_sitemap_content_sync(response.content, sitemap_url)

        except Exception as e:
            # Обробляємо різні типи мережевих помилок без падіння
            error_type = type(e).__name__
            logger.warning("Network error (%s) fetching sitemap %s: %s", error_type, sitemap_url, e)
            return result

    def _parse_sitemap_index(self, root: Element) -> List[str]:
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

    def _parse_urlset(self, root: Element) -> List[str]:
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

    async def close(self):
        """Закрити aiohttp сесію та ThreadPoolExecutor."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

        if hasattr(self, "_xml_executor") and self._xml_executor:
            self._xml_executor.shutdown(wait=False)
            self._xml_executor = None

    def __del__(self):
        """Cleanup on deletion."""
        # Закриваємо aiohttp сесію
        if self._session and not self._session.closed:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.close())
                else:
                    loop.run_until_complete(self.close())
            except Exception:
                pass  # Non-critical: cleanup/fallback

        if hasattr(self, "_xml_executor") and self._xml_executor:
            try:
                self._xml_executor.shutdown(wait=False)
            except Exception:
                pass  # Non-critical: cleanup/fallback
