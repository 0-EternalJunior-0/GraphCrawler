"""Event System для GraphCrawler."""

from graph_crawler.domain.events.event_bus import EventBus
from graph_crawler.domain.events.events import (
    CrawlerEvent,
    EventType,
)

# Алі аси для зручності
DomainEvent = CrawlerEvent
NodeCreatedEvent = CrawlerEvent
NodeScannedEvent = CrawlerEvent
CrawlStartedEvent = CrawlerEvent
CrawlCompletedEvent = CrawlerEvent
ProgressUpdateEvent = CrawlerEvent

__all__ = [
    "EventBus",
    "CrawlerEvent",
    "EventType",
    "DomainEvent",
    "NodeCreatedEvent",
    "NodeScannedEvent",
    "CrawlStartedEvent",
    "CrawlCompletedEvent",
    "ProgressUpdateEvent",
]
