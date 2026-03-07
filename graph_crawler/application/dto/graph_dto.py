"""Graph Data Transfer Objects.

DTO для передачі даних про Graph між шарами.

ВАЖЛИВО: DTO тепер знаходяться в shared/dto/ для дотримання Clean Architecture.
Цей модуль реекспортує класи для backward compatibility.

Використання:
    # Рекомендовано (Clean Architecture):
    from graph_crawler.shared.dto import GraphDTO, GraphStatsDTO, GraphSummaryDTO

    # Для backward compatibility:
    from graph_crawler.application.dto import GraphDTO, GraphStatsDTO, GraphSummaryDTO
"""

# Re-export from shared layer for backward compatibility
from graph_crawler.shared.dto.graph_dto import (
    GraphDTO,
    GraphStatsDTO,
    GraphSummaryDTO,
)

__all__ = [
    "GraphDTO",
    "GraphStatsDTO",
    "GraphSummaryDTO",
]
