"""Generator functions for browser fingerprint attributes.

These helpers operate on top of the static data defined in
:mod:`graph_crawler.shared.utils.fingerprint_data`.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Tuple

from .fingerprint_data import (
    COMMON_VIEWPORTS,
    LANGUAGES,
    TIMEZONES,
    WEBGL_RENDERERS,
    WEBGL_VENDORS,
)


def generate_random_viewport() -> Dict[str, int]:
    """Генерує випадковий розмір viewport з популярних варіантів."""
    return random.choice(COMMON_VIEWPORTS).copy()


def generate_realistic_headers(user_agent: str | None = None) -> Dict[str, str]:
    """Генерує реалістичні HTTP headers.

    Args:
        user_agent: User-Agent string (опціонально)
    """
    languages = random.choice(LANGUAGES)

    # Створюємо Accept-Language з правильними q-values
    accept_language = languages[0]
    for i, lang in enumerate(languages[1:], start=1):
        q_value = 0.9 - (i * 0.1)
        accept_language += f",{lang};q={q_value:.1f}"

    headers: Dict[str, str] = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": accept_language,
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": str(random.choice([1, 0])),  # Do Not Track
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }

    if user_agent:
        headers["User-Agent"] = user_agent

    return headers


def generate_random_timezone() -> str:
    """Генерує випадковий timezone ID."""
    return random.choice(TIMEZONES)


def generate_random_geolocation() -> Tuple[float, float]:
    """Генерує випадкові координати geolocation (latitude, longitude)."""
    # Major cities coordinates
    cities: List[Tuple[float, float]] = [
        (40.7128, -74.0060),  # New York
        (51.5074, -0.1278),  # London
        (48.8566, 2.3522),  # Paris
        (35.6762, 139.6503),  # Tokyo
        (34.0522, -118.2437),  # Los Angeles
        (41.8781, -87.6298),  # Chicago
        (52.5200, 13.4050),  # Berlin
        (55.7558, 37.6173),  # Moscow
        (-33.8688, 151.2093),  # Sydney
        (39.9042, 116.4074),  # Beijing
    ]

    lat, lon = random.choice(cities)

    # Додаємо невеликий random offset для унікальності
    lat += random.uniform(-0.05, 0.05)
    lon += random.uniform(-0.05, 0.05)

    return (round(lat, 4), round(lon, 4))


def generate_screen_metrics(viewport: Dict[str, int]) -> Dict[str, Any]:
    """Генерує метрики екрану based on viewport.

    Screen завжди трохи більший за viewport (taskbar, browser chrome).
    """
    width = viewport["width"]
    height = viewport["height"]

    # Screen зазвичай такий самий як viewport width
    # але height може бути більшим (taskbar)
    screen_height = height + random.choice([0, 30, 40, 50])  # Taskbar height

    color_depth = random.choice([24, 32])  # Bits per pixel
    pixel_depth = color_depth

    return {
        "width": width,
        "height": screen_height,
        "availWidth": width,
        "availHeight": screen_height - 40,  # Available height (minus taskbar)
        "colorDepth": color_depth,
        "pixelDepth": pixel_depth,
    }


def generate_webgl_params() -> Tuple[str, str]:
    """Генерує WebGL vendor та renderer strings."""
    vendor = random.choice(WEBGL_VENDORS)
    renderer = random.choice(WEBGL_RENDERERS)
    return (vendor, renderer)


__all__ = [
    "generate_random_viewport",
    "generate_realistic_headers",
    "generate_random_timezone",
    "generate_random_geolocation",
    "generate_screen_metrics",
    "generate_webgl_params",
]
