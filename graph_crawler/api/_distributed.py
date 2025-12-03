"""
Distributed crawling через Celery workers.

"""

import logging
from typing import Any, Optional

from graph_crawler.api._shared import DriverType
from graph_crawler.domain.entities.graph import Graph
from graph_crawler.domain.entities.node import Node
from graph_crawler.domain.value_objects.models import URLRule

logger = logging.getLogger(__name__)


def distributed_crawl(
    url: str,
    max_depth: int,
    max_pages: Optional[int],
    wrapper_config: dict,
    driver: Optional[DriverType] = None,
    driver_config: Optional[dict[str, Any]] = None,
    plugins: Optional[list] = None,
    node_class: Optional[type[Node]] = None,
    url_rules: Optional[list[URLRule]] = None,
    edge_strategy: str = "all",
    timeout: Optional[int] = None,
) -> Graph:
    """
    Розподілений краулінг через Celery workers.

     МОДУЛЬНА АРХІТЕКТУРА:
    - Всі параметри передаються на воркерів
    - Кастомні Node класи
    - Кастомні драйвери з плагінами
    - Кастомні плагіни
    - Будь-які брокери/БД
    - Timeout підтримка (як в локальному режимі)

    Args:
        url: URL для краулінгу
        max_depth: Максимальна глибина
        max_pages: Максимальна кількість сторінок
        wrapper_config: Конфігурація брокера/БД
        driver: Драйвер або його назва
        driver_config: Конфігурація драйвера
        plugins: Список плагінів
        node_class: Кастомний Node клас
        url_rules: Правила URL
        edge_strategy: Стратегія створення ребер
        timeout: Максимальний час краулінгу в секундах (опціонально)

    Returns:
        Graph з результатами (повний або частковий при timeout)
    """
    from graph_crawler.application.services.driver_factory import create_driver
    from graph_crawler.application.use_cases.crawling.celery_batch_spider import (
        CeleryBatchSpider,
    )
    from graph_crawler.domain.value_objects.configs import (
        CeleryConfig,
        CrawlerConfig,
        DriverConfig,
    )
    from graph_crawler.infrastructure.persistence.memory_storage import MemoryStorage
    from graph_crawler.infrastructure.persistence.mongodb_storage import MongoDBStorage
    from graph_crawler.infrastructure.persistence.postgresql_storage import (
        PostgreSQLStorage,
    )
    from graph_crawler.infrastructure.transport.sync import RequestsDriver as HTTPDriver

    logger.info(f" Starting DISTRIBUTED crawl for {url}")
    logger.info(f"   Broker: {wrapper_config.get('broker', {}).get('type', 'redis')}")
    logger.info(
        f"   Database: {wrapper_config.get('database', {}).get('type', 'memory')}"
    )

    # ========== КОНФІГУРАЦІЯ БРОКЕРА ==========
    broker_config = wrapper_config.get("broker", {})
    broker_type = broker_config.get("type", "redis")
    broker_host = broker_config.get("host", "localhost")
    broker_port = broker_config.get("port", 6379)
    broker_db = broker_config.get("db", 0)
    broker_password = broker_config.get("password")

    # Генеруємо broker URL
    if broker_type == "redis":
        auth = f":{broker_password}@" if broker_password else ""
        broker_url = f"redis://{auth}{broker_host}:{broker_port}/{broker_db}"
        backend_url = f"redis://{auth}{broker_host}:{broker_port}/{broker_db + 1}"
    elif broker_type == "rabbitmq":
        auth = f":{broker_password}@" if broker_password else ""
        broker_url = f"amqp://{auth}{broker_host}:{broker_port}//"
        backend_url = broker_url
    else:
        raise ValueError(f"Unsupported broker type: {broker_type}")

    # ========== КОНФІГУРАЦІЯ STORAGE ==========
    db_config = wrapper_config.get("database", {})
    db_type = db_config.get("type", "memory")

    if db_type == "memory":
        storage = MemoryStorage()
    elif db_type == "mongodb":
        db_host = db_config.get("host", "localhost")
        db_port = db_config.get("port", 27017)
        db_name = db_config.get("database", "crawler")
        db_user = db_config.get("username")
        db_pass = db_config.get("password")

        auth = f"{db_user}:{db_pass}@" if db_user else ""
        connection_string = f"mongodb://{auth}{db_host}:{db_port}/"

        storage = MongoDBStorage(
            {
                "connection_string": connection_string,
                "database": db_name,
            }
        )
    elif db_type == "postgresql":
        db_host = db_config.get("host", "localhost")
        db_port = db_config.get("port", 5432)
        db_name = db_config.get("database", "crawler")
        db_user = db_config.get("username")
        db_pass = db_config.get("password")

        auth = f"{db_user}:{db_pass}@" if db_user else ""
        connection_string = f"postgresql://{auth}{db_host}:{db_port}/{db_name}"

        storage = PostgreSQLStorage({"connection_string": connection_string})
    else:
        raise ValueError(f"Unsupported database type: {db_type}")

    # ========== СТВОРЕННЯ ДРАЙВЕРА ==========
    if driver is not None:
        if isinstance(driver, str):
            # Строка - створюємо через фабрику
            actual_driver = create_driver(driver, driver_config or {})
        elif isinstance(driver, type):
            # Передано клас, а не екземпляр - створюємо екземпляр
            logger.info(f"Creating driver instance from class: {driver.__name__}")
            actual_driver = driver(driver_config or {})
        else:
            # Вже інстанс драйвера
            actual_driver = driver
    else:
        # Дефолтний HTTPDriver
        actual_driver = HTTPDriver({})

    # ========== СТВОРЕННЯ КОНФІГУРАЦІЇ ==========
    crawler_config = CrawlerConfig(
        url=url,
        max_depth=max_depth,
        max_pages=max_pages,
        driver=DriverConfig(),
        node_plugins=plugins or [],
        custom_node_class=node_class,
        url_rules=url_rules or [],
        edge_strategy=edge_strategy,
        celery=CeleryConfig(
            enabled=True,
            broker_url=broker_url,
            backend_url=backend_url,
            workers=wrapper_config.get("workers", 10),
            task_time_limit=wrapper_config.get("task_time_limit", 600),
            worker_prefetch_multiplier=wrapper_config.get(
                "worker_prefetch_multiplier", 4
            ),
        ),
    )

    # ========== СТВОРЕННЯ CELERY BATCH SPIDER ==========
    # batch_size можна задати через wrapper config, або буде взято з драйвера
    batch_size = wrapper_config.get("batch_size")

    if batch_size is None:
        # Визначаємо batch_size з драйвера (для max ефективності)
        if hasattr(actual_driver, "max_concurrent"):
            batch_size = actual_driver.max_concurrent
        elif hasattr(actual_driver, "max_browsers") and hasattr(
            actual_driver, "max_tabs_per_browser"
        ):
            batch_size = actual_driver.max_browsers * actual_driver.max_tabs_per_browser

    logger.info(f"   Batch size: {batch_size}")

    # Передаємо timeout в spider для коректної обробки
    spider = CeleryBatchSpider(
        crawler_config, actual_driver, storage, batch_size=batch_size, timeout=timeout
    )

    # ========== ЗАПУСК КРАУЛІНГУ ==========
    # Тепер timeout обробляється всередині spider
    try:
        graph = spider.crawl()

        logger.info(f" Distributed crawl completed: {len(graph.nodes)} nodes")
        return graph
    except Exception as e:
        logger.error(f" Distributed crawl failed: {e}")
        # Повертаємо частковий граф якщо є
        graph = spider.get_partial_graph()
        if graph and len(graph.nodes) > 0:
            logger.info(f"Returning partial graph: {len(graph.nodes)} nodes")
            return graph
        raise


__all__ = ["distributed_crawl"]
