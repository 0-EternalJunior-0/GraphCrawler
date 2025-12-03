"""Domain Filter Strategy.

Alpha 2.0 CHANGES:
- Підтримка спеціальних патернів у allowed_domains:
  * '*' - wildcard режим (куди завгодно)
  * 'domain' - тільки основний домен
  * 'subdomains' - тільки субдомени
  * 'domain+subdomains' - домен + субдомени (DEFAULT)
- Автоматичне розділення спеціальних патернів та конкретних доменів
"""

import logging

from graph_crawler.application.use_cases.crawling.filters.base import BaseURLFilter
from graph_crawler.application.use_cases.crawling.filters.domain_patterns import (
    AllowedDomains,
)
from graph_crawler.domain.value_objects.models import DomainFilterConfig
from graph_crawler.shared.utils.url_utils import URLUtils

logger = logging.getLogger(__name__)


class DomainFilter(BaseURLFilter):
    """
    Фільтр за доменом з підтримкою спеціальних патернів.

    Alpha 2.0 NEW FEATURES:
    - Wildcard режим через '*' або AllowedDomains.ALL
    - Спеціальні патерни: 'domain', 'subdomains', 'domain+subdomains'
    - Автоматичне парсування та розділення патернів

    Конфіг:
        base_domain: str - базовий домен для порівняння
        allowed_domains: list - дозволені домени + спеціальні патерни
        blocked_domains: list - заблоковані домени

    Examples:
        >>> # Wildcard режим
        >>> config = DomainFilterConfig(
        ...     base_domain="company.com",
        ...     allowed_domains=["*"]
        ... )
        >>> filter = DomainFilter(config)
        >>> filter.is_allowed("https://any-site.com")  # True

        >>> # Тільки домен без субдоменів
        >>> config = DomainFilterConfig(
        ...     base_domain="company.com",
        ...     allowed_domains=["domain"]
        ... )
        >>> filter = DomainFilter(config)
        >>> filter.is_allowed("https://company.com/page")  # True
        >>> filter.is_allowed("https://jobs.company.com")  # False
    """

    def __init__(self, config: DomainFilterConfig, event_bus=None):
        """
        Ініціалізує фільтр з парсуванням спеціальних патернів.

        Args:
            config: DomainFilterConfig (Pydantic)
            event_bus: EventBus для публікації подій (опціонально)
        """
        self.config = config
        super().__init__(config)
        self.event_bus = event_bus

        # Парсимо спеціальні патерни
        self._parse_special_patterns()

        logger.info(
            f"DomainFilter initialized: "
            f"wildcard={self.wildcard_mode}, "
            f"domain_only={self.domain_only}, "
            f"subdomains_only={self.subdomains_only}, "
            f"domain_with_sub={self.domain_with_sub}, "
            f"concrete_domains={self.concrete_domains}"
        )

    def _parse_special_patterns(self):
        """
        Парсує allowed_domains і виділяє спеціальні патерни.

        Alpha 2.0: Розділяє спеціальні патерни ('*', 'domain', тощо)
        від конкретних доменів для оптимізації перевірок.
        """
        special_patterns = AllowedDomains.get_special_patterns()

        # Ініціалізуємо прапорці
        self.wildcard_mode = False
        self.domain_only = False
        self.subdomains_only = False
        self.domain_with_sub = False
        self.concrete_domains = set()

        # Парсимо кожен домен
        for domain in self.config.allowed_domains:
            if domain == AllowedDomains.ALL.value:  # '*'
                self.wildcard_mode = True
            elif domain == AllowedDomains.DOMAIN.value:  # 'domain'
                self.domain_only = True
            elif domain == AllowedDomains.SUBDOMAINS.value:  # 'subdomains'
                self.subdomains_only = True
            elif domain == AllowedDomains.DOMAIN_WITH_SUB.value:  # 'domain+subdomains'
                self.domain_with_sub = True
            else:
                # Конкретний домен (не спеціальний патерн)
                self.concrete_domains.add(domain)

    @property
    def name(self) -> str:
        return "domain"

    def _is_subdomain_of(self, domain: str, base_domain: str) -> bool:
        """
        Перевіряє чи domain є субдоменом base_domain або самим base_domain.

        Приклади:
            quotes.toscrape.com є субдоменом toscrape.com -> True
            www.toscrape.com є субдоменом toscrape.com -> True
            toscrape.com є субдоменом toscrape.com -> True
            goodreads.com є субдоменом toscrape.com -> False

        Args:
            domain: Домен для перевірки
            base_domain: Базовий домен

        Returns:
            True якщо domain є субдоменом base_domain
        """
        if not domain or not base_domain:
            return False

        # Якщо домени однакові
        if domain == base_domain:
            return True

        # Якщо domain закінчується на .base_domain
        # Наприклад: quotes.toscrape.com закінчується на .toscrape.com
        if domain.endswith("." + base_domain):
            return True

        return False

    def is_allowed(self, url: str, source_url: str = None) -> bool:
        """
        Перевіряє чи дозволений домен (Alpha 2.0 з підтримкою спеціальних патернів).

        Alpha 2.0 ПОРЯДОК ПЕРЕВІРКИ:
        1. Wildcard режим ('*') → дозволити все
        2. Заблоковані домени → заблокувати
        3. Спеціальні патерни ('domain', 'subdomains', 'domain+subdomains')
        4. Конкретні домени з allowed_domains
        5. Конкретні домени є субдоменами дозволених

        Args:
            url: URL для перевірки
            source_url: URL джерела (для визначення базового домену)

        Returns:
            True якщо домен дозволений

        Example:
            >>> filter = DomainFilter(config)
            >>> filter.is_allowed("https://company.com/page")
            True
        """
        if not self.enabled:
            return True

        domain = URLUtils.get_domain(url)
        if not domain:
            logger.debug(f"Invalid domain for URL: {url}")
            return False

        #  КРОК 1: Wildcard режим - дозволити все
        if self.wildcard_mode:
            logger.debug(f"Wildcard mode: allowing {url}")
            return True

        #  КРОК 2: Перевіряємо заблоковані домени
        if domain in self.config.blocked_domains:
            logger.debug(f"Blocked domain: {domain}")
            self._publish_filtered_event(url, "domain", "blocked_domain")
            return False

        #  КРОК 3: Перевіряємо спеціальні патерни
        base_domain = self.config.base_domain

        # 3.1: Тільки основний домен (без субдоменів)
        if self.domain_only:
            if domain == base_domain:
                logger.debug(f"Domain pattern matched: {domain} == {base_domain}")
                return True

        # 3.2: Тільки субдомени (без основного домену)
        if self.subdomains_only:
            if domain != base_domain and self._is_subdomain_of(domain, base_domain):
                logger.debug(
                    f"Subdomain pattern matched: {domain} is subdomain of {base_domain}"
                )
                return True

        # 3.3: Домен + субдомени (DEFAULT)
        if self.domain_with_sub:
            if self._is_subdomain_of(domain, base_domain):
                logger.debug(f"Domain+subdomains pattern matched: {domain}")
                return True

        #  КРОК 4: Перевіряємо конкретні домени
        if domain in self.concrete_domains:
            logger.debug(f"Concrete domain allowed: {domain}")
            return True

        #  КРОК 5: Перевіряємо чи domain є субдоменом будь-якого з concrete_domains
        if any(
            self._is_subdomain_of(domain, allowed) for allowed in self.concrete_domains
        ):
            logger.debug(f"Domain is subdomain of allowed: {domain}")
            return True

        # Домен не дозволений
        logger.debug(f"Domain not allowed: {domain}")
        self._publish_filtered_event(url, "domain", "not_allowed")
        return False
