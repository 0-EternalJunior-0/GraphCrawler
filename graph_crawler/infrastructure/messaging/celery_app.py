"""Celery application для distributed crawling.

 DEPRECATED: Для кращої продуктивності використовуйте celery_batch.py!

Цей файл обробляє 1 URL per task, що НЕ ефективно використовує
AsyncDriver.max_concurrent (типово 24 паралельних запити).

Migration:
    # Старий worker (неефективний):
    celery -A graph_crawler.celery_app worker --loglevel=info

    # Новий worker (24x швидше):
    celery -A graph_crawler.celery_batch worker --loglevel=info -Q graph_crawler_batch

Документація: docs/deployment/BATCH_TASKS.md

Архітектура (DEPRECATED):
    - celery_app.py - визначає Celery app та таски (1 URL per task)
    - CelerySpider - координатор, який відправляє таски
    - Workers - виконують таски crawl_page
"""

import asyncio
import logging
import os
import warnings
from typing import Any, Dict, List, Optional, Tuple

from celery import Celery

logger = logging.getLogger(__name__)

# =====================================
# DEPRECATION WARNING
# =====================================
warnings.warn(
    "celery_app.py is deprecated. Use celery_batch.py for 24x better performance. "
    "Run: celery -A graph_crawler.celery_batch worker -Q graph_crawler_batch",
    DeprecationWarning,
    stacklevel=2,
)

# =====================================
# Celery App Configuration
# =====================================

from graph_crawler.shared.utils.celery_config import (
    get_backend_url,
    get_broker_url,
    get_celery_app_config,
)

BROKER_URL = get_broker_url()
BACKEND_URL = get_backend_url()

# Створюємо Celery app
celery = Celery(
    "graph_crawler",
    broker=BROKER_URL,
    backend=BACKEND_URL,
)

# Налаштування Celery (з спільного модуля)
celery.conf.update(get_celery_app_config())

# =====================================
# Celery Tasks
# =====================================


@celery.task(name="graph_crawler.crawl_page", bind=True, max_retries=3)
def crawl_page_task(self, url: str, depth: int, config_dict: dict) -> Dict[str, Any]:
    """
    Celery task для краулінгу однієї сторінки.

     ASYNC-READY: Підтримує як синхронні так і асинхронні драйвери/плагіни.

    Цей таск виконується на воркерах і:
    1. Завантажує HTML сторінки
    2. Парсить посилання
    3. Виконує плагіни (extractors)
    4. Повертає результати координатору

    Args:
        url: URL сторінки для краулінгу
        depth: Глибина сторінки в графі
        config_dict: Серіалізована конфігурація краулера

    Returns:
        Dict з node_data, edges_data, new_urls, success
    """
    import importlib
    import inspect

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
        logger.info(f"Celery task started: {url} (depth={depth})")

        # Витягуємо metadata перед створенням конфігу
        plugin_paths = config_dict.pop("_plugin_paths", [])
        custom_node_class_path = config_dict.pop("_custom_node_class", None)
        driver_config = config_dict.pop("_driver_config", None)

        # Створюємо конфіг
        config = CrawlerConfig(**config_dict)

        # ========== ДЕСЕРІАЛІЗАЦІЯ ПЛАГІНІВ ==========
        plugins = []
        failed_plugins = []
        for plugin_path in plugin_paths:
            plugin = _import_plugin(plugin_path)
            if plugin:
                plugins.append(plugin)
            else:
                failed_plugins.append(plugin_path)

        # Якщо є failed plugins - логуємо помилку
        if failed_plugins:
            logger.error(
                f" Плагіни не знайдено на воркері: {failed_plugins}\n"
                f"Встановіть їх або видаліть з конфігурації."
            )

        config.node_plugins = plugins if plugins else None

        # ========== ДЕСЕРІАЛІЗАЦІЯ CUSTOM NODE CLASS ==========
        if custom_node_class_path:
            node_class = _import_class(custom_node_class_path)
            if not node_class:
                logger.warning(
                    f"Failed to import custom node class: {custom_node_class_path}, using default Node"
                )
                node_class = Node
        else:
            node_class = config.custom_node_class if config.custom_node_class else Node

        # ========== ДЕСЕРІАЛІЗАЦІЯ ДРАЙВЕРА ==========
        if driver_config:
            driver = _create_driver_from_config(driver_config)
        else:
            # Fallback - AsyncDriver (для сумісності з async GraphSpider)
            try:
                from graph_crawler.infrastructure.transport.async_http.driver import (
                    AsyncDriver,
                )

                driver_params = config.get_driver_params()
                driver = AsyncDriver(driver_params)
                logger.info("Using AsyncDriver (default for async GraphSpider)")
            except ImportError:
                # Якщо AsyncDriver недоступний - використовуємо RequestsDriver
                logger.warning(
                    "AsyncDriver not available, falling back to RequestsDriver"
                )
                driver_params = config.get_driver_params()
                driver = RequestsDriver(driver_params)

        # Створюємо storage для воркера
        storage = MemoryStorage()

        # Створюємо spider для сканування
        spider = GraphSpider(config, driver, storage)

        # Створюємо вузол
        node = node_class(
            url=url, depth=depth, plugin_manager=spider.node_plugin_manager
        )

        # ========== ASYNC/SYNC СКАНУВАННЯ ==========
        # Перевіряємо чи scan_node є async функцією
        if inspect.iscoroutinefunction(spider.scanner.scan_node):
            # Async шлях - використовуємо asyncio.run()
            logger.debug(f"Using async scanner for {url}")
            links = asyncio.run(spider.scanner.scan_node(node))
        else:
            # Sync шлях
            logger.debug(f"Using sync scanner for {url}")
            links = spider.scanner.scan_node(node)

        # Формуємо результат
        node_data = node.model_dump()
        edges_data = []
        new_urls = []

        if links:
            for link_url in links:
                # Перевіряємо фільтри
                if not spider.domain_filter.is_allowed(link_url):
                    continue
                if not spider.path_filter.is_allowed(link_url):
                    continue

                # Нормалізуємо URL
                normalized_url = URLUtils.normalize_url(link_url)

                # Створюємо ребро
                edge = Edge(source_node_id=node.node_id, target_node_id=normalized_url)
                edges_data.append(edge.model_dump())

                # Додаємо новий URL
                new_urls.append((normalized_url, depth + 1))

        # Закриваємо driver (async або sync)
        if inspect.iscoroutinefunction(driver.close):
            asyncio.run(driver.close())
        else:
            driver.close()

        logger.info(f"Celery task completed: {url}, found {len(new_urls)} links")

        return {
            "node_data": node_data,
            "edges_data": edges_data,
            "new_urls": new_urls,
            "success": True,
        }

    except Exception as e:
        logger.error(f"Celery task failed for {url}: {e}")
        # Retry з exponential backoff
        raise self.retry(exc=e, countdown=2**self.request.retries)


@celery.task(name="graph_crawler.health_check")
def health_check_task() -> Dict[str, Any]:
    """
    Health check task для перевірки що воркер працює.

    Returns:
        Dict з інформацією про воркера
    """
    import platform
    import socket

    return {
        "status": "ok",
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
    }


# =====================================
# Helper Functions
# =====================================
from graph_crawler.shared.utils.celery_helpers import (
    create_driver_from_config as _create_driver_from_config,
)
from graph_crawler.shared.utils.celery_helpers import import_class as _import_class
from graph_crawler.shared.utils.celery_helpers import import_plugin as _import_plugin

# Експортуємо для використання в інших модулях
__all__ = ["celery", "crawl_page_task", "health_check_task"]
