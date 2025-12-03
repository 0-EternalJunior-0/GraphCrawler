"""Модульні конфігурації для різних компонентів системи."""

from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_settings import BaseSettings

from graph_crawler.domain.entities.registries import (
    ChangeDetectionStrategyRegistry,
    CrawlModeRegistry,
    MergeStrategyRegistry,
)
from graph_crawler.shared.constants import (
    DEFAULT_CACHE_TTL,
    DEFAULT_CELERY_TASK_SOFT_TIME_LIMIT,
    DEFAULT_CELERY_TASK_TIME_LIMIT,
    DEFAULT_COMPRESSION_LEVEL,
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_MAX_CONCURRENT_REQUESTS,
    DEFAULT_MAX_DELAY,
    DEFAULT_MAX_RETRIES,
    DEFAULT_MIN_DELAY,
    DEFAULT_NAVIGATION_TIMEOUT,
    DEFAULT_PAGE_LOAD_TIMEOUT,
    DEFAULT_READ_TIMEOUT,
    DEFAULT_REDIS_DB,
    DEFAULT_REDIS_HOST,
    DEFAULT_REDIS_PORT,
    DEFAULT_REQUEST_DELAY,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_RETRY_DELAY,
    DEFAULT_STORAGE_DIR,
    DEFAULT_USER_AGENT,
    DEFAULT_VIEWPORT_HEIGHT,
    DEFAULT_VIEWPORT_WIDTH,
    JSON_INDENT,
    MAX_DEPTH_DEFAULT,
    MAX_PAGES_DEFAULT,
    MAX_PAGES_LIMIT,
    PROGRESS_UPDATE_INTERVAL,
    SQLITE_CACHE_SIZE,
    SQLITE_JOURNAL_MODE,
    SQLITE_SYNCHRONOUS,
)
from graph_crawler.shared.utils.validation_helpers import validate_enum_field


class ProxyType(str, Enum):
    """Типи проксі."""

    HTTP = "http"
    HTTPS = "https"
    SOCKS4 = "socks4"
    SOCKS5 = "socks5"


class SQLitePragmas(BaseModel):
    """
    Конфігурація SQLite pragma.

    Документація SQLite pragmas: https://www.sqlite.org/pragma.html
    """

    journal_mode: str = Field(
        default=SQLITE_JOURNAL_MODE,
        description="Journal mode (DELETE, TRUNCATE, PERSIST, MEMORY, WAL, OFF)",
    )
    synchronous: str = Field(
        default=SQLITE_SYNCHRONOUS,
        description="Synchronous mode (OFF, NORMAL, FULL, EXTRA)",
    )
    cache_size: int = Field(
        default=SQLITE_CACHE_SIZE,
        description="Cache size in KB (negative for KB, positive for pages)",
    )

    @field_validator("journal_mode")
    @classmethod
    def validate_journal_mode(cls, v: str) -> str:
        """Валідація journal_mode через универсальний helper."""
        return validate_enum_field(
            "journal_mode",
            v.upper(),
            ["DELETE", "TRUNCATE", "PERSIST", "MEMORY", "WAL", "OFF"],
            case_sensitive=True,
        )

    @field_validator("synchronous")
    @classmethod
    def validate_synchronous(cls, v: str) -> str:
        """Валідація synchronous режиму через універсальний helper."""
        return validate_enum_field(
            "synchronous",
            v.upper(),
            ["OFF", "NORMAL", "FULL", "EXTRA"],
            case_sensitive=True,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Конвертує в словник для використання в SQLite."""
        return {
            "journal_mode": self.journal_mode,
            "synchronous": self.synchronous,
            "cache_size": self.cache_size,
        }


class ProxyConfig(BaseModel):
    """
    Конфігурація проксі.

    Example:
        import os

        proxy = ProxyConfig(
            enabled=True,
            url=os.getenv("PROXY_URL", "http://proxy.example.com:8080"),
            username=os.getenv("PROXY_USER"),
            password=os.getenv("PROXY_PASSWORD")
        )
    """

    enabled: bool = False
    proxy_type: ProxyType = ProxyType.HTTP
    url: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    rotation_enabled: bool = False
    proxy_list: List[str] = Field(default_factory=list)

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,  # Дозволяє використовувати як url так і start_url (alias)
    )


class BrowserConfig(BaseModel):
    """
    Конфігурація браузера для Playwright драйвера.

    Налаштування браузера, viewport, screenshots, тощо.
    """

    headless: bool = True
    browser_type: str = "chromium"  # chromium, firefox, webkit
    viewport_width: int = DEFAULT_VIEWPORT_WIDTH
    viewport_height: int = DEFAULT_VIEWPORT_HEIGHT
    user_agent: Optional[str] = None
    locale: str = "en-US"
    timezone: str = "UTC"

    # JavaScript
    javascript_enabled: bool = True

    # Додаткові опції
    ignore_https_errors: bool = True
    device_scale_factor: float = 1.0

    # Затримки (використовуємо константи)
    page_load_timeout: int = DEFAULT_PAGE_LOAD_TIMEOUT
    navigation_timeout: int = DEFAULT_NAVIGATION_TIMEOUT


class DriverConfig(BaseModel):
    """
    Конфігурація драйвера для сканування.

    Загальні налаштування для всіх типів драйверів.
    """

    # Таймаути (використовуємо константи)
    request_timeout: int = DEFAULT_REQUEST_TIMEOUT
    connect_timeout: int = DEFAULT_CONNECT_TIMEOUT
    read_timeout: int = DEFAULT_READ_TIMEOUT

    # Затримки (використовуємо константи)
    request_delay: float = DEFAULT_REQUEST_DELAY
    min_delay: float = DEFAULT_MIN_DELAY
    max_delay: float = DEFAULT_MAX_DELAY

    # Headers (використовуємо константу для User-Agent)
    user_agent: str = DEFAULT_USER_AGENT
    custom_headers: Dict[str, str] = Field(default_factory=dict)

    # Retry (використовуємо константи)
    max_retries: int = DEFAULT_MAX_RETRIES
    retry_delay: float = DEFAULT_RETRY_DELAY

    # Proxy
    proxy: Optional[ProxyConfig] = None

    # Browser (для Playwright)
    browser: Optional[BrowserConfig] = None

    # Cookies
    cookies: Dict[str, str] = Field(default_factory=dict)

    # Async/Concurrency settings (використовуємо константу)
    max_concurrent_requests: int = DEFAULT_MAX_CONCURRENT_REQUESTS


class StorageConfig(BaseModel):
    """
    Конфігурація системи зберігання.

    Налаштування для JSON/SQLite/PostgreSQL/MongoDB storage.
    """

    storage_dir: str = DEFAULT_STORAGE_DIR

    # JSON settings (використовуємо константи)
    json_indent: int = JSON_INDENT
    json_ensure_ascii: bool = False

    # SQLite settings (використовуємо Pydantic модель)
    sqlite_pragmas: SQLitePragmas = Field(default_factory=SQLitePragmas)

    # Auto-save settings
    auto_save_enabled: bool = True
    auto_save_interval: int = 100  # Зберігати кожні N вузлів

    # Compression (використовуємо константу)
    compression_enabled: bool = False
    compression_level: int = DEFAULT_COMPRESSION_LEVEL

    # Auto Storage thresholds (пороги для автоматичного переключення)
    memory_threshold: int = 1000  # <1000 nodes → MemoryStorage
    json_threshold: int = 20000  # 1000-20000 nodes → JSONStorage
    # >20000 nodes → SQLite або PostgreSQL/MongoDB (для 100k+)

    # Database connection config (для PostgreSQL/MongoDB)
    db_config: Optional[Dict[str, Any]] = None


class PluginConfig(BaseModel):
    """
    Конфігурація плагінів.

    Кожен плагін може мати свої налаштування.
    """

    # Screenshot plugin
    screenshot_enabled: bool = False
    screenshot_format: str = "png"  # png, jpeg
    screenshot_quality: int = 80
    screenshot_full_page: bool = False

    # Scroll plugin
    scroll_enabled: bool = False
    scroll_pause: float = 0.5
    scroll_to_bottom: bool = True

    # Cache plugin
    cache_enabled: bool = False
    cache_ttl: int = DEFAULT_CACHE_TTL

    # Custom plugins
    custom_plugins: List[str] = Field(default_factory=list)
    plugin_settings: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class CeleryConfig(BaseModel):
    """
    Конфігурація Celery для розподіленого краулінгу.

    Налаштування для Celery workers та Redis/RabbitMQ брокера.
    """

    enabled: bool = False
    broker_url: str = (
        f"redis://{DEFAULT_REDIS_HOST}:{DEFAULT_REDIS_PORT}/{DEFAULT_REDIS_DB}"
    )
    backend_url: str = f"redis://{DEFAULT_REDIS_HOST}:{DEFAULT_REDIS_PORT}/1"
    workers: int = Field(default=100, ge=1, le=1000)

    # Task settings
    task_time_limit: int = DEFAULT_CELERY_TASK_TIME_LIMIT
    task_soft_time_limit: int = DEFAULT_CELERY_TASK_SOFT_TIME_LIMIT
    worker_prefetch_multiplier: int = 4
    worker_max_tasks_per_child: int = 100

    # Queue settings
    task_default_queue: str = "graph_crawler"
    task_default_routing_key: str = "graph_crawler.default"


class CrawlerConfig(BaseSettings):
    """
    Головна конфігурація краулера.

    Об'єднує всі конфігурації в один об'єкт.

    allowed_domains підтримує спеціальні патерни:
      * '*' або AllowedDomains.ALL - куди завгодно
      * 'domain' - тільки основний домен
      * 'subdomains' - тільки субдомени
      * 'domain+subdomains' - домен + субдомени (DEFAULT)

    url_rules мають ВИЩИЙ ПРІОРИТЕТ за allowed_domains.

    ВАЖЛИВО: max_pages не має жорсткого ліміту, але система виведе попередження при 20,000+ сторінок.
    Для великих проектів (100k+ сторінок) рекомендується використовувати PostgreSQL/MongoDB storage.
    """

    # Основні параметри
    url: str = Field(..., description="Початковий URL для краулінгу")
    max_depth: int = Field(default=MAX_DEPTH_DEFAULT, ge=0)
    max_pages: Optional[int] = Field(default=MAX_PAGES_DEFAULT, ge=1)

    # allowed_domains із спеціальними патернами
    allowed_domains: Optional[List[Union[str, Any]]] = Field(
        default=None,
        description=(
            "Дозволені домени + спеціальні патерни. "
            "Спеціальні значення: '*' (куди завгодно), 'domain' (тільки домен), "
            "'subdomains' (тільки субдомени), 'domain+subdomains' (DEFAULT)"
        ),
    )

    # Smart Scheduling - система контролю URL
    url_rules: List[Any] = Field(default_factory=list)  # List[URLRule]

    # Edge Creation Strategy
    # Контролює які edges створюються (економія пам'яті, зменшення noise)
    edge_strategy: str = Field(
        default="all",
        description="Стратегія створення edges: 'all', 'new_only', 'max_in_degree', 'same_depth_only', 'deeper_only', 'first_encounter_only'",
    )
    max_in_degree_threshold: int = Field(
        default=100,
        ge=1,
        description="Максимальна кількість incoming edges (для стратегії max_in_degree)",
    )

    # Модульні конфігурації
    driver: DriverConfig = Field(default_factory=DriverConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    plugins: PluginConfig = Field(default_factory=PluginConfig)
    celery: CeleryConfig = Field(default_factory=CeleryConfig)

    # Node плагіни
    # Список плагінів для обробки Node (MetadataExtractor, LinkExtractor, тощо)
    # За замовчуванням використовуються дефолтні плагіни
    node_plugins: Optional[List[Any]] = None  # List[BaseNodePlugin]
    custom_node_class: Optional[Any] = None  # Optional[Type[Node]]
    custom_edge_class: Optional[Any] = None  # Optional[Type[Edge]]

    # Path filtering - виключити/включити URL патерни
    excluded_paths: List[str] = Field(
        default_factory=list, description="URL патерни для виключення"
    )
    included_paths: List[str] = Field(
        default_factory=list, description="URL патерни для включення"
    )

    # Multiprocessing settings
    # Кількість паралельних воркерів для розподіленої обробки
    # Ліміт 32: базується на оптимальному балансі CPU/Memory для multiprocessing
    # Для більшої кількості воркерів використовуйте mode='celery'
    workers: int = Field(default=1, ge=1, le=32)
    mode: str = Field(
        default="sequential"
    )  # 'sequential', 'multiprocessing', або 'celery'

    # Incremental Crawling settings
    # Дозволяє сканувати тільки змінені сторінки, порівнюючи з попереднім графом
    incremental: bool = False
    base_graph_name: Optional[str] = None
    change_detection_strategy: str = Field(default="hash")  # 'hash' або 'metadata'

    # Graph Merge Strategy
    # Визначає як об'єднувати вузли при операціях union (g1 + g2)
    merge_strategy: str = Field(
        default="last",
        description="Стратегія merge: 'first', 'last', 'merge', 'newest', 'oldest', 'custom'",
    )

    # Logging
    verbose: bool = False
    log_level: str = "INFO"

    @field_validator("allowed_domains", mode="before")
    @classmethod
    def convert_enum_to_strings(
        cls, v: Optional[List[Union[str, Any]]]
    ) -> Optional[List[str]]:
        """
        Конвертує enum значення в строки.

        Args:
            v: Значення allowed_domains

        Returns:
            Список строк
        """
        if v is None:
            return None

        # Конвертуємо enum значення в строки
        result = []
        for item in v:
            # Якщо це enum (AllowedDomains)
            if hasattr(item, "value"):
                result.append(item.value)
            else:
                result.append(str(item))

        return result

    @model_validator(mode="after")
    def set_default_allowed_domains(self):
        """
        Встановлює default значення для allowed_domains якщо None.
        """
        if self.allowed_domains is None:
            self.allowed_domains = ["domain+subdomains"]

        return self

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Валідація URL."""
        from urllib.parse import urlparse

        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        parsed = urlparse(v)
        if not parsed.netloc:
            raise ValueError("URL must have a valid domain")
        return v

    @field_validator("max_pages")
    @classmethod
    def validate_max_pages(cls, v: Optional[int]) -> Optional[int]:
        """
        Валідація max_pages.

        Жорсткий ліміт відсутній (MAX_PAGES_LIMIT = None).
        Користувач може встановити будь-яке значення, але отримає попередження
        при досягненні 20,000 сторінок (MAX_PAGES_WARNING_THRESHOLD).

        ВАЖЛИВО: Відсутність ліміту може призвести до:
        - Використання великої кількості RAM
        - Довгого часу сканування
        - Рекомендується використовувати database storage (PostgreSQL/MongoDB) для >100k сторінок
        """
        return v

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        """
        Валідація режиму краулінгу через Registry Pattern.

        Використовує CrawlModeRegistry для перевірки дозволених режимів.
        Дозволяє додавати нові режими без зміни цього валідатора (OCP).
        """
        allowed_modes = CrawlModeRegistry.get_all_names()
        if v not in allowed_modes:
            raise ValueError(f"Invalid mode: {v}. Allowed: {allowed_modes}")
        return v

    @field_validator("change_detection_strategy")
    @classmethod
    def validate_strategy(cls, v: str) -> str:
        """
        Валідація стратегії детекції змін через Registry Pattern.

        Використовує ChangeDetectionStrategyRegistry для перевірки.
        Дозволяє додавати нові стратегії без зміни валідатора (OCP).
        """
        allowed = ChangeDetectionStrategyRegistry.get_all_names()
        if v not in allowed:
            raise ValueError(f"Invalid strategy: {v}. Allowed: {allowed}")
        return v

    @field_validator("merge_strategy")
    @classmethod
    def validate_merge_strategy(cls, v: str) -> str:
        """
        Валідація стратегії merge для операцій union через Registry Pattern.

        Використовує MergeStrategyRegistry для перевірки.
        Дозволяє додавати нові стратегії merge без зміни валідатора (OCP).
        """
        allowed = MergeStrategyRegistry.get_all_names()
        if v.lower() not in allowed:
            raise ValueError(f"Invalid merge_strategy: {v}. Allowed: {allowed}")
        return v.lower()

    @field_validator("edge_strategy")
    @classmethod
    def validate_edge_strategy(cls, v: str) -> str:
        """
        Валідація стратегії створення edges.

        Дозволені значення: all, new_only, max_in_degree, same_depth_only,
        deeper_only, first_encounter_only.
        """
        from graph_crawler.domain.value_objects.models import EdgeCreationStrategy

        allowed = [e.value for e in EdgeCreationStrategy]
        if v.lower() not in allowed:
            raise ValueError(f"Invalid edge_strategy: {v}. Allowed: {allowed}")
        return v.lower()

    @field_validator("workers")
    @classmethod
    def validate_workers(cls, v: int) -> int:
        """
        Валідація кількості воркерів.

        Обґрунтування ліміту MAX_MULTIPROCESSING_WORKERS:
        - Multiprocessing mode: оптимально 1-32 воркери (balance CPU/Memory)
        - Більше 32: overhead від context switching > переваги паралелізму
        - Для більшої кількості: використовуйте mode='celery' (до 1000 воркерів)

        Рекомендації:
        - CPU-bound tasks: workers = CPU cores
        - I/O-bound tasks: workers = 2-4x CPU cores
        - Large scale (100+ workers): mode='celery'
        """
        from graph_crawler.shared.constants import MAX_MULTIPROCESSING_WORKERS

        if v > MAX_MULTIPROCESSING_WORKERS:
            raise ValueError(
                f"Workers limit is {MAX_MULTIPROCESSING_WORKERS} for multiprocessing mode. "
                f"For more workers use mode='celery' (supports up to 1000 workers). "
                f"Current value: {v}"
            )
        return v

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )

    # =====================================
    # LAW OF DEMETER: Методи-обгортки
    # =====================================
    # Замість self.config.driver.request_delay використовуємо self.config.get_request_delay()

    def get_request_delay(self) -> float:
        """Отримати затримку між запитами (Law of Demeter wrapper)."""
        return self.driver.request_delay

    def get_max_retries(self) -> int:
        """Отримати максимальну кількість спроб (Law of Demeter wrapper)."""
        return self.driver.max_retries

    def get_retry_delay(self) -> float:
        """Отримати затримку між повторними спробами (Law of Demeter wrapper)."""
        return self.driver.retry_delay

    def get_timeout(self) -> int:
        """Отримати таймаут запиту (Law of Demeter wrapper)."""
        return self.driver.request_timeout

    def get_user_agent(self) -> str:
        """Отримати User-Agent (Law of Demeter wrapper)."""
        return self.driver.user_agent

    def has_url_rules(self) -> bool:
        """Перевірити чи є активні URL rules."""
        return len(self.url_rules) > 0

    def get_url_rules_count(self) -> int:
        """Отримати кількість URL rules."""
        return len(self.url_rules)

    def is_wildcard_allowed(self) -> bool:
        """
        Перевіряє чи дозволено сканувати куди завгодно.

        Returns:
            True якщо '*' в allowed_domains

        Example:
            >>> config = CrawlerConfig(
            ...     url="https://company.com",
            ...     allowed_domains=['*']
            ... )
            >>> config.is_wildcard_allowed()
            True
        """
        return "*" in self.allowed_domains

    def has_special_patterns(self) -> bool:
        """
        Перевіряє чи є спеціальні патерни в allowed_domains.

        Returns:
            True якщо є хоча б один спеціальний патерн

        Example:
            >>> config = CrawlerConfig(
            ...     url="https://company.com",
            ...     allowed_domains=["domain+subdomains", "partner.com"]
            ... )
            >>> config.has_special_patterns()
            True
        """
        from graph_crawler.application.use_cases.crawling.filters.domain_patterns import (
            AllowedDomains,
        )

        special_patterns = AllowedDomains.get_special_patterns()
        return any(domain in special_patterns for domain in self.allowed_domains)

    def get_driver_params(self) -> dict:
        """
        Отримати параметри driver як dict (Law of Demeter wrapper).

        Використовується для серіалізації driver config (напр. в Celery).

        Returns:
            dict: Словник з параметрами driver

        Example:
            >>> config = CrawlerConfig(url="https://example.com")
            >>> driver_params = config.get_driver_params()
            >>> driver = HTTPDriver(driver_params)
        """
        return self.driver.model_dump()

    def get_storage_dir(self) -> str:
        """
        Отримати директорію для зберігання (Law of Demeter wrapper).

        Returns:
            str: Шлях до директорії storage

        Example:
            >>> config = CrawlerConfig(url="https://example.com")
            >>> storage_dir = config.get_storage_dir()
        """
        return self.storage.storage_dir

    def set_storage_dir(self, path: str):
        """
        Встановити директорію для зберігання (Law of Demeter wrapper).

        Args:
            path: Шлях до директорії storage

        Example:
            >>> config = CrawlerConfig(url="https://example.com")
            >>> config.set_storage_dir("/tmp/test_storage")
        """
        self.storage.storage_dir = path
