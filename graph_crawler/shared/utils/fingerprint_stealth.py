"""JavaScript stealth-mode script generator for fingerprint profiles."""

from __future__ import annotations

import random

from .fingerprint_profile import FingerprintProfile


def get_stealth_script(profile: FingerprintProfile) -> str:
    """Генерує JavaScript код для injection в браузер для stealth режиму.

    Цей скрипт змінює різні browser APIs щоб обійти fingerprinting.
    """

    lat, lon = profile.geolocation if profile.geolocation else (0, 0)

    script = """
    // ============ STEALTH MODE INJECTION ============
    // Browser Fingerprinting
    """

    return script


__all__ = ["get_stealth_script"]
