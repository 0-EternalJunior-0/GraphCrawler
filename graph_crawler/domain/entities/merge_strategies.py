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
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

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

    Використовується в GraphOperations.union() для вирішення конфліктів
    коли два графи містять вузли з однаковими URL. Оптимізовано - dict mapping замість if-elif ланцюга

    Args:
        strategy: Стратегія merge (MergeStrategy enum або string)
        custom_merge_fn: Користувацька функція для strategy='custom'
                        Signature: fn(node1: Node, node2: Node) -> Node

    Example:
        >>> merger = NodeMerger(strategy='merge')
        >>> merged_node = merger.merge(node1, node2)
        >>>
        >>> # Користувацька стратегія
        >>> def my_merge(n1, n2):
        ...     # Власна логіка
        ...     return n1 if n1.scanned else n2
        >>>
        >>> merger = NodeMerger(strategy='custom', custom_merge_fn=my_merge)
        >>> merged = merger.merge(node1, node2)
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

        logger.debug(f"NodeMerger initialized with strategy: {self.strategy.value}")

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
            raise ValueError(
                f"Cannot merge nodes with different URLs: "
                f"{node1.url} != {node2.url}"
            )

        if self.strategy == MergeStrategy.CUSTOM:
            return self.custom_merge_fn(node1, node2)

        method_name = self._STRATEGY_MAP.get(self.strategy)
        if not method_name:
            raise ValueError(f"Unknown strategy: {self.strategy}")

        return getattr(self, method_name)(node1, node2)

    # ==================== ПРИВАТНІ МЕТОДИ СТРАТЕГІЙ ====================

    def _merge_first(self, node1: "Node", node2: "Node") -> "Node":
        """
        Стратегія FIRST: залишити node1, ігнорувати node2.

        Найпростіша стратегія - повертає перший вузол без змін.
        Використовується коли потрібно зберегти оригінальні дані.
        """
        logger.debug(f"FIRST strategy: keeping node1 for {node1.url}")
        return node1

    def _merge_last(self, node1: "Node", node2: "Node") -> "Node":
        """
        Стратегія LAST: взяти node2, ігнорувати node1.

        Перезаписує дані першого вузла даними з другого.
        Дефолтна стратегія - найчастіше потрібно оновити дані.
        """
        logger.debug(f"LAST strategy: using node2 for {node2.url}")
        return node2

    def _merge_intelligent(self, node1: "Node", node2: "Node") -> "Node":
        """
        Стратегія MERGE: інтелектуальне об'єднання даних.

        Розумно комбінує дані з обох вузлів:
        - metadata: об'єднання словників (node2 перезаписує node1)
        - user_data: об'єднання словників (node2 перезаписує node1)
        - scanned: True якщо хоча б один scanned
        - response_status: з node2 якщо є, інакше з node1
        - content_hash: з node2 якщо є, інакше з node1
        - created_at: найраніший (старший вузол)
        - depth: мінімальний (ближче до root)

        Це найрозумніша стратегія - рекомендується для більшості випадків.
        """
        from graph_crawler.domain.entities.node import Node

        logger.debug(f"MERGE strategy: intelligently merging {node1.url}")

        # Створюємо копію node1 як базу
        merged = Node.model_validate(node1.model_dump())

        # Об'єднуємо metadata (node2 перезаписує конфлікти)
        merged_metadata = node1.metadata.copy()
        merged_metadata.update(node2.metadata)
        merged.metadata = merged_metadata

        # Об'єднуємо user_data (node2 перезаписує конфлікти)
        merged_user_data = node1.user_data.copy()
        merged_user_data.update(node2.user_data)
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

        # lifecycle_stage: беремо більш просунутий
        from graph_crawler.domain.entities.lifecycle import NodeLifecycle

        if node2.lifecycle_stage == NodeLifecycle.HTML_STAGE:
            merged.lifecycle_stage = NodeLifecycle.HTML_STAGE

        logger.debug(
            f"Merged node {merged.url}: "
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
            logger.debug(f"NEWEST strategy: node2 is newer for {node2.url}")
            return node2
        else:
            logger.debug(f"NEWEST strategy: node1 is newer for {node1.url}")
            return node1

    def _merge_oldest(self, node1: "Node", node2: "Node") -> "Node":
        """
        Стратегія OLDEST: вибрати вузол з найстарішим created_at.

        Корисно коли потрібні оригінальні дані.
        """
        if node2.created_at < node1.created_at:
            logger.debug(f"OLDEST strategy: node2 is older for {node2.url}")
            return node2
        else:
            logger.debug(f"OLDEST strategy: node1 is older for {node1.url}")
            return node1


# ==================== УТИЛІТНІ ФУНКЦІЇ ====================


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
