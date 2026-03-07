"""Shared Data Transfer Objects (DTO) для GraphCrawler.

DTO знаходяться в shared layer щоб:
- Infrastructure Layer міг використовувати DTO без залежності від Application
- Application Layer міг використовувати DTO через реекспорт
- Зберегти Clean Architecture принципи

Всі DTO - Pydantic моделі для валідації та серіалізації.
"""

from graph_crawler.shared.dto.node_dto import (
    NodeDTO,
    CreateNodeDTO,
    NodeMetadataDTO,
)
from graph_crawler.shared.dto.edge_dto import (
    EdgeDTO,
    CreateEdgeDTO,
)
from graph_crawler.shared.dto.graph_dto import (
    GraphDTO,
    GraphStatsDTO,
    GraphSummaryDTO,
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
]
