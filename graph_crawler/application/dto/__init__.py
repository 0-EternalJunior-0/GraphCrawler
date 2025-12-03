"""Data Transfer Objects (DTO) для GraphCrawler.

DTO використовуються для передачі даних між шарами архітектури:
- Domain Layer (entities) ↔ Application Layer (use cases)
- Application Layer ↔ Infrastructure Layer (persistence, API)

Переваги DTO:
1. Ізоляція domain entities від зовнішніх шарів
2. Версіонування API без breaking changes
3. Простіше тестування (легко мокати)
4. Безпека (приховування internal полів)
5. Стабільні API contracts

Приклад використання:
    >>> from graph_crawler.application.dto import NodeDTO, GraphDTO
    >>> from graph_crawler.application.dto.mappers import NodeMapper, GraphMapper
    >>>
    >>> # Domain → DTO
    >>> node_dto = NodeMapper.to_dto(node)
    >>>
    >>> # DTO → Domain
    >>> node = NodeMapper.to_domain(node_dto)
    >>>
    >>> # Utility functions
    >>> from graph_crawler.application.dto import (
    ...     graph_to_json, json_to_graph, save_graph, load_graph
    ... )
    >>> json_str = graph_to_json(graph)
    >>> graph = json_to_graph(json_str)
"""

from graph_crawler.application.dto.node_dto import (
    NodeDTO,
    CreateNodeDTO,
    NodeMetadataDTO,
)
from graph_crawler.application.dto.edge_dto import (
    EdgeDTO,
    CreateEdgeDTO,
)
from graph_crawler.application.dto.graph_dto import (
    GraphDTO,
    GraphStatsDTO,
    GraphSummaryDTO,
)

# Mappers для конвертації Domain ↔ DTO
from graph_crawler.application.dto.mappers import (
    NodeMapper,
    EdgeMapper,
    GraphMapper,
)

# Utility functions
from graph_crawler.application.dto.utils import (
    graph_to_json,
    json_to_graph,
    graph_to_dict,
    dict_to_graph,
    save_graph,
    load_graph,
    merge_graphs,
    filter_graph,
    clone_graph,
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
