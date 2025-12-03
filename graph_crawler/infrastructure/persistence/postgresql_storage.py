"""Збереження графу у PostgreSQL базі даних через GraphDTO.
- Переписано на asyncpg для async операцій
- Всі методи тепер async  
- Використовує asyncpg connection pool
"""

import json
import logging
from typing import Any, Dict, List, Optional

from graph_crawler.application.dto import GraphDTO, NodeDTO, EdgeDTO, GraphStatsDTO
from graph_crawler.infrastructure.persistence.base import BaseStorage
from graph_crawler.shared.exceptions import LoadError, SaveError

logger = logging.getLogger(__name__)

# Check for asyncpg availability
try:
    import asyncpg

    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False
    asyncpg = None


class PostgreSQLStorage(BaseStorage):
    """
    Async збереження GraphDTO у PostgreSQL.

    BREAKING CHANGE: Тепер використовує GraphDTO замість Graph для ізоляції Domain Layer.

    Використовується для великих графів (>20k сторінок).
    Використовує asyncpg для async операцій.

    Приклад конфігурації:
        config = {
            'connection_string': 'postgresql://user:password@localhost:5432/graph_crawler'
            # АБО окремі параметри:
            'host': 'localhost',
            'port': 5432,
            'database': 'graph_crawler',
            'user': 'postgres',
            'password': 'password'
        }

    Приклад використання:
        >>> from graph_crawler.application.dto.mappers import GraphMapper
        >>>
        >>> storage = PostgreSQLStorage(config)
        >>> await storage.init()  # Async ініціалізація
        >>>
        >>> # Серіалізація Domain → DTO → PostgreSQL
        >>> graph_dto = GraphMapper.to_dto(graph)
        >>> await storage.save_graph(graph_dto)
        >>>
        >>> # Десеріалізація PostgreSQL → DTO → Domain
        >>> graph_dto = await storage.load_graph()
        >>> context = {'plugin_manager': pm, 'tree_parser': parser}
        >>> graph = GraphMapper.to_domain(graph_dto, context=context)
        >>> 
        >>> await storage.close()
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Ініціалізує PostgreSQLStorage.

        Args:
            config: Словник з налаштуваннями підключення до PostgreSQL

        Raises:
            ImportError: Якщо asyncpg не встановлений
        """
        super().__init__()
        self.config = config
        self.pool = None
        self._initialized = False

        if not ASYNCPG_AVAILABLE:
            logger.error("asyncpg not installed. Install it: pip install asyncpg")
            raise ImportError(
                "PostgreSQL async storage requires asyncpg. "
                "Install it: pip install asyncpg"
            )

        # Зберігаємо параметри для async init
        self.connection_string = config.get("connection_string")
        if not self.connection_string:
            host = config.get("host", "localhost")
            port = config.get("port", 5432)
            database = config.get("database", "graph_crawler")
            user = config.get("user", "postgres")
            password = config.get("password", "")
            self.connection_string = (
                f"postgresql://{user}:{password}@{host}:{port}/{database}"
            )

    async def init(self) -> None:
        """
        Async ініціалізація підключення до PostgreSQL.

        Викликати після створення екземпляру:
            storage = PostgreSQLStorage(config)
            await storage.init()
        """
        if self._initialized:
            return

        try:
            # Створюємо connection pool
            self.pool = await asyncpg.create_pool(
                self.connection_string, min_size=2, max_size=10
            )
            logger.info(
                f"Connected to PostgreSQL (async): {self.connection_string.split('@')[1] if '@' in self.connection_string else 'local'}"
            )
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise ConnectionError(f"Cannot connect to PostgreSQL: {e}") from e

        # Ініціалізуємо схему
        await self._init_schema()
        self._initialized = True
        logger.info(f"PostgreSQLStorage initialized successfully (async)")

    async def _init_schema(self) -> None:
        """Async створює таблиці для збереження графу (nodes, edges)."""
        async with self.pool.acquire() as conn:
            # Таблиця вузлів (nodes) - розширена для DTO
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS graph_nodes (
                    node_id VARCHAR(255) PRIMARY KEY,
                    url TEXT NOT NULL,
                    depth INTEGER DEFAULT 0,
                    scanned BOOLEAN DEFAULT FALSE,
                    should_scan BOOLEAN DEFAULT TRUE,
                    can_create_edges BOOLEAN DEFAULT TRUE,
                    response_status INTEGER,
                    metadata JSONB,
                    user_data JSONB,
                    content_hash VARCHAR(255),
                    priority INTEGER,
                    created_at TIMESTAMP,
                    lifecycle_stage VARCHAR(50)
                )
            """
            )

            # Таблиця ребер (edges) - розширена для DTO
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS graph_edges (
                    edge_id VARCHAR(255) PRIMARY KEY,
                    source_node_id VARCHAR(255) NOT NULL,
                    target_node_id VARCHAR(255) NOT NULL,
                    metadata JSONB,
                    created_at TIMESTAMP
                )
            """
            )

            # Індекси
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_nodes_url ON graph_nodes(url)
            """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_nodes_scanned ON graph_nodes(scanned)
            """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_edges_source ON graph_edges(source_node_id)
            """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_edges_target ON graph_edges(target_node_id)
            """
            )

            logger.debug("PostgreSQL schema initialized (async)")

    async def save_graph(self, graph_dto: GraphDTO) -> bool:
        """
        Async зберігає GraphDTO у PostgreSQL.

        BREAKING CHANGE: Тепер приймає GraphDTO замість Graph.

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
        if not self._initialized:
            await self.init()

        try:
            async with self.pool.acquire() as conn:
                # Початок транзакції
                async with conn.transaction():
                    # Очищуємо існуючі дані
                    await conn.execute("DELETE FROM graph_edges")
                    await conn.execute("DELETE FROM graph_nodes")

                    # Batch вставка вузлів з DTO
                    if graph_dto.nodes:
                        nodes_data = []
                        for node_dto in graph_dto.nodes:
                            nodes_data.append((
                                node_dto.node_id,
                                node_dto.url,
                                node_dto.depth,
                                node_dto.scanned,
                                node_dto.should_scan,
                                node_dto.can_create_edges,
                                node_dto.response_status,
                                json.dumps(node_dto.metadata),
                                json.dumps(node_dto.user_data),
                                node_dto.content_hash,
                                node_dto.priority,
                                node_dto.created_at,
                                node_dto.lifecycle_stage,
                            ))

                        await conn.executemany(
                            """
                            INSERT INTO graph_nodes 
                            (node_id, url, depth, scanned, should_scan, can_create_edges,
                             response_status, metadata, user_data, content_hash, priority,
                             created_at, lifecycle_stage)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                            """,
                            nodes_data,
                        )

                    # Batch вставка ребер з DTO
                    if graph_dto.edges:
                        edges_data = []
                        for edge_dto in graph_dto.edges:
                            edges_data.append((
                                edge_dto.edge_id,
                                edge_dto.source_node_id,
                                edge_dto.target_node_id,
                                json.dumps(edge_dto.metadata),
                                edge_dto.created_at,
                            ))

                        await conn.executemany(
                            """
                            INSERT INTO graph_edges 
                            (edge_id, source_node_id, target_node_id, metadata, created_at)
                            VALUES ($1, $2, $3, $4, $5)
                            """,
                            edges_data,
                        )

            logger.info(
                f"Graph saved to PostgreSQL (async): {len(graph_dto.nodes)} nodes, {len(graph_dto.edges)} edges"
            )
            return True

        except Exception as e:
            error_msg = f"Failed to save graph to PostgreSQL: {e}"
            logger.error(error_msg)
            raise SaveError(error_msg) from e

    async def load_graph(self, context: Optional[Dict[str, Any]] = None) -> Optional[GraphDTO]:
        """
        Async завантажує GraphDTO з PostgreSQL.

        BREAKING CHANGE: Тепер повертає GraphDTO замість Graph.

        Args:
            context: Контекст (не використовується в PostgreSQLStorage, але залишений для сумісності)

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
        if not self._initialized:
            await self.init()

        try:
            nodes_dtos = []
            edges_dtos = []

            async with self.pool.acquire() as conn:
                # Завантажуємо вузли
                rows = await conn.fetch("SELECT * FROM graph_nodes")
                for row in rows:
                    node_dto = NodeDTO(
                        node_id=row["node_id"],
                        url=row["url"],
                        depth=row["depth"],
                        scanned=row["scanned"],
                        should_scan=row["should_scan"],
                        can_create_edges=row["can_create_edges"],
                        response_status=row["response_status"],
                        metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                        user_data=json.loads(row["user_data"]) if row["user_data"] else {},
                        content_hash=row["content_hash"],
                        priority=row["priority"],
                        created_at=row["created_at"],
                        lifecycle_stage=row["lifecycle_stage"],
                    )
                    nodes_dtos.append(node_dto)

                # Завантажуємо ребра
                rows = await conn.fetch("SELECT * FROM graph_edges")
                for row in rows:
                    edge_dto = EdgeDTO(
                        edge_id=row["edge_id"],
                        source_node_id=row["source_node_id"],
                        target_node_id=row["target_node_id"],
                        metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                        created_at=row["created_at"],
                    )
                    edges_dtos.append(edge_dto)

            if not nodes_dtos:
                return None

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

            logger.info(
                f"Graph loaded from PostgreSQL (async): {len(nodes_dtos)} nodes, {len(edges_dtos)} edges"
            )
            return graph_dto

        except Exception as e:
            error_msg = f"Failed to load graph from PostgreSQL: {e}"
            logger.error(error_msg)
            raise LoadError(error_msg) from e

    async def save_partial(self, nodes: List[Dict], edges: List[Dict]) -> bool:
        """
        Async зберігає частину графу (інкрементально).

        Args:
            nodes: Список вузлів як dict
            edges: Список ребер як dict

        Returns:
            True якщо успішно
        """
        if not self._initialized:
            await self.init()

        try:
            async with self.pool.acquire() as conn:
                # Вставляємо вузли
                for node_data in nodes:
                    await conn.execute(
                        """
                        INSERT INTO graph_nodes 
                        (node_id, url, depth, scanned, should_scan, can_create_edges,
                         response_status, metadata, user_data, content_hash, priority,
                         created_at, lifecycle_stage)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                        ON CONFLICT (node_id) DO UPDATE SET
                            scanned = EXCLUDED.scanned,
                            metadata = EXCLUDED.metadata,
                            user_data = EXCLUDED.user_data
                        """,
                        node_data["node_id"],
                        node_data["url"],
                        node_data["depth"],
                        node_data["scanned"],
                        node_data.get("should_scan", True),
                        node_data.get("can_create_edges", True),
                        node_data.get("response_status"),
                        json.dumps(node_data.get("metadata", {})),
                        json.dumps(node_data.get("user_data", {})),
                        node_data.get("content_hash"),
                        node_data.get("priority"),
                        node_data.get("created_at"),
                        node_data.get("lifecycle_stage", "url_stage"),
                    )

                # Вставляємо ребра
                for edge_data in edges:
                    await conn.execute(
                        """
                        INSERT INTO graph_edges 
                        (edge_id, source_node_id, target_node_id, metadata, created_at)
                        VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (edge_id) DO NOTHING
                        """,
                        edge_data["edge_id"],
                        edge_data["source_node_id"],
                        edge_data["target_node_id"],
                        json.dumps(edge_data.get("metadata", {})),
                        edge_data.get("created_at"),
                    )

            return True

        except Exception as e:
            logger.error(f"Failed to save partial graph to PostgreSQL: {e}")
            return False

    async def clear(self) -> bool:
        """
        Async очищує таблиці (видаляє всі рядки).

        Returns:
            True якщо успішно
        """
        if not self._initialized:
            await self.init()

        try:
            async with self.pool.acquire() as conn:
                await conn.execute("DELETE FROM graph_edges")
                await conn.execute("DELETE FROM graph_nodes")
            logger.info("PostgreSQL storage cleared (async)")
            return True
        except Exception as e:
            logger.error(f"Failed to clear PostgreSQL storage: {e}")
            return False

    async def exists(self) -> bool:
        """
        Async перевіряє чи є дані в таблицях.

        Returns:
            True якщо є хоча б один вузол
        """
        if not self._initialized:
            await self.init()

        try:
            async with self.pool.acquire() as conn:
                count = await conn.fetchval("SELECT COUNT(*) FROM graph_nodes")
                return count > 0
        except Exception as e:
            logger.error(f"Failed to check PostgreSQL storage: {e}")
            return False

    async def close(self) -> None:
        """Async закриває з'єднання з PostgreSQL."""
        if self.pool:
            await self.pool.close()
            self._initialized = False
            logger.debug("PostgreSQL connection pool closed (async)")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.init()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
        return False
