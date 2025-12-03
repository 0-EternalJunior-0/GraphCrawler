"""Fingerprint profile dataclass and high-level profile generator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from .fingerprint_data import USER_AGENTS
from .fingerprint_generators import (
    generate_random_geolocation,
    generate_random_timezone,
    generate_random_viewport,
    generate_realistic_headers,
    generate_screen_metrics,
    generate_webgl_params,
)


@dataclass
class FingerprintProfile:
    """Профіль браузера для stealth режиму."""

    viewport: Dict[str, int]
    user_agent: str
    platform: str
    languages: List[str]
    timezone: str
    geolocation: Tuple[float, float] | None = None
    webgl_vendor: str | None = None
    webgl_renderer: str | None = None
    screen: Dict[str, Any] | None = None
    headers: Dict[str, str] | None = None


def generate_fingerprint_profile(
    viewport: Dict[str, int] | None = None,
    user_agent: str | None = None,
    timezone: str | None = None,
    geolocation: Tuple[float, float] | None = None,
    randomize_all: bool = True,
) -> FingerprintProfile:
    """Генерує повний fingerprint профіль браузера.

    Args:
        viewport: Розмір viewport (якщо None - генерується випадковий)
        user_agent: User-Agent string (якщо None - генерується випадковий)
        timezone: Timezone ID (якщо None - генерується випадковий)
        geolocation: Координати (якщо None - генерується випадковий)
        randomize_all: Рандомізувати всі параметри (default: True)
    """

    # Generate або використати надані параметри
    if viewport is None or randomize_all:
        viewport = generate_random_viewport()

    if user_agent is None or randomize_all:
        user_agent = random_choice_user_agent()

    if timezone is None or randomize_all:
        timezone = generate_random_timezone()

    if geolocation is None and randomize_all:
        geolocation = generate_random_geolocation()

    # Визначаємо platform на основі user_agent
    if "Windows" in user_agent:
        platform = "Win32"
    elif "Macintosh" in user_agent:
        platform = "MacIntel"
    else:
        platform = "Linux x86_64"

    # Визначаємо languages на основі timezone
    if "America" in timezone:
        languages = ["en-US", "en"]
    elif "Europe" in timezone:
        if "London" in timezone:
            languages = ["en-GB", "en"]
        elif "Paris" in timezone:
            languages = ["fr-FR", "fr", "en"]
        elif "Berlin" in timezone:
            languages = ["de-DE", "de", "en"]
        else:
            languages = ["en-GB", "en"]
    elif "Asia" in timezone:
        if "Tokyo" in timezone:
            languages = ["ja-JP", "ja", "en"]
        elif "Shanghai" in timezone or "Beijing" in timezone:
            languages = ["zh-CN", "zh", "en"]
        else:
            languages = ["en-US", "en"]
    else:
        languages = ["en-US", "en"]

    webgl_vendor, webgl_renderer = generate_webgl_params()
    screen = generate_screen_metrics(viewport)
    headers = generate_realistic_headers(user_agent)

    return FingerprintProfile(
        viewport=viewport,
        user_agent=user_agent,
        platform=platform,
        languages=languages,
        timezone=timezone,
        geolocation=geolocation,
        webgl_vendor=webgl_vendor,
        webgl_renderer=webgl_renderer,
        screen=screen,
        headers=headers,
    )


def random_choice_user_agent() -> str:
    """Helper to choose a random user-agent from the static dataset."""
    # Local import of ``random`` to keep the module import light-weight
    import random

    return random.choice(USER_AGENTS)


__all__ = ["FingerprintProfile", "generate_fingerprint_profile"]
