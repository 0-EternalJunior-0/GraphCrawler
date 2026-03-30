"""Native Acceleration Layer for GraphCrawler.

Python 3.14 Optimizations:
- Free-threading support для паралельних CPU-bound операцій
- Cython оптимізації для hot paths (URL, HTML parsing)
- Автоматичний fallback на pure Python

Usage:
    # Автоматичний fallback якщо native не скомпільовано
    from graph_crawler.native import (
        is_valid_url_fast,
        normalize_url_fast,
        get_domain_fast,
        parse_links_fast,
    )

Build:
    cd graph_crawler/native
    python setup.py build_ext --inplace
"""

import logging
import sys

logger = logging.getLogger(__name__)


def _detect_free_threading() -> bool:
    """
    Визначає чи Python 3.14 free-threading enabled.

    Returns:
        True якщо GIL disabled (free-threading mode)
        False якщо GIL enabled або Python < 3.14
    """
    if not hasattr(sys, "_is_gil_enabled"):
        return False
    return not sys._is_gil_enabled()  # type: ignore[attr-defined]


_IS_FREE_THREADED = _detect_free_threading()

if _IS_FREE_THREADED:
    logger.info(
        f"🚀 Python {sys.version_info.major}.{sys.version_info.minor} "
        f"Free-threading detected! Native extensions will use parallel execution."
    )
_NATIVE_URL_AVAILABLE = False
_NATIVE_HTML_AVAILABLE = False
_NATIVE_BLOOM_AVAILABLE = False

# URL Utils (Cython)
try:
    from graph_crawler.native._url_utils import (  # type: ignore[import-not-found]
        filter_valid_urls as _cython_filter_valid_urls,
    )
    from graph_crawler.native._url_utils import (
        get_domain_fast as _cython_get_domain,
    )
    from graph_crawler.native._url_utils import (
        is_valid_url_fast as _cython_is_valid_url,
    )
    from graph_crawler.native._url_utils import (
        make_absolute_fast as _cython_make_absolute,
    )
    from graph_crawler.native._url_utils import (
        normalize_url_fast as _cython_normalize_url,
    )
    from graph_crawler.native._url_utils import (
        normalize_urls as _cython_normalize_urls,
    )

    _NATIVE_URL_AVAILABLE = True
    logger.debug(" Native URL utils loaded (Cython)")

    # Використовуємо Cython версії
    is_valid_url_fast = _cython_is_valid_url
    normalize_url_fast = _cython_normalize_url
    get_domain_fast = _cython_get_domain
    make_absolute_fast = _cython_make_absolute
    filter_valid_urls = _cython_filter_valid_urls
    normalize_urls = _cython_normalize_urls

except ImportError as e:
    # Fallback to pure Python with lru_cache
    # Log the reason for fallback (helps debugging platform issues)
    logger.info(
        f"Native URL utils not available ({type(e).__name__}: {e}), using pure Python fallback"
    )

    from graph_crawler.shared.utils.url_utils import URLUtils, _parse_url_cached

    is_valid_url_fast = URLUtils.is_valid_url
    normalize_url_fast = URLUtils.normalize_url
    get_domain_fast = URLUtils.get_domain
    make_absolute_fast = URLUtils.make_absolute

    # Pure Python batch operations (optimized)
    def filter_valid_urls(urls: list) -> list:
        """Filter valid URLs (pure Python fallback)."""
        return [url for url in urls if URLUtils.is_valid_url(url)]

    def normalize_urls(urls: list) -> list:
        """Normalize URLs (pure Python fallback)."""
        return [URLUtils.normalize_url(url) for url in urls]


# HTML Parser (Cython)
try:
    from graph_crawler.native._html_parser import (  # type: ignore[import-not-found]
        count_links as _cython_count_links,
    )
    from graph_crawler.native._html_parser import (
        parse_all_urls_fast as _cython_parse_all_urls,
    )
    from graph_crawler.native._html_parser import (
        parse_links_fast as _cython_parse_links,
    )

    _NATIVE_HTML_AVAILABLE = True
    logger.debug(" Native HTML parser loaded (Cython)")

    parse_links_fast = _cython_parse_links
    parse_all_urls_fast = _cython_parse_all_urls
    count_links = _cython_count_links

except ImportError as e:
    # Fallback - буде None, використовується BeautifulSoup
    logger.info(
        f"Native HTML parser not available ({type(e).__name__}: {e}), using BeautifulSoup fallback"
    )
    parse_links_fast = None
    parse_all_urls_fast = None
    count_links = None

# Bloom Filter (Cython)
try:
    from graph_crawler.native._bloom_filter import BloomFilterFast  # type: ignore[import-not-found]

    _NATIVE_BLOOM_AVAILABLE = True
    logger.debug(" Native Bloom filter loaded (Cython)")
except ImportError as e:
    logger.info(
        f"Native Bloom filter not available ({type(e).__name__}: {e}), using pybloom_live fallback"
    )
    BloomFilterFast = None


def is_native_available() -> bool:
    """Check if any native extensions are loaded."""
    return _NATIVE_URL_AVAILABLE or _NATIVE_HTML_AVAILABLE or _NATIVE_BLOOM_AVAILABLE


def is_url_native_available() -> bool:
    """Check if native URL utils are loaded."""
    return _NATIVE_URL_AVAILABLE


def is_html_native_available() -> bool:
    """Check if native HTML parser is loaded."""
    return _NATIVE_HTML_AVAILABLE


def is_free_threaded() -> bool:
    """Check if Python 3.14 free-threading is enabled."""
    return _IS_FREE_THREADED


def get_native_status() -> dict:
    """
    Отримати статус native extensions.

    Returns:
        Dict з інформацією про native extensions
    """
    return {
        "native_available": is_native_available(),
        "url_utils": "cython" if _NATIVE_URL_AVAILABLE else "python+lru_cache",
        "html_parser": "cython" if _NATIVE_HTML_AVAILABLE else "beautifulsoup",
        "bloom_filter": "cython" if _NATIVE_BLOOM_AVAILABLE else "pybloom_live",
        "free_threading": _IS_FREE_THREADED,
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    }


__all__ = [
    # URL functions
    "is_valid_url_fast",
    "normalize_url_fast",
    "get_domain_fast",
    "make_absolute_fast",
    "filter_valid_urls",
    "normalize_urls",
    # HTML functions
    "parse_links_fast",
    "parse_all_urls_fast",
    "count_links",
    # Bloom Filter
    "BloomFilterFast",
    # Status
    "is_native_available",
    "is_url_native_available",
    "is_html_native_available",
    "is_free_threaded",
    "get_native_status",
]
