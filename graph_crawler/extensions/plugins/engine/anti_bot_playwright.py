"""Helpers to build Playwright stealth configuration and headers."""

from __future__ import annotations

import random
from typing import Any, Dict, Tuple


def build_stealth_headers() -> Dict[str, str]:
    return {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "max-age=0",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    }


def choose_viewport(config: Dict[str, Any]) -> Tuple[int, int]:
    viewport_sizes = config.get(
        "viewport_sizes",
        [
            (1920, 1080),
            (1366, 768),
            (1536, 864),
            (1440, 900),
            (1600, 900),
            (2560, 1440),
        ],
    )

    if config.get("randomize_viewport", True):
        return random.choice(viewport_sizes)

    return viewport_sizes[0]


def build_playwright_stealth_config(config: Dict[str, Any]) -> Dict[str, Any]:
    width, height = choose_viewport(config)

    base_config: Dict[str, Any] = {
        "viewport": {"width": width, "height": height},
        "user_agent": None,
        "locale": "en-US",
        "timezone_id": "America/New_York",
        "geolocation": None,
        "permissions": [],
        "extra_http_headers": build_stealth_headers(),
        "ignore_https_errors": True,
        "java_script_enabled": True,
        "bypass_csp": False,
        "has_touch": False,
        "is_mobile": False,
        "device_scale_factor": 1,
    }

    base_config["args"] = [
        "--disable-blink-features=AutomationControlled",
        "--disable-features=IsolateOrigins,site-per-process",
        "--disable-web-security",
        "--disable-features=BlockInsecurePrivateNetworkRequests",
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-accelerated-2d-canvas",
        "--no-first-run",
        "--no-zygote",
        "--disable-gpu",
    ]

    return base_config


__all__ = [
    "build_stealth_headers",
    "choose_viewport",
    "build_playwright_stealth_config",
]
