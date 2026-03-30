"""Shared URL pattern constants for plugins.

Provides common regex patterns for URL classification used across multiple plugins.
"""

from typing import List

# Content page patterns - pages that typically contain the main content
CONTENT_PAGE_PATTERNS: List[str] = [
    r"/fiction/\d+",      # Fiction/book pages
    r"/book/\d+",         # Book pages
    r"/novel/\d+",        # Novel pages
    r"/story/\d+",        # Story pages
    r"/chapter/",         # Chapter pages
    r"/article/",         # Articles
    r"/post/",            # Posts/blog posts
    r"/product/",         # Product pages
    r"/item/",            # Item pages
    r"/details/",         # Detail pages
    r"/view/",            # View pages
]

# Navigation patterns - pages that help navigate to content
NAVIGATION_PATTERNS: List[str] = [
    r"\?page=\d+",        # Query param pagination
    r"/page/\d+",         # Path pagination
    r"/category/",        # Category listings
    r"/tag/",             # Tag pages
    r"/genre/",           # Genre pages
    r"/list",             # List pages
    r"/browse",           # Browse pages
    r"/search",           # Search results
    r"best-rated",        # Best rated content
    r"popular",           # Popular content
    r"trending",          # Trending content
]

# Patterns to ignore - typically not useful for crawling
IGNORE_PATTERNS: List[str] = [
    # Authentication
    r"/login",
    r"/register",
    r"/signup",
    r"/signin",
    r"/logout",
    r"/auth/",
    # E-commerce non-content
    r"/cart",
    r"/checkout",
    r"/payment",
    r"/wishlist",
    # Legal/info pages
    r"/privacy",
    r"/terms",
    r"/cookie",
    r"/legal",
    r"/tos",
    r"/gdpr",
    r"/contact",
    r"/about",
    r"/faq",
    r"/help",
    # User-specific pages
    r"/profile/\d+$",
    r"/user/",
    r"/account",
    r"/settings",
    r"/notifications",
    r"/messages",
    r"/dashboard",
    # Community (usually low-value for crawling)
    r"/forums?/",
    r"/comment",
    r"/review",
    # Files and resources
    r"\.(pdf|doc|docx|xls|xlsx|zip|rar|exe|dmg)$",
    # Admin/technical
    r"/wp-admin",
    r"/admin",
    r"/api/",
    r"/ajax/",
    r"/cdn/",
    r"/static/",
    # Non-HTTP links
    r"^#",                # Anchors
    r"javascript:",       # JS links
    r"mailto:",           # Email links
    r"tel:",              # Phone links
]


def is_content_url(url: str) -> bool:
    """
    Check if URL matches content page patterns.

    Args:
        url: URL to check

    Returns:
        True if URL appears to be a content page
    """
    import re
    url_lower = url.lower()
    return any(re.search(pattern, url_lower) for pattern in CONTENT_PAGE_PATTERNS)


def is_navigation_url(url: str) -> bool:
    """
    Check if URL matches navigation patterns.

    Args:
        url: URL to check

    Returns:
        True if URL appears to be a navigation page
    """
    import re
    url_lower = url.lower()
    return any(re.search(pattern, url_lower) for pattern in NAVIGATION_PATTERNS)


def should_ignore_url(url: str) -> bool:
    """
    Check if URL should be ignored based on common patterns.

    Args:
        url: URL to check

    Returns:
        True if URL should be ignored
    """
    import re
    url_lower = url.lower()
    return any(re.search(pattern, url_lower) for pattern in IGNORE_PATTERNS)
