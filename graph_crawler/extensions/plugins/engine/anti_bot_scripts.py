"""JavaScript stealth scripts for anti-bot evasion."""

from __future__ import annotations

from typing import Any, Dict, List


def base_stealth_scripts(config: Dict[str, Any]) -> List[str]:
    scripts: List[str] = []

    stealth_mode = config.get("stealth_mode", "high")

    if config.get("hide_webdriver", True):
        scripts.append(
            """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            """
        )
        scripts.append(
            """
            window.navigator.chrome = {
                runtime: {},
            };
            """
        )

    if stealth_mode in ["medium", "high"] and config.get("spoof_fingerprint", True):
        scripts.append(
            """
            const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
            HTMLCanvasElement.prototype.toDataURL = function() {
                const noise = Math.random() * 0.0001;
                const context = this.getContext('2d');
                const imageData = context.getImageData(0, 0, this.width, this.height);
                for (let i = 0; i < imageData.data.length; i += 4) {
                    imageData.data[i] += noise;
                }
                context.putImageData(imageData, 0, 0);
                return originalToDataURL.apply(this, arguments);
            };
            """
        )

        scripts.append(
            """
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) {
                    return 'Intel Inc.';
                }
                if (parameter === 37446) {
                    return 'Intel Iris OpenGL Engine';
                }
                return getParameter.apply(this, arguments);
            };
            """
        )

    if stealth_mode == "high":
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
                    },
                    {
                        0: {type: "application/pdf", suffixes: "pdf", description: "Portable Document Format"},
                        description: "Portable Document Format",
                        filename: "mhjfbmdgcfjbbpaeojofohoefgiehjai",
                        length: 1,
                        name: "Chrome PDF Viewer"
                    }
                ]
            });
            """
        )

        scripts.append(
            """
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
            """
        )

        scripts.append(
            """
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            """
        )

    if config.get("bypass_cloudflare", True):
        scripts.append(
            """
            Object.defineProperty(navigator, 'platform', {
                get: () => 'Win32'
            });

            Object.defineProperty(navigator, 'hardwareConcurrency', {
                get: () => 8
            });
            """
        )

    custom_scripts = config.get("custom_scripts", [])
    scripts.extend(custom_scripts)

    return scripts


def cloudflare_specific_scripts() -> List[str]:
    return [
        """
        // Cloudflare TLS fingerprinting bypass
        window.chrome = {
            app: {
                isInstalled: false,
            },
            webstore: {
                onInstallStageChanged: {},
                onDownloadProgress: {},
            },
            runtime: {},
        };
        """
    ]


def datadome_specific_scripts() -> List[str]:
    return [
        """
        // DataDome fingerprinting bypass
        Object.defineProperty(navigator, 'deviceMemory', {
            get: () => 8
        });

        Object.defineProperty(navigator, 'maxTouchPoints', {
            get: () => 0
        });
        """
    ]


__all__ = [
    "base_stealth_scripts",
    "cloudflare_specific_scripts",
    "datadome_specific_scripts",
]
