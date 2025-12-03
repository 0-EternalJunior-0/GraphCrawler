"""SSRF Protection - URL Security Validator.

Захищає від Server-Side Request Forgery (SSRF) атак шляхом
блокування запитів до:
- Приватних IP адрес (192.168.x.x, 10.x.x.x, 172.16-31.x.x)
- Localhost (127.0.0.1, ::1)
- AWS metadata endpoint (169.254.169.254)
- Небезпечних портів (SSH, MySQL, PostgreSQL, Redis, MongoDB)

Використання:
    from graph_crawler.shared.security.url_validator import validate_url_security, SSRFError

    try:
        validate_url_security("http://192.168.1.1/admin")
    except SSRFError as e:
        print(f"Blocked: {e}")
"""

import ipaddress
import logging
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Заблоковані хости
BLOCKED_HOSTS = frozenset(
    [
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "169.254.169.254",  # AWS metadata
        "169.254.169.253",  # AWS metadata alternate
        "::1",  # IPv6 localhost
        "[::1]",  # IPv6 localhost in brackets
        "metadata.google.internal",  # GCP metadata
        "metadata.goog",  # GCP metadata alternate
    ]
)

# Заблоковані порти
BLOCKED_PORTS = frozenset(
    [
        22,  # SSH
        23,  # Telnet
        25,  # SMTP
        3306,  # MySQL
        5432,  # PostgreSQL
        6379,  # Redis
        27017,  # MongoDB
        9200,  # Elasticsearch
        11211,  # Memcached
    ]
)

# Дозволені протоколи
ALLOWED_PROTOCOLS = frozenset(["http", "https"])


class SSRFError(Exception):
    """SSRF attempt detected.

    Викидається коли URL вказує на приватні ресурси або
    заблоковані сервіси.
    """

    pass


def _is_private_ip(ip_str: str) -> bool:
    """Перевіряє чи IP є приватним/зарезервованим.

    Args:
        ip_str: Строка з IP адресою

    Returns:
        True якщо IP приватний/loopback/зарезервований
    """
    try:
        ip = ipaddress.ip_address(ip_str)
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_reserved
            or ip.is_link_local
            or ip.is_multicast
        )
    except ValueError:
        # Це не IP адреса (hostname)
        return False


def validate_url_security(url: str, allow_internal: bool = False) -> bool:
    """
    Валідує URL на SSRF вразливості.

    Перевіряє:
    1. Протокол (тільки http/https)
    2. Hostname (не в BLOCKED_HOSTS)
    3. IP адресу (не приватна/loopback)
    4. Порт (не в BLOCKED_PORTS)

    Args:
        url: URL для валідації
        allow_internal: Дозволити внутрішні адреси (для тестування)

    Returns:
        True якщо URL безпечний

    Raises:
        SSRFError: Якщо URL небезпечний

    Example:
        >>> validate_url_security("https://example.com/")
        True
        >>> validate_url_security("http://localhost/admin")
        SSRFError: Blocked hostname: localhost
    """
    try:
        parsed = urlparse(url)
    except Exception as e:
        raise SSRFError(f"Invalid URL format: {e}")

    # Перевірка протоколу
    if parsed.scheme not in ALLOWED_PROTOCOLS:
        raise SSRFError(
            f"Unsupported protocol: {parsed.scheme}. "
            f"Allowed: {', '.join(ALLOWED_PROTOCOLS)}"
        )

    # Перевірка hostname
    hostname = parsed.hostname
    if not hostname:
        raise SSRFError("Missing hostname in URL")

    hostname_lower = hostname.lower()

    # Перевірка на заблоковані хости
    if hostname_lower in BLOCKED_HOSTS:
        raise SSRFError(f"Blocked hostname: {hostname}")

    # Перевірка на приватні IP (якщо не дозволено)
    if not allow_internal:
        if _is_private_ip(hostname):
            raise SSRFError(f"Private/reserved IP not allowed: {hostname}")

    # Перевірка порту
    port = parsed.port
    if port and port in BLOCKED_PORTS:
        raise SSRFError(f"Blocked port: {port}")

    logger.debug(f"URL validated: {url}")
    return True


def is_url_safe(url: str) -> bool:
    """
    Перевіряє чи URL безпечний (не викидає exception).

    Args:
        url: URL для перевірки

    Returns:
        True якщо URL безпечний, False інакше

    Example:
        >>> is_url_safe("https://example.com")
        True
        >>> is_url_safe("http://127.0.0.1/admin")
        False
    """
    try:
        validate_url_security(url)
        return True
    except SSRFError:
        return False
