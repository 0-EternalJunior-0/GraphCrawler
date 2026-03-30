"""Node Data Transfer Objects.

DTO для передачі даних про Node між шарами.

ВАЖЛИВО: DTO тепер знаходяться в shared/dto/ для дотримання Clean Architecture.
Цей модуль реекспортує класи для backward compatibility.

Використання:
    # Рекомендовано (Clean Architecture):
    from graph_crawler.shared.dto import NodeDTO, CreateNodeDTO, NodeMetadataDTO

    # Для backward compatibility:
    from graph_crawler.application.dto import NodeDTO, CreateNodeDTO, NodeMetadataDTO
"""

# Re-export from shared layer for backward compatibility
from graph_crawler.shared.dto.node_dto import (
    CreateNodeDTO,
    NodeDTO,
    NodeMetadataDTO,
)

__all__ = [
    "NodeDTO",
    "CreateNodeDTO",
    "NodeMetadataDTO",
]
