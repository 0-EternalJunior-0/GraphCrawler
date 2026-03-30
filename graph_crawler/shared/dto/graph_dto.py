"""Graph Data Transfer Objects."""

from typing import List

from pydantic import BaseModel, ConfigDict, Field

from graph_crawler.shared.dto.edge_dto import EdgeDTO
from graph_crawler.shared.dto.node_dto import NodeDTO


class GraphStatsDTO(BaseModel):
    """DTO для статистики Graph."""

    total_nodes: int = Field(ge=0, description="Загальна кількість нод")
    scanned_nodes: int = Field(ge=0, description="Кількість просканованих нод")
    unscanned_nodes: int = Field(ge=0, description="Кількість непросканованих нод")
    total_edges: int = Field(ge=0, description="Загальна кількість edges")
    avg_depth: float = Field(ge=0.0, description="Середня глибина")
    max_depth: int = Field(ge=0, description="Максимальна глибина")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_nodes": 100,
                "scanned_nodes": 75,
                "unscanned_nodes": 25,
                "total_edges": 250,
                "avg_depth": 2.5,
                "max_depth": 5,
            }
        }
    )


class GraphDTO(BaseModel):
    """DTO для передачі даних про Graph між шарами."""

    nodes: List[NodeDTO] = Field(description="Список нод у графі")
    edges: List[EdgeDTO] = Field(description="Список edges у графі")
    stats: GraphStatsDTO = Field(description="Статистика графу")

    model_config = ConfigDict(
        json_schema_extra={
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
    )


class GraphSummaryDTO(BaseModel):
    """Спрощений DTO для Graph (для API responses)."""

    total_nodes: int = Field(ge=0)
    total_edges: int = Field(ge=0)
    root_url: str
    crawl_completed: bool

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_nodes": 100,
                "total_edges": 250,
                "root_url": "https://example.com",
                "crawl_completed": True,
            }
        }
    )
