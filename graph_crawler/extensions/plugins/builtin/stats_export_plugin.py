"""Stats export plugin for post-crawl statistics."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from graph_crawler.extensions.plugins.node import (
    BaseNodePlugin,
    NodePluginContext,
    NodePluginType,
)

logger = logging.getLogger(__name__)


class StatsExportPlugin(BaseNodePlugin):
    """
    Plugin for exporting crawl statistics to JSON file.

    Exports graph statistics, page counts, and top pages by link count
    after crawl completion.

    Attributes:
        export_path: Path to export JSON file (default: ./crawl_stats.json)
        pretty_print: Whether to format JSON with indentation (default: True)

    Example:
        >>> plugin = StatsExportPlugin(config={
        ...     "export_path": "./stats/crawl_report.json",
        ...     "pretty_print": True
        ... })
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
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
        export_data = {
            "graph_stats": stats,
            "pages_crawled": pages_crawled,
            "start_url": context.url,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Додати топ-10 сторінок за кількістю посилань (якщо граф доступний)
        if graph and hasattr(graph, "iter_nodes"):
            top_nodes = sorted(
                graph.iter_nodes(),
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

            logger.info("[STATS] Stats exported to %s", self.export_path)
        except Exception as e:
            logger.error("[STATS] Failed to export stats: %s", e, exc_info=True)

        return context
