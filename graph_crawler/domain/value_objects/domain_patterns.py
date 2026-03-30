"""
Enum патерни для allowed_domains.

This is domain logic - business rules for domain filtering patterns.

Спрощує конфігурацію доменів через спеціальні константи замість
складних комбінацій same_domain_only + allowed_domains.
"""

from enum import Enum


class AllowedDomains(str, Enum):
    """
    Спеціальні патерни для конфігурації allowed_domains.

    Examples:
        >>> # Куди завгодно
        >>> config = CrawlerConfig(
        ...     url="https://company.com",
        ...     allowed_domains=[AllowedDomains.ALL]
        ... )
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


__all__ = ["AllowedDomains"]
