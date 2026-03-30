"""Extensions Module для GraphCrawler.

Critical extensions для production stability:
- MemoryGuard: Моніторинг пам'яті з auto-shutdown
- StateManager: Збереження стану для resume capability
"""

from graph_crawler.observability.extensions.memory_guard import (
    MemoryGuard,
    MemoryGuardConfig,
)
from graph_crawler.observability.extensions.state_manager import StateManager

__all__ = [
    "MemoryGuard",
    "MemoryGuardConfig",
    "StateManager",
]
