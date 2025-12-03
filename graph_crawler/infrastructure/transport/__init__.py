"""Модуль DRIVERS - Драйвери для завантаження веб-сторінок.

v4.0: Нова архітектура з чітким розділенням:
- protocols.py: Protocol interfaces (IAsyncDriver, ISyncDriver, IBrowserDriver)
- core/: Базові класи та mixins
- factory.py: Factory для створення драйверів
- async_http/: Async HTTP драйвер (aiohttp)
- sync/: Sync драйвери (requests) - для legacy
- playwright/: Browser драйвер

**Рекомендовані драйвери:**

1. **AsyncDriver** (DriverType.AIOHTTP) - РЕКОМЕНДОВАНИЙ
   - Async HTTP через aiohttp
   - Найшвидший для статичних сайтів
   - Паралельне завантаження через fetch_many()

2. **PlaywrightDriver** (DriverType.PLAYWRIGHT)
   - Async браузер з JS рендерингом
   - Для SPA та динамічного контенту
   - Підтримка плагінів (stealth, captcha)

3. **RequestsDriver** (DriverType.REQUESTS) - LEGACY
   -  Sync, блокує виконання!
   - Тільки для legacy коду

**Приклад використання:**

```python
from graph_crawler.infrastructure.transport import create_driver, DriverType

# Рекомендований спосіб - через factory
driver = create_driver(DriverType.AIOHTTP)

# Або напряму
from graph_crawler.infrastructure.transport.async_http import AsyncDriver
driver = AsyncDriver(config={'timeout': 30})

async with driver:
    response = await driver.fetch('https://example.com')
    results = await driver.fetch_many([url1, url2, url3])
```
"""

# ============================================
# АРХІТЕКТУРА v4.0
# ============================================

# Драйвери
from graph_crawler.infrastructure.transport.async_http import AsyncDriver

# Legacy base (для зворотньої сумісності)
from graph_crawler.infrastructure.transport.base import BaseDriver

# Plugins
from graph_crawler.infrastructure.transport.base_plugin import BaseDriverPlugin

# Utils
from graph_crawler.infrastructure.transport.connection_pool import ConnectionPoolManager
from graph_crawler.infrastructure.transport.context import DriverContext, EventPriority

# Core - базові класи та mixins
from graph_crawler.infrastructure.transport.core import (
    BaseAsyncDriver,
    BaseSyncDriver,
    MetricsMixin,
    PluginSupportMixin,
    RetryMixin,
)

# Factory
from graph_crawler.infrastructure.transport.factory import (
    DriverFactory,
    DriverType,
    create_driver,
)
from graph_crawler.infrastructure.transport.plugin_manager import DriverPluginManager

# Protocols
from graph_crawler.infrastructure.transport.protocols import (
    IAsyncDriver,
    IBrowserDriver,
    IDriverWithPlugins,
    ISyncDriver,
)
from graph_crawler.infrastructure.transport.session_adapters import (
    RequestsSessionAdapter,
)

# ДОКУМЕНТАЦІЯ: HTTPDriver alias
# HTTPDriver є alias для AsyncDriver (async драйвер на базі aiohttp).
# УВАГА: Це НЕ sync HTTP драйвер! Якщо потрібен sync - використовуйте RequestsDriver.
# Міграція з попередніх версій:
# - Старий sync HTTPDriver → використовуйте RequestsDriver
# - Новий async HTTPDriver → використовуйте AsyncDriver або HTTPDriver (однакові)
# Приклад:
#   from graph_crawler.infrastructure.transport import HTTPDriver  # async!
#   async with HTTPDriver() as driver:
#       response = await driver.fetch(url)
HTTPDriver = AsyncDriver

# Playwright опціональний
try:
    from graph_crawler.infrastructure.transport.playwright import PlaywrightDriver
except ImportError:
    PlaywrightDriver = None

# Sync драйвери (legacy)
try:
    from graph_crawler.infrastructure.transport.sync import RequestsDriver
except ImportError:
    RequestsDriver = None

__all__ = [
    # Protocols
    "IAsyncDriver",
    "ISyncDriver",
    "IBrowserDriver",
    "IDriverWithPlugins",
    # Core
    "BaseAsyncDriver",
    "BaseSyncDriver",
    "PluginSupportMixin",
    "RetryMixin",
    "MetricsMixin",
    # Factory
    "DriverFactory",
    "DriverType",
    "create_driver",
    # Legacy base
    "BaseDriver",
    # Plugins
    "BaseDriverPlugin",
    "DriverPluginManager",
    "DriverContext",
    "EventPriority",
    # Drivers
    "AsyncDriver",
    "HTTPDriver",  # Alias для AsyncDriver
    "PlaywrightDriver",
    "RequestsDriver",  # Legacy sync
    # Utils
    "ConnectionPoolManager",
    "RequestsSessionAdapter",
]
