"""Health-check and recheck logic for proxy backends."""

from __future__ import annotations

import logging
import time
from typing import List

import requests

from graph_crawler.domain.events import CrawlerEvent, EventType
from graph_crawler.extensions.middleware.proxy_models import ProxyInfo
from graph_crawler.shared.constants import (
    DEFAULT_PROXY_HEALTH_CHECK_TIMEOUT,
    DEFAULT_PROXY_HEALTH_CHECK_URL,
    DEFAULT_PROXY_RECHECK_INTERVAL,
    HTTP_OK,
)

logger = logging.getLogger(__name__)


def check_proxy_health(proxy_info: ProxyInfo, health_check_url: str, timeout: int, event_bus=None) -> bool:
    """Perform a single health-check for the given proxy.

    Returns ``True`` if the proxy is considered alive.
    """
    try:
        start_time = time.time()
        proxies_dict = {"http": proxy_info.url, "https": proxy_info.url}

        response = requests.get(
            health_check_url,
            proxies=proxies_dict,
            timeout=timeout,
            verify=False,
        )

        response_time = time.time() - start_time

        if response.status_code == HTTP_OK:
            proxy_info.is_alive = True
            proxy_info.mark_success(response_time)
            proxy_info.last_check_time = time.time()
            logger.debug(
                "Proxy %s is alive (response time: %.2fs)",
                proxy_info.url,
                response_time,
            )

            if event_bus:
                event_bus.publish(
                    CrawlerEvent.create(
                        EventType.PROXY_HEALTH_CHECK,
                        data={
                            "proxy_url": proxy_info.url,
                            "is_alive": True,
                            "response_time": response_time,
                            "status_code": response.status_code,
                        },
                    )
                )
            return True

        proxy_info.is_alive = False
        proxy_info.mark_failure()
        logger.warning("Proxy %s returned status %s", proxy_info.url, response.status_code)

        if event_bus:
            event_bus.publish(
                CrawlerEvent.create(
                    EventType.PROXY_FAILED,
                    data={
                        "proxy_url": proxy_info.url,
                        "reason": f"Bad status code: {response.status_code}",
                        "status_code": response.status_code,
                    },
                )
            )
        return False

    except Exception as exc:  # pragma: no cover - defensive path
        proxy_info.is_alive = False
        proxy_info.mark_failure()
        proxy_info.last_check_time = time.time()
        logger.debug("Proxy %s health check failed: %s", proxy_info.url, exc)

        if event_bus:
            event_bus.publish(
                CrawlerEvent.create(
                    EventType.PROXY_FAILED,
                    data={
                        "proxy_url": proxy_info.url,
                        "reason": str(exc),
                        "error_type": type(exc).__name__,
                    },
                )
            )
        return False


def initial_health_check(proxies: List[ProxyInfo], config: dict, event_bus=None) -> None:
    """Run initial health-check across all proxies if enabled in config."""
    health_check_url = config.get("health_check_url", DEFAULT_PROXY_HEALTH_CHECK_URL)
    timeout = config.get("health_check_timeout", DEFAULT_PROXY_HEALTH_CHECK_TIMEOUT)

    for proxy_info in proxies:
        check_proxy_health(proxy_info, health_check_url, timeout, event_bus)


def recheck_dead_proxies(proxies: List[ProxyInfo], config: dict, last_recheck_time: float, event_bus=None) -> float:
    """Re-check dead proxies according to configured interval.

    Returns updated ``last_recheck_time``.
    """
    recheck_interval = config.get("recheck_interval", DEFAULT_PROXY_RECHECK_INTERVAL)
    current_time = time.time()

    if current_time - last_recheck_time < recheck_interval:
        return last_recheck_time

    dead_proxies = [p for p in proxies if not p.is_alive]

    if event_bus and dead_proxies:
        event_bus.publish(
            CrawlerEvent.create(
                EventType.PROXY_RECHECK,
                data={
                    "dead_proxies_count": len(dead_proxies),
                    "proxy_urls": [p.url for p in dead_proxies],
                },
            )
        )

    for proxy_info in dead_proxies:
        check_proxy_health(proxy_info, health_check_url=DEFAULT_PROXY_HEALTH_CHECK_URL, timeout=recheck_interval, event_bus=event_bus)

    return current_time


__all__ = ["ProxyInfo", "check_proxy_health", "initial_health_check", "recheck_dead_proxies"]
