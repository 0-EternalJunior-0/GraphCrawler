"""Базовий клас для driver-specific плагінів.

Нова архітектура:
- Кожен драйвер має свої етапи (stages)
- Плагіни підписуються на етапи драйвера
- Плагіни можуть створювати свої події
- Плагіни отримують доступ до внутрішніх об'єктів драйвера через контекст
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from graph_crawler.infrastructure.transport.context import EventPriority

logger = logging.getLogger(__name__)


class BaseDriverPlugin(ABC):
    """
    Базовий клас для всіх driver-specific плагінів.

    """

    def __init__(
        self, config: Optional[Dict[str, Any]] = None, priority: int = EventPriority.NORMAL
    ):
        """
        Ініціалізація плагіна.

        Args:
            config: Конфігурація плагіна
            priority: Пріоритет виконання (1-100, менше = вище пріоритет)
        """
        self._config = config or {}
        self.priority = priority
        self.enabled = True
        self._stats = {"executions": 0, "errors": 0, "total_time": 0.0}

    @property
    def config(self) -> Dict[str, Any]:
        """Повертає конфігурацію плагіна."""
        return self._config

    @staticmethod
    def create_config(**kwargs) -> Dict[str, Any]:
        """
        Створює конфігурацію для плагіна.

        Це статичний метод для зручного створення конфігів.
        Підкласи можуть перевизначити для власних параметрів.

        Example:
            config = MyPlugin.create_config(param1="value1", param2=123)
            plugin = MyPlugin(config)

        Args:
            **kwargs: Параметри конфігурації

        Returns:
            Dict з конфігурацією
        """
        return kwargs

    # Backward compatibility alias - для виклику як Plugin.config(...)
    # Примітка: не плутати з @property config який повертає _config
    @staticmethod
    def make_config(**kwargs) -> Dict[str, Any]:
        """Alias для create_config() для backward compatibility."""
        return kwargs

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Унікальна назва плагіна.

        Returns:
            Назва плагіна (наприклад, 'stealth', 'captcha_solver')
        """
        pass

    def get_hooks(self) -> List[str]:
        """
        Повертає список етапів (hooks) на які підписується плагін.

        Етапи визначаються драйвером (наприклад, 'navigation_completed', 'content_ready').

        Returns:
            Список назв етапів
        """
        return []

    def get_events(self) -> List[str]:
        """
        Повертає список подій від інших плагінів на які підписується плагін.

        Події створюються плагінами (наприклад, 'captcha_detected', 'cloudflare_detected').

        Returns:
            Список назв подій
        """
        return []

    def setup(self):
        """
        Ініціалізація плагіна при реєстрації.

        Викликається один раз при додаванні плагіна в драйвер.
        """
        logger.info("Plugin '%s' initialized (priority=%s)", self.name, self.priority)

    def teardown(self):
        """
        Очищення ресурсів плагіна.

        Викликається при закритті драйвера.
        """
        logger.debug("Plugin '%s' teardown", self.name)

    def get_stats(self) -> Dict[str, Any]:
        """
        Повертає статистику роботи плагіна.

        Returns:
            Словник зі статистикою
        """
        return {
            "name": self.name,
            "enabled": self.enabled,
            "priority": self.priority,
            "executions": self._stats["executions"],
            "errors": self._stats["errors"],
            "avg_time": (
                self._stats["total_time"] / self._stats["executions"]
                if self._stats["executions"] > 0
                else 0.0
            ),
        }

    def reset_stats(self):
        """Скидає статистику."""
        self._stats = {"executions": 0, "errors": 0, "total_time": 0.0}

    def _record_execution(self, duration: float, error: bool = False):
        """Записує статистику виконання."""
        self._stats["executions"] += 1
        self._stats["total_time"] += duration
        if error:
            self._stats["errors"] += 1

    def __repr__(self):
        return f"{self.__class__.__name__}(name='{self.name}', priority={self.priority}, enabled={self.enabled})"
