"""SSRF Protection - URL Security Validator.

Захищає від Server-Side Request Forgery (SSRF) атак шляхом
блокування запитів до:
- Приватних IP адрес (192.168.x.x, 10.x.x.x, 172.16-31.x.x)
- Localhost (127.0.0.1, ::1, та всі еквіваленти)
- AWS/GCP metadata endpoints (169.254.169.254)
- Небезпечних портів (SSH, MySQL, PostgreSQL, Redis, MongoDB)
- IPv4-mapped IPv6 addresses (::ffff:127.0.0.1)

Використання:
    from graph_crawler.shared.security.url_validator import validate_url_security, SSRFError

    try:
        validate_url_security("http://192.168.1.1/admin")
    except SSRFError as e:
        print(f"Blocked: {e}")
"""

import ipaddress
import logging
import re
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Заблоковані хости (case-insensitive matching)
BLOCKED_HOSTS = frozenset(
    [
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "169.254.169.254",  # AWS metadata
        "169.254.169.253",  # AWS metadata alternate
        "::1",  # IPv6 localhost
        "[::1]",  # IPv6 localhost in brackets
        "0:0:0:0:0:0:0:1",  # IPv6 localhost expanded
        "[0:0:0:0:0:0:0:1]",  # IPv6 localhost expanded in brackets
        "metadata.google.internal",  # GCP metadata
        "metadata.goog",  # GCP metadata alternate
        "169.254.169.254.xip.io",  # DNS rebinding attempt
        "169.254.169.254.nip.io",  # DNS rebinding attempt
    ]
)

# Заблоковані порти (common internal services)
BLOCKED_PORTS = frozenset(
    [
        22,  # SSH
        23,  # Telnet
        25,  # SMTP
        53,  # DNS
        110,  # POP3
        135,  # Windows RPC
        139,  # NetBIOS
        143,  # IMAP
        445,  # SMB
        3306,  # MySQL
        5432,  # PostgreSQL
        6379,  # Redis
        27017,  # MongoDB
        9200,  # Elasticsearch
        11211,  # Memcached
        5672,  # RabbitMQ
        9092,  # Kafka
        2181,  # Zookeeper
    ]
)

# Дозволені протоколи
ALLOWED_PROTOCOLS = frozenset(["http", "https"])

# Regex для виявлення IPv6 у різних форматах
IPV6_BRACKET_PATTERN = re.compile(r"^\[(.+)\]$")


class SSRFError(Exception):
    """SSRF attempt detected.

    Викидається коли URL вказує на приватні ресурси або
    заблоковані сервіси.
    """

    pass


def _normalize_ipv6(hostname: str) -> str:
    """
    Нормалізує IPv6 адресу для порівняння.

    Видаляє brackets та zone identifiers (%eth0).

    Args:
        hostname: Hostname який може бути IPv6

    Returns:
        Нормалізована IPv6 строка або оригінальний hostname
    """
    # Видаляємо brackets якщо є
    match = IPV6_BRACKET_PATTERN.match(hostname)
    if match:
        hostname = match.group(1)

    # Видаляємо zone identifier (%eth0, %1, etc.)
    if "%" in hostname:
        hostname = hostname.split("%")[0]

    return hostname


def _is_private_ip(ip_str: str) -> bool:
    """
    Перевіряє чи IP є приватним/зарезервованим.

    Підтримує:
    - IPv4: 10.x.x.x, 172.16-31.x.x, 192.168.x.x
    - IPv6: ::1, fe80::, fc00::, fd00::
    - IPv4-mapped IPv6: ::ffff:127.0.0.1
    - IPv4-compatible IPv6: ::127.0.0.1

    Args:
        ip_str: Строка з IP адресою

    Returns:
        True якщо IP приватний/loopback/зарезервований
    """
    # Нормалізуємо IPv6
    ip_str = _normalize_ipv6(ip_str)

    try:
        ip = ipaddress.ip_address(ip_str)

        # Базові перевірки
        if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local or ip.is_multicast:
            return True

        # Додаткові перевірки для IPv6
        if isinstance(ip, ipaddress.IPv6Address):
            # Перевірка IPv4-mapped IPv6 (::ffff:x.x.x.x)
            if ip.ipv4_mapped:
                ipv4 = ip.ipv4_mapped
                if ipv4.is_private or ipv4.is_loopback or ipv4.is_reserved or ipv4.is_link_local:
                    return True

            # Перевірка 6to4 адрес (2002::/16)
            if ip.sixtofour:
                ipv4 = ip.sixtofour
                if ipv4.is_private or ipv4.is_loopback or ipv4.is_reserved or ipv4.is_link_local:
                    return True

            # Перевірка Teredo адрес
            if ip.teredo:
                client_ipv4 = ip.teredo[1]
                if (
                    client_ipv4.is_private
                    or client_ipv4.is_loopback
                    or client_ipv4.is_reserved
                    or client_ipv4.is_link_local
                ):
                    return True

        return False

    except ValueError:
        # Це не IP адреса (hostname)
        return False


def _is_suspicious_hostname(hostname: str) -> bool:
    """
    Перевіряє чи hostname виглядає підозріло (DNS rebinding, тощо).

    Args:
        hostname: Hostname для перевірки

    Returns:
        True якщо hostname підозрілий
    """
    hostname_lower = hostname.lower()

    # DNS rebinding services
    suspicious_suffixes = (
        ".xip.io",
        ".nip.io",
        ".sslip.io",
        ".localtest.me",
        ".lvh.me",
        ".vcap.me",
    )

    for suffix in suspicious_suffixes:
        if hostname_lower.endswith(suffix):
            return True

    # Numeric-looking hostnames that could be IP obfuscation
    # e.g., "0x7f000001" = 127.0.0.1 in hex
    if hostname_lower.startswith("0x") and len(hostname_lower) <= 10:
        try:
            # Спроба розпарсити як hex IP
            ip_int = int(hostname_lower, 16)
            if 0 <= ip_int <= 0xFFFFFFFF:
                ip = ipaddress.ip_address(ip_int)
                if ip.is_private or ip.is_loopback:
                    return True
        except (ValueError, TypeError):
            pass

    return False


def validate_url_security(url: str, allow_internal: bool = False) -> bool:
    """
    Валідує URL на SSRF вразливості.

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
        >>> validate_url_security("http://[::ffff:127.0.0.1]/")
        SSRFError: Private/reserved IP not allowed
    """
    try:
        parsed = urlparse(url)
    except Exception as e:
        raise SSRFError(f"Invalid URL format: {e}")

    # Перевірка протоколу
    if parsed.scheme not in ALLOWED_PROTOCOLS:
        raise SSRFError(
            f"Unsupported protocol: {parsed.scheme}. Allowed: {', '.join(ALLOWED_PROTOCOLS)}"
        )

    # Перевірка hostname
    hostname = parsed.hostname
    if not hostname:
        raise SSRFError("Missing hostname in URL")

    hostname_lower = hostname.lower()

    # Перевірка на заблоковані хости
    if hostname_lower in BLOCKED_HOSTS:
        raise SSRFError(f"Blocked hostname: {hostname}")

    # Перевірка нормалізованого hostname (для IPv6 у brackets)
    normalized = _normalize_ipv6(hostname_lower)
    if normalized in BLOCKED_HOSTS or normalized.lower() in BLOCKED_HOSTS:
        raise SSRFError(f"Blocked hostname: {hostname}")

    # Перевірка на підозрілі DNS rebinding домени
    if not allow_internal and _is_suspicious_hostname(hostname):
        raise SSRFError(f"Suspicious hostname (possible DNS rebinding): {hostname}")

    # Перевірка на приватні IP (якщо не дозволено)
    if not allow_internal:
        if _is_private_ip(hostname):
            raise SSRFError(f"Private/reserved IP not allowed: {hostname}")

    # Перевірка порту
    port = parsed.port
    if port and port in BLOCKED_PORTS:
        raise SSRFError(f"Blocked port: {port}")

    logger.debug("URL validated: %s", url)
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
        >>> is_url_safe("http://[::ffff:192.168.1.1]/")
        False
    """
    try:
        validate_url_security(url)
        return True
    except SSRFError:
        return False
