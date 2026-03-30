"""Anti-bot Detection & Stealth Plugin - обхід anti-bot систем.

У цій версії модуль фокусується на orchestration, а не на дрібних
деталях. Детекція, JavaScript-скрипти та Playwright-конфіг винесені у
відповідні підмодулі.
"""

from __future__ import annotations

import logging
import random
from typing import Any, Dict, List

from graph_crawler.extensions.plugins.base import BasePlugin, PluginContext, PluginType
from graph_crawler.extensions.plugins.engine.anti_bot_detection import (
    AntiBotSystem,
    detect_anti_bot_system,
)
from graph_crawler.extensions.plugins.engine.anti_bot_playwright import (
    build_playwright_stealth_config,
    build_stealth_headers,
)
from graph_crawler.extensions.plugins.engine.anti_bot_scripts import (
    base_stealth_scripts,
    cloudflare_specific_scripts,
    datadome_specific_scripts,
)

logger = logging.getLogger(__name__)


class AntiBotStealthPlugin(BasePlugin):
    """Plugin для обходу anti-bot систем через stealth техніки."""

    def __init__(self, config: Dict[str, Any] | None = None):
        super().__init__(config)
        self.detected_systems: List[str] = []
        self.bypass_attempts = 0
        self.bypass_successes = 0

    @property
    def plugin_type(self) -> PluginType:
        return PluginType.PRE_REQUEST

    @property
    def name(self) -> str:
        return "anti_bot_stealth"

    def setup(self) -> None:
        stealth_mode = self.config.get("stealth_mode", "high")
        logger.info("Anti-bot Stealth Plugin initialized (mode: %s)", stealth_mode)

    # High-level helpers
    def _collect_stealth_scripts(self) -> List[str]:
        scripts = base_stealth_scripts(self.config)
        return scripts

    def _apply_cloudflare_bypass(self, context: PluginContext) -> None:
        """Apply Cloudflare-specific bypass techniques."""
        logger.info("Applying Cloudflare bypass techniques")

        # NOTE: CF-Connecting-IP header is set by Cloudflare itself and cannot be
        # spoofed by the client. We only add stealth scripts and human emulation.
        cf_scripts = cloudflare_specific_scripts()
        context.plugin_data.setdefault("stealth_scripts", []).extend(cf_scripts)

        if self.config.get("emulate_human", True):
            context.plugin_data["emulate_human"] = True
            context.plugin_data["wait_time"] = random.uniform(3, 7)

    def _apply_datadome_bypass(self, context: PluginContext) -> None:
        """Apply DataDome-specific bypass techniques."""
        logger.info("Applying DataDome bypass techniques")
        dd_scripts = datadome_specific_scripts()
        context.plugin_data.setdefault("stealth_scripts", []).extend(dd_scripts)

    # Core plugin API
    def apply_stealth_to_context(self, context: PluginContext) -> PluginContext:
        scripts = self._collect_stealth_scripts()
        context.plugin_data["stealth_scripts"] = scripts

        stealth_headers = build_stealth_headers()
        context.metadata.setdefault("extra_headers", {}).update(stealth_headers)

        context.plugin_data["playwright_config"] = build_playwright_stealth_config(
            self.config,
        )

        detected_system = detect_anti_bot_system(context.html)
        if detected_system:
            self.detected_systems.append(detected_system)
            context.plugin_data["anti_bot_system"] = detected_system
            logger.warning("Anti-bot system detected: %s", detected_system.value)

            if detected_system == AntiBotSystem.CLOUDFLARE and self.config.get(
                "bypass_cloudflare", True
            ):
                self._apply_cloudflare_bypass(context)
            elif detected_system == AntiBotSystem.DATADOME and self.config.get(
                "bypass_datadome", False
            ):
                self._apply_datadome_bypass(context)

        return context

    def execute(self, context: PluginContext) -> PluginContext:
        if not self.enabled:
            return context

        logger.debug("Applying stealth techniques to %s", context.url)
        self.bypass_attempts += 1
        return self.apply_stealth_to_context(context)

    # Stats API
    def report_success(self) -> None:
        self.bypass_successes += 1

    def report_failure(self) -> None:
        """Report a bypass failure. Attempts are already counted in execute()."""
        # Nothing to do here - attempts counter is already incremented in execute()

    def get_stats(self) -> Dict[str, Any]:
        return {
            "bypass_attempts": self.bypass_attempts,
            "bypass_successes": self.bypass_successes,
            "success_rate": (
                self.bypass_successes / self.bypass_attempts if self.bypass_attempts > 0 else 0.0
            ),
            "detected_systems": list(set(self.detected_systems)),
            "stealth_mode": self.config.get("stealth_mode", "high"),
            "enabled": self.enabled,
        }

    def reset_stats(self) -> None:
        self.detected_systems = []
        self.bypass_attempts = 0
        self.bypass_successes = 0
