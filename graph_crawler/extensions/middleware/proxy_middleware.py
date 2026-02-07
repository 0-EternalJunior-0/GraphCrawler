"""Proxy Rotation Middleware - ротація проксі з health checks та automatic failover.

Цей модуль тепер тонший: вся модель, health-check логіка та стратегії
вибору проксі винесені у відповідні підмодулі. Це зменшує кількість
відповідальностей одного файлу та краще відповідає SOLID.
"""

from __future__ import annotations

import logging
from typing import Optional

import requests

from graph_crawler.extensions.middleware.base import (
    BaseMiddleware,
    MiddlewareContext,
    MiddlewareType,
)
from graph_crawler.extensions.middleware.proxy_health import (
    initial_health_check,
    recheck_dead_proxies,
)
from graph_crawler.extensions.middleware.proxy_models import ProxyInfo
from graph_crawler.extensions.middleware.proxy_selection import select_next_proxy
from graph_crawler.shared.constants import (
    DEFAULT_MIN_SUCCESS_RATE,
    MIN_REQUESTS_FOR_STATS,
)

logger = logging.getLogger(__name__)


class ProxyRotationMiddleware(BaseMiddleware):
    """Async middleware для ротації проксі з health checks та автоматичним failover."""

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self.proxies: list[ProxyInfo] = []
        self.current_index: int = 0
        self.sticky_proxy: Optional[ProxyInfo] = None
        self.last_recheck_time: float = 0.0

    @property
    def middleware_type(self) -> MiddlewareType:
        return MiddlewareType.PRE_REQUEST

    @property
    def name(self) -> str:
        return "proxy_rotation"

    async def setup(self) -> None:
        proxy_list = self.config.get("proxy_list", [])
        if not proxy_list:
            logger.warning("Proxy list is empty - middleware will be disabled")
            self.enabled = False
            return

        self.proxies = [ProxyInfo(url=p) for p in proxy_list]
        logger.info("Initialized %s proxies", len(self.proxies))

        if self.config.get("check_health", True):
            logger.info("Running initial health checks...")
            initial_health_check(self.proxies, self.config, self.event_bus)
            alive_count = sum(1 for p in self.proxies if p.is_alive)
            logger.info(
                "Health check complete: %s/%s proxies alive",
                alive_count,
                len(self.proxies),
            )
            if alive_count == 0:
                logger.error("No alive proxies found - middleware will be disabled")
                self.enabled = False

        if self.config.get("rotation_strategy", "round_robin") == "sticky":
            self.sticky_proxy, _, _ = select_next_proxy(
                self.proxies,
                self.config,
                self.current_index,
                self.sticky_proxy,
            )
            if self.sticky_proxy:
                logger.info("Sticky mode: using proxy %s", self.sticky_proxy.url)

    async def process(self, context: MiddlewareContext) -> MiddlewareContext:
        if not self.enabled or not self.proxies:
            return context

        # Periodic re-check of dead proxies
        if self.config.get("auto_failover", True):
            self.last_recheck_time = recheck_dead_proxies(
                self.proxies, self.config, self.last_recheck_time, self.event_bus
            )

        proxy, self.current_index, self.sticky_proxy = select_next_proxy(
            self.proxies,
            self.config,
            self.current_index,
            self.sticky_proxy,
        )

        if proxy is None:
            logger.warning("No proxy available for request")
            return context

        context.metadata["proxy"] = {
            "url": proxy.url,
            "success_rate": proxy.success_rate,
            "avg_response_time": proxy.avg_response_time,
            "total_requests": proxy.total_requests,
        }
        context.metadata["proxy_url"] = proxy.url

        proxy.total_requests += 1
        logger.debug(
            "Using proxy: %s (success_rate: %.2f, requests: %s)",
            proxy.url,
            proxy.success_rate,
            proxy.total_requests,
        )

        if self.event_bus:
            from graph_crawler.domain.events import CrawlerEvent, EventType

            self.event_bus.publish(
                CrawlerEvent.create(
                    EventType.PROXY_SELECTED,
                    data={
                        "proxy_url": proxy.url,
                        "url": context.url,
                        "success_rate": proxy.success_rate,
                        "avg_response_time": proxy.avg_response_time,
                        "total_requests": proxy.total_requests,
                        "strategy": self.config.get("rotation_strategy", "round_robin"),
                    },
                )
            )

        return context

    def report_success(self, proxy_url: str, response_time: float = 0.0) -> None:
        for proxy in self.proxies:
            if proxy.url == proxy_url:
                proxy.mark_success(response_time)
                break

    def report_failure(self, proxy_url: str) -> None:
        auto_failover = self.config.get("auto_failover", True)

        for proxy in self.proxies:
            if proxy.url == proxy_url:
                proxy.mark_failure()

                if auto_failover and proxy.total_requests >= MIN_REQUESTS_FOR_STATS:
                    min_success_rate = self.config.get(
                        "min_success_rate", DEFAULT_MIN_SUCCESS_RATE
                    )
                    if proxy.success_rate < min_success_rate:
                        proxy.is_alive = False
                        logger.warning(
                            "Proxy %s disabled due to low success rate (%.2f)",
                            proxy_url,
                            proxy.success_rate,
                        )

                        if self.event_bus:
                            from graph_crawler.domain.events import (
                                CrawlerEvent,
                                EventType,
                            )

                            self.event_bus.publish(
                                CrawlerEvent.create(
                                    EventType.PROXY_DISABLED,
                                    data={
                                        "proxy_url": proxy_url,
                                        "reason": "low_success_rate",
                                        "success_rate": proxy.success_rate,
                                        "min_success_rate": min_success_rate,
                                        "total_requests": proxy.total_requests,
                                        "success_count": proxy.success_count,
                                        "failure_count": proxy.failure_count,
                                    },
                                ),
                            )
                break

    def get_stats(self) -> dict:
        alive_proxies = [p for p in self.proxies if p.is_alive]
        proxy_stats = [
            {
                "url": proxy.url,
                "is_alive": proxy.is_alive,
                "success_rate": proxy.success_rate,
                "success_count": proxy.success_count,
                "failure_count": proxy.failure_count,
                "total_requests": proxy.total_requests,
                "avg_response_time": proxy.avg_response_time,
            }
            for proxy in self.proxies
        ]

        return {
            "total_proxies": len(self.proxies),
            "alive_proxies": len(alive_proxies),
            "dead_proxies": len(self.proxies) - len(alive_proxies),
            "rotation_strategy": self.config.get("rotation_strategy", "round_robin"),
            "proxies": proxy_stats,
        }

    def reset_stats(self) -> None:
        for proxy in self.proxies:
            proxy.reset_stats()
