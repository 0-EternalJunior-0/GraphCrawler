"""Static data sets used by the fingerprint utilities.

This module separates large constant structures from the generation logic
for better readability and testability.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

# Реалістичні розміри viewport (топ 10 найпопулярніших)
COMMON_VIEWPORTS: List[Dict[str, int]] = [
    {"width": 1920, "height": 1080},  # Full HD
    {"width": 1366, "height": 768},  # HD
    {"width": 1440, "height": 900},  # WXGA+
    {"width": 1536, "height": 864},  # HD+
    {"width": 1280, "height": 720},  # HD 720p
    {"width": 1600, "height": 900},  # HD+ wide
    {"width": 2560, "height": 1440},  # 2K
    {"width": 1920, "height": 1200},  # WUXGA
    {"width": 1680, "height": 1050},  # WSXGA+
    {"width": 1280, "height": 1024},  # SXGA
]

# Популярні User-Agent для різних браузерів
USER_AGENTS: List[str] = [
    # Chrome Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    # Chrome macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    # Firefox Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/118.0",
    # Safari macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
]

# Timezone options
TIMEZONES: List[str] = [
    "America/New_York",
    "America/Chicago",
    "America/Los_Angeles",
    "Europe/London",
    "Europe/Paris",
    "Europe/Berlin",
    "Asia/Tokyo",
    "Asia/Shanghai",
    "Australia/Sydney",
    "America/Toronto",
]

# Language preferences
LANGUAGES: List[List[str]] = [
    ["en-US", "en"],
    ["en-GB", "en"],
    ["de-DE", "de", "en"],
    ["fr-FR", "fr", "en"],
    ["es-ES", "es", "en"],
    ["it-IT", "it", "en"],
    ["ja-JP", "ja", "en"],
    ["zh-CN", "zh", "en"],
    ["pt-BR", "pt", "en"],
    ["ru-RU", "ru", "en"],
]

# Platform strings
PLATFORMS: List[str] = [
    "Win32",
    "MacIntel",
    "Linux x86_64",
]

# WebGL vendors
WEBGL_VENDORS: List[str] = [
    "Intel Inc.",
    "NVIDIA Corporation",
    "AMD",
    "Google Inc. (NVIDIA Corporation)",
    "Google Inc. (Intel Inc.)",
]

WEBGL_RENDERERS: List[str] = [
    "Intel Iris OpenGL Engine",
    "NVIDIA GeForce GTX 1050 Ti/PCIe/SSE2",
    "AMD Radeon Pro 5500M OpenGL Engine",
    "ANGLE (NVIDIA GeForce GTX 1650 Direct3D11 vs_5_0 ps_5_0)",
    "ANGLE (Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0)",
]


__all__ = [
    "COMMON_VIEWPORTS",
    "USER_AGENTS",
    "TIMEZONES",
    "LANGUAGES",
    "PLATFORMS",
    "WEBGL_VENDORS",
    "WEBGL_RENDERERS",
]
