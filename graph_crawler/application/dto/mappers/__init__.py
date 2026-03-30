"""Mappers для конвертації Domain entities ↔ DTO.

Забезпечують ізоляцію Domain Layer від зовнішніх шарів.
"""

from graph_crawler.application.dto.mappers.edge_mapper import EdgeMapper
from graph_crawler.application.dto.mappers.graph_mapper import GraphMapper
from graph_crawler.application.dto.mappers.node_mapper import NodeMapper

__all__ = [
    "NodeMapper",
    "EdgeMapper",
    "GraphMapper",
]
