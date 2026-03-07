"""Base Exporter Interface - Clean Architecture з DTO.

ВИПРАВЛЕНО: Додано async методи з executor для неблокуючих операцій.

Всі exporters тепер працюють ТІЛЬКИ з DTO для ізоляції Domain Layer.
Domain entities (Graph, Node, Edge) НЕ використовуються в exporters.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Optional

from graph_crawler.application.dto import GraphDTO
from graph_crawler.domain.events.event_bus import EventBus
from graph_crawler.shared.utils.event_publisher_mixin import EventPublisherMixin

logger = logging.getLogger(__name__)

# Thread pool для неблокуючих file I/O операцій
_exporter_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="exporter_")


class BaseExporter(EventPublisherMixin, ABC):
    """
    Base class для всіх graph exporters з Clean Architecture.


    для повної ізоляції Domain Layer.

    Архітектурні принципи:
    1. Публічний API ТІЛЬКИ через DTO (GraphDTO)
    2. Domain entities (Graph, Node, Edge) НЕ передаються в exporters
    3. Всі дані отримуються з GraphDTO

    Усі exporters повинні реалізувати метод export().

    Example:
        >>> exporter = CSVExporter()
        >>> graph_dto = await storage.load_graph()  # Завантажуємо GraphDTO
        >>> exporter.export(graph_dto, "output.csv")
    """

    def __init__(self, event_bus: Optional[EventBus] = None, **kwargs):
        """
        Initialize exporter з опціональними параметрами.

        Args:
            event_bus: EventBus для публікації подій (опціонально)
            **kwargs: Exporter-specific конфігурація
        """
        self.event_bus = event_bus
        self.config = kwargs

    @abstractmethod
    def export(self, graph_dto: GraphDTO, output_path: str, **options) -> bool:
        """
        Експортувати граф у вказаний формат через DTO.



        Args:
            graph_dto: GraphDTO для експорту
            output_path: Шлях до output файлу
            **options: Додаткові опції експорту

        Returns:
            bool: True якщо успішно, False інакше

        Raises:
            Exception: При помилках експорту

        Example:
            >>> exporter = CSVExporter()
            >>> graph_dto = await storage.load_graph()
            >>> success = exporter.export(graph_dto, "graph.csv")
        """
        pass

    def validate_graph(self, graph_dto: GraphDTO) -> bool:
        """
        Валідація GraphDTO перед експортом.

        Args:
            graph_dto: GraphDTO instance

        Returns:
            bool: True якщо GraphDTO валідний

        Raises:
            ValueError: Якщо GraphDTO невалідний

        Example:
            >>> if exporter.validate_graph(graph_dto):
            ...     exporter.export(graph_dto, "output.csv")
        """
        if not isinstance(graph_dto, GraphDTO):
            raise ValueError(
                f"Expected GraphDTO instance, got {type(graph_dto).__name__}"
            )

        if len(graph_dto.nodes) == 0:
            logger.warning("GraphDTO has no nodes")
            return False

        return True

    def get_export_info(self, graph_dto: GraphDTO) -> dict:
        """
        Отримати інформацію про експорт через GraphDTO.

        Args:
            graph_dto: GraphDTO instance

        Returns:
            dict: Інформація про граф

        Example:
            >>> info = exporter.get_export_info(graph_dto)
            >>> print(f"Exporting {info['total_nodes']} nodes")
        """
        return {
            "total_nodes": len(graph_dto.nodes),
            "total_edges": len(graph_dto.edges),
            "scanned_nodes": graph_dto.stats.scanned_nodes,
            "unscanned_nodes": graph_dto.stats.unscanned_nodes,
            "avg_depth": graph_dto.stats.avg_depth,
            "max_depth": graph_dto.stats.max_depth,
            "format": self.__class__.__name__,
        }

    # ============= ASYNC МЕТОДИ =============

    async def export_async(self, graph_dto: GraphDTO, output_path: str, **options) -> bool:
        """
        Async версія експорту (неблокуюча).

        Виконує sync export() в thread pool executor.

        Args:
            graph_dto: GraphDTO для експорту
            output_path: Шлях до output файлу
            **options: Додаткові опції експорту

        Returns:
            bool: True якщо успішно
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _exporter_executor,
            partial(self.export, graph_dto, output_path, **options)
        )
