"""CloudScraper драйвер для обходу Cloudflare та інших захистів.

CloudScraper автоматично обходить:
- Cloudflare (JS Challenge, IUAM)
- Інші anti-bot захисти
- 403 Forbidden для сайтмапів

Використання:
    >>> from graph_crawler.infrastructure.transport.sync import CloudscraperDriver
    >>>
    >>> with CloudscraperDriver() as driver:
    ...     response = driver.fetch('https://epam.com/sitemap.xml')
    ...     print(response.html[:100])

Або через factory:
    >>> from graph_crawler.application.services.driver_factory import create_driver
    >>> driver = create_driver("cloudscraper")
"""

import logging
from typing import Any, Dict, Optional

try:
    import cloudscraper
except ImportError:
    cloudscraper = None

from graph_crawler.domain.events.event_bus import EventBus
from graph_crawler.domain.value_objects.models import FetchResponse
from graph_crawler.infrastructure.transport.core.base_sync import BaseSyncDriver
from graph_crawler.infrastructure.transport.core.mixins import RetryMixin
from graph_crawler.shared.constants import (
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_USER_AGENT,
)

logger = logging.getLogger(__name__)


class CloudscraperDriver(BaseSyncDriver, RetryMixin):
    """
    Sync HTTP драйвер на основі cloudscraper для обходу захистів.

    Example:
        >>> with CloudscraperDriver() as driver:
        ...     response = driver.fetch('https://protected-site.com/sitemap.xml')
        ...     if response.error is None:
        ...         print("Success:", response.status_code)
    """

    driver_name = "cloudscraper"

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        event_bus: Optional[EventBus] = None,
    ):
        if cloudscraper is None:
            raise ImportError(
                "CloudscraperDriver requires cloudscraper. Install with: pip install cloudscraper"
            )

        super().__init__(config, event_bus)

        self._timeout = self.config.get("timeout", DEFAULT_REQUEST_TIMEOUT)
        self._user_agent = self.config.get("user_agent", DEFAULT_USER_AGENT)
        self._max_retries = self.config.get("max_retries", 3)

        # Параметри cloudscraper
        browser_config = self.config.get("browser", {})

        # Створюємо cloudscraper session
        self._scraper = cloudscraper.create_scraper(
            browser={
                "browser": browser_config.get("browser", "chrome"),
                "platform": browser_config.get("platform", "windows"),
                "mobile": browser_config.get("mobile", False),
            },
            delay=self.config.get("delay", 0),
            debug=self.config.get("debug", False),
        )

        # Налаштовуємо User-Agent якщо вказано
        if self._user_agent:
            self._scraper.headers.update({"User-Agent": self._user_agent})

        logger.info(
            f"CloudscraperDriver initialized: timeout={self._timeout}s, "
            f"max_retries={self._max_retries}"
        )

    def _do_fetch(self, url: str) -> FetchResponse:
        """
        Sync завантаження через cloudscraper.

        Автоматично обходить Cloudflare та інші захисти.
        """
        try:
            response = self._scraper.get(url, timeout=self._timeout)

            return FetchResponse(
                url=url,
                html=response.text,
                status_code=response.status_code,
                headers={k: str(v) for k, v in response.headers.items()},
                error=None,
            )
        except cloudscraper.exceptions.CloudflareChallengeError as e:
            logger.warning("Cloudflare challenge failed for %s: %s", url, e)
            return FetchResponse(
                url=url,
                html=None,
                status_code=None,
                headers={},
                error=f"CloudflareChallengeError: {e}",
            )
        except Exception as e:
            logger.error("CloudscraperDriver fetch error for %s: %s", url, e)
            raise

    def _do_close(self) -> None:
        """Закриває cloudscraper session."""
        if self._scraper:
            self._scraper.close()
        logger.info("CloudscraperDriver closed")
