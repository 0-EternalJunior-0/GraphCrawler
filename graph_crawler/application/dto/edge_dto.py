"""Edge Data Transfer Objects.

DTO для передачі даних про Edge між шарами.

ВАЖЛИВО: DTO тепер знаходяться в shared/dto/ для дотримання Clean Architecture.
Цей модуль реекспортує класи для backward compatibility.

Використання:
    # Рекомендовано (Clean Architecture):
    from graph_crawler.shared.dto import EdgeDTO, CreateEdgeDTO

    # Для backward compatibility:
    from graph_crawler.application.dto import EdgeDTO, CreateEdgeDTO
"""

# Re-export from shared layer for backward compatibility
from graph_crawler.shared.dto.edge_dto import (
    EdgeDTO,
    CreateEdgeDTO,
)

__all__ = [
    "EdgeDTO",
    "CreateEdgeDTO",
]
