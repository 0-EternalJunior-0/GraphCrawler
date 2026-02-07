"""RobotsValidator - валідація URL згідно з robots.txt (SRP)."""

import logging
from urllib.robotparser import RobotFileParser

from graph_crawler.shared.exceptions import URLBlockedError

logger = logging.getLogger(__name__)


class RobotsValidator:
    """
    Валідація URL згідно з robots.txt.

        Відповідальність: перевірка дозволів robots.txt для URL.

        Методи:
        - validate() - перевіряє чи дозволено сканувати URL
        - can_fetch() - перевіряє дозвіл без викидання exception
    """

    def __init__(self, user_agent: str = "GraphCrawler/0.1.0"):
        """
        Ініціалізація валідатора.

        Args:
            user_agent: User-Agent для перевірки правил
        """
        self.user_agent = user_agent

    def validate(self, parser: RobotFileParser, url: str) -> None:
        """
        Перевіряє чи дозволено сканувати URL.

        Args:
            parser: RobotFileParser для домену
            url: URL для перевірки

        Raises:
            URLBlockedError: Якщо URL заблокований robots.txt
        """
        if not parser.can_fetch(self.user_agent, url):
            logger.warning(f"Blocked by robots.txt: {url}")
            raise URLBlockedError(f"URL blocked by robots.txt: {url}")

    def can_fetch(self, parser: RobotFileParser, url: str) -> bool:
        """
        Перевіряє чи дозволено сканувати URL (без exception).

        Args:
            parser: RobotFileParser для домену
            url: URL для перевірки

        Returns:
            True якщо дозволено, False якщо заблокований
        """
        is_allowed = parser.can_fetch(self.user_agent, url)
        if not is_allowed:
            logger.warning(f"Blocked by robots.txt: {url}")
        return is_allowed
