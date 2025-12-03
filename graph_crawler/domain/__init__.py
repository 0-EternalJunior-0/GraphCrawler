"""
Domain Layer - Чисте ядро без зовнішніх залежностей.

Містить:
- Entities: Node, Edge, Graph
- Value Objects: Lifecycle, Config
- Interfaces: IDriver, IStorage, IPlugin
- Events: Domain events для event-driven архітектури

Принципи:
 Domain НЕ залежить від Infrastructure
 Залежності через інтерфейси (Dependency Inversion)
 Immutability де можливо
 Event-driven підхід
"""

from graph_crawler.domain.entities.edge import Edge
from graph_crawler.domain.entities.graph import Graph
from graph_crawler.domain.entities.graph_operations import GraphOperations
from graph_crawler.domain.entities.graph_statistics import GraphStatistics

# Entities
from graph_crawler.domain.entities.node import Node

# Events
from graph_crawler.domain.events import (
    CrawlCompletedEvent,
    CrawlStartedEvent,
    DomainEvent,
    EventType,
    NodeCreatedEvent,
    NodeScannedEvent,
    ProgressUpdateEvent,
)

# Value Objects
from graph_crawler.domain.value_objects.lifecycle import (
    NodeLifecycle,
    NodeLifecycleError,
)

__all__ = [
    # Entities
    "Node",
    "Edge",
    "Graph",
    "GraphOperations",
    "GraphStatistics",
    # Value Objects
    "NodeLifecycle",
    "NodeLifecycleError",
    # Events
    "EventType",
    "DomainEvent",
    "NodeCreatedEvent",
    "NodeScannedEvent",
    "CrawlStartedEvent",
    "CrawlCompletedEvent",
    "ProgressUpdateEvent",
]
