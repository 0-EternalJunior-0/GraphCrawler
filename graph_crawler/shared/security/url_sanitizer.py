"""URL Sanitizer - Safe Logging Utility.

Видаляє пароль та інші sensitive дані з URL для безпечного логування.

Використання:
    from graph_crawler.shared.security.url_sanitizer import sanitize_url

    url = "redis://:password123@localhost:6379/0"
    safe_url = sanitize_url(url)
    logger.info(f"Connecting to: {safe_url}")  # redis://***:***@localhost:6379/0
"""

import logging
from urllib.parse import urlparse, urlunparse

logger = logging.getLogger(__name__)


def sanitize_url(url: str, mask: str = "***") -> str:
    """
    Видаляє пароль з URL для безпечного логування.

    Замінює username та password на mask.

    Args:
        url: URL який може містити credentials
        mask: Строка для заміни credentials (default: "***")

    Returns:
        URL з замаскованими credentials

    Example:
        >>> sanitize_url("redis://:secret@host:6379/0")
        "redis://***:***@host:6379/0"

        >>> sanitize_url("postgres://user:pass@host:5432/db")
        "postgres://***:***@host:5432/db"

        >>> sanitize_url("https://example.com/path")
        "https://example.com/path"
    """
    try:
        parsed = urlparse(url)
    except Exception:
        # Якщо URL невалідний - повертаємо як є
        return url

    # Якщо немає credentials - повертаємо як є
    if not parsed.username and not parsed.password:
        return url

    # Будуємо новий netloc з замаскованими credentials
    netloc_parts = []

    # Credentials
    if parsed.username or parsed.password:
        netloc_parts.append(f"{mask}:{mask}@")

    # Hostname
    if parsed.hostname:
        netloc_parts.append(parsed.hostname)

    # Port
    if parsed.port:
        netloc_parts.append(f":{parsed.port}")

    new_netloc = "".join(netloc_parts)

    # Створюємо новий URL
    sanitized = urlunparse(
        (
            parsed.scheme,
            new_netloc,
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        )
    )

    return sanitized


def sanitize_connection_string(conn_str: str) -> str:
    """
    Санітизує connection string для логування.

    Підтримує різні формати:
    - URL формат: postgres://user:pass@host/db
    - Key-value формат: host=localhost user=admin password=secret

    Args:
        conn_str: Connection string

    Returns:
        Санітизований connection string
    """
    # Спробуємо як URL
    if "://" in conn_str:
        return sanitize_url(conn_str)

    # Key-value формат
    import re

    # Маскуємо password=xxx
    sanitized = re.sub(
        r"(password\s*=\s*)([^\s]+)", r"\1***", conn_str, flags=re.IGNORECASE
    )

    # Маскуємо pwd=xxx
    sanitized = re.sub(
        r"(pwd\s*=\s*)([^\s]+)", r"\1***", sanitized, flags=re.IGNORECASE
    )

    return sanitized
