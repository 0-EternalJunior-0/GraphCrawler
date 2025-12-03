"""Базові класи для Node плагінів.

Node плагіни виконуються на різних етапах життєвого циклу ноди:
- ЕТАП 1 (URL): ON_NODE_CREATED
- ЕТАП 2 (HTML): ON_BEFORE_SCAN, ON_HTML_PARSED, ON_AFTER_SCAN
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class NodePluginType(str, Enum):
    """Типи плагінів для обробки Node."""

    # ЕТАП 1: URL_STAGE (при створенні ноди)
    ON_NODE_CREATED = "on_node_created"  # Після створення ноди

    # ЕТАП 2: HTML_STAGE (при скануванні)
    ON_BEFORE_SCAN = "on_before_scan"  # Перед скануванням
    ON_HTML_PARSED = "on_html_parsed"  # Після парсингу HTML в дерево
    ON_AFTER_SCAN = "on_after_scan"  # Після сканування

    # ЕТАП 3: CRAWL_STAGE (життєвий цикл краулінгу) - Alpha 2.0
    BEFORE_CRAWL = "before_crawl"  # Перед початком краулінгу
    AFTER_CRAWL = "after_crawl"  # Після завершення краулінгу


class NodePluginContext(BaseModel):
    """
    Контекст для Node плагінів (Pydantic BaseModel).

    Замінено @dataclass на Pydantic BaseModel для сумісності з архітектурою проекту.

    Переваги Pydantic:
    - Автоматична валідація даних
    - Сумісність з іншими Pydantic моделями проекту
    - Серіалізація через model_dump()

    ЖИТТЄВИЙ ЦИКЛ ПОЛІВ:

    ЕТАП 1 (URL_STAGE):
        Доступно: url, depth, should_scan, can_create_edges, node
         Недоступно: html, html_tree, parser (ще не створені)
         metadata, user_data - порожні dict

    ЕТАП 2 (HTML_STAGE):
         INPUT (початок process_html):
           * html - HTML string
           * html_tree - DOM після парсингу
           * parser - Tree adapter
           * metadata - порожній dict (заповнюється плагінами)
           * user_data - порожній dict (заповнюється плагінами)

         OUTPUT (після плагінів):
           * metadata - заповнений метаданими (title, h1, description)
           * user_data - заповнений даними від плагінів
           * extracted_links - список URL
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Основні дані
    node: Any  # Node об'єкт

    # Етап 1: URL_STAGE (завжди доступні)
    url: str
    depth: int
    should_scan: bool
    can_create_edges: bool

    # Етап 2: HTML_STAGE INPUT (доступні тільки після парсингу HTML)
    html: Optional[str] = None
    html_tree: Optional[Any] = (
        None  # Any замість BeautifulSoup (підтримка різних парсерів)
    )
    parser: Optional[Any] = None  # Tree adapter/parser instance

    # Етап 2: HTML_STAGE OUTPUT (заповнюються плагінами)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    extracted_links: List[str] = Field(default_factory=list)

    # Додаткові дані від користувача (заповнюються плагінами)
    user_data: Dict[str, Any] = Field(default_factory=dict)

    # Флаги
    skip_link_extraction: bool = False  # Не витягувати посилання
    skip_metadata_extraction: bool = False  # Не витягувати метадані

    # ==================== LAW OF DEMETER: Методи для metadata ====================

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """
        Безпечно отримує значення з metadata.

        Args:
            key: Ключ метаданих
            default: Значення за замовчуванням

        Returns:
            Значення метаданих або default якщо ключ не знайдено
        """
        return self.metadata.get(key, default)

    def set_metadata(self, key: str, value: Any) -> None:
        """
        Встановлює значення в metadata.

        Args:
            key: Ключ метаданих
            value: Значення для збереження
        """
        self.metadata[key] = value

    def has_metadata(self, key: str) -> bool:
        """
        Перевіряє наявність ключа в metadata.

        Args:
            key: Ключ для перевірки

        Returns:
            True якщо ключ існує
        """
        return key in self.metadata

    def __repr__(self):
        return f"NodePluginContext(url={self.url}, has_html={self.html is not None}, metadata_keys={list(self.metadata.keys())})"


class BaseNodePlugin(ABC):
    """
    Базовий клас для Node плагінів.

    Node плагіни виконуються на різних етапах життєвого циклу ноди:
    - ЕТАП 1 (URL): ON_NODE_CREATED
    - ЕТАП 2 (HTML): ON_BEFORE_SCAN, ON_HTML_PARSED, ON_AFTER_SCAN

    Приклад:
        class MyPlugin(BaseNodePlugin):
            @property
            def plugin_type(self):
                 "Повертає Plugin Type."
                return NodePluginType.ON_HTML_PARSED

            def execute(self, context: NodePluginContext) -> NodePluginContext:
                # Ваша логіка
                if context.html_tree:
                    context.user_data['my_data'] = 'value'
                return context
    """

    def __init__(self, config: Dict[str, Any] = None):
        """Ініціалізує NodePluginType."""
        self.config = config or {}
        self.enabled = self.config.get("enabled", True)

    @property
    @abstractmethod
    def plugin_type(self) -> NodePluginType:
        """Тип плагіну (етап життєвого циклу)."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Назва плагіну."""
        pass

    @abstractmethod
    def execute(self, context: NodePluginContext) -> NodePluginContext:
        """
        Виконує логіку плагіну.

        Args:
            context: Контекст з даними ноди

        Returns:
            Оновлений контекст
        """
        pass

    def setup(self):
        """Ініціалізація плагіну."""
        pass

    def teardown(self):
        """Очищення ресурсів."""
        pass

    def __repr__(self):
        return f"{self.__class__.__name__}(type={self.plugin_type.value}, enabled={self.enabled})"


class NodePluginManager:
    """
    Async менеджер для управління Node плагінами.

    Координує виконання плагінів на різних етапах життєвого циклу.
    Метод execute() є async для підтримки async плагінів.
    """

    def __init__(self, event_bus=None):
        """
        Ініціалізує NodePluginManager.

        Args:
            event_bus: EventBus для публікації подій (опціонально, Alpha 2.0)
        """
        self.plugins: Dict[NodePluginType, list[BaseNodePlugin]] = {
            plugin_type: [] for plugin_type in NodePluginType
        }
        self.event_bus = event_bus

    def register(self, plugin: BaseNodePlugin):
        """Реєструє плагін."""
        if plugin.enabled:
            self.plugins[plugin.plugin_type].append(plugin)
            # Викликаємо setup() тільки якщо метод існує
            if hasattr(plugin, "setup") and callable(getattr(plugin, "setup")):
                plugin.setup()

    async def execute(
        self, plugin_type: NodePluginType, context: NodePluginContext
    ) -> NodePluginContext:
        """
        Async виконує всі плагіни вказаного типу .

        Плагіни виконуються послідовно, кожен отримує context від попереднього.
        Підтримує як sync, так і async плагіни.

        Args:
            plugin_type: Тип плагінів для виконання
            context: Контекст з даними

        Returns:
            Оновлений контекст
        """
        import asyncio
        import inspect

        for plugin in self.plugins.get(plugin_type, []):
            if plugin.enabled:
                try:
                    # Подія перед виконанням плагіна (Alpha 2.0)
                    if self.event_bus:
                        from graph_crawler.domain.events import CrawlerEvent, EventType

                        self.event_bus.publish(
                            CrawlerEvent.create(
                                EventType.PLUGIN_STARTED,
                                data={
                                    "plugin_name": plugin.name,
                                    "plugin_type": plugin_type.value,
                                    "url": (
                                        context.url if hasattr(context, "url") else None
                                    ),
                                },
                            )
                        )

                    result = plugin.execute(context)
                    if inspect.isawaitable(result):
                        context = await result
                    else:
                        context = result

                    # Подія після успішного виконання (Alpha 2.0)
                    if self.event_bus:
                        from graph_crawler.domain.events import CrawlerEvent, EventType

                        self.event_bus.publish(
                            CrawlerEvent.create(
                                EventType.PLUGIN_COMPLETED,
                                data={
                                    "plugin_name": plugin.name,
                                    "plugin_type": plugin_type.value,
                                    "url": (
                                        context.url if hasattr(context, "url") else None
                                    ),
                                },
                            )
                        )

                except Exception as e:
                    # Логуємо помилку, але продовжуємо
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.error(f"Plugin {plugin.name} error: {e}", exc_info=True)

                    # Подія про помилку (Alpha 2.0)
                    if self.event_bus:
                        from graph_crawler.domain.events import CrawlerEvent, EventType

                        self.event_bus.publish(
                            CrawlerEvent.create(
                                EventType.PLUGIN_FAILED,
                                data={
                                    "plugin_name": plugin.name,
                                    "plugin_type": plugin_type.value,
                                    "url": (
                                        context.url if hasattr(context, "url") else None
                                    ),
                                    "error": str(e),
                                    "error_type": type(e).__name__,
                                },
                            )
                        )
        return context

    def has_plugins(self, plugin_type: NodePluginType) -> bool:
        """Перевіряє чи є плагіни вказаного типу."""
        return len(self.plugins.get(plugin_type, [])) > 0

    def execute_sync(
        self, plugin_type: NodePluginType, context: NodePluginContext
    ) -> NodePluginContext:
        """
        Синхронна версія execute() для виклику з sync коду.

        ВАЖЛИВО: Викликає тільки sync плагіни! Async плагіни будуть ігноровані
        з попередженням у логах.

        Args:
            plugin_type: Тип плагінів для виконання
            context: Контекст з даними

        Returns:
            Оновлений контекст
        """
        import inspect
        import logging

        logger = logging.getLogger(__name__)

        for plugin in self.plugins.get(plugin_type, []):
            if plugin.enabled:
                try:
                    result = plugin.execute(context)
                    if inspect.isawaitable(result):
                        # Async плагін в sync контексті - ігноруємо з попередженням
                        logger.warning(
                            f"Plugin {plugin.name} is async but called in sync context. "
                            f"Skipping. Use execute() for async plugins."
                        )
                        continue
                    context = result
                except Exception as e:
                    logger.error(f"Plugin {plugin.name} failed: {e}")
        return context

    async def teardown_all(self):
        """Async закриває всі плагіни ."""
        import inspect

        for plugins_list in self.plugins.values():
            for plugin in plugins_list:
                teardown = plugin.teardown
                if callable(teardown):
                    result = teardown()
                    if inspect.isawaitable(result):
                        await result

    def __repr__(self):
        total = sum(len(plugins) for plugins in self.plugins.values())
        return f"NodePluginManager(total_plugins={total})"
