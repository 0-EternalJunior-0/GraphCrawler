"""
Конфігурація краулера (аналог Scrapy settings.py).

"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DriverSettings(BaseModel):
    """Налаштування драйвера."""

    type: str = Field(default="http", description="Тип драйвера: http, playwright, stealth")
    user_agent: Optional[str] = Field(default=None, description="Custom User-Agent")
    headers: Dict[str, str] = Field(default_factory=dict, description="Додаткові HTTP headers")

    # Playwright specific
    headless: bool = Field(default=True, description="Запускати браузер без GUI")
    browser_type: str = Field(
        default="chromium", description="Тип браузера: chromium, firefox, webkit"
    )
    viewport_width: int = Field(default=1920, description="Ширина viewport")
    viewport_height: int = Field(default=1080, description="Висота viewport")
    block_resources: List[str] = Field(
        default_factory=lambda: ["image", "media", "font"], description="Ресурси для блокування"
    )

    # Timeouts
    page_load_timeout: int = Field(default=30000, description="Таймаут завантаження сторінки (ms)")
    navigation_timeout: int = Field(default=30000, description="Таймаут навігації (ms)")


class StorageSettings(BaseModel):
    """Налаштування storage."""

    type: str = Field(
        default="memory", description="Тип: memory, json, sqlite, postgresql, mongodb"
    )
    path: Optional[str] = Field(default=None, description="Шлях для файлового storage")

    # Database specific
    host: Optional[str] = Field(default=None)
    port: Optional[int] = Field(default=None)
    database: Optional[str] = Field(default=None)
    username: Optional[str] = Field(default=None)
    password: Optional[str] = Field(default=None)


class RetrySettings(BaseModel):
    """Налаштування retry."""

    max_retries: int = Field(default=3, ge=0, description="Максимум повторних спроб")
    retry_delay: float = Field(default=1.0, ge=0, description="Затримка між спробами (сек)")
    backoff_factor: float = Field(default=2.0, description="Множник для exponential backoff")
    retry_on_status: List[int] = Field(
        default_factory=lambda: [429, 500, 502, 503, 504], description="HTTP статуси для retry"
    )


class ConcurrencySettings(BaseModel):
    """Налаштування паралелізму."""

    max_concurrent_requests: int = Field(default=200, ge=1, description="Макс. одночасних запитів")
    connector_limit: int = Field(default=500, ge=1, description="Ліміт TCP з'єднань")
    connector_limit_per_host: int = Field(default=200, ge=1, description="Ліміт з'єднань на хост")
    dns_cache_ttl: int = Field(default=300, description="TTL DNS кешу (сек)")


class CrawlerSettings(BaseSettings):
    """
    Головний клас конфігурації краулера.

    """

    model_config = SettingsConfigDict(
        env_prefix="GC_",
        env_file=".env",
        env_nested_delimiter="__",
        extra="ignore",
    )
    project_name: str = Field(default="my_crawler", description="Назва проекту")
    max_depth: int = Field(default=3, ge=1, le=100, description="Максимальна глибина сканування")
    max_pages: Optional[int] = Field(
        default=100, ge=1, description="Максимум сторінок (None = без ліміту)"
    )
    request_delay: float = Field(default=0.5, ge=0, description="Затримка між запитами (сек)")
    timeout: Optional[int] = Field(default=300, ge=1, description="Загальний таймаут (сек)")
    same_domain: bool = Field(default=True, description="Сканувати тільки поточний домен")
    follow_links: bool = Field(default=True, description="Переходити за посиланнями")
    allowed_domains: List[str] = Field(default_factory=list, description="Дозволені домени")
    blocked_domains: List[str] = Field(default_factory=list, description="Заблоковані домени")
    blocked_paths: List[str] = Field(
        default_factory=lambda: ["/admin", "/login", "/logout", "/wp-admin"],
        description="Заблоковані шляхи (regex)",
    )
    driver: DriverSettings = Field(
        default_factory=DriverSettings, description="Налаштування драйвера"
    )
    storage: StorageSettings = Field(
        default_factory=StorageSettings, description="Налаштування storage"
    )
    retry: RetrySettings = Field(default_factory=RetrySettings, description="Налаштування retry")
    concurrency: ConcurrencySettings = Field(
        default_factory=ConcurrencySettings, description="Налаштування паралелізму"
    )
    respect_robots_txt: bool = Field(default=True, description="Дотримуватись robots.txt")
    extract_metadata: bool = Field(default=True, description="Витягувати метадані (title, h1, etc)")
    calculate_content_hash: bool = Field(default=True, description="Обчислювати hash контенту")
    edge_strategy: str = Field(
        default="all",
        description="Стратегія створення edges: all, new_only, max_in_degree, deeper_only",
    )
    log_level: str = Field(default="INFO", description="Рівень логування")
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s", description="Формат логів"
    )
    node_class: Optional[str] = Field(
        default=None, description="Шлях до кастомного Node класу (e.g., 'nodes.JobNode')"
    )
    plugins: List[str] = Field(
        default_factory=list,
        description="Список плагінів для завантаження (e.g., ['plugins.MetadataPlugin'])",
    )
    url_rules: List[Dict[str, Any]] = Field(
        default_factory=list, description="Правила для URL (pattern, priority, should_scan, etc)"
    )

    @classmethod
    def from_file(cls, path: Union[str, Path]) -> "CrawlerSettings":
        """
        Завантажує налаштування з файлу.

        Підтримує: YAML, JSON

        Args:
            path: Шлях до файлу налаштувань

        Returns:
            CrawlerSettings instance

        Example:
            >>> settings = CrawlerSettings.from_file("settings.yaml")
        """
        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(f"Settings file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            if path.suffix in (".yaml", ".yml"):
                try:
                    import yaml

                    data = yaml.safe_load(f)
                except ImportError:
                    raise ImportError(
                        "PyYAML required for YAML config. Install: pip install pyyaml"
                    )
            elif path.suffix == ".json":
                data = json.load(f)
            else:
                raise ValueError(
                    f"Unsupported file format: {path.suffix}. Use .yaml, .yml, or .json"
                )

        return cls(**data)

    def to_file(self, path: Union[str, Path]) -> None:
        """
        Зберігає налаштування у файл.

        Args:
            path: Шлях для збереження
        """
        path = Path(path)

        data = self.model_dump()

        with open(path, "w", encoding="utf-8") as f:
            if path.suffix in (".yaml", ".yml"):
                try:
                    import yaml

                    yaml.dump(
                        data, f, default_flow_style=False, allow_unicode=True, sort_keys=False
                    )
                except ImportError:
                    raise ImportError("PyYAML required. Install: pip install pyyaml")
            else:
                json.dump(data, f, indent=2, ensure_ascii=False)

    def to_crawl_kwargs(self) -> Dict[str, Any]:
        """
        Конвертує налаштування в kwargs для gc.crawl().

        Returns:
            Dict з параметрами для crawl()

        Example:
            >>> settings = CrawlerSettings(max_depth=5)
            >>> graph = gc.crawl("https://example.com", **settings.to_crawl_kwargs())
        """
        from graph_crawler.domain.value_objects.models import URLRule

        kwargs = {
            "max_depth": self.max_depth,
            "max_pages": self.max_pages,
            "same_domain": self.same_domain,
            "timeout": self.timeout,
            "request_delay": self.request_delay,
            "follow_links": self.follow_links,
            "edge_strategy": self.edge_strategy,
            "driver": self.driver.type,
            "driver_config": {
                "user_agent": self.driver.user_agent,
                "headers": self.driver.headers,
                "headless": self.driver.headless,
                "viewport_width": self.driver.viewport_width,
                "viewport_height": self.driver.viewport_height,
            },
            "storage": self.storage.type,
            "storage_config": {
                "path": self.storage.path,
            },
        }

        # URL Rules
        if self.url_rules:
            kwargs["url_rules"] = [URLRule(**rule) for rule in self.url_rules]

        return kwargs

    def get_node_class(self):
        """
        Завантажує кастомний Node клас.

        Returns:
            Node class або None
        """
        if not self.node_class:
            return None

        import importlib

        module_path, class_name = self.node_class.rsplit(".", 1)
        module = importlib.import_module(module_path)
        return getattr(module, class_name)

    def get_plugins(self) -> list:
        """
        Завантажує плагіни.

        Returns:
            Список інстансів плагінів
        """
        if not self.plugins:
            return []

        import importlib

        loaded_plugins = []
        for plugin_path in self.plugins:
            module_path, class_name = plugin_path.rsplit(".", 1)
            module = importlib.import_module(module_path)
            plugin_class = getattr(module, class_name)
            loaded_plugins.append(plugin_class())

        return loaded_plugins


# Експортуємо для зручності
__all__ = [
    "CrawlerSettings",
    "DriverSettings",
    "StorageSettings",
    "RetrySettings",
    "ConcurrencySettings",
]
