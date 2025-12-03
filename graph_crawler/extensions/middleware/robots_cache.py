"""RobotsCache - кешування robots.txt парсерів (SRP)."""

import logging
from typing import Dict
from urllib.robotparser import RobotFileParser

logger = logging.getLogger(__name__)


class RobotsCache:
    """
    Кешування robots.txt парсерів.

        Відповідальність: завантаження та кешування robots.txt для різних доменів.

        Методи:
        - get_parser() - отримує parser для домену (з кешу або завантажує)
        - _load_robots_txt() - завантажує robots.txt для домену
        - clear() - очищує кеш
    """

    def __init__(self):
        """Ініціалізація кешу."""
        self.parsers: Dict[str, RobotFileParser] = {}

    def get_parser(self, domain: str) -> RobotFileParser:
        """
        Отримує parser для домену (з кешу або завантажує).

        Args:
            domain: Домен (example.com)

        Returns:
            RobotFileParser для домену
        """
        if domain not in self.parsers:
            self._load_robots_txt(domain)
        return self.parsers[domain]

    def _load_robots_txt(self, domain: str):
        """
        Завантажує та парсить robots.txt для домену.

        Args:
            domain: Домен (example.com)

        Note:
            Якщо robots.txt недоступний - дозволяємо все.
        """
        parser = RobotFileParser()
        robots_url = f"https://{domain}/robots.txt"

        try:
            parser.set_url(robots_url)
            parser.read()
            logger.info(f"Loaded robots.txt from {robots_url}")
        except Exception as e:
            logger.warning(f"Could not load robots.txt from {robots_url}: {e}")
            logger.info(f"Allowing all URLs for {domain} (no robots.txt)")
            # Якщо не вдалося завантажити - дозволяємо все
            parser.allow_all = True

        self.parsers[domain] = parser

    def clear(self):
        """Очищує кеш парсерів."""
        self.parsers.clear()

    def __len__(self) -> int:
        """Повертає кількість закешованих парсерів."""
        return len(self.parsers)
