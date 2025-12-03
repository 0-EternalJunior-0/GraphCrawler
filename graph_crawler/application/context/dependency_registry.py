"""DependencyRegistry - Singleton для управління залежностями.

Вирішує проблему відновлення plugin_manager, tree_parser, hash_strategy
після десеріалізації Node з JSON/SQLite.

Проблема:
    Node має non-serializable поля:
    - plugin_manager: управляє плагінами (MetadataExtractor, LinkExtractor, тощо)
    - tree_parser: парсер HTML (BeautifulSoup, lxml)
    - hash_strategy: стратегія обчислення content_hash
    
    Ці поля мають exclude=True в Pydantic, тому при серіалізації вони втрачаються.
    При завантаженні Node з storage потрібно їх відновити.

Рішення:
    DependencyRegistry - Thread-safe Singleton з дефолтними значеннями.
    При десеріалізації Node використовує значення з registry якщо не передані явно.

Приклад:
    >>> # Налаштування дефолтів (зазвичай при старті програми)
    >>> DependencyRegistry.configure(
    ...     plugin_manager=NodePluginManager(),
    ...     tree_parser=BeautifulSoupAdapter(),
    ...     hash_strategy=DefaultHashStrategy(),
    ... )
    >>>
    >>> # Тепер при завантаженні Node залежності відновлюються автоматично
    >>> graph_dto = await storage.load_graph()
    >>> context = DependencyRegistry.get_context()  # Отримати всі дефолти
    >>> graph = GraphMapper.to_domain(graph_dto, context=context)
    >>>
    >>> # Або з override для конкретного випадку
    >>> context = DependencyRegistry.get_context(
    ...     plugin_manager=custom_pm,  # Override тільки plugin_manager
    ... )
"""

import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Type

logger = logging.getLogger(__name__)


@dataclass
class DependencyConfig:
    """
    Конфігурація залежностей для Node.
    
    Зберігає factory functions замість інстансів для lazy initialization
    та підтримки різних конфігурацій.
    
    Attributes:
        plugin_manager_factory: Фабрика для створення plugin_manager
        tree_parser_factory: Фабрика для створення tree_parser  
        hash_strategy_factory: Фабрика для створення hash_strategy
        node_class: Клас Node для створення (default: Node)
        edge_class: Клас Edge для створення (default: Edge)
        default_merge_strategy: Дефолтна стратегія merge (default: 'last')
    """
    plugin_manager_factory: Optional[Callable[[], Any]] = None
    tree_parser_factory: Optional[Callable[[], Any]] = None
    hash_strategy_factory: Optional[Callable[[], Any]] = None
    node_class: Optional[Type] = None
    edge_class: Optional[Type] = None
    default_merge_strategy: str = "last"
    
    # Кешовані інстанси (lazy initialization)
    _plugin_manager_instance: Optional[Any] = field(default=None, repr=False)
    _tree_parser_instance: Optional[Any] = field(default=None, repr=False)
    _hash_strategy_instance: Optional[Any] = field(default=None, repr=False)
    
    def get_plugin_manager(self) -> Optional[Any]:
        """Отримує plugin_manager (lazy initialization)."""
        if self._plugin_manager_instance is None and self.plugin_manager_factory:
            self._plugin_manager_instance = self.plugin_manager_factory()
        return self._plugin_manager_instance
    
    def get_tree_parser(self) -> Optional[Any]:
        """Отримує tree_parser (lazy initialization)."""
        if self._tree_parser_instance is None and self.tree_parser_factory:
            self._tree_parser_instance = self.tree_parser_factory()
        return self._tree_parser_instance
    
    def get_hash_strategy(self) -> Optional[Any]:
        """Отримує hash_strategy (lazy initialization)."""
        if self._hash_strategy_instance is None and self.hash_strategy_factory:
            self._hash_strategy_instance = self.hash_strategy_factory()
        return self._hash_strategy_instance


class DependencyRegistry:
    """
    Thread-safe Singleton для управління дефолтними залежностями.
    
    Зберігає дефолтні значення для:
    - plugin_manager: для виконання плагінів на Node
    - tree_parser: для парсингу HTML
    - hash_strategy: для обчислення content_hash
    - node_class: клас Node для створення
    - edge_class: клас Edge для створення
    - default_merge_strategy: стратегія merge для union операцій
    
    Thread-safety:
    - Використовує threading.Lock для захисту від race conditions
    - Singleton pattern через __new__
    
    Приклад:
        >>> # Конфігурація при старті
        >>> DependencyRegistry.configure(
        ...     plugin_manager_factory=lambda: NodePluginManager(),
        ...     tree_parser_factory=lambda: BeautifulSoupAdapter(),
        ...     default_merge_strategy='merge',
        ... )
        >>>
        >>> # Отримання контексту для десеріалізації
        >>> context = DependencyRegistry.get_context()
        >>> graph = GraphMapper.to_domain(graph_dto, context=context)
    """
    
    _instance: Optional['DependencyRegistry'] = None
    _lock = threading.Lock()
    _config: DependencyConfig = DependencyConfig()
    
    def __new__(cls):
        """Singleton pattern з thread-safety."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Ініціалізація (виконується один раз)."""
        if getattr(self, '_initialized', False):
            return
        self._initialized = True
        logger.debug("DependencyRegistry initialized")
    
    # ==================== CLASS METHODS (основний API) ====================
    
    @classmethod
    def configure(
        cls,
        plugin_manager: Optional[Any] = None,
        plugin_manager_factory: Optional[Callable[[], Any]] = None,
        tree_parser: Optional[Any] = None,
        tree_parser_factory: Optional[Callable[[], Any]] = None,
        hash_strategy: Optional[Any] = None,
        hash_strategy_factory: Optional[Callable[[], Any]] = None,
        node_class: Optional[Type] = None,
        edge_class: Optional[Type] = None,
        default_merge_strategy: str = "last",
    ) -> None:
        """
        Конфігурує дефолтні залежності.
        
        Можна передати або готовий інстанс, або factory function.
        Factory рекомендується для lazy initialization.
        
        Args:
            plugin_manager: Готовий інстанс plugin_manager
            plugin_manager_factory: Фабрика для створення plugin_manager
            tree_parser: Готовий інстанс tree_parser
            tree_parser_factory: Фабрика для створення tree_parser
            hash_strategy: Готовий інстанс hash_strategy
            hash_strategy_factory: Фабрика для створення hash_strategy
            node_class: Клас Node для створення
            edge_class: Клас Edge для створення
            default_merge_strategy: Дефолтна стратегія merge
            
        Example:
            >>> # Через factory (рекомендовано)
            >>> DependencyRegistry.configure(
            ...     plugin_manager_factory=lambda: NodePluginManager(),
            ...     default_merge_strategy='merge',
            ... )
            >>>
            >>> # Або через готовий інстанс
            >>> pm = NodePluginManager()
            >>> DependencyRegistry.configure(plugin_manager=pm)
        """
        with cls._lock:
            # Створюємо factory з інстансу якщо передано інстанс
            pm_factory = plugin_manager_factory
            if plugin_manager is not None and pm_factory is None:
                pm_factory = lambda pm=plugin_manager: pm
                
            tp_factory = tree_parser_factory
            if tree_parser is not None and tp_factory is None:
                tp_factory = lambda tp=tree_parser: tp
                
            hs_factory = hash_strategy_factory
            if hash_strategy is not None and hs_factory is None:
                hs_factory = lambda hs=hash_strategy: hs
            
            cls._config = DependencyConfig(
                plugin_manager_factory=pm_factory,
                tree_parser_factory=tp_factory,
                hash_strategy_factory=hs_factory,
                node_class=node_class,
                edge_class=edge_class,
                default_merge_strategy=default_merge_strategy,
            )
            
            logger.info(
                f"DependencyRegistry configured: "
                f"merge_strategy={default_merge_strategy}, "
                f"node_class={node_class}, "
                f"has_plugin_manager={pm_factory is not None}"
            )
    
    @classmethod
    def get_context(
        cls,
        plugin_manager: Optional[Any] = None,
        tree_parser: Optional[Any] = None,
        hash_strategy: Optional[Any] = None,
        node_class: Optional[Type] = None,
        edge_class: Optional[Type] = None,
        default_merge_strategy: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Отримує контекст для десеріалізації з можливістю override.
        
        Повертає dict з усіма залежностями, готовий для передачі
        в GraphMapper.to_domain() або NodeMapper.to_domain().
        
        Args:
            plugin_manager: Override для plugin_manager (опціонально)
            tree_parser: Override для tree_parser (опціонально)
            hash_strategy: Override для hash_strategy (опціонально)
            node_class: Override для node_class (опціонально)
            edge_class: Override для edge_class (опціонально)
            default_merge_strategy: Override для merge strategy (опціонально)
            
        Returns:
            Dict з усіма залежностями
            
        Example:
            >>> # Використати всі дефолти
            >>> context = DependencyRegistry.get_context()
            >>> graph = GraphMapper.to_domain(graph_dto, context=context)
            >>>
            >>> # Override тільки plugin_manager
            >>> context = DependencyRegistry.get_context(
            ...     plugin_manager=custom_pm,
            ... )
        """
        with cls._lock:
            config = cls._config
            
            return {
                'plugin_manager': plugin_manager if plugin_manager is not None else config.get_plugin_manager(),
                'tree_parser': tree_parser if tree_parser is not None else config.get_tree_parser(),
                'hash_strategy': hash_strategy if hash_strategy is not None else config.get_hash_strategy(),
                'node_class': node_class if node_class is not None else config.node_class,
                'edge_class': edge_class if edge_class is not None else config.edge_class,
                'default_merge_strategy': default_merge_strategy if default_merge_strategy is not None else config.default_merge_strategy,
            }
    
    @classmethod
    def get_default_merge_strategy(cls) -> str:
        """Отримує дефолтну стратегію merge."""
        with cls._lock:
            return cls._config.default_merge_strategy
    
    @classmethod
    def set_default_merge_strategy(cls, strategy: str) -> None:
        """
        Встановлює дефолтну стратегію merge.
        
        Args:
            strategy: Одна з: 'first', 'last', 'merge', 'newest', 'oldest', 'custom'
        """
        valid_strategies = ['first', 'last', 'merge', 'newest', 'oldest', 'custom']
        if strategy not in valid_strategies:
            raise ValueError(
                f"Invalid merge strategy: {strategy}. "
                f"Valid: {valid_strategies}"
            )
        
        with cls._lock:
            cls._config.default_merge_strategy = strategy
            logger.debug(f"Default merge strategy set to: {strategy}")
    
    @classmethod
    def reset(cls) -> None:
        """
        Скидає всі налаштування до дефолтних значень.
        
        Корисно для тестування.
        """
        with cls._lock:
            cls._config = DependencyConfig()
            logger.debug("DependencyRegistry reset to defaults")
    
    # ==================== SHORTCUT METHODS ====================
    
    @classmethod
    def set_plugin_manager(cls, plugin_manager: Any) -> None:
        """Shortcut для встановлення plugin_manager."""
        with cls._lock:
            cls._config._plugin_manager_instance = plugin_manager
            if cls._config.plugin_manager_factory is None:
                cls._config.plugin_manager_factory = lambda pm=plugin_manager: pm
    
    @classmethod
    def set_tree_parser(cls, tree_parser: Any) -> None:
        """Shortcut для встановлення tree_parser."""
        with cls._lock:
            cls._config._tree_parser_instance = tree_parser
            if cls._config.tree_parser_factory is None:
                cls._config.tree_parser_factory = lambda tp=tree_parser: tp
    
    @classmethod
    def set_hash_strategy(cls, hash_strategy: Any) -> None:
        """Shortcut для встановлення hash_strategy."""
        with cls._lock:
            cls._config._hash_strategy_instance = hash_strategy
            if cls._config.hash_strategy_factory is None:
                cls._config.hash_strategy_factory = lambda hs=hash_strategy: hs
    
    @classmethod
    def get_plugin_manager(cls) -> Optional[Any]:
        """Shortcut для отримання plugin_manager."""
        with cls._lock:
            return cls._config.get_plugin_manager()
    
    @classmethod
    def get_tree_parser(cls) -> Optional[Any]:
        """Shortcut для отримання tree_parser."""
        with cls._lock:
            return cls._config.get_tree_parser()
    
    @classmethod
    def get_hash_strategy(cls) -> Optional[Any]:
        """Shortcut для отримання hash_strategy."""
        with cls._lock:
            return cls._config.get_hash_strategy()
