"""
Enum патерни для allowed_domains (Alpha 2.0).

Спрощує конфігурацію доменів через спеціальні константи замість
складних комбінацій same_domain_only + allowed_domains.
"""

from enum import Enum


class AllowedDomains(str, Enum):
    """
    Спеціальні патерни для конфігурації allowed_domains.

    Alpha 2.0 NEW API: Замінює складні комбінації same_domain_only + allowed_domains
    простими і зрозумілими константами.

    Атрибути:
        ALL: Сканувати куди завгодно (wildcard режим)
        DOMAIN: Тільки основний домен без субдоменів
        SUBDOMAINS: Тільки субдомени без основного домену
        DOMAIN_WITH_SUB: Основний домен + всі субдомени (DEFAULT)

    Examples:
        >>> # Куди завгодно
        >>> config = CrawlerConfig(
        ...     url="https://company.com",
        ...     allowed_domains=[AllowedDomains.ALL]
        ... )

        >>> # Тільки основний домен
        >>> config = CrawlerConfig(
        ...     url="https://company.com",
        ...     allowed_domains=[AllowedDomains.DOMAIN]
        ... )
        >>> # company.com/page
        >>> # jobs.company.com

        >>> # Домен + субдомени (DEFAULT)
        >>> config = CrawlerConfig(
        ...     url="https://company.com",
        ...     allowed_domains=[AllowedDomains.DOMAIN_WITH_SUB]
        ... )
        >>> # company.com/page
        >>> # jobs.company.com
        >>> # career.company.com

        >>> # Комбінація з конкретними доменами
        >>> config = CrawlerConfig(
        ...     url="https://company.com",
        ...     allowed_domains=[
        ...         AllowedDomains.DOMAIN_WITH_SUB,  # company.com + субдомени
        ...         "partner-site.com"  # + зовнішній сайт
        ...     ]
        ... )

    See Also:
        - CrawlerConfig.allowed_domains
        - DomainFilterConfig.allowed_domains
        - DomainFilter._check_allowed_domains()
    """

    ALL = "*"  # Wildcard - куди завгодно
    DOMAIN = "domain"  # Тільки основний домен (без субдоменів)
    SUBDOMAINS = "subdomains"  # Тільки субдомени (без основного домену)
    DOMAIN_WITH_SUB = "domain+subdomains"  # Домен + субдомени (DEFAULT)

    def __repr__(self):
        """Readable representation."""
        return f"<AllowedDomains.{self.name}: {self.value!r}>"

    @classmethod
    def get_special_patterns(cls) -> set:
        """
        Повертає set усіх спеціальних патернів.

        Корисно для відокремлення спеціальних патернів від конкретних доменів.

        Returns:
            Set зі всіма спеціальними значеннями

        Example:
            >>> patterns = AllowedDomains.get_special_patterns()
            >>> patterns
            {'*', 'domain', 'subdomains', 'domain+subdomains'}
        """
        return {pattern.value for pattern in cls}

    @classmethod
    def is_special_pattern(cls, value: str) -> bool:
        """
        Перевіряє чи значення є спеціальним патерном.

        Args:
            value: Значення для перевірки

        Returns:
            True якщо це спеціальний патерн

        Example:
            >>> AllowedDomains.is_special_pattern('*')
            True
            >>> AllowedDomains.is_special_pattern('company.com')
            False
        """
        return value in cls.get_special_patterns()


# ==================== EXPORT ====================

__all__ = ["AllowedDomains"]
