"""Модуль UTILS - Допоміжні утіліти для роботи з URL та HTML.

Цей модуль містить статичні утіліти для:

**1. URLUtils** (utils/url_utils.py)

Робота з URL:
- **normalize_url()** - Нормалізація URL
  * Видалення query parameters
  * Видалення fragments (#)
  * Lowercase domain
  * Видалення trailing slash

- **make_absolute()** - Відносний → Абсолютний URL
  * urljoin(base_url, relative_url)
  * Обробка ../path, /path, path

- **get_domain()** - Витяг домену
  * urlparse(url).netloc
  * Видалення www. (опціонально)

- **get_path()** - Витяг шляху
  * urlparse(url).path

- **is_valid_url()** - Валідація URL
  * Перевірка схеми (http/https)
  * Перевірка домену
  * Перевірка формату

- **is_same_domain()** - Перевірка чи URL з того ж домену
  * Порівняння доменів
  * Опція ignore_www

**2. HTMLUtils** (utils/html_utils.py)

Робота з HTML:
- **parse_html()** - Парсинг HTML
  * BeautifulSoup(html, 'html.parser') або lxml
  * Альтернатива: selectolax (швидше в 10х)

- **extract_links()** - Витяг посилань
  * soup.find_all('a', href=True)
  * Фільтрація mailto:, tel:, javascript:
  * Перетворення відносних в абсолютні

- **extract_text()** - Витяг тексту
  * soup.get_text()
  * Очистка від зайвих пробілів
  * Використання: векторизація

- **extract_metadata()** - Витяг метаданих
  * title - <title>
  * description - <meta name="description">
  * keywords - <meta name="keywords">
  * h1 - <h1>
  * og:* - Open Graph tags

- **clean_html()** - Очистка HTML
  * Видалення <script>, <style>
  * Видалення коментарів

**Приклад використання:**

```python
from graph_crawler.shared.utils import URLUtils, HTMLUtils

# URL утіліти
base_url = "https://example.com/page"
relative = "../other"
absolute = URLUtils.make_absolute(relative, base_url)
print(absolute)  # "https://example.com/other"

normalized = URLUtils.normalize_url("https://Example.com/Path?a=1#section")
print(normalized)  # "https://example.com/path"

domain = URLUtils.get_domain("https://www.example.com/path")
print(domain)  # "www.example.com"

if URLUtils.is_valid_url("https://example.com"):
    print("Valid!")

# HTML утіліти
html = "<html><body><a href='/link'>Text</a></body></html>"
soup = HTMLUtils.parse_html(html)

links = HTMLUtils.extract_links(soup, base_url="https://example.com")
print(links)  # ["https://example.com/link"]

text = HTMLUtils.extract_text(soup)
print(text)  # "Text"

metadata = HTMLUtils.extract_metadata(soup)
print(metadata)  # {'title': None, 'description': None, ...}
```

**Best Practices:**

1. Всі методи - @staticmethod (не потрібен стан)
2. Використання urllib.parse для URL
3. BeautifulSoup або selectolax для HTML
4. Type hints на всі методи
5. Docstrings у Google style
6. Обробка помилок (try/except)
7. Логування через logging

**Продуктивність:**

Для високої продуктивності розгляньте:
- selectolax замість BeautifulSoup (10x швидше)
- lxml parser замість html.parser
- Кешування parse результатів
"""

from graph_crawler.shared.utils.bloom_filter import BloomFilter, create_bloom_filter

# CAPTCHA Detection: plugins_new/captcha_detector.py (CaptchaDetectorPlugin)
# Для standalone детекції використовуйте graph_crawler.plugins.engine.captcha_solver
from graph_crawler.shared.utils.captcha import (
    BypassAttempt,
    BypassResult,
    BypassStrategy,
    CaptchaBypassManager,
    SessionInfo,
)
from graph_crawler.shared.utils.fingerprint import (
    FingerprintProfile,
    generate_fingerprint_profile,
    generate_random_geolocation,
    generate_random_timezone,
    generate_random_viewport,
    generate_realistic_headers,
    get_stealth_script,
)
from graph_crawler.shared.utils.html_utils import HTMLUtils
from graph_crawler.shared.utils.proxy_manager import (
    Proxy,
    ProxyPoolManager,
    ProxyStats,
    ProxyType,
    RotationStrategy,
    create_proxy_manager,
)
from graph_crawler.shared.utils.rate_limiter import (
    DomainLimitConfig,
    DomainRateLimiter,
    RateLimiter,
)
from graph_crawler.shared.utils.url_utils import URLUtils
from graph_crawler.shared.utils.user_agent_rotator import (
    UserAgentRotator,
    create_rotator,
)


# Backward compatibility - create_captcha_bypass_manager
def create_captcha_bypass_manager(**kwargs) -> CaptchaBypassManager:
    """Factory функція для створення CaptchaBypassManager (backward compatibility)."""
    return CaptchaBypassManager(**kwargs)


# Celery Config
from graph_crawler.shared.utils.celery_config import (
    check_broker_connection,
    check_workers,
    get_backend_url,
    get_broker_url,
    get_celery_app_config,
    get_celery_batch_config,
    validate_distributed_setup,
)

# Celery Helpers
from graph_crawler.shared.utils.celery_helpers import (
    create_driver_from_config,
    import_class,
    import_plugin,
)
from graph_crawler.shared.utils.memory_optimizer import (
    MemoryEfficientNodeCache,
    MemoryMonitor,
    MemoryProfiler,
    MemoryStats,
    WeakValueGraph,
    estimate_graph_memory,
    get_object_size,
    memory_efficient_node_iterator,
    optimize_graph_memory,
)

__all__ = [
    "URLUtils",
    "HTMLUtils",
    "BloomFilter",
    "create_bloom_filter",
    # Rate Limiting
    "RateLimiter",
    "DomainRateLimiter",  # Backward compatibility alias
    "DomainLimitConfig",
    # User-Agent Rotation
    "UserAgentRotator",
    "create_rotator",
    # Proxy Manager
    "Proxy",
    "ProxyType",
    "ProxyStats",
    "RotationStrategy",
    "ProxyPoolManager",
    "create_proxy_manager",
    # Browser Fingerprinting
    "FingerprintProfile",
    "generate_fingerprint_profile",
    "generate_random_viewport",
    "generate_realistic_headers",
    "generate_random_timezone",
    "generate_random_geolocation",
    "get_stealth_script",
    # CAPTCHA Bypass
    "CaptchaBypassManager",
    "BypassStrategy",
    "BypassResult",
    "BypassAttempt",
    "SessionInfo",
    "create_captcha_bypass_manager",
    # Memory Optimization
    "MemoryProfiler",
    "MemoryStats",
    "MemoryMonitor",
    "WeakValueGraph",
    "get_object_size",
    "optimize_graph_memory",
    "memory_efficient_node_iterator",
    "estimate_graph_memory",
    "MemoryEfficientNodeCache",
    # Celery Config
    "get_broker_url",
    "get_backend_url",
    "get_celery_app_config",
    "get_celery_batch_config",
    "check_broker_connection",
    "check_workers",
    "validate_distributed_setup",
    # Celery Helpers
    "import_plugin",
    "import_class",
    "create_driver_from_config",
]
