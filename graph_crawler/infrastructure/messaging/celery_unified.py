"""Unified Celery Application для distributed crawling.

Description:
    Раніше було 2 Celery apps з різними чергами:
    - celery_app.py → queue: 'graph_crawler' (1 URL per task, DEPRECATED)
    - celery_batch.py → queue: 'graph_crawler_batch' (batch tasks, RECOMMENDED)

    Це призводило до:
    - Воркер для одного app НЕ бачив tasks іншого
    - Потрібно запускати різні команди для різних режимів
    - Плутанина в документації

РІШЕННЯ:
    Один Celery app з двома типами tasks:
    - crawl_page (legacy, для зворотної сумісності)
    - crawl_batch (recommended, 24x швидше)

    Обидва типи tasks використовують ОДНУ чергу: 'graph_crawler'

ВИКОРИСТАННЯ:
    # Worker (обробляє всі типи tasks)
    celery -A graph_crawler.celery_unified worker --loglevel=info

    # Або з явною чергою
    celery -A graph_crawler.celery_unified worker -Q graph_crawler --loglevel=info

МІГРАЦІЯ:
    Старий код:
        from graph_crawler.celery_app import celery, crawl_page_task
        from graph_crawler.celery_batch import celery_batch, crawl_batch_task

    Новий код:
        from graph_crawler.infrastructure.messaging.celery_unified import celery, crawl_page_task, crawl_batch_task
"""

import asyncio
import inspect
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from celery import Celery

# Безпечне логування URL
from graph_crawler.shared.security.url_sanitizer import sanitize_url

logger = logging.getLogger(__name__)

# =====================================
# Celery App Configuration
# =====================================

from graph_crawler.shared.utils.celery_config import (
    get_backend_url,
    get_broker_url,
)

BROKER_URL = get_broker_url()
BACKEND_URL = get_backend_url()

# Створюємо ОДИН Celery app для всіх tasks
celery = Celery(
    "graph_crawler.unified",
    broker=BROKER_URL,
    backend=BACKEND_URL,
)

# Конфігурація Celery (універсальна)
celery.conf.update(
    {
        # Serialization
        "task_serializer": "json",
        "result_serializer": "json",
        "accept_content": ["json"],
        # Timezone
        "timezone": "UTC",
        "enable_utc": True,
        # Task settings - ОДНА черга для всіх tasks
        "task_default_queue": "graph_crawler",
        "task_time_limit": 1200,  # 20 хвилин (для batch tasks)
        "task_soft_time_limit": 1140,  # 19 хвилин
        # Result settings
        "result_expires": 3600,  # 1 година
        # Worker settings - оптимізовано для batch
        "worker_prefetch_multiplier": 4,
        "worker_concurrency": 2,
    }
)

# =====================================
# Helper Functions
# =====================================

from graph_crawler.shared.utils.celery_helpers import (
    create_driver_from_config as _create_driver_from_config,
)
from graph_crawler.shared.utils.celery_helpers import import_class as _import_class
from graph_crawler.shared.utils.celery_helpers import import_plugin as _import_plugin

# =====================================
# TASK 1: crawl_page (Legacy, для зворотної сумісності)
# =====================================


@celery.task(name="graph_crawler.crawl_page", bind=True, max_retries=3)
def crawl_page_task(self, url: str, depth: int, config_dict: dict) -> Dict[str, Any]:
    """
    Legacy Celery task для краулінгу однієї сторінки.

     DEPRECATED: Використовуйте crawl_batch_task для кращої продуктивності!

    Цей task залишено для зворотної сумісності з існуючим кодом.

    Args:
        url: URL сторінки
        depth: Глибина сторінки
        config_dict: Конфігурація

    Returns:
        Dict з node_data, edges_data, new_urls, success
    """
    import warnings

    warnings.warn(
        "crawl_page_task is deprecated. Use crawl_batch_task for 24x better performance.",
        DeprecationWarning,
    )

    from graph_crawler.application.use_cases.crawling.spider import GraphSpider
    from graph_crawler.domain.entities.edge import Edge
    from graph_crawler.domain.entities.node import Node
    from graph_crawler.domain.value_objects.configs import CrawlerConfig
    from graph_crawler.infrastructure.persistence.memory_storage import MemoryStorage
    from graph_crawler.infrastructure.transport.sync.requests_driver import (
        RequestsDriver,
    )
    from graph_crawler.shared.utils.url_utils import URLUtils

    try:
        logger.info(f"[LEGACY] Crawling single URL: {url} (depth={depth})")

        # Десеріалізація конфігу
        plugin_paths = config_dict.pop("_plugin_paths", [])
        custom_node_class_path = config_dict.pop("_custom_node_class", None)
        driver_config = config_dict.pop("_driver_config", None)

        config = CrawlerConfig(**config_dict)

        # Плагіни
        plugins = []
        for plugin_path in plugin_paths:
            plugin = _import_plugin(plugin_path)
            if plugin:
                plugins.append(plugin)
        config.node_plugins = plugins if plugins else None

        # Node class
        if custom_node_class_path:
            node_class = _import_class(custom_node_class_path) or Node
        else:
            node_class = config.custom_node_class if config.custom_node_class else Node

        # Driver
        if driver_config:
            driver = _create_driver_from_config(driver_config)
        else:
            try:
                from graph_crawler.infrastructure.transport.async_http.driver import (
                    AsyncDriver,
                )

                driver = AsyncDriver(config.get_driver_params())
            except ImportError:
                driver = RequestsDriver(config.get_driver_params())

        # Spider
        storage = MemoryStorage()
        spider = GraphSpider(config, driver, storage)

        # Node та сканування
        node = node_class(
            url=url, depth=depth, plugin_manager=spider.node_plugin_manager
        )

        if inspect.iscoroutinefunction(spider.scanner.scan_node):
            links = asyncio.run(spider.scanner.scan_node(node))
        else:
            links = spider.scanner.scan_node(node)

        # Результат
        node_data = node.model_dump()
        edges_data = []
        new_urls = []

        if links:
            for link_url in links:
                if not spider.domain_filter.is_allowed(link_url):
                    continue
                if not spider.path_filter.is_allowed(link_url):
                    continue

                normalized_url = URLUtils.normalize_url(link_url)
                edge = Edge(source_node_id=node.node_id, target_node_id=normalized_url)
                edges_data.append(edge.model_dump())
                new_urls.append((normalized_url, depth + 1))

        # Закриваємо driver
        if inspect.iscoroutinefunction(driver.close):
            asyncio.run(driver.close())
        else:
            driver.close()

        logger.info(f"[LEGACY] Completed: {url}, {len(new_urls)} links")

        return {
            "node_data": node_data,
            "edges_data": edges_data,
            "new_urls": new_urls,
            "success": True,
        }

    except Exception as e:
        logger.error(f"[LEGACY] Failed for {url}: {e}")
        raise self.retry(exc=e, countdown=2**self.request.retries)


# =====================================
# TASK 2: crawl_batch (RECOMMENDED)
# =====================================


@celery.task(name="graph_crawler.crawl_batch", bind=True, max_retries=3)
def crawl_batch_task(
    self,
    urls_with_depth: List[Tuple[str, int]],
    config_dict: dict,
    batch_size: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Batch Celery task для краулінгу N сторінок одночасно.

     RECOMMENDED: 24x швидше ніж crawl_page_task!

    Args:
        urls_with_depth: Список [(url, depth), ...]
        config_dict: Конфігурація
        batch_size: Розмір batch (опціонально)

    Returns:
        Dict з results, success_count, error_count, total_new_urls
    """
    import time

    from graph_crawler.application.use_cases.crawling.spider import GraphSpider
    from graph_crawler.domain.entities.edge import Edge
    from graph_crawler.domain.entities.node import Node
    from graph_crawler.domain.value_objects.configs import CrawlerConfig
    from graph_crawler.infrastructure.persistence.memory_storage import MemoryStorage
    from graph_crawler.shared.constants import DEFAULT_MAX_CONCURRENT_REQUESTS
    from graph_crawler.shared.utils.url_utils import URLUtils

    try:
        batch_len = len(urls_with_depth)
        logger.info(f" Batch task: {batch_len} URLs")

        # Timeout check
        crawl_timeout = config_dict.pop("_crawl_timeout", None)
        crawl_start_time = config_dict.pop("_crawl_start_time", None)

        if crawl_timeout and crawl_start_time:
            elapsed = time.time() - crawl_start_time
            if elapsed >= (crawl_timeout - 5):
                logger.warning(f"⏱ Timeout reached, skipping batch")
                return {
                    "results": [],
                    "success_count": 0,
                    "error_count": 0,
                    "total_new_urls": [],
                    "batch_size": batch_len,
                    "skipped": True,
                    "reason": "timeout_reached",
                }

        # Десеріалізація
        plugin_paths = config_dict.pop("_plugin_paths", [])
        custom_node_class_path = config_dict.pop("_custom_node_class", None)
        driver_config = config_dict.pop("_driver_config", None)

        config = CrawlerConfig(**config_dict)

        # Плагіни
        plugins = []
        for plugin_path in plugin_paths:
            plugin = _import_plugin(plugin_path)
            if plugin:
                plugins.append(plugin)
        config.node_plugins = plugins if plugins else None

        # Node class
        if custom_node_class_path:
            node_class = _import_class(custom_node_class_path) or Node
        else:
            node_class = config.custom_node_class if config.custom_node_class else Node

        # Driver
        if driver_config:
            driver = _create_driver_from_config(driver_config)
        else:
            from graph_crawler.infrastructure.transport.async_http.driver import (
                AsyncDriver,
            )

            driver = AsyncDriver(config.get_driver_params())

        # Batch size
        if batch_size is None:
            batch_size = getattr(
                driver, "max_concurrent", DEFAULT_MAX_CONCURRENT_REQUESTS
            )

        # Spider
        storage = MemoryStorage()
        spider = GraphSpider(config, driver, storage)

        # Processing
        results = []
        success_count = 0
        error_count = 0
        total_new_urls = []

        urls_only = [url for url, _ in urls_with_depth]
        depth_map = {url: depth for url, depth in urls_with_depth}

        async def process_batch():
            nonlocal success_count, error_count

            responses = await driver.fetch_many(urls_only)

            for response in responses:
                url = response.url
                depth = depth_map.get(url, 0)

                try:
                    if response.error:
                        logger.warning(f"Fetch error for {url}: {response.error}")
                        error_count += 1
                        results.append(
                            {"url": url, "success": False, "error": response.error}
                        )
                        continue

                    node = node_class(
                        url=url, depth=depth, plugin_manager=spider.node_plugin_manager
                    )

                    links = []
                    if response.html:
                        if inspect.iscoroutinefunction(node.process_html):
                            links = await node.process_html(response.html)
                        else:
                            links = node.process_html(response.html)

                    node.response_status = response.status_code

                    node_data = node.model_dump()
                    edges_data = []
                    new_urls = []

                    for link_url in links:
                        if not spider.domain_filter.is_allowed(link_url):
                            continue
                        if not spider.path_filter.is_allowed(link_url):
                            continue

                        normalized_url = URLUtils.normalize_url(link_url)
                        edge = Edge(
                            source_node_id=node.node_id, target_node_id=normalized_url
                        )
                        edges_data.append(edge.model_dump())
                        new_urls.append((normalized_url, depth + 1))

                    results.append(
                        {
                            "node_data": node_data,
                            "edges_data": edges_data,
                            "new_urls": new_urls,
                            "success": True,
                        }
                    )
                    total_new_urls.extend(new_urls)
                    success_count += 1

                except Exception as e:
                    logger.error(f"Error processing {url}: {e}")
                    error_count += 1
                    results.append({"url": url, "success": False, "error": str(e)})

            await driver.close()

        asyncio.run(process_batch())

        logger.info(f" Batch completed: {success_count} success, {error_count} errors")

        return {
            "results": results,
            "success_count": success_count,
            "error_count": error_count,
            "total_new_urls": total_new_urls,
            "batch_size": batch_len,
        }

    except Exception as e:
        logger.error(f"Batch task failed: {e}")
        raise self.retry(exc=e, countdown=2**self.request.retries)


# =====================================
# TASK 3: Health Check
# =====================================


@celery.task(name="graph_crawler.health_check")
def health_check_task() -> Dict[str, Any]:
    """Health check task."""
    import platform
    import socket

    return {
        "status": "ok",
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "celery_app": "unified",
    }


# =====================================
# TASK 4: Get Driver Batch Size
# =====================================


@celery.task(name="graph_crawler.get_driver_batch_size")
def get_driver_batch_size_task(driver_config: Optional[dict] = None) -> int:
    """Повертає рекомендований batch size для драйвера."""
    from graph_crawler.shared.constants import DEFAULT_MAX_CONCURRENT_REQUESTS

    if not driver_config:
        return DEFAULT_MAX_CONCURRENT_REQUESTS

    driver = _create_driver_from_config(driver_config)
    batch_size = getattr(driver, "max_concurrent", DEFAULT_MAX_CONCURRENT_REQUESTS)

    driver_class = driver_config.get("driver_class", "")
    if "Playwright" in driver_class:
        browsers = driver_config.get("config", {}).get("browsers", 3)
        tabs = driver_config.get("config", {}).get("tabs_per_browser", 5)
        batch_size = browsers * tabs

    return batch_size


# =====================================
# Exports
# =====================================

__all__ = [
    "celery",
    "crawl_page_task",
    "crawl_batch_task",
    "health_check_task",
    "get_driver_batch_size_task",
]
