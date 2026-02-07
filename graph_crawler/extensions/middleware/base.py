"""Middleware Pattern - базовий клас ."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, Optional

from graph_crawler.shared.utils.event_publisher_mixin import EventPublisherMixin

if TYPE_CHECKING:
    from graph_crawler.domain.events import EventBus


class MiddlewareType(str, Enum):
    """Типи middleware."""

    PRE_REQUEST = "pre_request"  # Перед запитом
    POST_REQUEST = "post_request"  # Після запиту
    PRE_PARSE = "pre_parse"  # Перед парсингом
    POST_PARSE = "post_parse"  # Після парсингу
    ON_ERROR = "on_error"  # При помилці


@dataclass
class MiddlewareContext:
    """
    Контекст для middleware.

    Передається між middleware для обміну даними.
    """

    url: str
    html: Optional[str] = None
    status_code: Optional[int] = None
    headers: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[Exception] = None
    response: Optional[Any] = None  # Відповідь від драйвера

    # Дані від middleware
    middleware_data: Dict[str, Any] = field(default_factory=dict)

    # Флаги
    should_retry: bool = False
    skip_request: bool = False  # Для cache hit

    def get_meta_value(self, key: str, default: Any = None) -> Any:
        """
        Отримати значення з metadata за ключем (Law of Demeter wrapper).

        Args:
            key: Ключ метаданих
            default: Значення за замовчуванням

        Returns:
            Значення метаданих або default
        """
        return self.metadata.get(key, default)


class BaseMiddleware(EventPublisherMixin, ABC):
    """
        Async-First базовий клас для всіх middleware .

    Всі методи process() тепер async для неблокуючого виконання.
        Використовує asyncio.sleep() замість time.sleep().

        Middleware Pattern дозволяє обробляти request/response
        через ланцюжок обробників.

        Приклади middleware:
        - Logging - логування запитів
        - Retry - повтор при помилці
        - Cache - кешування відповідей
        - Proxy - ротація проксі
        - RateLimiting - обмеження частоти запитів

        Args:
            config: Конфігурація middleware
            event_bus: Event bus для публікації подій (опціонально, DI)
    """

    def __init__(
        self, config: Dict[str, Any] = None, event_bus: Optional["EventBus"] = None
    ):
        self.config = config or {}
        self.event_bus = event_bus
        self.enabled = True

    @property
    @abstractmethod
    def middleware_type(self) -> MiddlewareType:
        """Тип middleware."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Назва middleware."""
        pass

    @abstractmethod
    async def process(self, context: MiddlewareContext) -> MiddlewareContext:
        """
        Async обробляє контекст .

        Args:
            context: Контекст з даними

        Returns:
            Оновлений контекст
        """
        pass

    async def setup(self):
        """Async ініціалізація middleware."""
        pass

    async def teardown(self):
        """Async очищення ресурсів middleware."""
        pass

    def __repr__(self):
        return f"{self.__class__.__name__}(enabled={self.enabled})"
