"""
Утиліти для генерації browser fingerprint параметрів.

Цей модуль тепер є тонкою обгорткою над меншими підмодулями:
- :mod:`fingerprint_data` – великі константи
- :mod:`fingerprint_generators` – генератори окремих параметрів
- :mod:`fingerprint_profile` – ``FingerprintProfile`` та high-level builder
- :mod:`fingerprint_stealth` – JS injection для stealth режиму

Публічний API збережено (``FingerprintProfile``, ``generate_*``, ``get_stealth_script``).
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .fingerprint_data import (
    COMMON_VIEWPORTS,
    LANGUAGES,
    PLATFORMS,
    TIMEZONES,
    USER_AGENTS,
    WEBGL_RENDERERS,
    WEBGL_VENDORS,
)
from .fingerprint_generators import (
    generate_random_geolocation,
    generate_random_timezone,
    generate_random_viewport,
    generate_realistic_headers,
    generate_screen_metrics,
    generate_webgl_params,
)
from .fingerprint_profile import FingerprintProfile, generate_fingerprint_profile
from .fingerprint_stealth import get_stealth_script

__all__ = [
    "FingerprintProfile",
    "generate_random_viewport",
    "generate_realistic_headers",
    "generate_random_timezone",
    "generate_random_geolocation",
    "generate_screen_metrics",
    "generate_webgl_params",
    "generate_fingerprint_profile",
    "get_stealth_script",
]
