"""CSV Exporter - Clean Architecture з DTO.

BREAKING CHANGE (Фаза 6): Тепер використовує GraphDTO замість Graph.

Exports graph to CSV format (nodes and edges as separate files).
"""

import csv
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from graph_crawler.application.dto import GraphDTO, NodeDTO, EdgeDTO
from graph_crawler.application.services.exporters.base_exporter import BaseExporter
from graph_crawler.domain.events.events import EventType

logger = logging.getLogger(__name__)


class CSVExporter(BaseExporter):
    """
    Export graph to CSV format через DTO.

    BREAKING CHANGE (Фаза 6): Тепер працює ТІЛЬКИ з GraphDTO.

    Creates two CSV files:
    - {output_path}_nodes.csv - містить інформацію про nodes
    - {output_path}_edges.csv - містить інформацію про edges

    Features:
    - Customizable columns
    - Header row
    - UTF-8 encoding
    - Metadata extraction

    Example:
        >>> from graph_crawler.application.services.exporters import CSVExporter
        >>> from graph_crawler.application.dto import GraphDTO
        >>>
        >>> exporter = CSVExporter()
        >>> exporter.export(graph_dto, './output/graph')
        >>> # Creates: ./output/graph_nodes.csv and ./output/graph_edges.csv
    """

    def __init__(
        self,
        event_bus: Optional["EventBus"] = None,
        delimiter: str = ",",
        quoting: int = csv.QUOTE_MINIMAL,
        **kwargs,
    ):
        """
        Initialize CSV exporter.

        Args:
            event_bus: EventBus для публікації подій (опціонально)
            delimiter: CSV delimiter (default: ',')
            quoting: CSV quoting strategy
            **kwargs: Additional options
        """
        super().__init__(event_bus=event_bus, **kwargs)
        self.delimiter = delimiter
        self.quoting = quoting

    def export(
        self, graph_dto: GraphDTO, output_path: str, include_metadata: bool = True, **options
    ) -> bool:
        """
        Export graph to CSV files through DTO.

        BREAKING CHANGE (Фаза 6): Тепер приймає GraphDTO замість Graph.

        Args:
            graph_dto: GraphDTO для експорту
            output_path: Base path для output files (без розширення)
            include_metadata: Включити metadata в CSV
            **options: Additional options

        Returns:
            bool: True якщо успішно

        Raises:
            Exception: При помилках запису
        """
        start_time = time.time()

        # Подія: EXPORT_STARTED
        self.publish_event(
            EventType.EXPORT_STARTED,
            data={
                "exporter": "csv",
                "output_path": output_path,
                "nodes_count": len(graph_dto.nodes),
                "edges_count": len(graph_dto.edges),
            },
        )

        try:
            if not self.validate_graph(graph_dto):
                logger.warning("GraphDTO validation failed, exporting empty graph")

            # Створити output directory якщо не існує
            output_dir = Path(output_path).parent
            output_dir.mkdir(parents=True, exist_ok=True)

            # Export nodes
            nodes_file = f"{output_path}_nodes.csv"
            self._export_nodes(graph_dto, nodes_file, include_metadata)
            logger.info(f"Exported {len(graph_dto.nodes)} nodes to {nodes_file}")

            # Подія: EXPORT_PROGRESS (після nodes)
            self.publish_event(
                EventType.EXPORT_PROGRESS,
                data={
                    "exporter": "csv",
                    "progress": 50,
                    "message": f"Nodes exported: {len(graph_dto.nodes)}",
                },
            )

            # Export edges
            edges_file = f"{output_path}_edges.csv"
            self._export_edges(graph_dto, edges_file)
            logger.info(f"Exported {len(graph_dto.edges)} edges to {edges_file}")

            duration = time.time() - start_time

            # Подія: EXPORT_SUCCESS
            self.publish_event(
                EventType.EXPORT_SUCCESS,
                data={
                    "exporter": "csv",
                    "output_path": output_path,
                    "nodes_count": len(graph_dto.nodes),
                    "edges_count": len(graph_dto.edges),
                    "duration": round(duration, 3),
                    "files": [nodes_file, edges_file],
                },
            )

            return True

        except Exception as e:
            error_msg = f"Failed to export graph to CSV: {e}"
            logger.error(error_msg)

            # Подія: EXPORT_ERROR
            self.publish_event(
                EventType.EXPORT_ERROR,
                data={
                    "exporter": "csv",
                    "error": error_msg,
                    "error_type": type(e).__name__,
                    "output_path": output_path,
                },
            )

            raise

    def _export_nodes(self, graph_dto: GraphDTO, file_path: str, include_metadata: bool):
        """
        Export nodes to CSV from GraphDTO.

        Args:
            graph_dto: GraphDTO instance
            file_path: Path до nodes CSV файлу
            include_metadata: Включити metadata
        """
        with open(file_path, "w", newline="", encoding="utf-8") as f:
            # Визначити columns
            base_columns = ["url", "depth", "title", "status_code", "content_type", "scanned"]

            if include_metadata and graph_dto.nodes:
                # Додати metadata columns з першого node
                first_node = graph_dto.nodes[0]
                metadata_keys = list(first_node.metadata.keys())
                # Виключити вже додані поля
                metadata_keys = [
                    k
                    for k in metadata_keys
                    if k not in ["title", "status_code", "content_type"]
                ]
                columns = base_columns + metadata_keys
            else:
                columns = base_columns

            writer = csv.DictWriter(
                f,
                fieldnames=columns,
                delimiter=self.delimiter,
                quoting=self.quoting,
                extrasaction="ignore",
            )
            writer.writeheader()

            # Записати nodes з DTO
            for node_dto in graph_dto.nodes:
                row = {
                    "url": node_dto.url,
                    "depth": node_dto.depth,
                    "title": node_dto.metadata.get("title", ""),
                    "status_code": node_dto.response_status or "",
                    "content_type": node_dto.metadata.get("content_type", ""),
                    "scanned": node_dto.scanned,
                }

                # Додати додаткові metadata
                if include_metadata:
                    for key, value in node_dto.metadata.items():
                        if key not in row:
                            # Convert to string для CSV
                            row[key] = str(value) if value is not None else ""

                writer.writerow(row)

    def _export_edges(self, graph_dto: GraphDTO, file_path: str):
        """
        Export edges to CSV from GraphDTO.

        Args:
            graph_dto: GraphDTO instance
            file_path: Path до edges CSV файлу
        """
        # Створюємо lookup dict для швидкого доступу до nodes по ID
        nodes_by_id = {node.node_id: node for node in graph_dto.nodes}

        with open(file_path, "w", newline="", encoding="utf-8") as f:
            columns = ["source_url", "target_url", "source_node_id", "target_node_id", "link_type", "metadata"]

            writer = csv.DictWriter(
                f, fieldnames=columns, delimiter=self.delimiter, quoting=self.quoting
            )
            writer.writeheader()

            # Записати edges з DTO
            for edge_dto in graph_dto.edges:
                source_node = nodes_by_id.get(edge_dto.source_node_id)
                target_node = nodes_by_id.get(edge_dto.target_node_id)

                row = {
                    "source_url": source_node.url if source_node else "",
                    "target_url": target_node.url if target_node else "",
                    "source_node_id": edge_dto.source_node_id,
                    "target_node_id": edge_dto.target_node_id,
                    "link_type": edge_dto.metadata.get("link_type", []),
                    "metadata": str(edge_dto.metadata),
                }
                writer.writerow(row)

    def export_to_single_file(
        self, graph_dto: GraphDTO, output_path: str, format: str = "nodes_only"
    ) -> bool:
        """
        Export graph to single CSV file.

        Args:
            graph_dto: GraphDTO instance
            output_path: Output file path
            format: 'nodes_only' або 'edges_only'

        Returns:
            bool: True якщо успішно
        """
        if format == "nodes_only":
            self._export_nodes(graph_dto, output_path, include_metadata=True)
        elif format == "edges_only":
            self._export_edges(graph_dto, output_path)
        else:
            raise ValueError(f"Unknown format: {format}")

        logger.info(f"Exported {format} to {output_path}")
        return True
