"""Збереження графу у SQLite базі даних через GraphDTO. Використовує aiosqlite для async database I/O."""

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

try:
    import aiosqlite

    AIOSQLITE_AVAILABLE = True
except ImportError:
    AIOSQLITE_AVAILABLE = False

import sqlite3

if TYPE_CHECKING:
    from graph_crawler.domain.events.event_bus import EventBus

import logging

from graph_crawler.application.dto import GraphDTO, NodeDTO, EdgeDTO, GraphStatsDTO
from graph_crawler.domain.events.events import EventType
from graph_crawler.infrastructure.persistence.base import BaseStorage
from graph_crawler.shared.constants import (
    SQLITE_CACHE_SIZE,
    SQLITE_JOURNAL_MODE,
    SQLITE_SYNCHRONOUS,
)
from graph_crawler.shared.exceptions import LoadError, SaveError

logger = logging.getLogger(__name__)


class SQLiteStorage(BaseStorage):
    """
    Async збереження GraphDTO у SQLite.

    BREAKING CHANGE: Тепер використовує GraphDTO замість Graph для ізоляції Domain Layer.

    Використовується для великих сайтів (>10k сторінок).
    Зручніше працювати з графом через SQL запити. Використовує aiosqlite для async database I/O.

    Example:
        >>> from graph_crawler.application.dto.mappers import GraphMapper
        >>>
        >>> # Серіалізація Domain → DTO → SQLite
        >>> graph_dto = GraphMapper.to_dto(graph)
        >>> await storage.save_graph(graph_dto)
        >>>
        >>> # Десеріалізація SQLite → DTO → Domain
        >>> graph_dto = await storage.load_graph()
        >>> context = {'plugin_manager': pm, 'tree_parser': parser}
        >>> graph = GraphMapper.to_domain(graph_dto, context=context)
    """

    def __init__(
        self,
        storage_dir: str = "/tmp/graph_crawler",
        event_bus: Optional["EventBus"] = None,
    ):
        """
        Ініціалізує SQLiteStorage.

        Args:
            storage_dir: Директорія для збереження SQLite БД
            event_bus: EventBus для публікації подій (опціонально)
        """
        super().__init__(event_bus=event_bus)
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.db_file = self.storage_dir / "graph.db"
        self.conn: Optional[sqlite3.Connection] = None
        self._async_conn = None
        self._init_db()

        if not AIOSQLITE_AVAILABLE:
            logger.warning("aiosqlite not installed, falling back to sync I/O")

    async def _get_async_connection(self):
        """Отримує async connection до БД."""
        if AIOSQLITE_AVAILABLE:
            if self._async_conn is None:
                self._async_conn = await aiosqlite.connect(str(self.db_file))
                self._async_conn.row_factory = aiosqlite.Row
                await self._async_conn.execute(
                    f"PRAGMA journal_mode={SQLITE_JOURNAL_MODE}"
                )
                await self._async_conn.execute(
                    f"PRAGMA synchronous={SQLITE_SYNCHRONOUS}"
                )
                await self._async_conn.execute(f"PRAGMA cache_size={SQLITE_CACHE_SIZE}")
            return self._async_conn
        return None

    def _get_connection(self) -> sqlite3.Connection:
        """Отримує або створює connection до БД."""
        if self.conn is None:
            self.conn = sqlite3.connect(str(self.db_file))
            self.conn.row_factory = sqlite3.Row
            self.conn.execute(f"PRAGMA journal_mode={SQLITE_JOURNAL_MODE}")
            self.conn.execute(f"PRAGMA synchronous={SQLITE_SYNCHRONOUS}")
            self.conn.execute(f"PRAGMA cache_size={SQLITE_CACHE_SIZE}")
        return self.conn

    def _init_db(self):
        """Ініціалізує структуру бази даних."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Таблиця вузлів
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS nodes (
                    node_id TEXT PRIMARY KEY,
                    url TEXT NOT NULL UNIQUE,
                    depth INTEGER NOT NULL,
                    scanned INTEGER NOT NULL,
                    should_scan INTEGER NOT NULL,
                    can_create_edges INTEGER NOT NULL,
                    metadata TEXT,
                    user_data TEXT,
                    response_status INTEGER,
                    content_hash TEXT,
                    priority INTEGER,
                    created_at TEXT,
                    lifecycle_stage TEXT
                )
            """
            )

            # Таблиця ребер
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS edges (
                    edge_id TEXT PRIMARY KEY,
                    source_node_id TEXT NOT NULL,
                    target_node_id TEXT NOT NULL,
                    metadata TEXT,
                    created_at TEXT,
                    FOREIGN KEY (source_node_id) REFERENCES nodes(node_id),
                    FOREIGN KEY (target_node_id) REFERENCES nodes(node_id)
                )
            """
            )

            # Індекси для швидкого пошуку
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_nodes_url ON nodes(url)")
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_nodes_scanned ON nodes(scanned)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_node_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_node_id)"
            )

            conn.commit()
            logger.info(f"SQLiteStorage database initialized at: {self.db_file}")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    async def save_graph(self, graph_dto: GraphDTO) -> bool:
        """
        Async зберігає GraphDTO у SQLite.

        BREAKING CHANGE: Тепер приймає GraphDTO замість Graph.

        Використовує aiosqlite для async database I/O.

        Args:
            graph_dto: GraphDTO для збереження

        Returns:
            True якщо успішно

        Raises:
            SaveError: Якщо не вдалося зберегти граф

        Example:
            >>> from graph_crawler.application.dto.mappers import GraphMapper
            >>> graph_dto = GraphMapper.to_dto(graph)
            >>> await storage.save_graph(graph_dto)
        """
        start_time = time.time()

        # Подія: STORAGE_SAVE_STARTED
        self.publish_event(
            EventType.STORAGE_SAVE_STARTED,
            data={
                "storage_type": "sqlite",
                "nodes_count": len(graph_dto.nodes),
                "edges_count": len(graph_dto.edges),
            },
        )

        try:
            if AIOSQLITE_AVAILABLE:
                conn = await self._get_async_connection()
                cursor = await conn.cursor()

                # Очищаємо існуючі дані
                await cursor.execute("DELETE FROM edges")
                await cursor.execute("DELETE FROM nodes")

                # Batch вставка вузлів з DTO
                nodes_data = []
                for node_dto in graph_dto.nodes:
                    nodes_data.append(
                        (
                            node_dto.node_id,
                            node_dto.url,
                            node_dto.depth,
                            1 if node_dto.scanned else 0,
                            1 if node_dto.should_scan else 0,
                            1 if node_dto.can_create_edges else 0,
                            json.dumps(node_dto.metadata),
                            json.dumps(node_dto.user_data),
                            node_dto.response_status,
                            node_dto.content_hash,
                            node_dto.priority,
                            node_dto.created_at.isoformat(),
                            node_dto.lifecycle_stage,
                        )
                    )

                await cursor.executemany(
                    """
                    INSERT INTO nodes (node_id, url, depth, scanned, should_scan, can_create_edges,
                                       metadata, user_data, response_status, content_hash, priority,
                                       created_at, lifecycle_stage)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    nodes_data,
                )

                # Batch вставка ребер з DTO
                edges_data = []
                for edge_dto in graph_dto.edges:
                    edges_data.append(
                        (
                            edge_dto.edge_id,
                            edge_dto.source_node_id,
                            edge_dto.target_node_id,
                            json.dumps(edge_dto.metadata),
                            edge_dto.created_at.isoformat(),
                        )
                    )

                await cursor.executemany(
                    """
                    INSERT INTO edges (edge_id, source_node_id, target_node_id, metadata, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    edges_data,
                )

                await conn.commit()
            else:
                # Fallback до sync
                conn = self._get_connection()
                cursor = conn.cursor()

                cursor.execute("DELETE FROM edges")
                cursor.execute("DELETE FROM nodes")

                nodes_data = []
                for node_dto in graph_dto.nodes:
                    nodes_data.append(
                        (
                            node_dto.node_id,
                            node_dto.url,
                            node_dto.depth,
                            1 if node_dto.scanned else 0,
                            1 if node_dto.should_scan else 0,
                            1 if node_dto.can_create_edges else 0,
                            json.dumps(node_dto.metadata),
                            json.dumps(node_dto.user_data),
                            node_dto.response_status,
                            node_dto.content_hash,
                            node_dto.priority,
                            node_dto.created_at.isoformat(),
                            node_dto.lifecycle_stage,
                        )
                    )

                cursor.executemany(
                    """
                    INSERT INTO nodes (node_id, url, depth, scanned, should_scan, can_create_edges,
                                       metadata, user_data, response_status, content_hash, priority,
                                       created_at, lifecycle_stage)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    nodes_data,
                )

                edges_data = []
                for edge_dto in graph_dto.edges:
                    edges_data.append(
                        (
                            edge_dto.edge_id,
                            edge_dto.source_node_id,
                            edge_dto.target_node_id,
                            json.dumps(edge_dto.metadata),
                            edge_dto.created_at.isoformat(),
                        )
                    )

                cursor.executemany(
                    """
                    INSERT INTO edges (edge_id, source_node_id, target_node_id, metadata, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    edges_data,
                )

                conn.commit()

            duration = time.time() - start_time

            # Подія: STORAGE_SAVE_SUCCESS
            self.publish_event(
                EventType.STORAGE_SAVE_SUCCESS,
                data={
                    "storage_type": "sqlite",
                    "nodes_count": len(nodes_data),
                    "edges_count": len(edges_data),
                    "duration": round(duration, 3),
                    "db_path": str(self.db_file),
                },
            )

            logger.info(
                f"Graph saved: {len(nodes_data)} nodes, {len(edges_data)} edges"
            )
            return True
        except Exception as e:
            error_msg = f"Failed to save graph: {e}"
            logger.error(error_msg)

            # Подія: STORAGE_SAVE_ERROR
            self.publish_event(
                EventType.STORAGE_SAVE_ERROR,
                data={
                    "storage_type": "sqlite",
                    "error": error_msg,
                    "error_type": type(e).__name__,
                },
            )
            raise SaveError(error_msg) from e

    async def load_graph(self, context: Optional[Dict[str, Any]] = None) -> Optional[GraphDTO]:
        """
        Async завантажує GraphDTO з SQLite.

        BREAKING CHANGE: Тепер повертає GraphDTO замість Graph.

        Використовує aiosqlite для async database I/O.

        Args:
            context: Контекст (не використовується в SQLiteStorage, але залишений для сумісності)

        Returns:
            GraphDTO або None якщо не знайдено

        Raises:
            LoadError: Якщо не вдалося завантажити граф

        Example:
            >>> graph_dto = await storage.load_graph()
            >>> # Конвертація в Domain Graph (якщо потрібно)
            >>> from graph_crawler.application.dto.mappers import GraphMapper
            >>> context = {'plugin_manager': pm, 'tree_parser': parser}
            >>> graph = GraphMapper.to_domain(graph_dto, context=context)
        """
        if not await self.exists():
            logger.warning("No saved graph found")
            return None

        start_time = time.time()

        # Подія: STORAGE_LOAD_STARTED
        self.publish_event(
            EventType.STORAGE_LOAD_STARTED,
            data={"storage_type": "sqlite", "db_path": str(self.db_file)},
        )

        try:
            nodes_dtos = []
            edges_dtos = []

            if AIOSQLITE_AVAILABLE:
                conn = await self._get_async_connection()
                cursor = await conn.cursor()

                # Завантажуємо вузли
                await cursor.execute("SELECT * FROM nodes")
                rows = await cursor.fetchall()
                for row in rows:
                    node_dto = NodeDTO(
                        node_id=row[0],
                        url=row[1],
                        depth=row[2],
                        scanned=bool(row[3]),
                        should_scan=bool(row[4]),
                        can_create_edges=bool(row[5]),
                        metadata=json.loads(row[6]) if row[6] else {},
                        user_data=json.loads(row[7]) if row[7] else {},
                        response_status=row[8],
                        content_hash=row[9],
                        priority=row[10],
                        created_at=row[11],
                        lifecycle_stage=row[12],
                    )
                    nodes_dtos.append(node_dto)

                # Завантажуємо ребра
                await cursor.execute("SELECT * FROM edges")
                rows = await cursor.fetchall()
                for row in rows:
                    edge_dto = EdgeDTO(
                        edge_id=row[0],
                        source_node_id=row[1],
                        target_node_id=row[2],
                        metadata=json.loads(row[3]) if row[3] else {},
                        created_at=row[4],
                    )
                    edges_dtos.append(edge_dto)
            else:
                # Fallback до sync
                conn = self._get_connection()
                cursor = conn.cursor()

                cursor.execute("SELECT * FROM nodes")
                for row in cursor.fetchall():
                    node_dto = NodeDTO(
                        node_id=row["node_id"],
                        url=row["url"],
                        depth=row["depth"],
                        scanned=bool(row["scanned"]),
                        should_scan=bool(row["should_scan"]),
                        can_create_edges=bool(row["can_create_edges"]),
                        metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                        user_data=json.loads(row["user_data"]) if row["user_data"] else {},
                        response_status=row["response_status"],
                        content_hash=row["content_hash"],
                        priority=row["priority"],
                        created_at=row["created_at"],
                        lifecycle_stage=row["lifecycle_stage"],
                    )
                    nodes_dtos.append(node_dto)

                cursor.execute("SELECT * FROM edges")
                for row in cursor.fetchall():
                    edge_dto = EdgeDTO(
                        edge_id=row["edge_id"],
                        source_node_id=row["source_node_id"],
                        target_node_id=row["target_node_id"],
                        metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                        created_at=row["created_at"],
                    )
                    edges_dtos.append(edge_dto)

            # Створюємо stats
            stats = GraphStatsDTO(
                total_nodes=len(nodes_dtos),
                scanned_nodes=sum(1 for n in nodes_dtos if n.scanned),
                unscanned_nodes=sum(1 for n in nodes_dtos if not n.scanned),
                total_edges=len(edges_dtos),
                avg_depth=sum(n.depth for n in nodes_dtos) / len(nodes_dtos) if nodes_dtos else 0.0,
                max_depth=max((n.depth for n in nodes_dtos), default=0),
            )

            # Створюємо GraphDTO
            graph_dto = GraphDTO(
                nodes=nodes_dtos,
                edges=edges_dtos,
                stats=stats,
            )

            duration = time.time() - start_time

            # Подія: STORAGE_LOAD_SUCCESS
            self.publish_event(
                EventType.STORAGE_LOAD_SUCCESS,
                data={
                    "storage_type": "sqlite",
                    "nodes_count": len(nodes_dtos),
                    "edges_count": len(edges_dtos),
                    "duration": round(duration, 3),
                    "db_path": str(self.db_file),
                },
            )

            logger.info(
                f"Graph loaded: {len(nodes_dtos)} nodes, {len(edges_dtos)} edges"
            )
            return graph_dto
        except Exception as e:
            error_msg = f"Failed to load graph: {e}"
            logger.error(error_msg)

            # Подія: STORAGE_LOAD_ERROR
            self.publish_event(
                EventType.STORAGE_LOAD_ERROR,
                data={
                    "storage_type": "sqlite",
                    "error": error_msg,
                    "error_type": type(e).__name__,
                },
            )

            raise LoadError(error_msg) from e

    async def save_partial(self, nodes: List[Dict], edges: List[Dict]) -> bool:
        """
        Async додає нові вузли та ребра до бази (інкрементальне збереження).

        Args:
            nodes: Список вузлів (dict)
            edges: Список ребер (dict)

        Returns:
            True якщо успішно
        """
        try:
            if AIOSQLITE_AVAILABLE:
                conn = await self._get_async_connection()
                cursor = await conn.cursor()

                # Вставляємо вузли (ігноруємо дублікати)
                for node_data in nodes:
                    await cursor.execute(
                        """
                        INSERT OR REPLACE INTO nodes
                        (node_id, url, depth, scanned, should_scan, can_create_edges, metadata, 
                         user_data, response_status, content_hash, priority, created_at, lifecycle_stage)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            node_data["node_id"],
                            node_data["url"],
                            node_data["depth"],
                            1 if node_data["scanned"] else 0,
                            1 if node_data.get("should_scan", True) else 0,
                            1 if node_data.get("can_create_edges", True) else 0,
                            json.dumps(node_data.get("metadata", {})),
                            json.dumps(node_data.get("user_data", {})),
                            node_data.get("response_status"),
                            node_data.get("content_hash"),
                            node_data.get("priority"),
                            node_data.get("created_at"),
                            node_data.get("lifecycle_stage", "url_stage"),
                        ),
                    )

                # Вставляємо ребра (ігноруємо дублікати)
                for edge_data in edges:
                    await cursor.execute(
                        """
                        INSERT OR IGNORE INTO edges
                        (edge_id, source_node_id, target_node_id, metadata, created_at)
                        VALUES (?, ?, ?, ?, ?)
                    """,
                        (
                            edge_data["edge_id"],
                            edge_data["source_node_id"],
                            edge_data["target_node_id"],
                            json.dumps(edge_data.get("metadata", {})),
                            edge_data.get("created_at"),
                        ),
                    )

                await conn.commit()
            else:
                # Fallback до sync
                conn = self._get_connection()
                cursor = conn.cursor()

                for node_data in nodes:
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO nodes
                        (node_id, url, depth, scanned, should_scan, can_create_edges, metadata,
                         user_data, response_status, content_hash, priority, created_at, lifecycle_stage)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            node_data["node_id"],
                            node_data["url"],
                            node_data["depth"],
                            1 if node_data["scanned"] else 0,
                            1 if node_data.get("should_scan", True) else 0,
                            1 if node_data.get("can_create_edges", True) else 0,
                            json.dumps(node_data.get("metadata", {})),
                            json.dumps(node_data.get("user_data", {})),
                            node_data.get("response_status"),
                            node_data.get("content_hash"),
                            node_data.get("priority"),
                            node_data.get("created_at"),
                            node_data.get("lifecycle_stage", "url_stage"),
                        ),
                    )

                for edge_data in edges:
                    cursor.execute(
                        """
                        INSERT OR IGNORE INTO edges
                        (edge_id, source_node_id, target_node_id, metadata, created_at)
                        VALUES (?, ?, ?, ?, ?)
                    """,
                        (
                            edge_data["edge_id"],
                            edge_data["source_node_id"],
                            edge_data["target_node_id"],
                            json.dumps(edge_data.get("metadata", {})),
                            edge_data.get("created_at"),
                        ),
                    )

                conn.commit()

            logger.debug(f"Saved partial: {len(nodes)} nodes, {len(edges)} edges")
            return True
        except Exception as e:
            logger.error(f"Failed to save partial graph: {e}")
            return False

    async def clear(self) -> bool:
        """Async очищує базу даних."""
        try:
            if self._async_conn:
                await self._async_conn.close()
                self._async_conn = None

            if self.conn:
                self.conn.close()
                self.conn = None

            if self.db_file.exists():
                self.db_file.unlink()
                logger.info("Storage cleared")

            self._init_db()
            return True
        except Exception as e:
            logger.error(f"Error clearing storage: {e}")
            return False

    async def exists(self) -> bool:
        """Async перевіряє чи існує база з даними."""
        if not self.db_file.exists():
            return False

        try:
            if AIOSQLITE_AVAILABLE:
                conn = await self._get_async_connection()
                cursor = await conn.cursor()
                await cursor.execute("SELECT COUNT(*) FROM nodes")
                row = await cursor.fetchone()
                count = row[0]
            else:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM nodes")
                count = cursor.fetchone()[0]
            return count > 0
        except Exception:
            return False

    async def close(self) -> None:
        """Async закриває SQLite з'єднання."""
        if self._async_conn:
            await self._async_conn.close()
            self._async_conn = None
        if self.conn:
            self.conn.close()
            self.conn = None

    def __del__(self):
        """Закриває sync connection при видаленні об'єкта."""
        if self.conn:
            self.conn.close()
            self.conn = None
        # Note: async connection should be closed via await close() explicitly
