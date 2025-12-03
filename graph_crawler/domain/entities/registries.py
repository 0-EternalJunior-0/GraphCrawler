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


# ============================================================================
# ІНІЦІАЛІЗАЦІЯ РЕЄСТРІВ (default values)
# Тепер використовується lazy factory pattern замість None
# ============================================================================


def _lazy_import_spider(mode: str):
    """
    Lazy factory для імпорту Spider класів.
    Уникає circular imports та None значень в реєстрі.
    """

    def factory():
        if mode == "sequential":
            from graph_crawler.application.use_cases.crawling.spider import GraphSpider

            return GraphSpider
        elif mode == "multiprocessing":
            from graph_crawler.application.use_cases.crawling.multiprocessing_spider import (
                MultiprocessingSpider,
            )

            return MultiprocessingSpider
        elif mode == "celery":
            from graph_crawler.application.use_cases.crawling.celery_batch_spider import (
                CeleryBatchSpider,
            )

            return CeleryBatchSpider
        else:
            raise ValueError(f"Unknown crawl mode: {mode}")

    return factory


def _lazy_import_change_strategy(strategy: str):
    """Lazy factory для стратегій детекції змін."""

    def factory():
        if strategy == "hash":
            from graph_crawler.domain.entities.strategies import HashStrategy

            return HashStrategy
        elif strategy == "metadata":
            from graph_crawler.domain.entities.strategies import MetadataStrategy

            return MetadataStrategy
        else:
            raise ValueError(f"Unknown change detection strategy: {strategy}")

    return factory


def _lazy_import_merge_strategy(strategy: str):
    """Lazy factory для merge стратегій."""

    def factory():
        from graph_crawler.domain.entities.merge_strategies import (
            CustomStrategy,
            FirstStrategy,
            LastStrategy,
            MergeStrategy,
            NewestStrategy,
            OldestStrategy,
        )

        strategies = {
            "first": FirstStrategy,
            "last": LastStrategy,
            "merge": MergeStrategy,
            "newest": NewestStrategy,
            "oldest": OldestStrategy,
            "custom": CustomStrategy,
        }
        if strategy not in strategies:
            raise ValueError(f"Unknown merge strategy: {strategy}")
        return strategies[strategy]

    return factory


def _init_default_registries():
    """
    Ініціалізує реєстри з lazy factory функціями.
    які імпортують потрібні класи тільки при використанні.
    Це вирішує circular imports та забезпечує валідні значення в реєстрі.
    """
    # Crawl Modes (режими краулінгу)
    _default_crawl_modes = ["sequential", "multiprocessing", "celery"]
    for mode in _default_crawl_modes:
        CrawlModeRegistry.register(mode, _lazy_import_spider(mode))

    # Change Detection Strategies
    _default_change_strategies = ["hash", "metadata"]
    for strategy in _default_change_strategies:
        ChangeDetectionStrategyRegistry.register(
            strategy, _lazy_import_change_strategy(strategy)
        )

    # Merge Strategies
    _default_merge_strategies = ["first", "last", "merge", "newest", "oldest", "custom"]
    for strategy in _default_merge_strategies:
        MergeStrategyRegistry.register(strategy, _lazy_import_merge_strategy(strategy))


# Ініціалізуємо реєстри при імпорті
_init_default_registries()

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


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
