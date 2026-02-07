"""Detection helpers for various anti-bot protection systems."""

from __future__ import annotations

from enum import Enum
from typing import Optional


class AntiBotSystem(str, Enum):
    CLOUDFLARE = "cloudflare"
    AKAMAI = "akamai"
    DATADOME = "datadome"
    PERIMETERX = "perimeterx"
    RECAPTCHA = "recaptcha"
    HCAPTCHA = "hcaptcha"
    IMPERVA = "imperva"
    GENERIC = "generic"


def detect_anti_bot_system(html: Optional[str]) -> Optional[AntiBotSystem]:
    """Best-effort detection of an anti-bot system based on HTML markers."""
    if not html:
        return None

    html_lower = html.lower()

    if any(
        marker in html_lower
        for marker in [
            "cloudflare",
            "cf-ray",
            "cf-cache-status",
            "__cf_bm",
            "challenge-platform",
        ]
    ):
        return AntiBotSystem.CLOUDFLARE

    if any(marker in html_lower for marker in ["datadome", "dd_cookie", "datadome.co", "dd-cid"]):
        return AntiBotSystem.DATADOME

    if any(marker in html_lower for marker in ["perimeterx", "_px", "px-captcha", "pxhd"]):
        return AntiBotSystem.PERIMETERX

    if any(marker in html_lower for marker in ["akamai", "_abck", "bm_sz", "sensor_data"]):
        return AntiBotSystem.AKAMAI

    if any(marker in html_lower for marker in ["incapsula", "imperva", "visid_incap", "_incap"]):
        return AntiBotSystem.IMPERVA

    return None


__all__ = ["AntiBotSystem", "detect_anti_bot_system"]
