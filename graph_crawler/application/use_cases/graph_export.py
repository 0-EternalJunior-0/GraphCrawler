"""
GraphExportUseCase - Use Case для експорту графів (Clean Architecture).

"""

import logging
from typing import TYPE_CHECKING, Any, Callable, List, Optional, Type

if TYPE_CHECKING:
    from graph_crawler.domain.entities.graph import Graph

logger = logging.getLogger(__name__)


class GraphExportUseCase:
    """
    Use Case для експорту графів.

    Реалізує Clean Architecture патерн - Graph не залежить від експортерів напряму.

    Args:
        node_exporter: Клас NodeExporter (або сумісний)
        edge_exporter: Клас EdgeExporter (опціонально)

    Example:
        >>> exporter = GraphExportUseCase(node_exporter=NodeExporter)
        >>> result = exporter.export_nodes(graph, 'jobs.json', format='json')
        >>> print(f"Exported {result['total_nodes']} nodes")
    """

    def __init__(
        self,
        node_exporter: Optional[Type] = None,
        edge_exporter: Optional[Type] = None,
    ):
        self._node_exporter = node_exporter
        self._edge_exporter = edge_exporter

    def export_nodes(
        self,
        graph: "Graph",
        filepath: str,
        format: str = "json",
        node_fields: Optional[List[str]] = None,
        transform_node: Optional[Callable] = None,
        predicate: Optional[Callable] = None,
        **kwargs,
    ) -> Any:
        """
        Експортує ноди графу в файл.

        Args:
            graph: Граф для експорту
            filepath: Шлях до файлу
            format: Формат експорту ('json', 'csv')
            node_fields: Список полів для включення (dot notation підтримується)
            transform_node: Функція трансформації (node) -> dict
            predicate: Фільтр нод (node) -> bool
            **kwargs: Додаткові параметри для експортера
        Returns:
            Результат експорту (залежить від формату)
        Raises:
            ValueError: Якщо node_exporter не встановлено або формат не підтримується
        Example:
            >>> exporter.export_nodes(
            ...     graph,
            ...     'vacancies.json',
            ...     format='json',
            ...     node_fields=['url', 'metadata.title'],
            ...     predicate=lambda n: n.scanned and n.depth <= 2
            ... )
        """
        if not self._node_exporter:
            raise ValueError(
                "node_exporter not configured. "
                "Initialize with: GraphExportUseCase(node_exporter=NodeExporter)"
            )

        # Отримуємо список нод (streaming через iter_nodes для великих графів)
        nodes = (
            list(graph.iter_nodes())
            if hasattr(graph, "iter_nodes")
            else (list(graph.iter_nodes()) if hasattr(graph, "iter_nodes") else list(graph))
        )

        logger.info("Exporting %s nodes to %s (format=%s)", len(nodes), filepath, format)

        format_lower = format.lower()

        if format_lower == "json":
            return self._node_exporter.export_to_json(
                nodes=nodes,
                filepath=filepath,
                node_fields=node_fields,
                transform_node=transform_node,
                predicate=predicate,
                **kwargs,
            )
        elif format_lower == "csv":
            return self._node_exporter.export_to_csv(
                nodes=nodes,
                filepath=filepath,
                node_fields=node_fields,
                transform_node=transform_node,
                predicate=predicate,
                **kwargs,
            )
        else:
            raise ValueError(f"Unsupported format: {format}. Supported formats: json, csv")

    async def export_nodes_async(
        self,
        graph: "Graph",
        filepath: str,
        format: str = "json",
        node_fields: Optional[List[str]] = None,
        transform_node: Optional[Callable] = None,
        predicate: Optional[Callable] = None,
        **kwargs,
    ) -> Any:
        """
        Async версія експорту нод (неблокуюча).

        Args:
            graph: Граф для експорту
            filepath: Шлях до файлу
            format: Формат експорту ('json', 'csv')
            node_fields: Список полів для включення
            transform_node: Функція трансформації
            predicate: Фільтр нод
            **kwargs: Додаткові параметри

        Returns:
            Результат експорту
        """
        if not self._node_exporter:
            raise ValueError("node_exporter not configured")

        nodes = (
            list(graph.iter_nodes())
            if hasattr(graph, "iter_nodes")
            else (list(graph.nodes.values()) if hasattr(graph, "nodes") else list(graph))
        )

        logger.info("Async exporting %s nodes to %s", len(nodes), filepath)

        format_lower = format.lower()

        if format_lower == "json":
            if hasattr(self._node_exporter, "export_to_json_async"):
                return await self._node_exporter.export_to_json_async(
                    nodes=nodes,
                    filepath=filepath,
                    node_fields=node_fields,
                    transform_node=transform_node,
                    predicate=predicate,
                    **kwargs,
                )
            else:
                # Fallback до sync версії
                return self._node_exporter.export_to_json(
                    nodes=nodes,
                    filepath=filepath,
                    node_fields=node_fields,
                    transform_node=transform_node,
                    predicate=predicate,
                    **kwargs,
                )
        elif format_lower == "csv":
            if hasattr(self._node_exporter, "export_to_csv_async"):
                return await self._node_exporter.export_to_csv_async(
                    nodes=nodes,
                    filepath=filepath,
                    node_fields=node_fields,
                    transform_node=transform_node,
                    predicate=predicate,
                    **kwargs,
                )
            else:
                return self._node_exporter.export_to_csv(
                    nodes=nodes,
                    filepath=filepath,
                    node_fields=node_fields,
                    transform_node=transform_node,
                    predicate=predicate,
                    **kwargs,
                )
        else:
            raise ValueError(f"Unsupported format: {format}")

    def export_edges(self, graph: "Graph", filepath: str, format: str = "json", **kwargs) -> Any:
        """
        Експортує edges графу в файл.

        Args:
            graph: Граф для експорту
            filepath: Шлях до файлу
            format: Формат експорту ('json', 'csv', 'dot')
            **kwargs: Додаткові параметри

        Returns:
            Результат експорту
        """
        if not self._edge_exporter:
            raise ValueError(
                "edge_exporter not configured. "
                "Initialize with: GraphExportUseCase(edge_exporter=EdgeExporter)"
            )

        # Конвертуємо граф в DTO якщо потрібно
        from graph_crawler.application.dto.mappers.graph_mapper import GraphMapper

        graph_dto = GraphMapper.to_dto(graph)

        format_lower = format.lower()

        if format_lower == "json":
            return self._edge_exporter.export_to_json(graph_dto, filepath, **kwargs)
        elif format_lower == "csv":
            return self._edge_exporter.export_to_csv(graph_dto, filepath, **kwargs)
        elif format_lower == "dot":
            return self._edge_exporter.export_to_dot(graph_dto, filepath, **kwargs)
        else:
            raise ValueError(f"Unsupported edge format: {format}")


__all__ = ["GraphExportUseCase"]
