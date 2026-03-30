"""
Enhanced Stealth плагін для Playwright драйвера.

Використовує playwright-stealth для максимального приховування автоматизації.
Це покращена версія StealthPlugin з повною інтеграцією playwright-stealth.

Features:
- Повна інтеграція playwright-stealth
- Рандомізація fingerprint
- Human-like поведінка (mouse movements, typing delays)
- WebRTC leak protection
- Canvas/WebGL fingerprint spoofing
"""

import asyncio
import logging
import random
from typing import Dict, List

from graph_crawler.infrastructure.transport.base_plugin import BaseDriverPlugin
from graph_crawler.infrastructure.transport.playwright.context import BrowserContext
from graph_crawler.infrastructure.transport.playwright.stages import BrowserStage

logger = logging.getLogger(__name__)


class EnhancedStealthPlugin(BaseDriverPlugin):
    """
    Покращений Stealth плагін з playwright-stealth.

    Конфігурація:
        stealth_level: Рівень stealth ('basic', 'standard', 'maximum') (default: 'maximum')
        human_behavior: Емуляція людської поведінки (default: True)
        randomize_fingerprint: Рандомізація fingerprint (default: True)
        webrtc_protection: Захист від WebRTC leak (default: True)
        navigator_override: Перевизначення navigator properties (default: True)

    Приклад:
        plugin = EnhancedStealthPlugin(EnhancedStealthPlugin.config(
            stealth_level='maximum',
            human_behavior=True
        ))
    """

    @property
    def name(self) -> str:
        return "enhanced_stealth"

    def get_hooks(self) -> List[str]:
        return [
            BrowserStage.CONTEXT_CREATING,  # Для зміни user_agent
            BrowserStage.CONTEXT_CREATED,
            BrowserStage.PAGE_CREATED,
            BrowserStage.NAVIGATION_STARTING,
        ]

    async def on_context_creating(self, ctx: BrowserContext) -> BrowserContext:
        """
        Перехоплює створення контексту для зміни User-Agent.
        """
        # Встановлюємо реалістичний User-Agent
        realistic_ua = self._get_realistic_user_agent()
        ctx.data["override_user_agent"] = realistic_ua
        logger.debug("Setting realistic User-Agent: %s...", realistic_ua)
        return ctx

    def _get_realistic_viewport(self) -> Dict[str, int]:
        """Повертає реалістичний viewport на основі популярних розмірів."""
        viewports = [
            {"width": 1920, "height": 1080},
            {"width": 1366, "height": 768},
            {"width": 1536, "height": 864},
            {"width": 1440, "height": 900},
            {"width": 1280, "height": 720},
            {"width": 2560, "height": 1440},
        ]
        return random.choice(viewports)

    def _get_realistic_user_agent(self) -> str:
        """Повертає реалістичний User-Agent."""
        try:
            from fake_useragent import UserAgent

            ua = UserAgent()
            return ua.chrome
        except Exception:
            # Fallback до популярних Chrome UA
            user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            ]
            return random.choice(user_agents)

    def _get_stealth_scripts(self) -> List[str]:
        """Повертає додаткові stealth scripts."""
        scripts = []

        stealth_level = self.config.get("stealth_level", "maximum")

        # Webdriver hiding - must run before page load
        # This script runs in the page context before any other script
        scripts.append("""
            // === WEBDRIVER EVASION (HIGHEST PRIORITY) ===
            // Must delete before any detection script runs
        """)

        if stealth_level in ["standard", "maximum"]:
            # Chrome runtime mock
            scripts.append("""
                // Chrome runtime mock
                window.chrome = {
            """)

            # Plugins mock
            scripts.append("""
                // Plugins array mock
                Object.defineProperty(navigator, 'plugins', {
            """)

            # Languages
            scripts.append("""
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en', 'uk'],
                    configurable: true
                });

                Object.defineProperty(navigator, 'language', {
                    get: () => 'en-US',
                    configurable: true
                });
            """)

        if stealth_level == "maximum":
            # WebGL vendor/renderer spoofing
            if self.config.get("randomize_fingerprint", True):
                scripts.append("""
                    // WebGL fingerprint spoofing
                    const getParameterProto = WebGLRenderingContext.prototype.getParameter;
                    WebGLRenderingContext.prototype.getParameter = function(parameter) {
                        if (parameter === 37445) return 'Intel Inc.';
                        if (parameter === 37446) return 'Intel Iris OpenGL Engine';
                        if (parameter === 7937) return 'WebKit WebGL';
                        if (parameter === 7938) return 'WebGL 1.0 (OpenGL ES 2.0 Chromium)';
                        return getParameterProto.call(this, parameter);
                    };

                    const getParameter2Proto = WebGL2RenderingContext.prototype.getParameter;
                    WebGL2RenderingContext.prototype.getParameter = function(parameter) {
                        if (parameter === 37445) return 'Intel Inc.';
                        if (parameter === 37446) return 'Intel Iris OpenGL Engine';
                        if (parameter === 7937) return 'WebKit WebGL';
                        if (parameter === 7938) return 'WebGL 2.0 (OpenGL ES 3.0 Chromium)';
                        return getParameter2Proto.call(this, parameter);
                    };
                """)

            # Canvas fingerprint noise
            scripts.append("""
                // Canvas fingerprint noise
                const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
                HTMLCanvasElement.prototype.toDataURL = function(type) {
                    if (type === 'image/png' || type === undefined) {
                        const context = this.getContext('2d');
                        if (context) {
                            const imageData = context.getImageData(0, 0, this.width, this.height);
                            for (let i = 0; i < imageData.data.length; i += 4) {
                                // Add minimal noise that doesn't affect visual appearance
                                imageData.data[i] = imageData.data[i] ^ (Math.random() > 0.99 ? 1 : 0);
                            }
                            context.putImageData(imageData, 0, 0);
                        }
                    }
                    return originalToDataURL.apply(this, arguments);
                };
            """)

            # Permissions API mock
            scripts.append("""
                // Permissions API mock
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => {
                    if (parameters.name === 'notifications') {
                        return Promise.resolve({ state: Notification.permission });
                    }
                    return originalQuery(parameters);
                };
            """)

            # WebRTC protection
            if self.config.get("webrtc_protection", True):
                scripts.append("""
                    // WebRTC leak protection
                    const originalRTCPeerConnection = window.RTCPeerConnection;
                    window.RTCPeerConnection = function(...args) {
                        const pc = new originalRTCPeerConnection(...args);
                        const originalCreateOffer = pc.createOffer.bind(pc);
                        pc.createOffer = async function(options) {
                            const offer = await originalCreateOffer(options);
                            // Remove local IP candidates
                            offer.sdp = offer.sdp.replace(/a=candidate:.*typ host.*/g, '');
                            return offer;
                        };
                        return pc;
                    };
                    window.RTCPeerConnection.prototype = originalRTCPeerConnection.prototype;
                """)

            # Hardware concurrency randomization
            scripts.append("""
                // Hardware concurrency - realistic value
                Object.defineProperty(navigator, 'hardwareConcurrency', {
                    get: () => [4, 6, 8, 12, 16][Math.floor(Math.random() * 5)],
                    configurable: true
                });

                // Device memory - realistic value
                Object.defineProperty(navigator, 'deviceMemory', {
                    get: () => [4, 8, 16][Math.floor(Math.random() * 3)],
                    configurable: true
                });
            """)

            # Screen properties
            scripts.append("""
                // Screen properties
                Object.defineProperty(screen, 'colorDepth', {
                    get: () => 24,
                    configurable: true
                });

                Object.defineProperty(screen, 'pixelDepth', {
                    get: () => 24,
                    configurable: true
                });
            """)

        return scripts

    async def on_context_created(self, ctx: BrowserContext) -> BrowserContext:
        """
        Застосовує playwright-stealth та додаткові скрипти після створення контексту.
        """
        if not ctx.context:
            logger.warning("BrowserContext not available for stealth injection")
            return ctx

        try:
            # 1. Застосовуємо playwright-stealth
            try:
                from playwright_stealth import Stealth  # type: ignore[import-not-found]

                stealth = Stealth()
                await stealth.apply_stealth_async(ctx.context)
                logger.info("[STEALTH] playwright-stealth applied to context")
            except ImportError:
                logger.warning("playwright-stealth not installed, using fallback")
            except AttributeError:
                # Старий API
                try:
                    from playwright_stealth import stealth_async  # type: ignore[import-not-found]

                    await stealth_async(ctx.context)
                    logger.info("[STEALTH] playwright-stealth (legacy) applied to context")
                except Exception as e:
                    logger.warning("playwright-stealth legacy error: %s", e)
            except Exception as e:
                logger.warning("playwright-stealth error: %s, using fallback", e)

            # 2. Додаємо власні stealth скрипти
            scripts = self._get_stealth_scripts()
            for script in scripts:
                await ctx.context.add_init_script(script)

            # 3. Перехоплюємо запити для модифікації Sec-Ch-Ua заголовків
            # Це приховує HeadlessChrome в заголовках
            chrome_version = random.choice(["131", "130", "129", "128"])

            async def handle_route(route):
                headers = route.request.headers.copy()

                # Замінюємо Sec-Ch-Ua заголовки
                headers["sec-ch-ua"] = (
                    f'"Google Chrome";v="{chrome_version}", "Chromium";v="{chrome_version}", "Not?A_Brand";v="99"'
                )
                headers["sec-ch-ua-mobile"] = "?0"
                headers["sec-ch-ua-platform"] = '"Windows"'

                await route.continue_(headers=headers)

            await ctx.context.route("**/*", handle_route)
            logger.debug("Request interception enabled for header modification")

            logger.info(
                "[STEALTH] Injected %s enhanced stealth scripts (level: %s)",
                len(scripts), self.config.get('stealth_level', 'maximum')
            )

            ctx.data["enhanced_stealth_enabled"] = True
            ctx.data["stealth_level"] = self.config.get("stealth_level", "maximum")

        except Exception as e:
            logger.error("Error in enhanced stealth setup: %s", e)
            ctx.errors.append(e)

        return ctx

    async def on_page_created(self, ctx: BrowserContext) -> BrowserContext:
        """
        Додає human-like поведінку після створення сторінки.
        """
        if not ctx.page or not self.config.get("human_behavior", True):
            return ctx

        try:
            # Зберігаємо оригінальні методи для human-like interaction
            ctx.data["original_click"] = ctx.page.click
            ctx.data["original_type"] = ctx.page.type

            logger.debug("Human behavior hooks installed")

        except Exception as e:
            logger.debug("Human behavior setup skipped: %s", e)

        return ctx

    async def on_navigation_starting(self, ctx: BrowserContext) -> BrowserContext:
        """
        Додає мінімальну затримку перед навігацією (human-like).
        ОПТИМІЗОВАНО: зменшено з 100-500ms до 10-50ms
        """
        if not self.config.get("human_behavior", True):
            return ctx

        try:
            # Мінімальна затримка - достатньо для stealth, не блокує
            delay = random.uniform(0.01, 0.05)
            await asyncio.sleep(delay)

        except Exception as e:
            logger.debug("Navigation delay skipped: %s", e)

        return ctx


# Допоміжні функції для human-like interaction
async def human_type(page, selector: str, text: str, delay_range: tuple = (50, 150)):
    """Друкує текст з випадковими затримками між символами."""
    element = await page.wait_for_selector(selector)
    await element.click()

    for char in text:
        await page.keyboard.type(char)
        await asyncio.sleep(random.uniform(delay_range[0], delay_range[1]) / 1000)


async def human_click(page, selector: str, move_delay: float = 0.3):
    """Клікає з плавним рухом миші."""
    element = await page.wait_for_selector(selector)
    box = await element.bounding_box()

    if box:
        # Випадкова точка всередині елемента
        x = box["x"] + random.uniform(0.2, 0.8) * box["width"]
        y = box["y"] + random.uniform(0.2, 0.8) * box["height"]

        await page.mouse.move(x, y, steps=random.randint(5, 15))
        await asyncio.sleep(move_delay)
        await page.mouse.click(x, y)
    else:
        await element.click()
