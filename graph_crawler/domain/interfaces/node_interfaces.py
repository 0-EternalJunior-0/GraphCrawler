"""
Внутрішні інтерфейси для Core модуля.

Цей модуль створено для вирішення circular imports в Node.py.
Замість імпорту конкретних реалізацій (NodePluginContext, NodePluginType),
Node тепер залежить тільки від абстракцій (Protocols).

Dependency Inversion Principle (DIP):
- High-level modules (Node) не повинні залежати від low-level modules (Plugins)
- Обидва повинні залежати від абстракцій (Protocols)

Переваги:
1. Немає circular imports
2. Швидші імпорти (no lazy imports)
3. Краща IDE підтримка (type hints працюють)
4. Легше тестувати (можна підміняти реалізації)
"""

from enum import Enum
from typing import Any, Dict, Optional, Protocol, runtime_checkable


@runtime_checkable
class INodePluginType(Protocol):
    """
    Protocol для NodePluginType enum.

    Визначає lifecycle hooks для Node плагінів:
    - ON_NODE_CREATED: після створення Node
    - ON_HTML_PARSED: після парсингу HTML
    - ON_LINKS_EXTRACTED: після витягування посилань
    - ON_AFTER_SCAN: після завершення сканування
    """

    value: str


@runtime_checkable
class INodePluginContext(Protocol):
    """
    Protocol для NodePluginContext.

    Контекст передається між плагінами та містить:
    - url: URL сторінки
    - depth: Глибина краулінгу
    - html: HTML контент
    - html_tree: Parsed HTML (BeautifulSoup/lxml)
    - metadata: Витягнуті метадані
    - links: Знайдені посилання
    - plugin_data: Дані між плагінами
    """

    url: str
    depth: int
    html: Optional[str]
    html_tree: Optional[Any]  # BeautifulSoup/lxml object
    metadata: Dict[str, Any]
    links: list
    plugin_data: Dict[str, Any]


@runtime_checkable
class IPluginManager(Protocol):
    """
    Protocol для NodePluginManager.

    Менеджер виконує зареєстровані плагіни на різних етапах
    lifecycle Node (ON_NODE_CREATED, ON_HTML_PARSED, etc.).

    Example:
        >>> class CustomPluginManager:
        ...     def execute(self, plugin_type, context):
        ...         # кастомна логіка виконання плагінів
        ...         return context
        >>> node = Node(url="...", plugin_manager=CustomPluginManager())
    """

    def execute(self, plugin_type: Any, context: Any) -> Any:
        """
        Виконує всі зареєстровані плагіни вказаного типу.

        Args:
            plugin_type: Тип плагіна (INodePluginType)
            context: Контекст виконання (INodePluginContext)

        Returns:
            Оновлений контекст після виконання всіх плагінів
        """
        ...


@runtime_checkable
class ISimHashStrategy(Protocol):
    """
    Protocol для обчислення SimHash (Locality-Sensitive Hash).

    SimHash використовується для знаходження ПОДІБНИХ документів (near-duplicates),
    на відміну від SHA256 content_hash який знаходить ТОЧНІ дублікати.

    Контракт:
    - Метод повертає 64-бітний SimHash як hex string (16 символів)
    - SimHash схожих документів матиме малу Hamming distance
    - SimHash різних документів матиме велику Hamming distance

    Example:
        >>> class CustomSimHashStrategy:
        ...     def compute_simhash(self, node: 'Node') -> str:
        ...         # Кастомна логіка обчислення SimHash
        ...         return simhash_hex_value  # 16 hex символів
        >>>
        >>> node.simhash_strategy = CustomSimHashStrategy()
        >>> simhash = node.get_simhash()
    """

    def compute_simhash(self, node: Any) -> str:
        """
        Обчислює SimHash для ноди.

        Контракт:
        - MUST повертати hex string (16 символів для 64-бітного SimHash)
        - MUST бути детермінованим (однакові дані → однаковий хеш)
        - MUST викликатися тільки після process_html() (HTML_STAGE)

        Args:
            node: Node для якої обчислюється SimHash

        Returns:
            SimHash hex string (16 символів)
        """
        ...


__all__ = [
    "INodePluginType",
    "INodePluginContext",
    "IPluginManager",
    "ISimHashStrategy",
]
