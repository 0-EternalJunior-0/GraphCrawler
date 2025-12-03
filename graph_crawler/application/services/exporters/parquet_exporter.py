"""Parquet Exporter - Clean Architecture з DTO.

BREAKING CHANGE (Фаза 6): Тепер використовує GraphDTO замість Graph.

Exports graph to Parquet format (for big data processing with Spark/Dask).
"""

import logging
import time
from pathlib import Path
from typing import Optional

from graph_crawler.application.dto import GraphDTO, NodeDTO, EdgeDTO
from graph_crawler.application.services.exporters.base_exporter import BaseExporter
from graph_crawler.domain.events.events import EventType

try:
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq

    PYARROW_AVAILABLE = True
except ImportError:
    PYARROW_AVAILABLE = False

logger = logging.getLogger(__name__)


class ParquetExporter(BaseExporter):
    """
    Export graph to Parquet format через DTO.

    BREAKING CHANGE (Фаза 6): Тепер працює ТІЛЬКИ з GraphDTO.

    Features:
    - Columnar storage (efficient for big data)
    - Compression (snappy, gzip, brotli)
    - Compatible з Spark, Dask, Pandas
    - Partition support для великих datasets

    Requirements:
        pip install pandas pyarrow

    Example:
        >>> from graph_crawler.application.services.exporters import ParquetExporter
        >>> from graph_crawler.application.dto import GraphDTO
        >>>
        >>> exporter = ParquetExporter(compression='snappy')
        >>> exporter.export(graph_dto, './output/graph.parquet')
        >>>
        >>> # Read back:
        >>> import pandas as pd
        >>> df = pd.read_parquet('./output/graph_nodes.parquet')
    """

    def __init__(
        self,
        event_bus: Optional["EventBus"] = None,
        compression: str = "snappy",
        **kwargs,
    ):
        """
        Initialize Parquet exporter.

        Args:
            event_bus: EventBus для публікації подій (опціонально)
            compression: Compression codec ('snappy', 'gzip', 'brotli', None)
            **kwargs: Additional options

        Raises:
            ImportError: Якщо pyarrow не встановлено
        """
        super().__init__(event_bus=event_bus, **kwargs)
        if not PYARROW_AVAILABLE:
            raise ImportError(
                "pandas and pyarrow are required for ParquetExporter. "
                "Install with: pip install pandas pyarrow"
            )

        self.compression = compression

    def export(
        self,
        graph_dto: GraphDTO,
        output_path: str,
        partition_by: Optional[str] = None,
        **options,
    ) -> bool:
        """
        Export graph to Parquet files through DTO.

        BREAKING CHANGE (Фаза 6): Тепер приймає GraphDTO замість Graph.

        Args:
            graph_dto: GraphDTO для експорту
            output_path: Base path для output files
            partition_by: Column для partitioning (e.g., 'depth')
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
                "exporter": "parquet",
                "output_path": output_path,
                "nodes_count": len(graph_dto.nodes),
                "edges_count": len(graph_dto.edges),
            },
        )

        try:
            if not self.validate_graph(graph_dto):
                logger.warning("GraphDTO validation failed, exporting empty graph")

            # Створити output directory
            output_dir = Path(output_path).parent
            output_dir.mkdir(parents=True, exist_ok=True)

            # Export nodes
            nodes_file = f"{output_path}_nodes.parquet"
            self._export_nodes(graph_dto, nodes_file, partition_by)
            logger.info(f"Exported {len(graph_dto.nodes)} nodes to {nodes_file}")

            # Export edges
            edges_file = f"{output_path}_edges.parquet"
            self._export_edges(graph_dto, edges_file)
            logger.info(f"Exported {len(graph_dto.edges)} edges to {edges_file}")

            duration = time.time() - start_time

            # Подія: EXPORT_SUCCESS
            self.publish_event(
                EventType.EXPORT_SUCCESS,
                data={
                    "exporter": "parquet",
                    "output_path": output_path,
                    "nodes_count": len(graph_dto.nodes),
                    "edges_count": len(graph_dto.edges),
                    "duration": round(duration, 3),
                    "files": [nodes_file, edges_file],
                },
            )

            return True

        except Exception as e:
            error_msg = f"Failed to export graph to Parquet: {e}"
            logger.error(error_msg)

            # Подія: EXPORT_ERROR
            self.publish_event(
                EventType.EXPORT_ERROR,
                data={
                    "exporter": "parquet",
                    "error": error_msg,
                    "error_type": type(e).__name__,
                    "output_path": output_path,
                },
            )

            raise

    def _export_nodes(self, graph_dto: GraphDTO, file_path: str, partition_by: Optional[str]):
        """
        Export nodes to Parquet from GraphDTO.

        Args:
            graph_dto: GraphDTO instance
            file_path: Path до output file
            partition_by: Column для partitioning
        """
        # Create DataFrame from DTO
        nodes_data = []
        for node_dto in graph_dto.nodes:
            node_dict = {
                "node_id": node_dto.node_id,
                "url": node_dto.url,
                "depth": node_dto.depth,
                "title": node_dto.metadata.get("title", ""),
                "status_code": node_dto.response_status or 0,
                "content_type": node_dto.metadata.get("content_type", ""),
                "scanned": node_dto.scanned,
            }

            # Додати metadata (тільки примітивні типи)
            for key, value in node_dto.metadata.items():
                if key not in node_dict and isinstance(value, (str, int, float, bool)):
                    node_dict[key] = value

            nodes_data.append(node_dict)

        df = pd.DataFrame(nodes_data)

        # Write Parquet
        if partition_by and partition_by in df.columns:
            # Partitioned write
            table = pa.Table.from_pandas(df)
            pq.write_to_dataset(
                table,
                root_path=file_path.replace(".parquet", ""),
                partition_cols=[partition_by],
                compression=self.compression,
            )
        else:
            # Single file write
            df.to_parquet(
                file_path,
                compression=self.compression,
                index=False,
            )

    def _export_edges(self, graph_dto: GraphDTO, file_path: str):
        """
        Export edges to Parquet from GraphDTO.

        Args:
            graph_dto: GraphDTO instance
            file_path: Path до output file
        """
        # Створюємо lookup dict для швидкого доступу до nodes по ID
        nodes_by_id = {node.node_id: node for node in graph_dto.nodes}

        edges_data = []
        for edge_dto in graph_dto.edges:
            source_node = nodes_by_id.get(edge_dto.source_node_id)
            target_node = nodes_by_id.get(edge_dto.target_node_id)

            edges_data.append(
                {
                    "edge_id": edge_dto.edge_id,
                    "source_node_id": edge_dto.source_node_id,
                    "target_node_id": edge_dto.target_node_id,
                    "source_url": source_node.url if source_node else "",
                    "target_url": target_node.url if target_node else "",
                    "link_type": str(edge_dto.metadata.get("link_type", [])),
                }
            )

        df = pd.DataFrame(edges_data)
        df.to_parquet(
            file_path,
            compression=self.compression,
            index=False,
        )
