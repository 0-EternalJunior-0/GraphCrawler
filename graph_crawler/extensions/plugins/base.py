"""Базовий клас для всіх плагінів."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class PluginType(str, Enum):
    """Типи плагінів."""

    PRE_REQUEST = "pre_request"  # Перед запитом
    POST_REQUEST = "post_request"  # Після запиту
    PRE_PARSE = "pre_parse"  # Перед парсингом
    POST_PARSE = "post_parse"  # Після парсингу
    ON_ERROR = "on_error"  # При помилці


@dataclass
class PluginContext:
    """
    Контекст для плагінів.

    Передається між плагінами для обміну даними.
    """

    url: str
    html: Optional[str] = None
    node: Optional[Any] = None  # Node об'єкт
    driver: Optional[Any] = None  # Driver об'єкт
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[Exception] = None

    # Додаткові дані від плагінів
    plugin_data: Dict[str, Any] = field(default_factory=dict)


class BasePlugin(ABC):
    """
    Базовий клас для всіх плагінів.

    Плагіни дозволяють розширювати функціональність краулера:
    - Скріншоти
    - Прокрутка сторінки
    - Проксі ротація
    - Retry логіка
    - Кешування
    - тощо

    Приклад:
        class MyPlugin(BasePlugin):
            def execute(self, context: PluginContext) -> PluginContext:
                # Ваша логіка
                context.plugin_data['my_data'] = 'value'
                return context
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.enabled = True

    @property
    @abstractmethod
    def plugin_type(self) -> PluginType:
        """Тип плагіну."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Назва плагіну."""
        pass

    @abstractmethod
    def execute(self, context: PluginContext) -> PluginContext:
        """
        Виконує логіку плагіну.

        Args:
            context: Контекст з даними

        Returns:
            Оновлений контекст
        """
        pass

    def setup(self):
        """Ініціалізація плагіну."""
        pass

    def teardown(self):
        """Очищення ресурсів плагіну."""
        pass

    def __repr__(self):
        return f"{self.__class__.__name__}(enabled={self.enabled})"


class PluginManager:
    """
    Менеджер для управління плагінами.

    Координує виконання плагінів в правильному порядку.
    """

    def __init__(self):
        self.plugins: Dict[PluginType, list[BasePlugin]] = {
            plugin_type: [] for plugin_type in PluginType
        }

    def register(self, plugin: BasePlugin):
        """Реєструє плагін."""
        if plugin.enabled:
            self.plugins[plugin.plugin_type].append(plugin)
            plugin.setup()

    def execute(self, plugin_type: PluginType, context: PluginContext) -> PluginContext:
        """
        Виконує всі плагіни вказаного типу.

        Плагіни виконуються послідовно, кожен отримує context від попереднього.
        """
        for plugin in self.plugins.get(plugin_type, []):
            if plugin.enabled:
                try:
                    context = plugin.execute(context)
                except Exception as e:
                    print(f"Plugin {plugin.name} error: {e}")
                    context.error = e
        return context

    def teardown_all(self):
        """Закриває всі плагіни."""
        for plugins_list in self.plugins.values():
            for plugin in plugins_list:
                plugin.teardown()
