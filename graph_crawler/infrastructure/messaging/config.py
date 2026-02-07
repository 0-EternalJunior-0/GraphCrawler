"""Конфігурація для distributed crawling через YAML.

Цей модуль надає Pydantic схеми для налаштування розподіленого краулінгу.
"""

from typing import List, Literal, Optional, Union

from pydantic import BaseModel, Field, model_validator

from graph_crawler.shared.constants import (
    DEFAULT_REDIS_HOST,
    DEFAULT_REDIS_PORT,
    DEFAULT_REDIS_DB,
    DEFAULT_CELERY_TASK_TIME_LIMIT,
    DEFAULT_CELERY_WORKERS,
    MAX_PAGES_DEFAULT,
    MAX_API_WORKERS,
)


class DistributedBrokerConfig(BaseModel):
    """Конфігурація Redis/RabbitMQ брокера для Celery.

    Attributes:
        type: Тип брокера ('redis' або 'rabbitmq')
        host: Адреса сервера брокера
        port: Порт брокера
        db: Номер бази даних (тільки для Redis)
        password: Пароль для підключення (опціонально)

    Example:
        broker = DistributedBrokerConfig(
            type="redis",
            host="server11.example.com",
            port=DEFAULT_REDIS_PORT,
            db=0
        )
    """

    type: Literal["redis", "rabbitmq"] = "redis"
    host: str = DEFAULT_REDIS_HOST
    port: int = DEFAULT_REDIS_PORT
    db: int = DEFAULT_REDIS_DB
    password: Optional[str] = None

    @property
    def url(self) -> str:
        """Генерує URL для Celery.

        Returns:
            Connection string для Celery broker
        """
        if self.type == "redis":
            auth = f":{self.password}@" if self.password else ""
            return f"redis://{auth}{self.host}:{self.port}/{self.db}"
        else:
            auth = f":{self.password}@" if self.password else ""
            return f"amqp://{auth}{self.host}:{self.port}//"


class DistributedDatabaseConfig(BaseModel):
    """Конфігурація БД для збереження результатів.

    Підтримує три типи:
    - 'memory': Зберігання в RAM (для малих сайтів <1000 сторінок)
    - 'mongodb': MongoDB база даних
    - 'postgresql': PostgreSQL база даних

    Attributes:
        type: Тип БД ('memory', 'mongodb' або 'postgresql')
        host: Адреса сервера БД (не потрібно для memory)
        port: Порт БД (не потрібно для memory)
        database: Назва бази даних (не потрібно для memory)
        username: Ім'я користувача (опціонально)
        password: Пароль (опціонально)

    Example:
        # Memory storage (локальне)
        db = DistributedDatabaseConfig(type="memory")

        # MongoDB
        db = DistributedDatabaseConfig(
            type="mongodb",
            host="server12.example.com",
            port=27017,
            database="crawler_results"
        )
    """

    type: Literal["memory", "mongodb", "postgresql"]
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None

    @model_validator(mode="after")
    def validate_database_config(self):
        """Валідація конфігурації залежно від типу."""
        if self.type in ("mongodb", "postgresql"):
            if not self.host:
                raise ValueError(f"'host' is required for {self.type}")
            if not self.port:
                raise ValueError(f"'port' is required for {self.type}")
            if not self.database:
                raise ValueError(f"'database' is required for {self.type}")
        return self

    @property
    def connection_string(self) -> Optional[str]:
        """Генерує connection string.

        Returns:
            Connection string для БД або None для memory
        """
        if self.type == "memory":
            return None
        elif self.type == "mongodb":
            auth = f"{self.username}:{self.password}@" if self.username else ""
            return f"mongodb://{auth}{self.host}:{self.port}/"
        else:
            auth = f"{self.username}:{self.password}@" if self.username else ""
            return f"postgresql://{auth}{self.host}:{self.port}/{self.database}"


class DistributedProxyConfig(BaseModel):
    """Конфігурація proxy rotation.

    Attributes:
        enabled: Чи використовувати proxy
        type: Тип джерела proxy ('file' або 'api')
        source: Шлях до файлу або API URL

    Example:
        proxy = DistributedProxyConfig(
            enabled=True,
            type="file",
            source="./proxies.txt"
        )
    """

    enabled: bool = False
    type: Literal["file", "api"] = "file"
    source: str = ""


class CrawlTaskConfig(BaseModel):
    """Конфігурація задачі краулінгу.

    Attributes:
        urls: Список початкових URL для краулінгу
        max_depth: Максимальна глибина краулінгу
        max_pages: Максимальна кількість сторінок (опціонально)
        extractors: Shortcut aliases для стандартних extractors ('phones', 'emails', 'prices')
        plugins: Список плагінів як повні import paths

    Example:
        # Використання aliases (зручно)
        task = CrawlTaskConfig(
            urls=["https://example.com"],
            extractors=["phones", "emails"]
        )

        # Використання повних import paths (гнучко)
        task = CrawlTaskConfig(
            urls=["https://example.com"],
            CustomPlugins=[
                "graph_crawler.CustomPlugins.node.extractors.PhoneExtractorPlugin",
                "myapp.CustomPlugins.CustomPlugin"
            ]
        )
    """

    urls: List[str]
    max_depth: int = 3
    max_pages: Optional[int] = MAX_PAGES_DEFAULT
    extractors: List[Literal["phones", "emails", "prices"]] = []  # Shortcut aliases
    plugins: List[str] = []  # Повні import paths (має пріоритет)


class DistributedCrawlConfig(BaseModel):
    """Головна конфігурація distributed crawling.

    Attributes:
        broker: Конфігурація Celery брокера
        database: Конфігурація БД для результатів
        proxy: Конфігурація proxy (опціонально)
        crawl_task: Конфігурація задачі краулінгу
        workers: Кількість Celery workers
        task_time_limit: Ліміт часу виконання задачі (секунди)
        worker_prefetch_multiplier: Префетч множник для workers

    Example:
        # З memory storage (локально)
        config = DistributedCrawlConfig(
            broker=DistributedBrokerConfig(host="server.com"),
            database=DistributedDatabaseConfig(type="memory"),
            crawl_task=CrawlTaskConfig(urls=["https://example.com"])
        )

        # З MongoDB
        config = DistributedCrawlConfig(
            broker=DistributedBrokerConfig(...),
            database=DistributedDatabaseConfig(
                type="mongodb",
                host="localhost",
                port=27017,
                database="results"
            ),
            crawl_task=CrawlTaskConfig(...),
            workers=10
        )
    """

    broker: DistributedBrokerConfig
    database: DistributedDatabaseConfig
    proxy: Optional[DistributedProxyConfig] = None
    crawl_task: CrawlTaskConfig

    # Celery settings
    workers: int = Field(default=DEFAULT_CELERY_WORKERS, ge=1, le=MAX_API_WORKERS)
    task_time_limit: int = DEFAULT_CELERY_TASK_TIME_LIMIT
    worker_prefetch_multiplier: int = 4


def load_config(yaml_path: str) -> DistributedCrawlConfig:
    """Завантажити конфіг з YAML файлу.

    Args:
        yaml_path: Шлях до YAML файлу з конфігурацією

    Returns:
        DistributedCrawlConfig об'єкт

    Raises:
        FileNotFoundError: Якщо файл не знайдено
        yaml.YAMLError: Якщо помилка парсингу YAML
        pydantic.ValidationError: Якщо некоректна конфігурація

    Example:
        config = load_config("config.yaml")
        package_crawler = EasyDistributedCrawler(config)
    """
    from pathlib import Path

    import yaml

    path = Path(yaml_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {yaml_path}")

    with open(path) as f:
        data = yaml.safe_load(f)

    return DistributedCrawlConfig(**data)
