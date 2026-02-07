"""Graph Data Transfer Objects.

DTO для передачі даних про Graph між шарами.
"""

from typing import List

from pydantic import BaseModel, Field

from graph_crawler.application.dto.edge_dto import EdgeDTO
from graph_crawler.application.dto.node_dto import NodeDTO


class GraphStatsDTO(BaseModel):
    """
    DTO для статистики Graph.

    Містить основні показники графу без self граф даних.

    Attributes:
        total_nodes: Загальна кількість нод
        scanned_nodes: Кількість просканованих нод
        unscanned_nodes: Кількість непросканованих нод
        total_edges: Загальна кількість edges
        avg_depth: Середня глибина нод
        max_depth: Максимальна глибина

    Example:
        >>> stats = GraphStatsDTO(
        ...     total_nodes=100,
        ...     scanned_nodes=75,
        ...     unscanned_nodes=25,
        ...     total_edges=250,
        ...     avg_depth=2.5,
        ...     max_depth=5
        ... )
    """

    total_nodes: int = Field(ge=0, description="Загальна кількість нод")
    scanned_nodes: int = Field(ge=0, description="Кількість просканованих нод")
    unscanned_nodes: int = Field(ge=0, description="Кількість непросканованих нод")
    total_edges: int = Field(ge=0, description="Загальна кількість edges")
    avg_depth: float = Field(ge=0.0, description="Середня глибина")
    max_depth: int = Field(ge=0, description="Максимальна глибина")

    class Config:
        """Pydantic конфігурація."""

        json_schema_extra = {
            "example": {
                "total_nodes": 100,
                "scanned_nodes": 75,
                "unscanned_nodes": 25,
                "total_edges": 250,
                "avg_depth": 2.5,
                "max_depth": 5,
            }
        }


class GraphDTO(BaseModel):
    """
    Data Transfer Object для Graph.

    Використовується для передачі даних про граф між шарами.
    Містить всі ноди, edges та статистику.

    Attributes:
        nodes: Список нод у графі
        edges: Список edges у графі
        stats: Статистика графу

    Example:
        >>> graph_dto = GraphDTO(
        ...     nodes=[node_dto1, node_dto2],
        ...     edges=[edge_dto1],
        ...     stats=GraphStatsDTO(...)
        ... )
    """

    nodes: List[NodeDTO] = Field(description="Список нод у графі")
    edges: List[EdgeDTO] = Field(description="Список edges у графі")
    stats: GraphStatsDTO = Field(description="Статистика графу")

    class Config:
        """Pydantic конфігурація."""

        json_schema_extra = {
            "example": {
                "nodes": [
                    {
                        "node_id": "node-1",
                        "url": "https://example.com",
                        "depth": 0,
                        "should_scan": True,
                        "can_create_edges": True,
                        "scanned": True,
                        "response_status": 200,
                        "metadata": {"title": "Example"},
                        "user_data": {},
                        "created_at": "2024-12-03T10:30:00",
                        "lifecycle_stage": "html_stage",
                    }
                ],
                "edges": [
                    {
                        "edge_id": "edge-1",
                        "source_node_id": "node-1",
                        "target_node_id": "node-2",
                        "metadata": {"link_type": ["internal"]},
                        "created_at": "2024-12-03T10:30:01",
                    }
                ],
                "stats": {
                    "total_nodes": 2,
                    "scanned_nodes": 1,
                    "unscanned_nodes": 1,
                    "total_edges": 1,
                    "avg_depth": 0.5,
                    "max_depth": 1,
                },
            }
        }


class GraphSummaryDTO(BaseModel):
    """
    Спрощений DTO для Graph (без повних даних).

    Використовується для легких відповідей API коли не потрібен повний граф.
    Містить тільки основну інформацію.

    Attributes:
        total_nodes: Загальна кількість нод
        total_edges: Загальна кількість edges
        root_url: Кореневий URL (початок краулінгу)
        crawl_completed: Чи завершено краулінг

    Example:
        >>> summary = GraphSummaryDTO(
        ...     total_nodes=100,
        ...     total_edges=250,
        ...     root_url="https://example.com",
        ...     crawl_completed=True
        ... )
    """

    total_nodes: int = Field(ge=0)
    total_edges: int = Field(ge=0)
    root_url: str
    crawl_completed: bool

    class Config:
        """Pydantic конфігурація."""

        json_schema_extra = {
            "example": {
                "total_nodes": 100,
                "total_edges": 250,
                "root_url": "https://example.com",
                "crawl_completed": True,
            }
        }
