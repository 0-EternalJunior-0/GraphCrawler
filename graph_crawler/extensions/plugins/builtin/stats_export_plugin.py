"""Плагін для експорту статистики після краулінгу."""

import json
import logging
from pathlib import Path
from typing import Any, Dict

from graph_crawler.extensions.plugins.node import (
    BaseNodePlugin,
    NodePluginContext,
    NodePluginType,
)

logger = logging.getLogger(__name__)


class StatsExportPlugin(BaseNodePlugin):
    """
    Плагін для експорту статистики після краулінгу.

    Автоматично експортує статистику графа в JSON файл
    після завершення краулінгу.

    Приклад:
        plugin = StatsExportPlugin(config={
            'export_path': './stats.json',
            'enabled': True,
            'pretty_print': True
        })

        config = CrawlerConfig(
            url="...",
            node_plugins=[plugin]
        )

        client = GraphCrawlerClient()
        graph = client.crawl(url="https://example.com", node_plugins=[plugin])
        # Після краулінгу автоматично створюється stats.json

    Формат експорту:
        {
            "graph_stats": {
                "total_nodes": 47,
                "scanned_nodes": 45,
                "total_edges": 156,
                ...
            },
            "pages_crawled": 45,
            "start_url": "https://example.com",
            "timestamp": "2025-11-22T12:34:56"
        }
    """

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.export_path = self.config.get("export_path", "./crawl_stats.json")
        self.pretty_print = self.config.get("pretty_print", True)

    @property
    def plugin_type(self) -> NodePluginType:
        return NodePluginType.AFTER_CRAWL

    @property
    def name(self) -> str:
        return "StatsExportPlugin"

    def execute(self, context: NodePluginContext) -> NodePluginContext:
        """Експортувати статистику."""
        stats = context.user_data.get("stats", {})
        pages_crawled = context.user_data.get("pages_crawled", 0)
        graph = context.user_data.get("graph")

        # Додати додаткову інфо
        from datetime import datetime

        export_data = {
            "graph_stats": stats,
            "pages_crawled": pages_crawled,
            "start_url": context.url,
            "timestamp": datetime.now().isoformat(),
        }

        # Додати топ-10 сторінок за кількістю посилань (якщо граф доступний)
        if graph and hasattr(graph, "nodes"):
            top_nodes = sorted(
                graph.nodes.values(),
                key=lambda n: len(n.extracted_links or []),
                reverse=True,
            )[:10]
            export_data["top_pages_by_links"] = [
                {
                    "url": node.url,
                    "links_count": len(node.extracted_links or []),
                    "title": node.get_title() or "N/A",
                }
                for node in top_nodes
            ]

        # Експортувати
        try:
            # Створити директорію якщо не існує
            export_path = Path(self.export_path)
            export_path.parent.mkdir(parents=True, exist_ok=True)

            # Записати JSON
            with open(export_path, "w", encoding="utf-8") as f:
                if self.pretty_print:
                    json.dump(export_data, f, indent=2, ensure_ascii=False)
                else:
                    json.dump(export_data, f, ensure_ascii=False)

            logger.info(f" Stats exported to {self.export_path}")
        except Exception as e:
            logger.error(f" Failed to export stats: {e}", exc_info=True)

        return context
