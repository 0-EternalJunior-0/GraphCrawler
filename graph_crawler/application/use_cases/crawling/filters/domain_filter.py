"""Domain Filter Strategy.

- Підтримка спеціальних патернів у allowed_domains:
  * '*' - wildcard режим (куди завгодно)
  * 'domain' - тільки основний домен
  * 'subdomains' - тільки субдомени
  * 'domain+subdomains' - домен + субдомени (DEFAULT)
- Автоматичне розділення спеціальних патернів та конкретних доменів
"""

import logging
from typing import Optional

from graph_crawler.application.use_cases.crawling.filters.base import BaseURLFilter
from graph_crawler.domain.value_objects.domain_patterns import AllowedDomains
from graph_crawler.domain.value_objects.models import DomainFilterConfig
from graph_crawler.shared.utils.url_utils import URLUtils

logger = logging.getLogger(__name__)


class DomainFilter(BaseURLFilter):
    """
    Фільтр за доменом з підтримкою спеціальних патернів.

    Examples:
        >>> # Wildcard режим
        >>> config = DomainFilterConfig(
        ...     base_domain="company.com",
        ...     allowed_domains=["*"]
        ... )
        >>> filter = DomainFilter(config)
        >>> filter.is_allowed("https://any-site.com")  # True
    """

    def __init__(self, config: DomainFilterConfig, event_bus=None):
        """
        Ініціалізує фільтр з парсуванням спеціальних патернів.

        Args:
            config: DomainFilterConfig (Pydantic)
            event_bus: EventBus для публікації подій (опціонально)
        """
        # Зберігаємо оригінальний config ДО виклику super().__init__
        self._domain_config = config
        super().__init__(config.model_dump() if hasattr(config, "model_dump") else dict(config))
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

        від конкретних доменів для оптимізації перевірок.
        """
        AllowedDomains.get_special_patterns()

        # Ініціалізуємо прапорці
        self.wildcard_mode = False
        self.domain_only = False
        self.subdomains_only = False
        self.domain_with_sub = False
        self.concrete_domains = set()

        # Парсимо кожен домен
        for domain in self._domain_config.allowed_domains:
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

    def is_allowed(self, url: str, source_url: Optional[str] = None) -> bool:
        """
        Перевіряє чи дозволений домен.

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
            logger.debug("Invalid domain for URL: %s", url)
            return False

        #  КРОК 1: Перевіряємо заблоковані домени ПЕРШИМ (навіть при wildcard!)
        if domain in self._domain_config.blocked_domains:
            logger.debug("Blocked domain: %s", domain)
            self._publish_filtered_event(url, "domain", "blocked_domain")
            return False

        #  КРОК 2: Wildcard режим - дозволити все (крім blocked)
        if self.wildcard_mode:
            logger.debug("Wildcard mode: allowing %s", url)
            return True

        #  КРОК 3: Перевіряємо спеціальні патерни
        base_domain = self._domain_config.base_domain

        # 3.1: Тільки основний домен (без субдоменів)
        if self.domain_only:
            if domain == base_domain:
                logger.debug("Domain pattern matched: %s == %s", domain, base_domain)
                return True

        # 3.2: Тільки субдомени (без основного домену)
        if self.subdomains_only:
            if domain != base_domain and self._is_subdomain_of(domain, base_domain):
                logger.debug("Subdomain pattern matched: %s is subdomain of %s", domain, base_domain)
                return True

        # 3.3: Домен + субдомени (DEFAULT)
        if self.domain_with_sub:
            if self._is_subdomain_of(domain, base_domain):
                logger.debug("Domain+subdomains pattern matched: %s", domain)
                return True

        #  КРОК 4: Перевіряємо конкретні домени
        if domain in self.concrete_domains:
            logger.debug("Concrete domain allowed: %s", domain)
            return True

        #  КРОК 5: Перевіряємо чи domain є субдоменом будь-якого з concrete_domains
        if any(self._is_subdomain_of(domain, allowed) for allowed in self.concrete_domains):
            logger.debug("Domain is subdomain of allowed: %s", domain)
            return True

        # Домен не дозволений
        logger.debug("Domain not allowed: %s", domain)
        self._publish_filtered_event(url, "domain", "not_allowed")
        return False
