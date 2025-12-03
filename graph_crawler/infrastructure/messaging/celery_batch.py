"""Celery Batch Tasks - ефективні batch задачі для distributed crawling.

Цей модуль вирішує проблему неефективності стандартного celery_app.py:
- Стара архітектура: 1 task = 1 URL (AsyncDriver з 24 concurrent не використовується)
- Нова архітектура: 1 task = N URLs (AsyncDriver використовується на повну)

Архітектура:
```

  BATCH TASK ARCHITECTURE


  Redis Queue: [Batch(24 URLs)] [Batch(24 URLs)] ...

  Worker 1:     fetch_many(24)   fetch_many(24)

  AsyncDriver:   24 parallel      24 parallel

  РЕЗУЛЬТАТ: 24x ефективніше!


```

Використання:
    # Worker
    celery -A graph_crawler.celery_batch worker --loglevel=info

    # Master (CelerySpider з batch mode)
    spider = CelerySpider(config, driver, storage, use_batch_mode=True)
"""

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from celery import Celery

logger = logging.getLogger(__name__)

# =====================================
# Celery App Configuration
# =====================================

from graph_crawler.shared.utils.celery_config import (
    get_backend_url,
    get_broker_url,
    get_celery_batch_config,
)

BROKER_URL = get_broker_url()
BACKEND_URL = get_backend_url()

# Створюємо Celery app для batch tasks
celery_batch = Celery(
    "graph_crawler.batch",
    broker=BROKER_URL,
    backend=BACKEND_URL,
)

# Налаштування Celery для batch режиму (з спільного модуля)
celery_batch.conf.update(get_celery_batch_config())

# =====================================
# Batch Task - ГОЛОВНА ІННОВАЦІЯ
# =====================================


@celery_batch.task(name="graph_crawler.crawl_batch", bind=True, max_retries=3)
def crawl_batch_task(
    self,
    urls_with_depth: List[Tuple[str, int]],
    config_dict: dict,
    batch_size: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Celery task для краулінгу BATCH сторінок.

     КЛЮЧОВА ВІДМІННІСТЬ від crawl_page_task:
    - crawl_page_task: 1 URL per task (AsyncDriver idle)
    - crawl_batch_task: N URLs per task (AsyncDriver fully utilized)

    Алгоритм:
    1. Worker отримує batch з N URLs
    2. AsyncDriver.fetch_many() обробляє всі паралельно
    3. Результати повертаються як один response

    Args:
        urls_with_depth: Список [(url, depth), ...] для краулінгу
        config_dict: Серіалізована конфігурація краулера
        batch_size: Розмір batch (опціонально, береться з driver config)

    Returns:
        Dict з:
        - results: List[{node_data, edges_data, new_urls}]
        - success_count: int
        - error_count: int
        - total_new_urls: int
    """
    import importlib
    import inspect
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
        logger.info(f" Batch task started: {batch_len} URLs")

        # ========== ОТРИМУЄМО TIMEOUT INFO ==========
        crawl_timeout = config_dict.pop("_crawl_timeout", None)
        crawl_start_time = config_dict.pop("_crawl_start_time", None)

        # Перевіряємо чи не вичерпаний timeout (з запасом 5 секунд)
        if crawl_timeout and crawl_start_time:
            elapsed = time.time() - crawl_start_time
            if elapsed >= (crawl_timeout - 5):
                logger.warning(
                    f"⏱ Crawl timeout already reached ({elapsed:.1f}s >= {crawl_timeout}s), skipping batch"
                )
                return {
                    "results": [],
                    "success_count": 0,
                    "error_count": 0,
                    "total_new_urls": [],
                    "batch_size": batch_len,
                    "skipped": True,
                    "reason": "timeout_reached",
                }

        # ========== ДЕСЕРІАЛІЗАЦІЯ КОНФІГУ ==========
        plugin_paths = config_dict.pop("_plugin_paths", [])
        custom_node_class_path = config_dict.pop("_custom_node_class", None)
        driver_config = config_dict.pop("_driver_config", None)

        config = CrawlerConfig(**config_dict)

        # ========== ДЕСЕРІАЛІЗАЦІЯ ПЛАГІНІВ ==========
        plugins = []
        for plugin_path in plugin_paths:
            plugin = _import_plugin(plugin_path)
            if plugin:
                plugins.append(plugin)

        config.node_plugins = plugins if plugins else None

        # ========== ДЕСЕРІАЛІЗАЦІЯ CUSTOM NODE CLASS ==========
        if custom_node_class_path:
            node_class = _import_class(custom_node_class_path)
            if not node_class:
                node_class = Node
        else:
            node_class = config.custom_node_class if config.custom_node_class else Node

        # ========== СТВОРЕННЯ ДРАЙВЕРА ==========
        if driver_config:
            driver = _create_driver_from_config(driver_config)
        else:
            from graph_crawler.infrastructure.transport.async_http.driver import (
                AsyncDriver,
            )

            driver_params = config.get_driver_params()
            driver = AsyncDriver(driver_params)

        # Визначаємо batch_size з драйвера
        if batch_size is None:
            batch_size = getattr(
                driver, "max_concurrent", DEFAULT_MAX_CONCURRENT_REQUESTS
            )

        logger.info(f"Using batch_size={batch_size} from driver")

        # Storage для воркера
        storage = MemoryStorage()

        # Spider для сканування
        spider = GraphSpider(config, driver, storage)

        # ========== BATCH PROCESSING ==========
        results = []
        success_count = 0
        error_count = 0
        total_new_urls = []

        # Розділяємо URLs на batches для fetch_many
        urls_only = [url for url, _ in urls_with_depth]
        depth_map = {url: depth for url, depth in urls_with_depth}

        # Async batch fetch
        async def process_batch():
            nonlocal success_count, error_count

            # Fetch all URLs in parallel
            logger.info(f"Fetching {len(urls_only)} URLs in parallel...")
            responses = await driver.fetch_many(urls_only)

            # Process each response
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

                    # Створюємо Node
                    node = node_class(
                        url=url, depth=depth, plugin_manager=spider.node_plugin_manager
                    )

                    # Обробляємо HTML та отримуємо посилання
                    links = []
                    if response.html:
                        if inspect.iscoroutinefunction(node.process_html):
                            links = await node.process_html(response.html)
                        else:
                            links = node.process_html(response.html)

                    node.response_status = response.status_code

                    # Формуємо результат
                    node_data = node.model_dump()
                    edges_data = []
                    new_urls = []

                    for link_url in links:
                        # Перевіряємо фільтри
                        if not spider.domain_filter.is_allowed(link_url):
                            continue
                        if not spider.path_filter.is_allowed(link_url):
                            continue

                        # Нормалізуємо URL
                        normalized_url = URLUtils.normalize_url(link_url)

                        # Edge
                        edge = Edge(
                            source_node_id=node.node_id, target_node_id=normalized_url
                        )
                        edges_data.append(edge.model_dump())

                        # New URL
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

            # Закриваємо driver
            await driver.close()

        # Запускаємо async processing
        asyncio.run(process_batch())

        logger.info(
            f" Batch task completed: "
            f"{success_count} success, {error_count} errors, "
            f"{len(total_new_urls)} new URLs"
        )

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


@celery_batch.task(name="graph_crawler.get_driver_batch_size")
def get_driver_batch_size_task(driver_config: Optional[dict] = None) -> int:
    """
    Повертає рекомендований batch size для драйвера.

    Це допоміжна задача для CelerySpider щоб знати
    скільки URLs складати в один batch.

    Args:
        driver_config: Конфігурація драйвера

    Returns:
        int: Рекомендований batch size
    """
    from graph_crawler.shared.constants import DEFAULT_MAX_CONCURRENT_REQUESTS

    if not driver_config:
        return DEFAULT_MAX_CONCURRENT_REQUESTS

    driver = _create_driver_from_config(driver_config)

    # Отримуємо batch size з драйвера
    batch_size = getattr(driver, "max_concurrent", DEFAULT_MAX_CONCURRENT_REQUESTS)

    # Для Playwright - менший batch через пам'ять
    driver_class = driver_config.get("driver_class", "")
    if "Playwright" in driver_class:
        # Playwright: browsers × tabs
        browsers = driver_config.get("config", {}).get("browsers", 3)
        tabs = driver_config.get("config", {}).get("tabs_per_browser", 5)
        batch_size = browsers * tabs

    return batch_size


# =====================================
# Helper Functions
# =====================================
from graph_crawler.shared.utils.celery_helpers import (
    create_driver_from_config as _create_driver_from_config,
)
from graph_crawler.shared.utils.celery_helpers import import_class as _import_class
from graph_crawler.shared.utils.celery_helpers import import_plugin as _import_plugin

# =====================================
# Exports
# =====================================

__all__ = ["celery_batch", "crawl_batch_task", "get_driver_batch_size_task"]
