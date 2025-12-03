"""
Webhook Notifications

Provides webhook notifications for crawler events.
Supports:
- HTTP/HTTPS webhooks via aiohttp
- Configurable events
- Async retry logic
- Event filtering
- Замінено requests на aiohttp для async HTTP
- Замінено time.sleep() на asyncio.sleep()
- Async delivery worker через asyncio.Task
- Async context manager підтримка
"""

import asyncio
import json
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

try:
    import aiohttp

    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

logger = logging.getLogger(__name__)


class WebhookEvent(str, Enum):
    """Supported webhook events."""

    CRAWL_STARTED = "crawl_started"
    CRAWL_FINISHED = "crawl_finished"
    CRAWL_PAUSED = "crawl_paused"
    CRAWL_ERROR = "crawl_error"
    PAGE_CRAWLED = "page_crawled"
    MILESTONE_REACHED = "milestone_reached"  # e.g., every 100 pages


class WebhookConfig:
    """
    Webhook configuration.

    Attributes:
        url: Webhook endpoint URL
        events: List of events to subscribe to
        secret: Optional secret for signature verification
        headers: Additional HTTP headers
        timeout: Request timeout in seconds
        max_retries: Maximum retry attempts
        retry_delay: Delay between retries in seconds
    """

    def __init__(
        self,
        url: str,
        events: List[WebhookEvent],
        secret: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 10,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """
        Initialize webhook config.

        Args:
            url: Webhook endpoint URL
            events: List of events to subscribe
            secret: Optional secret for HMAC signature
            headers: Additional headers
            timeout: Request timeout
            max_retries: Max retry attempts
            retry_delay: Delay between retries
        """
        self.url = url
        self.events = events
        self.secret = secret
        self.headers = headers or {}
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def should_trigger(self, event: WebhookEvent) -> bool:
        """
        Check if webhook should trigger for event.

        Args:
            event: Event type

        Returns:
            bool: True if should trigger
        """
        return event in self.events or WebhookEvent("*") in self.events


class WebhookManager:
    """
    Async-First manager для webhook notifications .

    Features:
    - Multiple webhook endpoints
    - Event filtering
    - Async retry logic з exponential backoff
    - Async delivery (asyncio.Task)
    - Event history tracking Використовує aiohttp та asyncio.sleep() замість blocking операцій.

    Example:
        >>> from graph_crawler.api.webhooks import WebhookManager, WebhookEvent
        >>>
        >>> manager = WebhookManager()
        >>> manager.add_webhook(
        ...     url='https://example.com/webhook',
        ...     events=[WebhookEvent.CRAWL_STARTED, WebhookEvent.CRAWL_FINISHED]
        ... )
        >>>
        >>> # Start async delivery
        >>> await manager.start()
        >>>
        >>> # Integrate з EventBus
        >>> event_bus.subscribe('crawl_started', manager.handle_event)
    """

    def __init__(self):
        """Initialize webhook manager."""
        self.webhooks: List[WebhookConfig] = []
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._delivery_task: Optional[asyncio.Task] = None
        self._running = False
        self._session: Optional[aiohttp.ClientSession] = None
        self._stats = {
            "total_sent": 0,
            "total_failed": 0,
            "total_retried": 0,
        }

        if not AIOHTTP_AVAILABLE:
            logger.warning("aiohttp not installed, webhook delivery will fail")

        logger.info("WebhookManager (async) initialized")

    def add_webhook(self, url: str, events: List[WebhookEvent], **kwargs):
        """
        Add webhook endpoint.

        Args:
            url: Webhook URL
            events: List of events to subscribe
            **kwargs: Additional WebhookConfig parameters
        """
        config = WebhookConfig(url, events, **kwargs)
        self.webhooks.append(config)

        logger.info(f"Added webhook: {url} for events: {events}")

    def remove_webhook(self, url: str):
        """
        Remove webhook endpoint.

        Args:
            url: Webhook URL to remove
        """
        self.webhooks = [w for w in self.webhooks if w.url != url]
        logger.info(f"Removed webhook: {url}")

    async def start(self):
        """
        Async start webhook delivery .

        Створює aiohttp session та запускає delivery worker.
        """
        if self._running:
            logger.warning("WebhookManager already running")
            return

        if not AIOHTTP_AVAILABLE:
            logger.error("Cannot start WebhookManager: aiohttp not installed")
            return

        self._running = True
        self._session = aiohttp.ClientSession()
        self._delivery_task = asyncio.create_task(self._delivery_worker())

        logger.info("WebhookManager delivery started")

    async def stop(self):
        """
        Async stop webhook delivery .
        """
        self._running = False

        if self._delivery_task:
            self._delivery_task.cancel()
            try:
                await self._delivery_task
            except asyncio.CancelledError:
                pass

        if self._session:
            await self._session.close()
            self._session = None

        logger.info("WebhookManager stopped")

    def handle_event(self, event_type: str, data: Dict[str, Any]):
        """
        Handle crawler event.

        Додає подію в чергу для async доставки.

        Args:
            event_type: Event type
            data: Event data
        """
        try:
            webhook_event = WebhookEvent(event_type)
        except ValueError:
            # Unknown event type, skip
            return

        # Queue event for delivery
        payload = {
            "event": event_type,
            "data": data,
            "timestamp": datetime.now().isoformat(),
        }

        try:
            self._event_queue.put_nowait(
                {
                    "webhook_event": webhook_event,
                    "payload": payload,
                }
            )
        except asyncio.QueueFull:
            logger.warning("Webhook event queue full, dropping event")

    async def _delivery_worker(self):
        """
        Async background worker для доставки webhooks .

        Використовує asyncio замість threading.
        """
        while self._running:
            try:
                # Чекаємо подію з таймаутом
                try:
                    event_data = await asyncio.wait_for(
                        self._event_queue.get(), timeout=0.1
                    )
                except asyncio.TimeoutError:
                    continue

                webhook_event = event_data["webhook_event"]
                payload = event_data["payload"]

                # Send to all matching webhooks
                for webhook in self.webhooks:
                    if webhook.should_trigger(webhook_event):
                        await self._send_webhook(webhook, payload)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Webhook delivery worker error: {e}")

    async def _send_webhook(self, webhook: WebhookConfig, payload: Dict[str, Any]):
        """
        Async send webhook notification з retry logic .

        Використовує aiohttp та asyncio.sleep() для non-blocking операцій.

        Args:
            webhook: Webhook configuration
            payload: Payload to send
        """
        if not self._session:
            logger.error("No aiohttp session available")
            return

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "GraphCrawler-Webhook/3.0.0",
            **webhook.headers,
        }

        # Add signature if secret provided
        if webhook.secret:
            import hashlib
            import hmac

            signature = hmac.new(
                webhook.secret.encode(), json.dumps(payload).encode(), hashlib.sha256
            ).hexdigest()
            headers["X-Webhook-Signature"] = signature

        # Async retry logic з exponential backoff
        for attempt in range(webhook.max_retries):
            try:
                async with self._session.post(
                    webhook.url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=webhook.timeout),
                ) as response:

                    if response.status < 300:
                        # Success
                        self._stats["total_sent"] += 1

                        logger.debug(
                            f"Webhook delivered to {webhook.url}: "
                            f"{payload['event']}"
                        )
                        return
                    else:
                        logger.warning(
                            f"Webhook failed (status {response.status}): "
                            f"{webhook.url}"
                        )

            except asyncio.TimeoutError:
                logger.warning(f"Webhook timeout: {webhook.url}")
            except aiohttp.ClientError as e:
                logger.error(f"Webhook client error: {webhook.url} - {e}")
            except Exception as e:
                logger.error(f"Webhook error: {webhook.url} - {e}")

            if attempt < webhook.max_retries - 1:
                delay = webhook.retry_delay * (2**attempt)
                await asyncio.sleep(delay)  # NON-BLOCKING!

                self._stats["total_retried"] += 1

        # All retries failed
        self._stats["total_failed"] += 1

        logger.error(
            f"Webhook failed after {webhook.max_retries} attempts: " f"{webhook.url}"
        )

    def get_stats(self) -> Dict[str, Any]:
        """
        Get webhook statistics.

        Returns:
            Dict з статистикою
        """
        return {
            **self._stats,
            "webhooks_count": len(self.webhooks),
            "queue_size": self._event_queue.qsize(),
        }

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()
        return False


# Global webhook manager instance
_webhook_manager: Optional[WebhookManager] = None


async def setup_webhooks() -> WebhookManager:
    """
    Async setup global webhook manager .

    Returns:
        WebhookManager: Global instance
    """
    global _webhook_manager

    if _webhook_manager is None:
        _webhook_manager = WebhookManager()
        await _webhook_manager.start()
        logger.info("Global webhook manager setup complete")

    return _webhook_manager


def get_webhook_manager() -> Optional[WebhookManager]:
    """
    Get global webhook manager.

    Returns:
        WebhookManager or None якщо не ініціалізовано
    """
    return _webhook_manager


async def integrate_webhooks_with_crawler(
    event_bus, webhook_configs: List[Dict[str, Any]]
):
    """
    Async integrate webhooks з GraphCrawler EventBus .

    Args:
        event_bus: EventBus instance
        webhook_configs: List of webhook configurations

    Example:
        >>> webhook_configs = [
        ...     {
        ...         'url': 'https://example.com/webhook',
        ...         'events': ['crawl_started', 'crawl_finished'],
        ...         'secret': 'my-secret-key',
        ...     }
        ... ]
        >>> await integrate_webhooks_with_crawler(event_bus, webhook_configs)
    """
    manager = await setup_webhooks()

    # Add webhooks
    for config in webhook_configs:
        manager.add_webhook(
            url=config["url"],
            events=[WebhookEvent(e) for e in config.get("events", [])],
            secret=config.get("secret"),
            headers=config.get("headers"),
        )

    # Subscribe to all events
    for event_type in WebhookEvent:
        event_bus.subscribe(event_type.value, manager.handle_event)

    logger.info(f"Webhooks integrated with {len(webhook_configs)} endpoints")
