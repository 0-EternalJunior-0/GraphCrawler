"""JSON Lines Exporter — Streaming export для великих графів.

JSON Lines формат підходить для:
- Streaming великих датасетів
- Інкрементальна обробка
- BigQuery / Dataflow import
- Line-by-line processing

Usage:
    exporter = JSONLExporter()
    count = await exporter.export_async(graph_dto, "output.jsonl")
"""

import json
import logging
from pathlib import Path
from typing import AsyncIterator, Optional, Union

from graph_crawler.application.dto import GraphDTO, NodeDTO
from graph_crawler.application.services.exporters.base_exporter import BaseExporter
from graph_crawler.domain.events import CrawlerEvent, EventBus, EventType

logger = logging.getLogger(__name__)


class JSONLExporter(BaseExporter):
    """
    Export graph nodes to JSON Lines format.

    JSON Lines (jsonl) — один JSON object per line.
    Ідеально для streaming та великих датасетів.

    Features:
    - Memory efficient (no full graph in memory)
    - Streaming support
    - BigQuery compatible
    - Progress events через EventBus

    Attributes:
        event_bus: EventBus для публікації подій
        include_edges: Чи включати edges в export
        pretty: Чи форматувати JSON (для debugging)

    Example:
        >>> exporter = JSONLExporter()
        >>> exporter.export(graph_dto, "output.jsonl")
        1000  # exported 1000 nodes
    """

    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        include_edges: bool = True,
        pretty: bool = False,
        **kwargs,
    ):
        """Initialize JSONLExporter.

        Args:
            event_bus: EventBus для публікації подій (optional)
            include_edges: Чи включати edges в export (default: True)
            pretty: Чи форматувати JSON (default: False)
            **kwargs: Додаткові параметри для BaseExporter
        """
        super().__init__(event_bus=event_bus, **kwargs)
        self.include_edges = include_edges
        self.pretty = pretty

    def export(self, graph_dto: GraphDTO, output_path: str = "", **options) -> bool:
        """
        Export GraphDTO to JSON Lines file.

        Args:
            graph_dto: GraphDTO для експорту
            output_path: Шлях до output файлу
            **options: Додаткові опції:
                - include_edges: Override instance setting
                - pretty: Override instance setting

        Returns:
            bool: True якщо успішно

        Raises:
            ValueError: Якщо GraphDTO невалідний
            OSError: Якщо file write fails
        """
        if not output_path:
            raise ValueError("output_path is required for JSONLExporter")

        self.validate_graph(graph_dto)

        include_edges = options.get("include_edges", self.include_edges)
        pretty = options.get("pretty", self.pretty)

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Publish start event
        if self.event_bus:
            self.event_bus.publish(
                CrawlerEvent.create(
                    EventType.EXPORT_STARTED,
                    data={
                        "format": "jsonl",
                        "output_path": str(output_file),
                        "total_nodes": len(graph_dto.nodes),
                        "total_edges": len(graph_dto.edges),
                    },
                )
            )

        try:
            node_count = 0
            edge_count = 0

            with open(output_file, "w", encoding="utf-8") as f:
                # Export nodes
                for node_dto in graph_dto.nodes:
                    record = self._node_to_record(node_dto, record_type="node")
                    line = self._serialize_record(record, pretty)
                    f.write(line + "\n")
                    node_count += 1

                    # Progress event every 1000 nodes
                    if node_count % 1000 == 0 and self.event_bus:
                        self.event_bus.publish(
                            CrawlerEvent.create(
                                EventType.EXPORT_PROGRESS,
                                data={
                                    "format": "jsonl",
                                    "nodes_exported": node_count,
                                    "progress_percent": round(
                                        node_count / len(graph_dto.nodes) * 100, 1
                                    ),
                                },
                            )
                        )

                # Export edges
                if include_edges:
                    for edge_dto in graph_dto.edges:
                        record = {
                            "_type": "edge",
                            "source_url": edge_dto.source_url,
                            "target_url": edge_dto.target_url,
                            "link_text": edge_dto.link_text,
                            "edge_type": edge_dto.edge_type,
                            "weight": edge_dto.weight,
                        }
                        line = self._serialize_record(record, pretty)
                        f.write(line + "\n")
                        edge_count += 1

            logger.info(
                "JSONL export completed: %s (nodes: %d, edges: %d)",
                output_file,
                node_count,
                edge_count,
            )

            # Publish success event
            if self.event_bus:
                self.event_bus.publish(
                    CrawlerEvent.create(
                        EventType.EXPORT_SUCCESS,
                        data={
                            "format": "jsonl",
                            "output_path": str(output_file),
                            "nodes_exported": node_count,
                            "edges_exported": edge_count,
                            "file_size_bytes": output_file.stat().st_size,
                        },
                    )
                )

            return True

        except Exception as e:
            logger.error("JSONL export failed: %s", e)

            if self.event_bus:
                self.event_bus.publish(
                    CrawlerEvent.create(
                        EventType.EXPORT_ERROR,
                        data={
                            "format": "jsonl",
                            "error": str(e),
                            "output_path": str(output_file),
                        },
                    )
                )
            raise

    def _node_to_record(self, node_dto: NodeDTO, record_type: str = "node") -> dict:
        """Convert NodeDTO to JSONL record."""
        return {
            "_type": record_type,
            "url": node_dto.url,
            "node_id": node_dto.node_id,
            "depth": node_dto.depth,
            "scanned": node_dto.scanned,
            "response_status": node_dto.response_status,
            "content_type": node_dto.content_type,
            "content_hash": node_dto.content_hash,
            "simhash": node_dto.simhash,
            "created_at": node_dto.created_at.isoformat() if node_dto.created_at else None,
            "metadata": node_dto.metadata or {},
            "user_data": node_dto.user_data or {},
        }

    def _serialize_record(self, record: dict, pretty: bool = False) -> str:
        """Serialize record to JSON string."""
        if pretty:
            return json.dumps(record, ensure_ascii=False, indent=2, default=str)
        return json.dumps(record, ensure_ascii=False, default=str)

    async def export_streaming(
        self,
        nodes: AsyncIterator[NodeDTO],
        output: Union[str, Path],
        include_type: bool = True,
    ) -> int:
        """
        Streaming export для memory efficiency.

        Дозволяє експортувати nodes без завантаження всього графа в пам'ять.

        Args:
            nodes: AsyncIterator of NodeDTO objects
            output: Шлях до output файлу
            include_type: Чи включати _type field

        Returns:
            Number of exported nodes
        """
        output_file = Path(output)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        count = 0
        with open(output_file, "w", encoding="utf-8") as f:
            async for node_dto in nodes:
                record = self._node_to_record(node_dto, "node" if include_type else "")
                if not include_type:
                    record.pop("_type", None)
                line = self._serialize_record(record, self.pretty)
                f.write(line + "\n")
                count += 1

        logger.info("Streaming JSONL export: %d nodes to %s", count, output_file)
        return count

    def get_export_info(self, graph_dto: GraphDTO) -> dict:
        """Get export info with JSONL-specific details."""
        info = super().get_export_info(graph_dto)
        info.update(
            {
                "format": "jsonl",
                "include_edges": self.include_edges,
                "estimated_lines": len(graph_dto.nodes)
                + (len(graph_dto.edges) if self.include_edges else 0),
            }
        )
        return info
