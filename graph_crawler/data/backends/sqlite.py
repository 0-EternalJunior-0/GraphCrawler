"""
SQLiteBackend - SQLite Implementation of IGraphBackend.

"""

import asyncio
import json
import logging
import os
import re
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, Iterator, List, Optional, Set, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class SQLiteBackend:
    """
    SQLite Backend для Graph Storage.

    Persistent storage з streaming queries для великих графів.

    Schema:
        nodes: node_id, url, depth, scanned, response_status, content_hash,
               simhash, priority, metadata_json, user_data_json, created_at, updated_at
        edges: source_node_id, target_node_id, metadata_json, created_at

    Indexes:
        - nodes: url (unique), depth, scanned
        - edges: (source_node_id, target_node_id) unique

    Performance:
        - WAL mode for concurrent reads
        - Batch inserts for speed
        - Prepared statements caching
    """

    def __init__(self, db_path: str = ":memory:", journal_mode: str = "WAL"):
        """
        Ініціалізує SQLiteBackend.

        Args:
            db_path: Шлях до SQLite файлу або ":memory:" для in-memory
            journal_mode: WAL (швидше) або DELETE (сумісніше)
        """
        self.db_path = db_path
        self.journal_mode = journal_mode
        self._conn = None
        self._is_open = False

        # In-memory caches for fast access (updated on mutations)
        self._nodes: Dict[str, Any] = {}  # node_id -> Node (cache)
        self._edges: List[Any] = []  # List of Edge (cache)
        self._url_to_node: Dict[str, Any] = {}  # url -> Node (cache)
        self._edge_index: Set[Tuple[str, str]] = set()  # (source_id, target_id)
        self._adjacency_out: Dict[str, Set[str]] = defaultdict(set)
        self._adjacency_in: Dict[str, Set[str]] = defaultdict(set)

        # Async lock
        self._lock = asyncio.Lock()

        # Stats
        self._use_cache = True  # Use in-memory cache for fast reads

        logger.debug("SQLiteBackend initialized: %s", db_path)

    # ═══════════════════════════════════════════════════════════════════════════
    # LIFECYCLE
    # ═══════════════════════════════════════════════════════════════════════════

    async def open(self) -> None:
        """Відкриває з'єднання та ініціалізує схему."""
        try:
            import aiosqlite
        except ImportError:
            raise ImportError(
                "aiosqlite is required for SQLiteBackend. Install it with: pip install aiosqlite"
            )

        self._conn = await aiosqlite.connect(self.db_path)

        # Configure for performance
        await self._conn.execute(f"PRAGMA journal_mode={self.journal_mode}")
        await self._conn.execute("PRAGMA synchronous=NORMAL")
        await self._conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
        await self._conn.execute("PRAGMA temp_store=MEMORY")
        await self._init_schema()

        # Load cache from existing data
        if self._use_cache:
            await self._load_cache()

        self._is_open = True
        logger.info("SQLiteBackend opened: %s", self.db_path)

    async def _init_schema(self) -> None:
        """Створює таблиці та індекси."""
        await self._conn.executescript("""
            -- Nodes table
            CREATE TABLE IF NOT EXISTS nodes (
                node_id TEXT PRIMARY KEY,
                url TEXT UNIQUE NOT NULL,
                depth INTEGER DEFAULT 0,
                scanned INTEGER DEFAULT 0,
                response_status INTEGER,
                content_hash TEXT,
                simhash TEXT,
                priority INTEGER DEFAULT 0,
                metadata_json TEXT,
                user_data_json TEXT,
                created_at TEXT,
                updated_at TEXT
            );

            -- Edges table
            CREATE TABLE IF NOT EXISTS edges (
                source_node_id TEXT NOT NULL,
                target_node_id TEXT NOT NULL,
                metadata_json TEXT,
                created_at TEXT,
                PRIMARY KEY (source_node_id, target_node_id)
            );

            -- Indexes for performance
            CREATE INDEX IF NOT EXISTS idx_nodes_url ON nodes(url);
            CREATE INDEX IF NOT EXISTS idx_nodes_depth ON nodes(depth);
            CREATE INDEX IF NOT EXISTS idx_nodes_scanned ON nodes(scanned);
            CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_node_id);
            CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_node_id);
        """)
        await self._conn.commit()

    async def _load_cache(self) -> None:
        """Завантажує дані в кеш при відкритті."""
        # Load nodes
        async with self._conn.execute("SELECT * FROM nodes") as cursor:
            async for row in cursor:
                node = self._row_to_node(row)
                self._nodes[node.node_id] = node
                self._url_to_node[node.url] = node

        # Load edges
        async with self._conn.execute("SELECT * FROM edges") as cursor:
            async for row in cursor:
                edge = self._row_to_edge(row)
                self._edges.append(edge)
                self._edge_index.add((edge.source_node_id, edge.target_node_id))
                self._adjacency_out[edge.source_node_id].add(edge.target_node_id)
                self._adjacency_in[edge.target_node_id].add(edge.source_node_id)

        logger.debug("Cache loaded: %s nodes, %s edges", len(self._nodes), len(self._edges))

    async def close(self) -> None:
        """Закриває з'єднання."""
        if self._conn:
            await self._conn.close()
            self._conn = None
        self._is_open = False
        logger.info("SQLiteBackend closed")

    @asynccontextmanager
    async def transaction(self):
        """Context manager для транзакцій."""
        async with self._lock:
            try:
                yield
                await self._conn.commit()
            except Exception:
                await self._conn.rollback()
                raise

    async def checkpoint(self) -> None:
        """Примусовий flush на диск."""
        await self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    # ═══════════════════════════════════════════════════════════════════════════
    # URL NORMALIZATION
    # ═══════════════════════════════════════════════════════════════════════════

    def _normalize_url(self, url: str) -> str:
        """Нормалізує URL."""
        parsed = urlparse(url)
        netloc = parsed.netloc.lower().rstrip("\\")
        path = parsed.path.replace("\\", "/")
        path = re.sub(r"/+", "/", path)
        path = path.rstrip("/")

        normalized = f"{parsed.scheme}://{netloc}{path}"
        if parsed.query:
            normalized += f"?{parsed.query}"
        return normalized

    # ═══════════════════════════════════════════════════════════════════════════
    # NODE SERIALIZATION
    # ═══════════════════════════════════════════════════════════════════════════

    def _node_to_row(self, node: Any) -> tuple:
        """Конвертує Node в tuple для INSERT."""
        metadata_json = json.dumps(node.metadata) if node.metadata else None
        user_data_json = (
            json.dumps(node.user_data) if hasattr(node, "user_data") and node.user_data else None
        )
        now = datetime.now(timezone.utc).isoformat()

        return (
            node.node_id,
            node.url,
            getattr(node, "depth", 0),
            1 if getattr(node, "scanned", False) else 0,
            getattr(node, "response_status", None),
            getattr(node, "content_hash", None),
            getattr(node, "simhash", None),
            getattr(node, "priority", 0),
            metadata_json,
            user_data_json,
            now,
            now,
        )

    def _row_to_node(self, row: tuple) -> Any:
        """Конвертує row в Node."""
        from graph_crawler.domain.entities.node import Node

        node = Node(
            url=row[1],
            node_id=row[0],
        )
        node.depth = row[2] or 0
        node.scanned = bool(row[3])
        node.response_status = row[4]
        node.content_hash = row[5]
        node.simhash = row[6]
        node.priority = row[7] if row[7] and row[7] >= 1 else None

        if row[8]:  # metadata_json
            node.metadata = json.loads(row[8])
        if row[9]:  # user_data_json
            node.user_data = json.loads(row[9])

        return node

    def _edge_to_row(self, edge: Any) -> tuple:
        """Конвертує Edge в tuple для INSERT."""
        metadata_json = json.dumps(edge.metadata) if edge.metadata else None
        now = datetime.now(timezone.utc).isoformat()

        return (
            edge.source_node_id,
            edge.target_node_id,
            metadata_json,
            now,
        )

    def _row_to_edge(self, row: tuple) -> Any:
        """Конвертує row в Edge."""
        from graph_crawler.domain.entities.edge import Edge

        edge = Edge(
            source_node_id=row[0],
            target_node_id=row[1],
        )
        if row[2]:  # metadata_json
            edge.metadata = json.loads(row[2])

        return edge

    # ═══════════════════════════════════════════════════════════════════════════
    # NODE OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════════

    async def insert_node(self, node: Any) -> Any:
        """Додає ноду (без перезапису існуючої)."""
        # Normalize URL
        original_url = node.url
        normalized_url = self._normalize_url(original_url)

        if original_url != normalized_url:
            node.url = normalized_url
            if not hasattr(node, "metadata") or node.metadata is None:
                node.metadata = {}
            node.metadata["_original_url"] = original_url

        # Check cache first
        if self._use_cache and normalized_url in self._url_to_node:
            return self._url_to_node[normalized_url]

        async with self._lock:
            # Check DB
            cursor = await self._conn.execute(
                "SELECT * FROM nodes WHERE url = ?", (normalized_url,)
            )
            row = await cursor.fetchone()
            if row:
                existing = self._row_to_node(row)
                if self._use_cache:
                    self._nodes[existing.node_id] = existing
                    self._url_to_node[normalized_url] = existing
                return existing

            # Insert new
            await self._conn.execute(
                """INSERT INTO nodes
                   (node_id, url, depth, scanned, response_status, content_hash,
                    simhash, priority, metadata_json, user_data_json, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                self._node_to_row(node),
            )
            await self._conn.commit()

            # Update cache
            if self._use_cache:
                self._nodes[node.node_id] = node
                self._url_to_node[normalized_url] = node

            return node

    async def insert_node_overwrite(self, node: Any) -> Any:
        """Додає або перезаписує ноду."""
        normalized_url = self._normalize_url(node.url)
        node.url = normalized_url

        async with self._lock:
            await self._conn.execute(
                """INSERT OR REPLACE INTO nodes
                   (node_id, url, depth, scanned, response_status, content_hash,
                    simhash, priority, metadata_json, user_data_json, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                self._node_to_row(node),
            )
            await self._conn.commit()

            if self._use_cache:
                self._nodes[node.node_id] = node
                self._url_to_node[normalized_url] = node

            return node

    async def insert_nodes_batch(self, nodes: List[Any]) -> int:
        """Batch insert нод."""
        async with self._lock:
            count = 0
            for node in nodes:
                normalized_url = self._normalize_url(node.url)
                node.url = normalized_url
                if self._use_cache and normalized_url in self._url_to_node:
                    continue

                try:
                    await self._conn.execute(
                        """INSERT OR IGNORE INTO nodes
                           (node_id, url, depth, scanned, response_status, content_hash,
                            simhash, priority, metadata_json, user_data_json, created_at, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        self._node_to_row(node),
                    )
                    if self._use_cache:
                        self._nodes[node.node_id] = node
                        self._url_to_node[normalized_url] = node
                    count += 1
                except Exception:
                    pass  # Ignore duplicates

            await self._conn.commit()
            return count

    async def get_node_by_url(self, url: str) -> Optional[Any]:
        """Отримує ноду за URL."""
        normalized = self._normalize_url(url)

        # Check cache
        if self._use_cache and normalized in self._url_to_node:
            return self._url_to_node[normalized]

        cursor = await self._conn.execute("SELECT * FROM nodes WHERE url = ?", (normalized,))
        row = await cursor.fetchone()
        if row:
            node = self._row_to_node(row)
            if self._use_cache:
                self._nodes[node.node_id] = node
                self._url_to_node[normalized] = node
            return node
        return None

    async def get_node_by_id(self, node_id: str) -> Optional[Any]:
        """Отримує ноду за ID."""
        if self._use_cache and node_id in self._nodes:
            return self._nodes[node_id]

        cursor = await self._conn.execute("SELECT * FROM nodes WHERE node_id = ?", (node_id,))
        row = await cursor.fetchone()
        if row:
            node = self._row_to_node(row)
            if self._use_cache:
                self._nodes[node.node_id] = node
                self._url_to_node[node.url] = node
            return node
        return None

    async def get_nodes_batch(self, urls: List[str]) -> Dict[str, Any]:
        """Batch отримання нод."""
        result = {}
        for url in urls:
            node = await self.get_node_by_url(url)
            if node:
                result[url] = node
        return result

    async def update_node(self, node: Any) -> bool:
        """Оновлює ноду."""
        async with self._lock:
            cursor = await self._conn.execute(
                """UPDATE nodes SET
                   depth=?, scanned=?, response_status=?, content_hash=?,
                   simhash=?, priority=?, metadata_json=?, user_data_json=?, updated_at=?
                   WHERE node_id=?""",
                (
                    getattr(node, "depth", 0),
                    1 if getattr(node, "scanned", False) else 0,
                    getattr(node, "response_status", None),
                    getattr(node, "content_hash", None),
                    getattr(node, "simhash", None),
                    getattr(node, "priority", 0),
                    json.dumps(node.metadata) if node.metadata else None,
                    json.dumps(node.user_data)
                    if hasattr(node, "user_data") and node.user_data
                    else None,
                    datetime.now(timezone.utc).isoformat(),
                    node.node_id,
                ),
            )
            await self._conn.commit()

            if cursor.rowcount > 0:
                if self._use_cache:
                    self._nodes[node.node_id] = node
                    self._url_to_node[node.url] = node
                return True
            return False

    async def delete_node(self, node_id: str) -> bool:
        """Видаляє ноду."""
        async with self._lock:
            # Get node for cache cleanup
            node = self._nodes.get(node_id) if self._use_cache else None
            if not node:
                cursor = await self._conn.execute(
                    "SELECT url FROM nodes WHERE node_id = ?", (node_id,)
                )
                row = await cursor.fetchone()
                if not row:
                    return False
                url = row[0]
            else:
                url = node.url

            # Delete from DB
            await self._conn.execute("DELETE FROM nodes WHERE node_id = ?", (node_id,))
            await self._conn.execute(
                "DELETE FROM edges WHERE source_node_id = ? OR target_node_id = ?",
                (node_id, node_id),
            )
            await self._conn.commit()

            # Update cache
            if self._use_cache:
                self._nodes.pop(node_id, None)
                self._url_to_node.pop(url, None)

                # Remove related edges from cache
                self._edges = [
                    e
                    for e in self._edges
                    if e.source_node_id != node_id and e.target_node_id != node_id
                ]
                self._edge_index = {
                    (s, t) for s, t in self._edge_index if s != node_id and t != node_id
                }
                self._adjacency_out.pop(node_id, None)
                self._adjacency_in.pop(node_id, None)

            return True

    async def url_exists(self, url: str) -> bool:
        """Перевіряє чи URL існує."""
        normalized = self._normalize_url(url)

        if self._use_cache:
            return normalized in self._url_to_node

        cursor = await self._conn.execute(
            "SELECT 1 FROM nodes WHERE url = ? LIMIT 1", (normalized,)
        )
        return await cursor.fetchone() is not None

    async def urls_exist_batch(self, urls: List[str]) -> Set[str]:
        """Batch перевірка URLs."""
        result = set()
        for url in urls:
            if await self.url_exists(url):
                result.add(url)
        return result

    # ═══════════════════════════════════════════════════════════════════════════
    # EDGE OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════════

    async def insert_edge(self, edge: Any) -> Any:
        """Додає ребро."""
        async with self._lock:
            try:
                await self._conn.execute(
                    """INSERT OR IGNORE INTO edges
                       (source_node_id, target_node_id, metadata_json, created_at)
                       VALUES (?, ?, ?, ?)""",
                    self._edge_to_row(edge),
                )
                await self._conn.commit()
            except Exception:
                pass  # Ignore duplicates

            # Update cache
            if self._use_cache:
                key = (edge.source_node_id, edge.target_node_id)
                if key not in self._edge_index:
                    self._edges.append(edge)
                    self._edge_index.add(key)
                    self._adjacency_out[edge.source_node_id].add(edge.target_node_id)
                    self._adjacency_in[edge.target_node_id].add(edge.source_node_id)

            return edge

    async def insert_edges_batch(self, edges: List[Any]) -> int:
        """Batch insert ребер."""
        async with self._lock:
            count = 0
            for edge in edges:
                key = (edge.source_node_id, edge.target_node_id)
                if self._use_cache and key in self._edge_index:
                    continue

                try:
                    await self._conn.execute(
                        """INSERT OR IGNORE INTO edges
                           (source_node_id, target_node_id, metadata_json, created_at)
                           VALUES (?, ?, ?, ?)""",
                        self._edge_to_row(edge),
                    )

                    if self._use_cache:
                        self._edges.append(edge)
                        self._edge_index.add(key)
                        self._adjacency_out[edge.source_node_id].add(edge.target_node_id)
                        self._adjacency_in[edge.target_node_id].add(edge.source_node_id)
                    count += 1
                except Exception:
                    pass  # Non-critical: cleanup/fallback

            await self._conn.commit()
            return count

    async def get_edges_from(self, source_node_id: str) -> List[Any]:
        """Отримує ребра ВІД ноди."""
        if self._use_cache:
            return [e for e in self._edges if e.source_node_id == source_node_id]

        result = []
        async with self._conn.execute(
            "SELECT * FROM edges WHERE source_node_id = ?", (source_node_id,)
        ) as cursor:
            async for row in cursor:
                result.append(self._row_to_edge(row))
        return result

    async def get_edges_to(self, target_node_id: str) -> List[Any]:
        """Отримує ребра ДО ноди."""
        if self._use_cache:
            return [e for e in self._edges if e.target_node_id == target_node_id]

        result = []
        async with self._conn.execute(
            "SELECT * FROM edges WHERE target_node_id = ?", (target_node_id,)
        ) as cursor:
            async for row in cursor:
                result.append(self._row_to_edge(row))
        return result

    async def edge_exists(self, source_node_id: str, target_node_id: str) -> bool:
        """Перевіряє чи існує ребро."""
        if self._use_cache:
            return (source_node_id, target_node_id) in self._edge_index

        cursor = await self._conn.execute(
            "SELECT 1 FROM edges WHERE source_node_id = ? AND target_node_id = ? LIMIT 1",
            (source_node_id, target_node_id),
        )
        return await cursor.fetchone() is not None

    async def delete_edges_for_node(self, node_id: str) -> int:
        """Видаляє всі ребра для ноди."""
        async with self._lock:
            cursor = await self._conn.execute(
                "DELETE FROM edges WHERE source_node_id = ? OR target_node_id = ?",
                (node_id, node_id),
            )
            await self._conn.commit()

            if self._use_cache:
                self._edges = [
                    e
                    for e in self._edges
                    if e.source_node_id != node_id and e.target_node_id != node_id
                ]
                old_count = len(self._edge_index)
                self._edge_index = {
                    (s, t) for s, t in self._edge_index if s != node_id and t != node_id
                }
                self._adjacency_out.pop(node_id, None)
                self._adjacency_in.pop(node_id, None)
                return old_count - len(self._edge_index)

            return cursor.rowcount

    # ═══════════════════════════════════════════════════════════════════════════
    # QUERY OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════════

    async def count_nodes(self) -> int:
        """Повертає кількість нод."""
        if self._use_cache:
            return len(self._nodes)

        cursor = await self._conn.execute("SELECT COUNT(*) FROM nodes")
        row = await cursor.fetchone()
        return row[0]

    async def count_edges(self) -> int:
        """Повертає кількість ребер."""
        if self._use_cache:
            return len(self._edges)

        cursor = await self._conn.execute("SELECT COUNT(*) FROM edges")
        row = await cursor.fetchone()
        return row[0]

    async def count_nodes_by_status(self, scanned: bool) -> int:
        """Повертає кількість нод за статусом."""
        if self._use_cache:
            return sum(1 for n in self._nodes.values() if n.scanned == scanned)

        cursor = await self._conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE scanned = ?", (1 if scanned else 0,)
        )
        row = await cursor.fetchone()
        return row[0]

    async def get_stats(self) -> Dict[str, Any]:
        """Повертає статистику."""
        total = await self.count_nodes()
        scanned = await self.count_nodes_by_status(True)
        edges = await self.count_edges()

        # Get file size
        db_size_mb = 0.0
        if self.db_path != ":memory:" and os.path.exists(self.db_path):
            db_size_mb = os.path.getsize(self.db_path) / (1024 * 1024)

        return {
            "backend_type": "sqlite",
            "db_path": self.db_path,
            "total_nodes": total,
            "total_edges": edges,
            "scanned_nodes": scanned,
            "unscanned_nodes": total - scanned,
            "db_size_mb": round(db_size_mb, 2),
            "cache_enabled": self._use_cache,
        }

    # ═══════════════════════════════════════════════════════════════════════════
    # STREAMING OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════════

    async def iter_nodes(self, batch_size: int = 1000) -> AsyncIterator[Any]:
        """Streaming ітератор по нодах."""
        if self._use_cache:
            for node in self._nodes.values():
                yield node
            return

        offset = 0
        while True:
            cursor = await self._conn.execute(
                "SELECT * FROM nodes LIMIT ? OFFSET ?", (batch_size, offset)
            )
            rows = await cursor.fetchall()
            if not rows:
                break
            for row in rows:
                yield self._row_to_node(row)
            offset += batch_size

    async def iter_edges(self, batch_size: int = 1000) -> AsyncIterator[Any]:
        """Streaming ітератор по ребрах."""
        if self._use_cache:
            for edge in self._edges:
                yield edge
            return

        offset = 0
        while True:
            cursor = await self._conn.execute(
                "SELECT * FROM edges LIMIT ? OFFSET ?", (batch_size, offset)
            )
            rows = await cursor.fetchall()
            if not rows:
                break
            for row in rows:
                yield self._row_to_edge(row)
            offset += batch_size

    async def iter_unscanned_nodes(self, batch_size: int = 100) -> AsyncIterator[Any]:
        """Streaming ітератор по unscanned нодах."""
        if self._use_cache:
            for node in self._nodes.values():
                if not node.scanned:
                    yield node
            return

        offset = 0
        while True:
            cursor = await self._conn.execute(
                "SELECT * FROM nodes WHERE scanned = 0 LIMIT ? OFFSET ?", (batch_size, offset)
            )
            rows = await cursor.fetchall()
            if not rows:
                break
            for row in rows:
                yield self._row_to_node(row)
            offset += batch_size

    async def iter_nodes_at_depth(self, depth: int, batch_size: int = 1000) -> AsyncIterator[Any]:
        """Streaming ітератор по нодах на глибині."""
        if self._use_cache:
            for node in self._nodes.values():
                if node.depth == depth:
                    yield node
            return

        offset = 0
        while True:
            cursor = await self._conn.execute(
                "SELECT * FROM nodes WHERE depth = ? LIMIT ? OFFSET ?", (depth, batch_size, offset)
            )
            rows = await cursor.fetchall()
            if not rows:
                break
            for row in rows:
                yield self._row_to_node(row)
            offset += batch_size

    # ═══════════════════════════════════════════════════════════════════════════
    # SYNC WRAPPERS
    # ═══════════════════════════════════════════════════════════════════════════

    def _run_async(self, coro):
        """Запускає coroutine синхронно."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Already in async context - use cache directly
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, coro)
                    return future.result()
            return loop.run_until_complete(coro)
        except RuntimeError:
            return asyncio.run(coro)

    def insert_node_sync(self, node: Any) -> Any:
        """Sync версія insert_node."""
        # Use cache directly for sync calls
        normalized_url = self._normalize_url(node.url)
        if normalized_url in self._url_to_node:
            return self._url_to_node[normalized_url]

        # Insert to cache (DB will be synced on next async call)
        node.url = normalized_url
        self._nodes[node.node_id] = node
        self._url_to_node[normalized_url] = node
        return node

    def get_node_by_url_sync(self, url: str) -> Optional[Any]:
        """Sync версія get_node_by_url."""
        normalized = self._normalize_url(url)
        return self._url_to_node.get(normalized)

    def get_node_by_id_sync(self, node_id: str) -> Optional[Any]:
        """Sync версія get_node_by_id."""
        return self._nodes.get(node_id)

    def url_exists_sync(self, url: str) -> bool:
        """Sync версія url_exists."""
        normalized = self._normalize_url(url)
        return normalized in self._url_to_node

    def count_nodes_sync(self) -> int:
        """Sync версія count_nodes."""
        return len(self._nodes)

    def count_edges_sync(self) -> int:
        """Sync версія count_edges."""
        return len(self._edges)

    def iter_nodes_sync(self, batch_size: int = 1000) -> Iterator[Any]:
        """Sync streaming ітератор."""
        yield from self._nodes.values()

    def iter_edges_sync(self, batch_size: int = 1000) -> Iterator[Any]:
        """Sync streaming ітератор по ребрах."""
        yield from self._edges

    # ═══════════════════════════════════════════════════════════════════════════
    # DIRECT ACCESS (for backward compatibility)
    # ═══════════════════════════════════════════════════════════════════════════

    @property
    def nodes(self) -> Dict[str, Any]:
        """Direct access to nodes cache."""
        return self._nodes

    @property
    def edges(self) -> List[Any]:
        """Direct access to edges cache."""
        return self._edges

    @property
    def url_to_node(self) -> Dict[str, Any]:
        """Direct access to url_to_node cache."""
        return self._url_to_node

    @property
    def edge_index(self) -> Set[Tuple[str, str]]:
        """Direct access to edge_index."""
        return self._edge_index

    @property
    def adjacency_out(self) -> Dict[str, Set[str]]:
        """Direct access to adjacency_out."""
        return self._adjacency_out

    @property
    def adjacency_in(self) -> Dict[str, Set[str]]:
        """Direct access to adjacency_in."""
        return self._adjacency_in


__all__ = ["SQLiteBackend"]
