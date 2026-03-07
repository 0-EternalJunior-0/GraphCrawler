"""
Registries for extensible validation and configuration.

Це модуль реалізує Registry Pattern для OCP (Open/Closed Principle).
Дозволяє додавати нові режими, стратегії без зміни коду валідаторів.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type


class BaseRegistry(ABC):
    """Базовий клас для всіх реєстрів."""

    _registry: Dict[str, Any] = {}

    @classmethod
    @abstractmethod
    def get_registry_name(cls) -> str:
        """Повертає назву реєстру для логування."""
        pass

    @classmethod
    def register(cls, name: str, item: Any) -> None:
        """
        Реєструє елемент в реєстрі.

        Args:
            name: Назва елемента (ключ)
            item: Елемент для реєстрації (клас, функція, значення)

        Raises:
            ValueError: Якщо елемент з такою назвою вже зареєстровано
        """
        name_lower = name.lower()
        if name_lower in cls._registry:
            raise ValueError(
                f"{cls.get_registry_name()}: Item '{name}' is already registered"
            )
        cls._registry[name_lower] = item

    @classmethod
    def unregister(cls, name: str) -> None:
        """
        Видаляє елемент з реєстру.

        Args:
            name: Назва елемента для видалення
        """
        name_lower = name.lower()
        if name_lower in cls._registry:
            del cls._registry[name_lower]

    @classmethod
    def get(cls, name: str) -> Optional[Any]:
        """
        Отримує елемент з реєстру.

        Args:
            name: Назва елемента

        Returns:
            Елемент або None якщо не знайдено
        """
        return cls._registry.get(name.lower())

    @classmethod
    def get_all_names(cls) -> List[str]:
        """
        Повертає список всіх зареєстрованих назв.

        Returns:
            Відсортований список назв
        """
        return sorted(cls._registry.keys())

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """
        Перевіряє чи елемент зареєстровано.

        Args:
            name: Назва елемента

        Returns:
            True якщо зареєстровано, False інакше
        """
        return name.lower() in cls._registry

    @classmethod
    def clear(cls) -> None:
        """Очищає весь реєстр (використовується в тестах)."""
        cls._registry.clear()


class CrawlModeRegistry(BaseRegistry):
    """
    Реєстр режимів краулінгу.

    Дозволяє додавати нові режими без зміни валідатора в configs.py.

    Example:
        >>> from graph_crawler.application.use_cases.crawling.spider import SequentialSpider
        >>> CrawlModeRegistry.register("sequential", SequentialSpider)
        >>> modes = CrawlModeRegistry.get_all_names()
        >>> print(modes)
        ['sequential', 'multiprocessing', 'celery']
    """

    _registry: Dict[str, Type] = {}

    @classmethod
    def get_registry_name(cls) -> str:
        return "CrawlModeRegistry"


class ChangeDetectionStrategyRegistry(BaseRegistry):
    """
    Реєстр стратегій детекції змін.

    Дозволяє додавати нові стратегії без зміни валідатора.

    Example:
        >>> from graph_crawler.domain.entities.strategies import HashStrategy
        >>> ChangeDetectionStrategyRegistry.register("hash", HashStrategy)
        >>> strategies = ChangeDetectionStrategyRegistry.get_all_names()
        >>> print(strategies)
        ['hash', 'metadata']
    """

    _registry: Dict[str, Type] = {}

    @classmethod
    def get_registry_name(cls) -> str:
        return "ChangeDetectionStrategyRegistry"


class MergeStrategyRegistry(BaseRegistry):
    """
    Реєстр стратегій merge для Graph.union().

    Дозволяє додавати нові стратегії merge без зміни валідатора.

    Example:
        >>> from graph_crawler.domain.entities.merge_strategies import FirstStrategy
        >>> MergeStrategyRegistry.register("first", FirstStrategy)
        >>> strategies = MergeStrategyRegistry.get_all_names()
        >>> print(strategies)
        ['first', 'last', 'merge', 'newest', 'oldest', 'custom']
    """

    _registry: Dict[str, Type] = {}

    @classmethod
    def get_registry_name(cls) -> str:
        return "MergeStrategyRegistry"


# ІНІЦІАЛІЗАЦІЯ РЕЄСТРІВ (default values)
#
# Domain layer only defines Registry base classes.
# Application layer calls register() during bootstrap.
# See: graph_crawler/application/__init__.py for bootstrap example
#
# IMPORTANT: DO NOT import from Application/Infrastructure layers here!


def _init_default_registries():
    """
    Initialize registries with placeholder factories.
    
    in Application layer bootstrap, not here.
    
    This function only registers placeholder factories that raise helpful errors
    if user tries to use uninitialized registry entries.
    """
    # Crawl Modes (режими краулінгу)
    # Actual spiders are registered in application/__init__.py
    pass

    # Change Detection Strategies
    # Actual strategies are registered in application/__init__.py
    pass

    # Merge Strategies
    # Actual strategies are registered in application/__init__.py
    pass


# Ініціалізуємо реєстри при імпорті
_init_default_registries()

# HELPER FUNCTIONS


def register_crawl_mode(name: str, spider_class: Type) -> None:
    """
    Helper функція для реєстрації режиму краулінгу.

    Args:
        name: Назва режиму (напр. "distributed")
        spider_class: Клас spider для цього режиму

    Example:
        >>> from graph_crawler.domain.entities.registries import register_crawl_mode
        >>> register_crawl_mode("distributed", DistributedSpider)
    """
    CrawlModeRegistry.register(name, spider_class)


def register_change_detection_strategy(name: str, strategy_class: Type) -> None:
    """
    Helper функція для реєстрації стратегії детекції змін.

    Args:
        name: Назва стратегії (напр. "content_diff")
        strategy_class: Клас стратегії

    Example:
        >>> register_change_detection_strategy("content_diff", ContentDiffStrategy)
    """
    ChangeDetectionStrategyRegistry.register(name, strategy_class)


def register_merge_strategy(name: str, strategy_class: Type) -> None:
    """
    Helper функція для реєстрації merge стратегії.

    Args:
        name: Назва стратегії (напр. "smart_merge")
        strategy_class: Клас стратегії

    Example:
        >>> register_merge_strategy("smart_merge", SmartMergeStrategy)
    """
    MergeStrategyRegistry.register(name, strategy_class)
