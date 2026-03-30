"""Data Transfer Objects (DTO) для GraphCrawler.

DTO використовуються для передачі даних між шарами архітектури:
"""

from graph_crawler.application.dto.edge_dto import (
    CreateEdgeDTO,
    EdgeDTO,
)
from graph_crawler.application.dto.graph_dto import (
    GraphDTO,
    GraphStatsDTO,
    GraphSummaryDTO,
)

# Mappers для конвертації Domain ↔ DTO
from graph_crawler.application.dto.mappers import (
    EdgeMapper,
    GraphMapper,
    NodeMapper,
)
from graph_crawler.application.dto.node_dto import (
    CreateNodeDTO,
    NodeDTO,
    NodeMetadataDTO,
)

# Utility functions
from graph_crawler.application.dto.utils import (
    clone_graph,
    dict_to_graph,
    filter_graph,
    graph_to_dict,
    graph_to_json,
    json_to_graph,
    load_graph,
    merge_graphs,
    save_graph,
)

__all__ = [
    # Node DTOs
    "NodeDTO",
    "CreateNodeDTO",
    "NodeMetadataDTO",
    # Edge DTOs
    "EdgeDTO",
    "CreateEdgeDTO",
    # Graph DTOs
    "GraphDTO",
    "GraphStatsDTO",
    "GraphSummaryDTO",
    # Mappers
    "NodeMapper",
    "EdgeMapper",
    "GraphMapper",
    # Utility Functions
    "graph_to_json",
    "json_to_graph",
    "graph_to_dict",
    "dict_to_graph",
    "save_graph",
    "load_graph",
    "merge_graphs",
    "filter_graph",
    "clone_graph",
]
