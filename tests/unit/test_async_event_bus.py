"""Async tests for event bus (v3.0).

"""

import pytest
import asyncio
from graph_crawler.domain.events.event_bus import EventBus
from graph_crawler.domain.events.events import CrawlerEvent, EventType


@pytest.mark.asyncio
async def test_event_bus_async_publish():
    """Test that EventBus.publish_async() works with async callbacks."""
    bus = EventBus()
    received_events = []
    
    async def async_handler(event):
        """Async event handler."""
        await asyncio.sleep(0.001)  # Simulate async work
        received_events.append(event)
    
    bus.subscribe(EventType.NODE_CREATED, async_handler)
    
    event = CrawlerEvent.create(
        EventType.NODE_CREATED,
        data={'url': 'https://example.com'}
    )
    
    await bus.publish_async(event)
    
    assert len(received_events) == 1
    assert received_events[0].data['url'] == 'https://example.com'


@pytest.mark.asyncio
async def test_event_bus_async_with_sync_callback():
    """Test that EventBus.publish_async() works with sync callbacks too."""
    bus = EventBus()
    received_events = []
    
    def sync_handler(event):
        """Sync event handler."""
        received_events.append(event)
    
    bus.subscribe(EventType.NODE_CREATED, sync_handler)
    
    event = CrawlerEvent.create(
        EventType.NODE_CREATED,
        data={'url': 'https://example.com'}
    )
    
    await bus.publish_async(event)
    
    assert len(received_events) == 1


@pytest.mark.asyncio
async def test_event_bus_mixed_callbacks():
    """Test that EventBus.publish_async() handles mixed sync/async callbacks."""
    bus = EventBus()
    sync_received = []
    async_received = []
    
    def sync_handler(event):
        sync_received.append(event)
    
    async def async_handler(event):
        await asyncio.sleep(0.001)
        async_received.append(event)
    
    bus.subscribe(EventType.NODE_CREATED, sync_handler)
    bus.subscribe(EventType.NODE_CREATED, async_handler)
    
    event = CrawlerEvent.create(
        EventType.NODE_CREATED,
        data={'url': 'https://example.com'}
    )
    
    await bus.publish_async(event)
    
    assert len(sync_received) == 1
    assert len(async_received) == 1
