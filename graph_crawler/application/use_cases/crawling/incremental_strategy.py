"""
Incremental Crawl Strategy - логіка інкрементального краулінгу.

Відокремлює відповідальність за детекцію змін та порівняння нод
від основного класу GraphSpider (SRP - Single Responsibility Principle).
"""

import logging
from typing import Optional

from graph_crawler.domain.entities.graph import Graph
from graph_crawler.domain.entities.node import Node
from graph_crawler.domain.events import CrawlerEvent, EventBus, EventType
from graph_crawler.domain.value_objects.configs import CrawlerConfig

logger = logging.getLogger(__name__)


class IncrementalCrawlStrategy:
    """
    Стратегія інкрементального краулінгу.

    Responsibilities:
    - Детекція нових сторінок
    - Детекція змін в існуючих сторінках
    - Порівняння нод через hash або metadata
    - Публікація подій про зміни

    Це окремий клас для дотримання SRP - тільки incremental логіка.
    """

    def __init__(
        self,
        config: CrawlerConfig,
        base_graph: Optional[Graph],
        event_bus: Optional[EventBus] = None,
    ):
        """
        Ініціалізує Incremental Strategy.

        Args:
            config: Конфігурація краулера (містить change_detection_strategy)
            base_graph: Базовий граф для порівняння (може бути None)
            event_bus: Event bus для публікації подій
        """
        self.config = config
        self.base_graph = base_graph
        self.event_bus = event_bus

        if config.incremental and base_graph:
            logger.info(
                f" Incremental mode enabled (strategy={config.change_detection_strategy})"
            )

    def should_process_node_links(self, node: Node) -> bool:
        """
        Перевіряє чи потрібно обробляти посилання для ноди.

        Порівнює поточну ноду з нодою з базового графа:
        - Якщо нода нова → обробляємо
        - Якщо нода змінилась → обробляємо
        - Якщо нода не змінилась → пропускаємо

        Args:
            node: Поточна просканована нода

        Returns:
            True - обробити посилання, False - пропустити
        """
        # Якщо incremental mode вимкнено → завжди обробляємо
        if not self.config.incremental or not self.base_graph:
            return True

        # Шукаємо стару ноду в базовому графі
        old_node = self.base_graph.get_node_by_url(node.url)

        # Якщо ноди немає в старому графі → нова сторінка
        if old_node is None:
            logger.debug(f" New page detected: {node.url}")
            return True

        # Перевіряємо чи можна порівнювати ноди
        if not self._can_compare_nodes(old_node, node):
            logger.debug(f" Cannot compare nodes (unscanned or no hash): {node.url}")
            return True  # Обробляємо на всяк випадок

        # Детекція змін залежно від стратегії
        changed = self._detect_changes(old_node, node)

        if changed:
            logger.debug(f" Changed page detected: {node.url}")
            self._publish_change_event(old_node, node)
            return True
        else:
            # Сторінка не змінилась - пропускаємо обробку посилань
            logger.debug(f"⏩ Skipping unchanged: {node.url}")
            self._publish_unchanged_event(node)
            return False

    def _can_compare_nodes(self, old_node: Node, new_node: Node) -> bool:
        """
        Перевіряє чи можна порівнювати дві ноди.

        Ноди можна порівняти якщо:
        - Обидві були просканованні (scanned=True)
        - Обидві мають content_hash

        Args:
            old_node: Стара нода з базового графа
            new_node: Нова нода з поточного краулінгу

        Returns:
            True якщо можна порівняти
        """
        # Перевіряємо чи ноди були просканованні
        if not old_node.scanned or not new_node.scanned:
            return False

        # Перевіряємо чи є hash (може бути None для PDF, помилок завантаження)
        if old_node.content_hash is None or new_node.content_hash is None:
            return False

        return True

    def _detect_changes(self, old_node: Node, new_node: Node) -> bool:
        """
        Детекція змін залежно від налаштованої стратегії.

        Args:
            old_node: Стара нода
            new_node: Нова нода

        Returns:
            True якщо є зміни
        """
        strategy = self.config.change_detection_strategy

        if strategy == "hash":
            return self._detect_changes_hash(old_node, new_node)
        elif strategy == "metadata":
            return self._detect_changes_metadata(old_node, new_node)
        else:
            logger.warning(f"Unknown strategy '{strategy}', using 'hash'")
            return self._detect_changes_hash(old_node, new_node)

    def _detect_changes_hash(self, old_node: Node, new_node: Node) -> bool:
        """
        Детекція змін через порівняння hash (стратегія 'hash').

        Швидкий та надійний спосіб - порівнює SHA256 хеші контенту.

        Args:
            old_node: Стара нода
            new_node: Нова нода

        Returns:
            True якщо є зміни
        """
        return old_node.content_hash != new_node.content_hash

    def _detect_changes_metadata(self, old_node: Node, new_node: Node) -> bool:
        """
        Детекція змін через порівняння metadata (стратегія 'metadata').

        Порівнює поля metadata (title, description, h1, keywords).
        Якщо metadata порожня → ValueError.

        Args:
            old_node: Стара нода
            new_node: Нова нода

        Returns:
            True якщо є зміни

        Raises:
            ValueError: Якщо metadata порожня
        """
        # Перевіряємо чи є metadata
        if not old_node.metadata or not new_node.metadata:
            raise ValueError(
                f"Node {new_node.url} has empty metadata. "
                f"Cannot use 'metadata' strategy. "
                f"Use 'hash' strategy or override get_content_hash() method."
            )

        # Знаходимо спільні ключі
        common_keys = set(old_node.metadata.keys()) & set(new_node.metadata.keys())

        if not common_keys:
            raise ValueError(
                f"Nodes have no common metadata fields for {new_node.url}. "
                f"Cannot use 'metadata' strategy. "
                f"Use 'hash' strategy instead."
            )

        # Порівнюємо спільні поля
        for key in common_keys:
            if old_node.metadata[key] != new_node.metadata[key]:
                logger.debug(
                    f"Metadata changed: {key} = "
                    f"'{old_node.metadata[key]}' → '{new_node.metadata[key]}'"
                )
                return True  # Зміна знайдена

        return False  # Метадані однакові

    def _publish_change_event(self, old_node: Node, new_node: Node) -> None:
        """Публікує подію про детекцію змін."""
        if not self.event_bus:
            return

        strategy = self.config.change_detection_strategy

        self.event_bus.publish(
            CrawlerEvent.create(
                EventType.NODE_DETECTED_CHANGED,
                data={
                    "url": new_node.url,
                    "strategy": strategy,
                    "old_hash": old_node.content_hash if strategy == "hash" else None,
                    "new_hash": new_node.content_hash if strategy == "hash" else None,
                },
            )
        )

    def _publish_unchanged_event(self, node: Node) -> None:
        """Публікує подію про пропуск незміненої сторінки."""
        if not self.event_bus:
            return

        self.event_bus.publish(
            CrawlerEvent.create(
                EventType.NODE_SKIPPED_UNCHANGED,
                data={
                    "url": node.url,
                    "reason": "unchanged",
                    "strategy": self.config.change_detection_strategy,
                },
            )
        )
