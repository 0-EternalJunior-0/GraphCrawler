"""
Spider Lifecycle Manager - управління життєвим циклом краулінгу.

Відокремлює відповідальність за lifecycle hooks (BEFORE_CRAWL, AFTER_CRAWL)
від основного класу GraphSpider (SRP - Single Responsibility Principle).
"""

import logging
from typing import Any, Dict, Optional

from graph_crawler.domain.entities.graph import Graph
from graph_crawler.domain.value_objects.configs import CrawlerConfig
from graph_crawler.extensions.plugins.node import (
    NodePluginContext,
    NodePluginManager,
    NodePluginType,
)

logger = logging.getLogger(__name__)


class SpiderLifecycleManager:
    """
    Управляє життєвим циклом краулінгу (lifecycle hooks).

    Responsibilities:
    - Виконання BEFORE_CRAWL hooks
    - Виконання AFTER_CRAWL hooks
    - Підготовка контексту для плагінів

    Це окремий клас для дотримання SRP - тільки lifecycle управління.
    """

    def __init__(
        self,
        config: CrawlerConfig,
        plugin_manager: NodePluginManager,
        graph: Graph,
    ):
        """
        Ініціалізує Lifecycle Manager.

        Args:
            config: Конфігурація краулера
            plugin_manager: Менеджер плагінів для виконання hooks
            graph: Граф для передачі в контекст
        """
        self.config = config
        self.plugin_manager = plugin_manager
        self.graph = graph

    def execute_before_crawl(self) -> None:
        """
        Виконує BEFORE_CRAWL lifecycle hook.

        Викликається перед початком краулінгу.
        Дозволяє плагінам виконати ініціалізацію, логування, перевірки.
        """
        logger.debug("Executing BEFORE_CRAWL lifecycle hook")

        context = NodePluginContext(
            node=None,
            url=self.config.url,
            depth=0,
            should_scan=True,
            can_create_edges=True,
            user_data={
                "graph": self.graph,
                "config": self.config,
            },
        )

        self.plugin_manager.execute_sync(NodePluginType.BEFORE_CRAWL, context)

        logger.info(f"BEFORE_CRAWL hooks executed for {self.config.url}")

    def execute_after_crawl(self, pages_crawled: int) -> None:
        """
        Виконує AFTER_CRAWL lifecycle hook.

        Викликається після завершення краулінгу (у блоці finally).
        Дозволяє плагінам виконати cleanup, звіти, збереження.

        Args:
            pages_crawled: Кількість просканованих сторінок
        """
        logger.debug("Executing AFTER_CRAWL lifecycle hook")

        stats = self.graph.get_stats()

        context = NodePluginContext(
            node=None,
            url=self.config.url,
            depth=0,
            should_scan=True,
            can_create_edges=True,
            user_data={
                "graph": self.graph,
                "stats": stats,
                "pages_crawled": pages_crawled,
            },
        )

        self.plugin_manager.execute_sync(NodePluginType.AFTER_CRAWL, context)

        logger.info(f"AFTER_CRAWL hooks executed (pages: {pages_crawled})")
