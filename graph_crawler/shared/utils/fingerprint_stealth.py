"""JavaScript stealth-mode script generator for fingerprint profiles."""

from __future__ import annotations

import random

from .fingerprint_profile import FingerprintProfile


def get_stealth_script(profile: FingerprintProfile) -> str:
    """Генерує JavaScript код для injection в браузер для stealth режиму.

    Цей скрипт змінює різні browser APIs щоб обійти fingerprinting.
    """

    lat, lon = profile.geolocation if profile.geolocation else (0, 0)

    script = f"""
    // ============ STEALTH MODE INJECTION ============
    // Browser Fingerprinting

    // 1. Navigator.webdriver bypass
    Object.defineProperty(navigator, 'webdriver', {{
        get: () => undefined
    }});

    // 2. Chrome runtime
    window.navigator.chrome = {{
        runtime: {{}},
        loadTimes: function() {{}},
        csi: function() {{}},
        app: {{}}
    }};

    // 3. Permissions API
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) => (
        parameters.name === 'notifications' ?
            Promise.resolve({{ state: Notification.permission }}) :
            originalQuery(parameters)
    );

    // 4. Plugins
    Object.defineProperty(navigator, 'plugins', {{
        get: () => [
            {{
                name: 'Chrome PDF Plugin',
                filename: 'internal-pdf-viewer',
                description: 'Portable Document Format',
                length: 1
            }},
            {{
                name: 'Chrome PDF Viewer',
                filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai',
                description: '',
                length: 1
            }},
            {{
                name: 'Native Client',
                filename: 'internal-nacl-plugin',
                description: '',
                length: 2
            }}
        ]
    }});

    // 5. Languages
    Object.defineProperty(navigator, 'languages', {{
        get: () => {profile.languages}
    }});

    // 6. Platform
    Object.defineProperty(navigator, 'platform', {{
        get: () => '{profile.platform}'
    }});

    // 7. Hardware concurrency
    Object.defineProperty(navigator, 'hardwareConcurrency', {{
        get: () => {random.choice([2, 4, 8, 16])}
    }});

    // 8. Device memory
    Object.defineProperty(navigator, 'deviceMemory', {{
        get: () => {random.choice([4, 8, 16])}
    }});

    // 9. Screen properties
    Object.defineProperty(window.screen, 'width', {{
        get: () => {profile.screen['width']}
    }});
    Object.defineProperty(window.screen, 'height', {{
        get: () => {profile.screen['height']}
    }});
    Object.defineProperty(window.screen, 'availWidth', {{
        get: () => {profile.screen['availWidth']}
    }});
    Object.defineProperty(window.screen, 'availHeight', {{
        get: () => {profile.screen['availHeight']}
    }});
    Object.defineProperty(window.screen, 'colorDepth', {{
        get: () => {profile.screen['colorDepth']}
    }});
    Object.defineProperty(window.screen, 'pixelDepth', {{
        get: () => {profile.screen['pixelDepth']}
    }});

    // 10. Geolocation override
    if (navigator.geolocation) {{
        const originalGetCurrentPosition = navigator.geolocation.getCurrentPosition;
        navigator.geolocation.getCurrentPosition = function(success, error, options) {{
            const position = {{
                coords: {{
                    latitude: {lat},
                    longitude: {lon},
                    accuracy: {random.uniform(10, 50)},
                    altitude: null,
                    altitudeAccuracy: null,
                    heading: null,
                    speed: null
                }},
                timestamp: Date.now()
            }};
            success(position);
        }};
    }}

    // 11. Timezone override
    Date.prototype.getTimezoneOffset = function() {{
        // Timezone offset in minutes
        const timezones = {{
            'America/New_York': 300,
            'America/Chicago': 360,
            'America/Los_Angeles': 480,
            'Europe/London': 0,
            'Europe/Paris': -60,
            'Europe/Berlin': -60,
            'Asia/Tokyo': -540,
            'Asia/Shanghai': -480,
            'Australia/Sydney': -660,
            'America/Toronto': 300
        }};
        return timezones['{profile.timezone}'] || 0;
    }};

    // 12. WebGL fingerprinting bypass
    const getParameter = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(parameter) {{
        if (parameter === 37445) {{
            return '{profile.webgl_vendor}';
        }}
        if (parameter === 37446) {{
            return '{profile.webgl_renderer}';
        }}
        return getParameter.apply(this, arguments);
    }};

    // 13. Canvas fingerprinting bypass
    const toDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function(type) {{
        if (type === 'image/png' && this.width === 220 && this.height === 30) {{
            // Fingerprinting attempt detected - return noise
            const canvas = document.createElement('canvas');
            canvas.width = this.width;
            canvas.height = this.height;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(this, 0, 0);
            // Add random noise
            const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
            for (let i = 0; i < imageData.data.length; i += 4) {{
                imageData.data[i] += Math.floor(Math.random() * 3) - 1;
                imageData.data[i + 1] += Math.floor(Math.random() * 3) - 1;
                imageData.data[i + 2] += Math.floor(Math.random() * 3) - 1;
            }}
            ctx.putImageData(imageData, 0, 0);
            return toDataURL.apply(canvas, arguments);
        }}
        return toDataURL.apply(this, arguments);
    }};

    // 14. AudioContext fingerprinting bypass
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (AudioContext) {{
        const createAnalyser = AudioContext.prototype.createAnalyser;
        AudioContext.prototype.createAnalyser = function() {{
            const analyser = createAnalyser.apply(this, arguments);
            const getFloatFrequencyData = analyser.getFloatFrequencyData;
            analyser.getFloatFrequencyData = function(array) {{
                getFloatFrequencyData.apply(this, arguments);
                // Add noise to defeat audio fingerprinting
                for (let i = 0; i < array.length; i++) {{
                    array[i] += Math.random() * 0.0001;
                }}
            }};
            return analyser;
        }};
    }}

    // 15. Battery API removal (used for fingerprinting)
    if (navigator.getBattery) {{
        navigator.getBattery = undefined;
    }}

    // 16. Connection API spoofing
    if (navigator.connection) {{
        Object.defineProperty(navigator.connection, 'effectiveType', {{
            get: () => '4g'
        }});
        Object.defineProperty(navigator.connection, 'rtt', {{
            get: () => {random.choice([50, 100, 150])}
        }});
    }}

    // ============ END STEALTH INJECTION ============
    console.log(' Stealth mode activated - fingerprint randomized');
    """

    return script


__all__ = ["get_stealth_script"]
