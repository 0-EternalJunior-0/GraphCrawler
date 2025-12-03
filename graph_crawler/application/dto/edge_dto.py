"""Edge Data Transfer Objects.

DTO для передачі даних про Edge між шарами.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class EdgeDTO(BaseModel):
    """
    Data Transfer Object для Edge.

    Використовується для передачі даних про Edge між шарами.
    Представляє зв'язок між двома нодами.

    Attributes:
        edge_id: Унікальний ID edge
        source_node_id: ID ноди-джерела
        target_node_id: ID цільової ноди
        metadata: Додаткові метадані edge
        created_at: Час створення edge

    Example:
        >>> edge_dto = EdgeDTO(
        ...     edge_id="edge-123",
        ...     source_node_id="node-1",
        ...     target_node_id="node-2",
        ...     metadata={"link_type": ["internal", "deeper"]},
        ...     created_at=datetime.now()
        ... )
    """

    edge_id: str
    source_node_id: str = Field(description="ID ноди-джерела")
    target_node_id: str = Field(description="ID цільової ноди")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Метадані edge"
    )
    created_at: datetime = Field(description="Час створення edge")

    class Config:
        """Pydantic конфігурація."""

        json_schema_extra = {
            "example": {
                "edge_id": "edge-550e8400-e29b-41d4-a716-446655440000",
                "source_node_id": "node-550e8400-e29b-41d4-a716-446655440001",
                "target_node_id": "node-550e8400-e29b-41d4-a716-446655440002",
                "metadata": {
                    "link_type": ["internal", "deeper"],
                    "depth_diff": 1,
                    "target_scanned": False,
                },
                "created_at": "2024-12-03T10:30:00",
            }
        }


class CreateEdgeDTO(BaseModel):
    """
    DTO для створення нового Edge.

    Містить мінімальний набір полів для створення edge.

    Attributes:
        source_node_id: ID ноди-джерела (обов'язково)
        target_node_id: ID цільової ноди (обов'язково)
        metadata: Додаткові метадані (optional)

    Example:
        >>> create_dto = CreateEdgeDTO(
        ...     source_node_id="node-1",
        ...     target_node_id="node-2",
        ...     metadata={"link_type": ["internal"]}
        ... )
    """

    source_node_id: str
    target_node_id: str
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        """Pydantic конфігурація."""

        json_schema_extra = {
            "example": {
                "source_node_id": "node-550e8400-e29b-41d4-a716-446655440001",
                "target_node_id": "node-550e8400-e29b-41d4-a716-446655440002",
                "metadata": {"link_type": ["internal", "deeper"]},
            }
        }
