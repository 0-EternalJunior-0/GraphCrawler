"""Proxy selection strategies for the proxy middleware."""

from __future__ import annotations

import logging
import random
from typing import Dict, List, Optional

from graph_crawler.extensions.middleware.proxy_models import ProxyInfo
from graph_crawler.shared.constants import (
    DEFAULT_MIN_SUCCESS_RATE,
    MIN_REQUESTS_FOR_STATS,
)

logger = logging.getLogger(__name__)


def filter_alive(proxies: List[ProxyInfo]) -> List[ProxyInfo]:
    return [p for p in proxies if p.is_alive]


def filter_good(proxies: List[ProxyInfo], min_success_rate: float) -> List[ProxyInfo]:
    good: List[ProxyInfo] = []
    for p in proxies:
        if p.success_rate >= min_success_rate or p.total_requests < MIN_REQUESTS_FOR_STATS:
            good.append(p)
    return good


def select_best_proxy(proxies: List[ProxyInfo]) -> Optional[ProxyInfo]:
    """Select the best proxy based on success-rate and response time."""
    alive = filter_alive(proxies)
    if not alive:
        return None

    alive.sort(key=lambda p: (p.success_rate, -p.avg_response_time), reverse=True)
    return alive[0]


def select_next_proxy(
    proxies: List[ProxyInfo],
    config: Dict,
    current_index: int,
    sticky_proxy: Optional[ProxyInfo],
) -> tuple[Optional[ProxyInfo], int, Optional[ProxyInfo]]:
    """Select next proxy according to rotation strategy.

    Returns a tuple of ``(selected_proxy, new_index, new_sticky_proxy)``.
    """
    strategy = config.get("rotation_strategy", "round_robin")
    min_success_rate = config.get("min_success_rate", DEFAULT_MIN_SUCCESS_RATE)

    alive_proxies = filter_alive(proxies)
    if not alive_proxies:
        logger.error("No alive proxies available")
        return None, current_index, sticky_proxy

    good_proxies = filter_good(alive_proxies, min_success_rate)
    if not good_proxies:
        good_proxies = alive_proxies

    if strategy == "sticky":
        if sticky_proxy and sticky_proxy.is_alive:
            return sticky_proxy, current_index, sticky_proxy
        new_sticky = select_best_proxy(good_proxies)
        return new_sticky, current_index, new_sticky

    if strategy == "round_robin":
        proxy = good_proxies[current_index % len(good_proxies)]
        return proxy, current_index + 1, sticky_proxy

    if strategy == "random":
        return random.choice(good_proxies), current_index, sticky_proxy

    if strategy == "weighted":
        weights = [p.success_rate for p in good_proxies]
        total_weight = sum(weights)
        if total_weight == 0:
            return random.choice(good_proxies), current_index, sticky_proxy
        weights = [w / total_weight for w in weights]
        proxy = random.choices(good_proxies, weights=weights)[0]
        return proxy, current_index, sticky_proxy

    # default fallback
    proxy = good_proxies[current_index % len(good_proxies)]
    return proxy, current_index + 1, sticky_proxy


__all__ = ["select_best_proxy", "select_next_proxy"]
