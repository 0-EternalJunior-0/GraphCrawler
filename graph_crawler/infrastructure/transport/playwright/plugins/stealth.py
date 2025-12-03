"""
Stealth плагін для Playwright драйвера.

Приховує ознаки автоматизації для обходу anti-bot систем.
Інжектить JavaScript на етапі CONTEXT_CREATED.
"""

import logging
import random
from typing import Any, Dict, List

from graph_crawler.infrastructure.transport.base_plugin import BaseDriverPlugin
from graph_crawler.infrastructure.transport.context import EventPriority
from graph_crawler.infrastructure.transport.playwright.context import BrowserContext
from graph_crawler.infrastructure.transport.playwright.stages import BrowserStage

logger = logging.getLogger(__name__)


class StealthPlugin(BaseDriverPlugin):
    """
    Stealth плагін для обходу anti-bot систем.

    Інжектить JavaScript скрипти для:
    - Приховання navigator.webdriver
    - Canvas fingerprinting evasion
    - WebGL fingerprinting evasion
    - Plugin spoofing
    - Тощо

    Конфігурація:
        stealth_mode: Рівень stealth ('low', 'medium', 'high') (default: 'high')
        hide_webdriver: Приховати webdriver (default: True)
        spoof_fingerprint: Підмінити fingerprint (default: True)
        randomize_viewport: Випадковий viewport (default: False)

    Приклад:
        plugin = StealthPlugin(StealthPlugin.config(
            stealth_mode='high',
            hide_webdriver=True,
            spoof_fingerprint=True
        ))
    """

    @property
    def name(self) -> str:
        return "stealth"

    def get_hooks(self) -> List[str]:
        # Підписуємось на створення context (тут інжектимо scripts)
        return [BrowserStage.CONTEXT_CREATED]

    def _get_stealth_scripts(self) -> List[str]:
        """Повертає JavaScript скрипти для stealth режиму."""
        scripts = []

        stealth_mode = self.config.get("stealth_mode", "high")

        # Базові скрипти (завжди)
        if self.config.get("hide_webdriver", True):
            scripts.append(
                """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });

                window.navigator.chrome = {
                    runtime: {}
                };
            """
            )

        if stealth_mode in ["medium", "high"]:
            # Canvas fingerprinting evasion
            if self.config.get("spoof_fingerprint", True):
                scripts.append(
                    """
                    const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
                    HTMLCanvasElement.prototype.toDataURL = function() {
                        const noise = Math.random() * 0.0001;
                        const context = this.getContext('2d');
                        if (context) {
                            const imageData = context.getImageData(0, 0, this.width, this.height);
                            for (let i = 0; i < imageData.data.length; i += 4) {
                                imageData.data[i] += noise;
                            }
                            context.putImageData(imageData, 0, 0);
                        }
                        return originalToDataURL.apply(this, arguments);
                    };
                """
                )

            # WebGL fingerprinting evasion
            scripts.append(
                """
                const getParameter = WebGLRenderingContext.prototype.getParameter;
                WebGLRenderingContext.prototype.getParameter = function(parameter) {
                    if (parameter === 37445) return 'Intel Inc.';
                    if (parameter === 37446) return 'Intel Iris OpenGL Engine';
                    return getParameter.apply(this, arguments);
                };
            """
            )

        if stealth_mode == "high":
            # Plugin array spoofing
            scripts.append(
                """
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [
                        {
                            0: {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format"},
                            description: "Portable Document Format",
                            filename: "internal-pdf-viewer",
                            length: 1,
                            name: "Chrome PDF Plugin"
                        }
                    ]
                });

                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });

                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
            """
            )

        return scripts

    async def on_context_created(self, ctx: BrowserContext) -> BrowserContext:
        """
        Інжектить stealth scripts після створення context.

        Args:
            ctx: Browser контекст

        Returns:
            Оновлений контекст
        """
        if not ctx.context:
            logger.warning("BrowserContext not available for stealth injection")
            return ctx

        try:
            # Отримуємо stealth скрипти
            scripts = self._get_stealth_scripts()

            # Інжектимо кожен скрипт
            for script in scripts:
                await ctx.context.add_init_script(script)

            logger.info(
                f"Injected {len(scripts)} stealth script(s) into browser context"
            )

            # Зберігаємо в контексті
            ctx.data["stealth_enabled"] = True
            ctx.data["stealth_mode"] = self.config.get("stealth_mode", "high")

        except Exception as e:
            logger.error(f"Error injecting stealth scripts: {e}")
            ctx.errors.append(e)

        return ctx
