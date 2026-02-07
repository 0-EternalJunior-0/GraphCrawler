"""Mappers для конвертації Domain entities ↔ DTO.

Забезпечують ізоляцію Domain Layer від зовнішніх шарів.

Використання:
    >>> from graph_crawler.application.dto.mappers import (
    ...     NodeMapper,
    ...     EdgeMapper,
    ...     GraphMapper
    ... )
    >>>
    >>> # Domain → DTO
    >>> node_dto = NodeMapper.to_dto(node)
    >>> edge_dto = EdgeMapper.to_dto(edge)
    >>> graph_dto = GraphMapper.to_dto(graph)
    >>>
    >>> # DTO → Domain
    >>> context = {'plugin_manager': pm, 'tree_parser': parser}
    >>> node = NodeMapper.to_domain(node_dto, context=context)
    >>> edge = EdgeMapper.to_domain(edge_dto)
    >>> graph = GraphMapper.to_domain(graph_dto, context=context)
"""

from graph_crawler.application.dto.mappers.edge_mapper import EdgeMapper
from graph_crawler.application.dto.mappers.graph_mapper import GraphMapper
from graph_crawler.application.dto.mappers.node_mapper import NodeMapper

__all__ = [
    "NodeMapper",
    "EdgeMapper",
    "GraphMapper",
]
