"""Константи та магічні значення GraphCrawler.

Цей модуль містить всі константи які використовуються в проекті.
Замінює магічні числа та рядки на іменовані константи.

Alpha 2.0:
- Змінено DEFAULT_BROWSER_WAIT_UNTIL з 'networkidle' на 'domcontentloaded'
- Додано нові константи для scroll
"""

import os
import tempfile

# Version - єдине джерело версії
from graph_crawler.__version__ import __version__

# ==================== ЛІМІТИ СИСТЕМИ ====================

MAX_PAGES_LIMIT = None
"""Ліміт сторінок для краулінгу (None = без ліміту).

 ВАЖЛИВО: Відсутність ліміту може призвести до:
- Використання великої кількості RAM
- Довгого часу сканування
- Перевантаження цільового сервера

РЕКОМЕНДАЦІЇ:
- <1k сторінок: Memory storage
- 1k-10k: JSON storage
- 10k-100k: SQLite storage
- >100k: PostgreSQL/MongoDB + chunked processing
"""

MAX_PAGES_WARNING_THRESHOLD = 20000
"""Поріг попередження про велику кількість сторінок.

Якщо сканується більше сторінок - буде виведено попередження.
"""

MAX_DEPTH_DEFAULT = 3
"""Дефолтна максимальна глибина сканування."""

MAX_PAGES_DEFAULT = 100
"""Дефолтна кількість сторінок для сканування."""

# ==================== ТАЙМАУТИ ====================

DEFAULT_REQUEST_TIMEOUT = 30
"""Дефолтний таймаут для HTTP запитів (секунди)."""

DEFAULT_CONNECT_TIMEOUT = 10
"""Дефолтний таймаут для підключення (секунди)."""

DEFAULT_READ_TIMEOUT = 30
"""Дефолтний таймаут для читання відповіді (секунди)."""

# ==================== ЗАТРИМКИ ====================

DEFAULT_REQUEST_DELAY = 0.005
"""Дефолтна затримка між запитами (секунди)."""

DEFAULT_MIN_DELAY = 0.3
"""Мінімальна затримка між запитами (секунди)."""

DEFAULT_MAX_DELAY = 1.0
"""Максимальна затримка між запитами (секунди)."""

# ==================== USER AGENT ====================

USER_AGENT_TEMPLATE = "GraphCrawler/{version} (https://example.com)"
"""Шаблон для User-Agent. {version} буде замінено на поточну версію."""

DEFAULT_USER_AGENT = USER_AGENT_TEMPLATE.format(version=__version__)
"""Дефолтний User-Agent з поточною версією."""

# ==================== STORAGE ====================

DEFAULT_STORAGE_DIR = os.path.join(tempfile.gettempdir(), "graph_crawler")
"""Дефолтна директорія для тимчасових файлів.

Використовує tempfile.gettempdir() для кросплатформності:
- Linux/Unix: /tmp/graph_crawler
- Windows: C:\\Users\\USERNAME\\AppData\\Local\\Temp\\graph_crawler
- macOS: /var/folders/.../T/graph_crawler
"""

JSON_INDENT = 2
"""Відступ для JSON файлів."""

DEFAULT_JSON_THRESHOLD = 20000
"""Дефолтний поріг для автоматичного переходу JSON → Database storage.

При AutoStorage:
- < memory_threshold: MemoryStorage
- memory_threshold - json_threshold: JSONStorage
- > json_threshold: SQLite/PostgreSQL/MongoDB
"""

# ==================== BROWSER (Playwright) ====================

DEFAULT_VIEWPORT_WIDTH = 1920
"""Дефолтна ширина viewport для браузера."""

DEFAULT_VIEWPORT_HEIGHT = 1080
"""Дефолтна висота viewport для браузера."""

DEFAULT_PAGE_LOAD_TIMEOUT = 30000
"""Дефолтний таймаут завантаження сторінки (мілісекунди)."""

DEFAULT_NAVIGATION_TIMEOUT = 30000
"""Дефолтний таймаут навігації (мілісекунди)."""

# ==================== RETRY ====================

DEFAULT_MAX_RETRIES = 3
"""Дефолтна кількість повторних спроб при помилці."""

DEFAULT_RETRY_DELAY = 1.0
"""Дефолтна затримка між повторними спробами (секунди)."""

# ==================== CONCURRENCY ====================

DEFAULT_MAX_CONCURRENT_REQUESTS = 100
"""Дефолтна кількість одночасних запитів (для async драйверів).
 
- Швидкістю паралельної обробки
- Навантаженням на сервер
- Ризиком rate limiting

"""

# ==================== COMPRESSION ====================

DEFAULT_COMPRESSION_LEVEL = 6
"""Дефолтний рівень компресії (1-9)."""

# ==================== TEXT LIMITS ====================

MAX_TEXT_LENGTH = 10000
"""Максимальна довжина тексту для sanitization."""

MAX_TITLE_LENGTH = 500
"""Максимальна довжина title."""

MAX_DESCRIPTION_LENGTH = 1000
"""Максимальна довжина description."""

MAX_KEYWORDS_LENGTH = 500
"""Максимальна довжина keywords."""

MAX_H1_LENGTH = 500
"""Максимальна довжина H1."""

# ==================== GRAPH OPERATIONS ====================

MAX_BFS_ITERATIONS = 100000
"""Максимальна кількість ітерацій BFS для запобігання зависання."""

# ==================== CRAWLER PROGRESS ====================

PROGRESS_UPDATE_INTERVAL = 10
"""Інтервал оновлення прогресу (кожні N сторінок)."""

DEFAULT_BATCH_SIZE = 50
"""Дефолтний розмір batch для паралельної обробки."""

# ==================== CACHE ====================

DEFAULT_CACHE_TTL = 3600
"""Дефолтний TTL для кешу (секунди) - 1 година."""

# ==================== EVENT BUS ====================

DEFAULT_EVENT_HISTORY_SIZE = 1000
"""Дефолтний розмір історії подій в EventBus."""

# ==================== URL SCHEDULING ====================

DEFAULT_URL_PRIORITY = 5
"""Дефолтний пріоритет для URL (шкала 1-10)."""

PRIORITY_MIN = 1
"""Мінімальний пріоритет URL."""

PRIORITY_MAX = 10
"""Максимальний пріоритет URL."""

# ==================== SQLITE PRAGMAS ====================

SQLITE_JOURNAL_MODE = "WAL"
"""Дефолтний journal mode для SQLite."""

SQLITE_SYNCHRONOUS = "NORMAL"
"""Дефолтний synchronous режим для SQLite."""

SQLITE_CACHE_SIZE = -64000
"""Дефолтний cache size для SQLite (в KB, негативне значення)."""

# ==================== HTTP STATUS CODES ====================

HTTP_OK = 200
"""HTTP 200 OK - успішний запит."""

HTTP_BAD_REQUEST = 400
"""HTTP 400 Bad Request - невірний запит."""

HTTP_TOO_MANY_REQUESTS = 429
"""HTTP 429 Too Many Requests - забагато запитів (rate limiting)."""

HTTP_INTERNAL_SERVER_ERROR = 500
"""HTTP 500 Internal Server Error - внутрішня помилка сервера."""

HTTP_BAD_GATEWAY = 502
"""HTTP 502 Bad Gateway - помилка шлюзу."""

HTTP_SERVICE_UNAVAILABLE = 503
"""HTTP 503 Service Unavailable - сервіс недоступний."""

HTTP_GATEWAY_TIMEOUT = 504
"""HTTP 504 Gateway Timeout - таймаут шлюзу."""

HTTP_RETRYABLE_STATUS_CODES = [
    HTTP_TOO_MANY_REQUESTS,
    HTTP_INTERNAL_SERVER_ERROR,
    HTTP_BAD_GATEWAY,
    HTTP_SERVICE_UNAVAILABLE,
    HTTP_GATEWAY_TIMEOUT,
]
"""HTTP коди, при яких потрібно повторити запит.

Ці коди зазвичай вказують на тимчасові проблеми сервера,
а не на помилки клієнта, тому має сенс повторити запит.
"""

HTTP_CLIENT_ERROR_START = 400
"""Початок діапазону HTTP клієнтських помилок (4xx)."""

HTTP_SERVER_ERROR_START = 500
"""Початок діапазону HTTP серверних помилок (5xx)."""

# ==================== REDIS/CELERY ====================

DEFAULT_REDIS_HOST = "localhost"
"""Дефолтний хост для Redis."""

DEFAULT_REDIS_PORT = 6379
"""Дефолтний порт для Redis."""

DEFAULT_REDIS_DB = 0
"""Дефолтна база даних Redis (0-15)."""

DEFAULT_CELERY_TASK_TIME_LIMIT = 600
"""Дефолтний hard limit для Celery задачі (секунди) - 10 хвилин."""

DEFAULT_CELERY_TASK_SOFT_TIME_LIMIT = 540
"""Дефолтний soft limit для Celery задачі (секунди) - 9 хвилин.

Soft limit дає змогу задачі завершитися gracefully.
"""

DEFAULT_CELERY_RESULTS_TIMEOUT = 600
"""Дефолтний таймаут очікування результатів Celery (секунди) - 10 хвилин."""

# ==================== RETRY CONFIGURATION ====================

DEFAULT_RETRY_BACKOFF_FACTOR = 0.5
"""Дефолтний backoff factor для retry (exponential backoff).

Затримка = backoff_factor * (2 ^ retry_attempt)
"""

DEFAULT_RETRY_EXPONENTIAL_BASE = 2
"""Дефолтна база для експоненційного backoff (2^n)."""

# ==================== HTTP METHODS ====================

HTTP_METHODS_SAFE = ["HEAD", "GET", "OPTIONS"]
"""HTTP методи, які можна безпечно повторювати (idempotent)."""

# ==================== CONNECTION POOLING ====================

DEFAULT_CONNECTION_POOL_SIZE = 10
"""Дефолтний розмір connection pool для HTTP клієнта."""

DEFAULT_CONNECTION_POOL_MAXSIZE = 10
"""Дефолтний максимальний розмір connection pool."""

# ==================== MONGODB ====================

DEFAULT_MONGODB_TIMEOUT_MS = 5000
"""Дефолтний таймаут підключення до MongoDB (мілісекунди) - 5 секунд."""

# ==================== MULTIPROCESSING ====================

MAX_MULTIPROCESSING_WORKERS = 32
"""Максимальна кількість воркерів для multiprocessing.

 ВАЖЛИВО: Більше 32 воркерів може призвести до:
- Перевантаження системи
- Зниження продуктивності через context switching
- Проблем з лімітами операційної системи
"""

# ==================== STATISTICS ====================

PERCENTAGE_MULTIPLIER = 100
"""Множник для конвертації в відсотки (0.85 * 100 = 85%)."""

DEFAULT_MIN_SUCCESS_RATE = 0.5
"""Дефолтний мінімальний success rate (50%)."""

MIN_REQUESTS_FOR_STATS = 10
"""Мінімальна кількість запитів для валідної статистики."""

MAX_RESPONSE_TIME_SAMPLES = 100
"""Максимальна кількість збережених зразків response time."""

# ==================== DASHBOARD & MONITORING ====================

MAX_DASHBOARD_HISTORY_SIZE = 1000
"""Максимальний розмір історії для dashboard."""

DEFAULT_DASHBOARD_HISTORY_PREVIEW = 100
"""Кількість останніх записів історії для попереднього перегляду."""

# ==================== PROXY MIDDLEWARE ====================

DEFAULT_PROXY_RECHECK_INTERVAL = 300
"""Дефолтний інтервал перевірки proxy (секунди) - 5 хвилин."""

DEFAULT_PROXY_HEALTH_CHECK_TIMEOUT = 5
"""Дефолтний таймаут для health check proxy (секунди)."""

DEFAULT_PROXY_HEALTH_CHECK_URL = "http://httpbin.org/ip"
"""Дефолтний URL для health check proxy."""

# ==================== HASH & VALIDATION ====================

SHA256_HASH_LENGTH = 64
"""Довжина SHA256 хешу в hex форматі (256 біт = 64 hex символи)."""

DEFAULT_HASH_ENCODING = "utf-8"
"""Дефолтне кодування для хешування."""

SHA256_HASH_PATTERN = r"^[a-f0-9]{64}$"
"""Регулярний вираз для валідації SHA256 хешу."""

# ==================== PLAYWRIGHT BROWSER ====================

DEFAULT_BROWSER_TYPE = "chromium"
"""Дефолтний тип браузера для Playwright."""

SUPPORTED_BROWSERS = ["chromium", "firefox", "webkit"]
"""Підтримувані типи браузерів для Playwright."""

DEFAULT_BROWSER_VIEWPORT_WIDTH = 1920
"""Дефолтна ширина viewport для браузера."""

DEFAULT_BROWSER_VIEWPORT_HEIGHT = 1080
"""Дефолтна висота viewport для браузера."""

DEFAULT_BROWSER_WAIT_TIMEOUT = 30000
"""Дефолтний таймаут очікування селектора в браузері (мілісекунди) - 30 секунд."""

DEFAULT_BROWSER_WAIT_UNTIL = "domcontentloaded"
"""Дефолтна стратегія очікування завантаження сторінки.

Використовується 'domcontentloaded' для стабільності.
'networkidle' часто не спрацьовує на динамічних сайтах з постійними запитами.

Опції:
- 'load': чекає на load event
- 'domcontentloaded': чекає на domcontentloaded event (РЕКОМЕНДОВАНО)
- 'networkidle': чекає поки мережа стане idle (може timeout на динамічних сайтах)
- 'commit': чекає на перший response byte (найшвидший)
"""

# Playwright Stealth Mode Arguments
PLAYWRIGHT_STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-web-security",
    "--disable-features=IsolateOrigins,site-per-process",
]
"""Аргументи браузера для stealth режиму (обхід anti-bot detection)."""

DEFAULT_SCREENSHOT_DIRECTORY = "./screenshots"
"""Дефолтна директорія для збереження screenshots."""

# ==================== SCROLL SETTINGS ====================

DEFAULT_SCROLL_STEP = 500
"""Дефолтний крок скролу в пікселях."""

DEFAULT_SCROLL_PAUSE = 0.3
"""Дефолтна пауза між скролами в секундах."""

DEFAULT_SCROLL_TIMEOUT = 30
"""Дефолтний максимальний час скролу в секундах."""

DEFAULT_MAX_SCROLLS = 200
"""Дефолтна максимальна кількість скролів."""

# ==================== HTTP RETRY ====================

DEFAULT_RETRY_MAX_ATTEMPTS = 3
"""Дефолтна максимальна кількість спроб повтору запиту."""

# ПРИМІТКА: DEFAULT_RETRY_DELAY вже визначено на рядку ~119

# ==================== USER AGENT ====================

UA_DISPLAY_LENGTH = 50
"""Довжина User-Agent для відображення в логах (символів)."""

UA_TOP_COUNT = 5
"""Кількість топ User-Agent для відображення в статистиці."""

# ==================== PROXY ====================

DEFAULT_PROXY_HEALTH_CHECK_URL = "http://httpbin.org/ip"
"""Дефолтний URL для перевірки працездатності proxy."""
