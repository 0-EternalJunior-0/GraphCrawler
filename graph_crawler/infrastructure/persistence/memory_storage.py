"""Збереження графу у пам'яті (RAM) через GraphDTO."""

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from graph_crawler.application.dto import GraphDTO
from graph_crawler.infrastructure.persistence.base import BaseStorage

if TYPE_CHECKING:
    from graph_crawler.domain.events.event_bus import EventBus

import logging
import time

from graph_crawler.domain.events.events import EventType

logger = logging.getLogger(__name__)


class MemoryStorage(BaseStorage):
    """
    Async збереження GraphDTO у пам'яті.

    BREAKING CHANGE: Тепер використовує GraphDTO замість Graph для ізоляції Domain Layer.

    Використовується для малих сайтів (<1000 сторінок).
    GraphDTO зберігається тільки в пам'яті, без файлів.

    Обмеження: максимум 1000 вузлів. Всі методи async для сумісності з async інтерфейсом,
    хоча операції в пам'яті виконуються миттєво.

    Example:
        >>> from graph_crawler.application.dto.mappers import GraphMapper
        >>>
        >>> # Серіалізація Domain → DTO → Memory
        >>> graph_dto = GraphMapper.to_dto(graph)
        >>> await storage.save_graph(graph_dto)
        >>>
        >>> # Десеріалізація Memory → DTO → Domain
        >>> graph_dto = await storage.load_graph()
        >>> context = {'plugin_manager': pm, 'tree_parser': parser}
        >>> graph = GraphMapper.to_domain(graph_dto, context=context)
    """

    MAX_NODES = 1000  # Жорсткий ліміт для запобігання memory overflow

    def __init__(self, event_bus: Optional["EventBus"] = None):
        """
        Ініціалізує MemoryStorage.

        Args:
            event_bus: EventBus для публікації подій (опціонально)
        """
        super().__init__(event_bus=event_bus)
        self.graph_dto: Optional[GraphDTO] = None

    async def save_graph(self, graph_dto: GraphDTO) -> bool:
        """
        Async зберігає GraphDTO у пам'яті.

        BREAKING CHANGE: Тепер приймає GraphDTO замість Graph.

        Args:
            graph_dto: GraphDTO для збереження

        Returns:
            True якщо успішно

        Raises:
            MemoryError: Якщо граф перевищує MAX_NODES

        Example:
            >>> from graph_crawler.application.dto.mappers import GraphMapper
            >>> graph_dto = GraphMapper.to_dto(graph)
            >>> await storage.save_graph(graph_dto)
        """
        start_time = time.time()

        # Подія: STORAGE_SAVE_STARTED
        self.publish_event(
            EventType.STORAGE_SAVE_STARTED,
            data={
                "storage_type": "memory",
                "nodes_count": len(graph_dto.nodes),
                "edges_count": len(graph_dto.edges),
            },
        )

        try:
            if len(graph_dto.nodes) > self.MAX_NODES:
                error_msg = (
                    f"MemoryStorage exceeded limit: {len(graph_dto.nodes)} nodes > {self.MAX_NODES}. "
                    f"Please use JSONStorage (up to 10k nodes) or SQLiteStorage (up to 20k nodes) instead."
                )

                # Подія: STORAGE_SAVE_ERROR
                self.publish_event(
                    EventType.STORAGE_SAVE_ERROR,
                    data={
                        "storage_type": "memory",
                        "error": error_msg,
                        "error_type": "MemoryError",
                        "nodes_count": len(graph_dto.nodes),
                        "max_nodes": self.MAX_NODES,
                    },
                )

                raise MemoryError(error_msg)

            logger.debug(f"Storing GraphDTO in memory: {len(graph_dto.nodes)} nodes")
            self.graph_dto = graph_dto

            duration = time.time() - start_time

            # Подія: STORAGE_SAVE_SUCCESS
            self.publish_event(
                EventType.STORAGE_SAVE_SUCCESS,
                data={
                    "storage_type": "memory",
                    "nodes_count": len(graph_dto.nodes),
                    "edges_count": len(graph_dto.edges),
                    "duration": round(duration, 3),
                },
            )

            return True

        except MemoryError:
            raise
        except Exception as e:
            # Подія: STORAGE_SAVE_ERROR (для неочікуваних помилок)
            self.publish_event(
                EventType.STORAGE_SAVE_ERROR,
                data={
                    "storage_type": "memory",
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
            raise

    async def load_graph(self, context: Optional[Dict[str, Any]] = None) -> Optional[GraphDTO]:
        """
        Async повертає GraphDTO з пам'яті.

        BREAKING CHANGE: Тепер повертає GraphDTO замість Graph.

        Args:
            context: Контекст (не використовується в MemoryStorage, але залишений для сумісності)

        Returns:
            GraphDTO або None якщо не знайдено

        Example:
            >>> graph_dto = await storage.load_graph()
            >>> # Конвертація в Domain Graph (якщо потрібно)
            >>> from graph_crawler.application.dto.mappers import GraphMapper
            >>> context = {'plugin_manager': pm, 'tree_parser': parser}
            >>> graph = GraphMapper.to_domain(graph_dto, context=context)
        """
        start_time = time.time()

        # Подія: STORAGE_LOAD_STARTED
        self.publish_event(
            EventType.STORAGE_LOAD_STARTED, data={"storage_type": "memory"}
        )

        if self.graph_dto is not None:
            duration = time.time() - start_time

            # Подія: STORAGE_LOAD_SUCCESS
            self.publish_event(
                EventType.STORAGE_LOAD_SUCCESS,
                data={
                    "storage_type": "memory",
                    "nodes_count": len(self.graph_dto.nodes),
                    "edges_count": len(self.graph_dto.edges),
                    "duration": round(duration, 3),
                },
            )

        return self.graph_dto

    async def save_partial(self, nodes: List[Dict], edges: List[Dict]) -> bool:
        """Async для in-memory не потрібно часткове збереження ."""
        return True

    async def clear(self) -> bool:
        """Async очищує пам'ять."""
        self.graph_dto = None
        return True

    async def exists(self) -> bool:
        """Async перевіряє чи є GraphDTO у пам'яті."""
        return self.graph_dto is not None
