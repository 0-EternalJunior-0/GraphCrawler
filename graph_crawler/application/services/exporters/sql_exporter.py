"""SQL Exporter - Clean Architecture з DTO.

BREAKING CHANGE (Фаза 6): Тепер використовує GraphDTO замість Graph.

Exports graph to SQL databases (PostgreSQL, MySQL, SQLite).
"""

import json
import logging
import time
from typing import Optional

from graph_crawler.application.dto import GraphDTO, NodeDTO, EdgeDTO
from graph_crawler.application.services.exporters.base_exporter import BaseExporter
from graph_crawler.domain.events.events import EventType

try:
    from sqlalchemy import Column, Integer, MetaData, String, Table, Text, create_engine
    from sqlalchemy.orm import sessionmaker

    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False

logger = logging.getLogger(__name__)


class SQLExporter(BaseExporter):
    """
    Export graph to SQL database через DTO.

    BREAKING CHANGE (Фаза 6): Тепер працює ТІЛЬКИ з GraphDTO.

    Supports:
    - PostgreSQL
    - MySQL
    - SQLite

    Creates two tables:
    - graph_nodes: містить node information
    - graph_edges: містить edge connections

    Requirements:
        pip install sqlalchemy

        # For PostgreSQL:
        pip install psycopg2-binary

        # For MySQL:
        pip install pymysql

    Example:
        >>> from graph_crawler.application.services.exporters import SQLExporter
        >>> from graph_crawler.application.dto import GraphDTO
        >>>
        >>> # SQLite
        >>> exporter = SQLExporter('sqlite:///graph.db')
        >>> exporter.export(graph_dto, table_prefix='my_crawl')
        >>>
        >>> # PostgreSQL
        >>> exporter = SQLExporter('postgresql://user:pass@localhost/dbname')
        >>> exporter.export(graph_dto, table_prefix='crawl_20250124')
    """

    def __init__(
        self, connection_string: str, event_bus: Optional["EventBus"] = None, **kwargs
    ):
        """
        Initialize SQL exporter.

        Args:
            connection_string: SQLAlchemy connection string
            event_bus: EventBus для публікації подій (опціонально)
            **kwargs: Additional options

        Raises:
            ImportError: Якщо SQLAlchemy не встановлено
        """
        super().__init__(event_bus=event_bus, **kwargs)
        if not SQLALCHEMY_AVAILABLE:
            raise ImportError(
                "sqlalchemy is required for SQLExporter. "
                "Install with: pip install sqlalchemy"
            )

        self.connection_string = connection_string
        self.engine = create_engine(connection_string)
        self.metadata = MetaData()

    def export(
        self,
        graph_dto: GraphDTO,
        table_prefix: str = "graph",
        drop_existing: bool = False,
        **options,
    ) -> bool:
        """
        Export graph to SQL database through DTO.

        BREAKING CHANGE (Фаза 6): Тепер приймає GraphDTO замість Graph.

        Args:
            graph_dto: GraphDTO для експорту
            table_prefix: Prefix для table names
            drop_existing: Видалити існуючі таблиці
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
                "exporter": "sql",
                "connection": self.connection_string,
                "table_prefix": table_prefix,
                "nodes_count": len(graph_dto.nodes),
                "edges_count": len(graph_dto.edges),
            },
        )

        try:
            if not self.validate_graph(graph_dto):
                logger.warning("GraphDTO validation failed, exporting empty graph")

            # Create tables
            nodes_table = self._create_nodes_table(table_prefix)
            edges_table = self._create_edges_table(table_prefix)

            if drop_existing:
                nodes_table.drop(self.engine, checkfirst=True)
                edges_table.drop(self.engine, checkfirst=True)

            self.metadata.create_all(self.engine)

            # Insert data from DTO
            self._insert_nodes(graph_dto, nodes_table)
            self._insert_edges(graph_dto, edges_table)

            duration = time.time() - start_time

            # Подія: EXPORT_SUCCESS
            self.publish_event(
                EventType.EXPORT_SUCCESS,
                data={
                    "exporter": "sql",
                    "table_prefix": table_prefix,
                    "nodes_count": len(graph_dto.nodes),
                    "edges_count": len(graph_dto.edges),
                    "duration": round(duration, 3),
                },
            )

            logger.info(
                f"Exported graph to SQL: {len(graph_dto.nodes)} nodes, "
                f"{len(graph_dto.edges)} edges"
            )
            return True

        except Exception as e:
            error_msg = f"Failed to export graph to SQL: {e}"
            logger.error(error_msg)

            # Подія: EXPORT_ERROR
            self.publish_event(
                EventType.EXPORT_ERROR,
                data={
                    "exporter": "sql",
                    "error": error_msg,
                    "error_type": type(e).__name__,
                    "table_prefix": table_prefix,
                },
            )

            raise

    def _create_nodes_table(self, table_prefix: str) -> "Table":
        """
        Create nodes table schema.

        Args:
            table_prefix: Table prefix

        Returns:
            Table: SQLAlchemy Table object
        """
        return Table(
            f"{table_prefix}_nodes",
            self.metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("node_id", String(36), nullable=False, unique=True),
            Column("url", Text, nullable=False),
            Column("depth", Integer),
            Column("title", Text),
            Column("status_code", Integer),
            Column("content_type", String(255)),
            Column("scanned", Integer),  # Boolean as integer
            Column("metadata_json", Text),  # JSON string для додаткових metadata
        )

    def _create_edges_table(self, table_prefix: str) -> "Table":
        """
        Create edges table schema.

        Args:
            table_prefix: Table prefix

        Returns:
            Table: SQLAlchemy Table object
        """
        return Table(
            f"{table_prefix}_edges",
            self.metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("edge_id", String(36), nullable=False, unique=True),
            Column("source_node_id", String(36), nullable=False),
            Column("target_node_id", String(36), nullable=False),
            Column("source_url", Text),
            Column("target_url", Text),
            Column("link_type", String(255)),
            Column("metadata_json", Text),
        )

    def _insert_nodes(self, graph_dto: GraphDTO, table: "Table"):
        """
        Insert nodes into database from GraphDTO.

        Args:
            graph_dto: GraphDTO instance
            table: Nodes table
        """
        with self.engine.connect() as conn:
            for node_dto in graph_dto.nodes:
                # Prepare metadata JSON (виключаємо вже додані поля)
                metadata_dict = {
                    k: v
                    for k, v in node_dto.metadata.items()
                    if k not in ["title", "status_code", "content_type"]
                }

                conn.execute(
                    table.insert().values(
                        node_id=node_dto.node_id,
                        url=node_dto.url,
                        depth=node_dto.depth,
                        title=node_dto.metadata.get("title", ""),
                        status_code=node_dto.response_status,
                        content_type=node_dto.metadata.get("content_type", ""),
                        scanned=1 if node_dto.scanned else 0,
                        metadata_json=json.dumps(metadata_dict),
                    )
                )
            conn.commit()

    def _insert_edges(self, graph_dto: GraphDTO, table: "Table"):
        """
        Insert edges into database from GraphDTO.

        Args:
            graph_dto: GraphDTO instance
            table: Edges table
        """
        # Створюємо lookup dict для швидкого доступу до nodes по ID
        nodes_by_id = {node.node_id: node for node in graph_dto.nodes}

        with self.engine.connect() as conn:
            for edge_dto in graph_dto.edges:
                source_node = nodes_by_id.get(edge_dto.source_node_id)
                target_node = nodes_by_id.get(edge_dto.target_node_id)

                conn.execute(
                    table.insert().values(
                        edge_id=edge_dto.edge_id,
                        source_node_id=edge_dto.source_node_id,
                        target_node_id=edge_dto.target_node_id,
                        source_url=source_node.url if source_node else "",
                        target_url=target_node.url if target_node else "",
                        link_type=str(edge_dto.metadata.get("link_type", [])),
                        metadata_json=json.dumps(edge_dto.metadata),
                    )
                )
            conn.commit()
