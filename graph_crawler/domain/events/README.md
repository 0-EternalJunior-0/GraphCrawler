# Event Bus System

Система подій для GraphCrawler (Observer Pattern).

## EventType

```python
class EventType(str, Enum):
    # Node події
    NODE_CREATED = "node_created"
    NODE_SCAN_STARTED = "node_scan_started"
    NODE_SCANNED = "node_scanned"
    NODE_FAILED = "node_failed"
    
    # Edge події
    EDGE_CREATED = "edge_created"
    
    # Crawler події
    CRAWL_STARTED = "crawl_started"
    CRAWL_COMPLETED = "crawl_completed"
    
    # Error події
    ERROR_OCCURRED = "error_occurred"
    
    # Fetch події
    FETCH_STARTED = "fetch_started"
    FETCH_SUCCESS = "fetch_success"
    FETCH_ERROR = "fetch_error"
    
    # Plugin події
    PLUGIN_STARTED = "plugin_started"
    PLUGIN_COMPLETED = "plugin_completed"
    PLUGIN_FAILED = "plugin_failed"
```

## Використання

```python
from graph_crawler.core.events import EventBus, EventType, CrawlerEvent

bus = EventBus()

def on_node_scanned(event: CrawlerEvent):
    print(f"Scanned: {event.data['url']}")

bus.subscribe(EventType.NODE_SCANNED, on_node_scanned)
```

## CrawlerEvent

```python
@dataclass
class CrawlerEvent:
    event_type: EventType
    timestamp: datetime
    data: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None
    
    @classmethod
    def create(cls, event_type: EventType, data: Dict[str, Any] = None):
        return cls(
            event_type=event_type,
            timestamp=datetime.now(),
            data=data or {}
        )
    
    def to_dict(self) -> Dict[str, Any]: ...
```
