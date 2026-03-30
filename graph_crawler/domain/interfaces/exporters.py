"""
Interfaces for Graph Export functionality (Clean Architecture).

These interfaces allow Graph to delegate export functionality via DI.

Usage:
    Instead of importing EdgeExporter/NodeExporter directly in Graph,
    inject IGraphExporter implementation.
"""

from typing import Any, Callable, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class IEdgeExporter(Protocol):
    """
    Interface for edge export functionality (ISP).

        importing EdgeExporter from Application layer directly.
    """

    @staticmethod
    def export_to_json(graph_dto: Any, filepath: str, **kwargs) -> Any:
        """Exports edges to JSON format."""
        ...

    @staticmethod
    def export_to_csv(graph_dto: Any, filepath: str, **kwargs) -> Any:
        """Exports edges to CSV format."""
        ...

    @staticmethod
    def export_to_dot(graph_dto: Any, filepath: str, **kwargs) -> Any:
        """Exports edges to DOT format (Graphviz)."""
        ...


@runtime_checkable
class INodeExporter(Protocol):
    """
    Interface for node export functionality (ISP).

        importing NodeExporter from Application layer directly.
    """

    @staticmethod
    def export_to_json(
        nodes: List[Any],
        filepath: str,
        node_fields: Optional[List[str]] = None,
        transform_node: Optional[Callable] = None,
        predicate: Optional[Callable] = None,
        **kwargs,
    ) -> Any:
        """Exports nodes to JSON format."""
        ...

    @staticmethod
    def export_to_csv(
        nodes: List[Any],
        filepath: str,
        node_fields: Optional[List[str]] = None,
        transform_node: Optional[Callable] = None,
        predicate: Optional[Callable] = None,
        **kwargs,
    ) -> Any:
        """Exports nodes to CSV format."""
        ...


@runtime_checkable
class IGraphMapper(Protocol):
    """
    Interface for Graph to DTO mapping.

    Used by export functions to convert Graph entity to DTO.
    """

    @staticmethod
    def to_dto(graph: Any) -> Any:
        """Converts Graph entity to GraphDTO."""
        ...


__all__ = [
    "IEdgeExporter",
    "INodeExporter",
    "IGraphMapper",
]
