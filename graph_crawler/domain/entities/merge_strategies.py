"""
Стратегії об'єднання (merge) вузлів при операціях над графами.

Коли два графи містять вузли з однаковими URL але різними даними,
merge strategy визначає як комбінувати ці дані.

Приклад:
    >>> from graph_crawler.domain.entities.merge_strategies import MergeStrategy, NodeMerger
    >>>
    >>> # Використання через GraphOperations
    >>> merged = GraphOperations.union(g1, g2, merge_strategy='last')
    >>>
    >>> # Або прямий merge двох нод
    >>> merger = NodeMerger(strategy='merge')
    >>> merged_node = merger.merge(node1, node2)
"""

import logging
from enum import Enum
from typing import TYPE_CHECKING, Callable, Dict, Optional

if TYPE_CHECKING:
    from graph_crawler.domain.entities.node import Node

logger = logging.getLogger(__name__)


class MergeStrategy(str, Enum):
    """
    Стратегії об'єднання вузлів з однаковими URL.

    FIRST - залишити дані з першого вузла (консервативний підхід)
    LAST - взяти дані з другого вузла (перезаписати)
    MERGE - інтелектуальне об'єднання (рекомендовано)
    NEWEST - вибрати вузол з найновішим created_at
    OLDEST - вибрати вузол з найстарішим created_at
    CUSTOM - користувацька функція merge
    """

    FIRST = "first"  # Залишити node1, ігнорувати node2
    LAST = "last"  # Взяти node2, ігнорувати node1 (дефолт)
    MERGE = "merge"  # Інтелектуальне об'єднання
    NEWEST = "newest"  # Вибрати найновіший за created_at
    OLDEST = "oldest"  # Вибрати найстаріший за created_at
    CUSTOM = "custom"  # Користувацька функція


class NodeMerger:
    """
    Об'єднує два вузли (Node) з однаковими URL за заданою стратегією.

    Args:
        strategy: Стратегія merge (MergeStrategy enum або string)
        custom_merge_fn: Користувацька функція для strategy='custom'
                        Signature: fn(node1: Node, node2: Node) -> Node
    """

    _STRATEGY_MAP = {
        MergeStrategy.FIRST: "_merge_first",
        MergeStrategy.LAST: "_merge_last",
        MergeStrategy.MERGE: "_merge_intelligent",
        MergeStrategy.NEWEST: "_merge_newest",
        MergeStrategy.OLDEST: "_merge_oldest",
    }

    def __init__(
        self,
        strategy: str | MergeStrategy = MergeStrategy.LAST,
        custom_merge_fn: Optional[Callable[["Node", "Node"], "Node"]] = None,
    ):
        """
        Ініціалізує merger зі стратегією.

        Args:
            strategy: Стратегія merge
            custom_merge_fn: Функція для CUSTOM стратегії
        """
        # Конвертуємо string в enum
        if isinstance(strategy, str):
            try:
                strategy = MergeStrategy(strategy.lower())
            except ValueError:
                raise ValueError(
                    f"Invalid merge strategy: {strategy}. "
                    f"Allowed: {[s.value for s in MergeStrategy]}"
                )

        self.strategy = strategy
        self.custom_merge_fn = custom_merge_fn

        # Перевірка для CUSTOM стратегії
        if self.strategy == MergeStrategy.CUSTOM and not custom_merge_fn:
            raise ValueError("custom_merge_fn required for CUSTOM strategy")

        logger.debug("NodeMerger initialized with strategy: %s", self.strategy.value)

    def merge(self, node1: "Node", node2: "Node") -> "Node":
        """
        Об'єднує два вузли за обраною стратегією. Оптимізовано - dict lookup O(1) замість if-elif O(n)

        Args:
            node1: Перший вузол (з першого графа)
            node2: Другий вузол (з другого графа)

        Returns:
            Об'єднаний вузол

        Raises:
            ValueError: Якщо вузли мають різні URL
        """
        # Перевірка URL
        if node1.url != node2.url:
            raise ValueError(f"Cannot merge nodes with different URLs: {node1.url} != {node2.url}")

        if self.strategy == MergeStrategy.CUSTOM:
            return self.custom_merge_fn(node1, node2)

        method_name = self._STRATEGY_MAP.get(self.strategy)
        if not method_name:
            raise ValueError(f"Unknown strategy: {self.strategy}")

        return getattr(self, method_name)(node1, node2)

    def _merge_first(self, node1: "Node", node2: "Node") -> "Node":
        """
        Стратегія FIRST: залишити node1, ігнорувати node2.

        Найпростіша стратегія - повертає перший вузол без змін.
        Використовується коли потрібно зберегти оригінальні дані.
        """
        logger.debug("FIRST strategy: keeping node1 for %s", node1.url)
        return node1

    def _merge_last(self, node1: "Node", node2: "Node") -> "Node":
        """
        Стратегія LAST: взяти node2, ігнорувати node1.

        Перезаписує дані першого вузла даними з другого.
        Дефолтна стратегія - найчастіше потрібно оновити дані.
        """
        logger.debug("LAST strategy: using node2 for %s", node2.url)
        return node2

    # Критичні поля metadata, які НЕ повинні перезаписуватись іншими вузлами
    # Ці поля специфічні для кожного URL і не повинні "перемішуватись"
    PROTECTED_METADATA_FIELDS = frozenset(
        {
            "canonical_url",  # Канонічний URL сторінки
            "title",  # Заголовок сторінки
            "h1",  # H1 заголовок
            "description",  # Мета-опис
            "og:url",  # OpenGraph URL
            "og:title",  # OpenGraph заголовок
            "twitter:url",  # Twitter URL
        }
    )

    def _merge_intelligent(self, node1: "Node", node2: "Node") -> "Node":
        """
        Стратегія MERGE: інтелектуальне об'єднання даних.

        Розумно комбінує дані з обох вузлів:
        - metadata: об'єднання словників з ЗАХИСТОМ критичних полів
        - user_data: об'єднання словників (node2 перезаписує node1)
        - scanned: True якщо хоча б один scanned
        - response_status: з node2 якщо є, інакше з node1
        - content_hash: з node2 якщо є, інакше з node1
        - created_at: найраніший (старший вузол)
        - depth: мінімальний (ближче до root)
        - Кастомні атрибути: об'єднуються (node2 перезаписує node1)

        ВИПРАВЛЕННЯ v4.0.11: Захист критичних metadata полів від перезапису
        при конкурентному краулінгу (canonical_url, title, h1, description тощо).

        Це найрозумніша стратегія - рекомендується для більшості випадків.
        """
        logger.debug("MERGE strategy: intelligently merging %s", node1.url)

        # ВИПРАВЛЕННЯ: Зберігаємо оригінальний тип ноди!
        # Використовуємо тип node1 (або node2 якщо він більш специфічний)
        node_class = type(node1)
        if type(node2).__mro__[:-1].__len__() > type(node1).__mro__[:-1].__len__():
            # node2 має глибшу ієрархію наслідування - він більш специфічний
            node_class = type(node2)

        # Створюємо копію через правильний клас
        merged = node_class.model_validate(node1.model_dump())

        # ВИПРАВЛЕННЯ v4.0.11: Захист критичних metadata полів
        # Об'єднуємо metadata БЕЗ перезапису критичних полів якщо вони вже заповнені
        import copy as copy_module

        merged_metadata = copy_module.deepcopy(node1.metadata) if node1.metadata else {}

        for key, value in node2.metadata.items():
            # Для критичних полів - НЕ перезаписуємо якщо node1 вже має непорожнє значення
            if key in self.PROTECTED_METADATA_FIELDS:
                existing_value = merged_metadata.get(key)
                if existing_value:
                    # node1 вже має значення - перевіряємо консистентність
                    if value and existing_value != value:
                        logger.warning(
                            f"Metadata conflict for '{key}' during merge of {node1.url}: "
                            f"keeping '{existing_value}', ignoring '{value}'"
                        )
                    continue  # Зберігаємо оригінальне значення
            # Для некритичних полів - стандартна поведінка (node2 перезаписує)
            merged_metadata[key] = value

        merged.metadata = merged_metadata

        # Об'єднуємо user_data (node2 перезаписує конфлікти)
        merged_user_data = copy_module.deepcopy(node1.user_data) if node1.user_data else {}
        for key, value in node2.user_data.items():
            if isinstance(value, (dict, list)):
                merged_user_data[key] = copy_module.deepcopy(value)
            else:
                merged_user_data[key] = value
        merged.user_data = merged_user_data

        # scanned: True якщо хоча б один scanned
        merged.scanned = node1.scanned or node2.scanned

        # response_status: беремо з node2 якщо є
        if node2.response_status is not None:
            merged.response_status = node2.response_status

        # content_hash: беремо з node2 якщо є (новіші дані)
        if node2.content_hash is not None:
            merged.content_hash = node2.content_hash

        # created_at: беремо найраніший (старший вузол)
        if node2.created_at < node1.created_at:
            merged.created_at = node2.created_at

        # depth: беремо мінімальний (ближче до root)
        merged.depth = min(node1.depth, node2.depth)

        # ВИПРАВЛЕННЯ: Копіюємо кастомні атрибути з node2 (новіші дані)
        # Отримуємо всі атрибути які є в node2 але не в базовому Node
        from graph_crawler.domain.entities.node import Node

        base_fields = set(Node.model_fields)

        for field_name in type(node2).model_fields:
            if field_name not in base_fields:
                # Це кастомний атрибут - копіюємо з node2
                if hasattr(merged, field_name):
                    node2_value = getattr(node2, field_name)
                    node1_value = getattr(node1, field_name)
                    # Якщо node2 має "позитивне" значення - використовуємо його
                    # Логіка: True > False, непорожнє > порожнє
                    if node2_value or not node1_value:
                        setattr(merged, field_name, node2_value)

        try:
            from graph_crawler.domain.value_objects.lifecycle import NodeLifecycle

            if node2.lifecycle_stage == NodeLifecycle.HTML_STAGE:
                merged.lifecycle_stage = NodeLifecycle.HTML_STAGE
        except (ImportError, AttributeError):
            # Якщо модуль відсутній або атрибут не існує, пропускаємо
            pass

        logger.debug(
            f"Merged node {merged.url}: "
            f"type={type(merged).__name__}, "
            f"metadata={len(merged.metadata)} keys, "
            f"user_data={len(merged.user_data)} keys, "
            f"scanned={merged.scanned}"
        )

        return merged

    def _merge_newest(self, node1: "Node", node2: "Node") -> "Node":
        """
        Стратегія NEWEST: вибрати вузол з найновішим created_at.

        Корисно коли потрібні найсвіжіші дані.
        """
        if node2.created_at > node1.created_at:
            logger.debug("NEWEST strategy: node2 is newer for %s", node2.url)
            return node2
        else:
            logger.debug("NEWEST strategy: node1 is newer for %s", node1.url)
            return node1

    def _merge_oldest(self, node1: "Node", node2: "Node") -> "Node":
        """
        Стратегія OLDEST: вибрати вузол з найстарішим created_at.

        Корисно коли потрібні оригінальні дані.
        """
        if node2.created_at < node1.created_at:
            logger.debug("OLDEST strategy: node2 is older for %s", node2.url)
            return node2
        else:
            logger.debug("OLDEST strategy: node1 is older for %s", node1.url)
            return node1


def merge_nodes(
    node1: "Node",
    node2: "Node",
    strategy: str | MergeStrategy = MergeStrategy.LAST,
    custom_merge_fn: Optional[Callable[["Node", "Node"], "Node"]] = None,
) -> "Node":
    """
    Утилітна функція для швидкого merge двох вузлів.

    Args:
        node1: Перший вузол
        node2: Другий вузол
        strategy: Стратегія merge
        custom_merge_fn: Функція для CUSTOM стратегії

    Returns:
        Об'єднаний вузол

    Example:
        >>> from graph_crawler.domain.entities.merge_strategies import merge_nodes
        >>> merged = merge_nodes(node1, node2, strategy='merge')
    """
    merger = NodeMerger(strategy=strategy, custom_merge_fn=custom_merge_fn)
    return merger.merge(node1, node2)


def get_available_strategies() -> Dict[str, str]:
    """
    Повертає список доступних стратегій з описами.

    Returns:
        Словник {strategy_name: description}

    Example:
        >>> strategies = get_available_strategies()
        >>> for name, desc in strategies.items():
        ...     print(f"{name}: {desc}")
    """
    return {
        "first": "Залишити дані з першого графа (консервативно)",
        "last": "Взяти дані з другого графа (перезаписати) - ДЕФОЛТ",
        "merge": "Інтелектуальне об'єднання даних (рекомендовано)",
        "newest": "Вибрати вузол з найновішим timestamp",
        "oldest": "Вибрати вузол з найстарішим timestamp",
        "custom": "Користувацька функція merge",
    }
