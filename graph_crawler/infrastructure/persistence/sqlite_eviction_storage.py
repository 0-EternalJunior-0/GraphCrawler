"""
SQLiteEvictionStorage - спеціалізований storage для eviction operations.

Оптимізований для:
1. APPEND операцій (batch inserts)
2. LOOKUP операцій (indexed URL)
3. WAL mode для concurrent access

Відмінності від SQLiteStorage:
- НЕ підтримує load_graph() - тільки окремі ноди
- Оптимізований для high-throughput writes
- Мінімальний overhead для eviction workflow

ВИПРАВЛЕНО v4.0:
- Ultra-fast batch inserts з PRAGMA optimizations
- Chunked processing для великих batches (35k+ нод)
- Deferred index rebuild для max insert speed
- Page size 8KB для кращого I/O

ВИПРАВЛЕНО v4.1:
- Автоматичне збереження кастомних полів підкласів Node
- Відновлення кастомних полів при завантаженні з диску
- Підтримка _custom_fields в user_data для повної серіалізації
"""

import asyncio
import json
import logging
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, Set, Type

logger = logging.getLogger(__name__)

# Thread pool для неблокуючих SQLite операцій - збільшено workers
_sqlite_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="sqlite_eviction_")

# Оптимальний розмір chunk для batch inserts
# 5000 записів - баланс між швидкістю та memory usage
_BATCH_CHUNK_SIZE = 5000

# Базові поля Node які не потрібно зберігати в _custom_fields
_BASE_NODE_FIELDS: FrozenSet[str] = frozenset(
    {
        "url",
        "node_id",
        "depth",
        "should_scan",
        "can_create_edges",
        "created_at",
        "metadata",
        "user_data",
        "scanned",
        "response_status",
        "content_hash",
        "simhash",
        "priority",
        "lifecycle_stage",
        "content_type",
        "plugin_manager",
        "tree_parser",
        "hash_strategy",
        "simhash_strategy",
    }
)

# Базові поля Edge які не потрібно зберігати в _custom_fields
_BASE_EDGE_FIELDS: FrozenSet[str] = frozenset(
    {"source_node_id", "target_node_id", "edge_id", "metadata", "created_at"}
)


def _extract_custom_fields(node: Any) -> Dict[str, Any]:
    """
    Витягує кастомні поля з підкласу Node для збереження.

    Працює з будь-яким підкласом Node (JobsNode, CustomNode, etc.)
    Зберігає тільки серіалізовані типи (str, int, float, bool, list, dict).

    Args:
        node: Node або підклас Node

    Returns:
        Dict з кастомними полями або пустий dict
    """
    # Перевіряємо чи є це Pydantic модель з model_fields
    if not hasattr(node, "model_fields"):
        return {}

    custom_fields = {}
    for field_name in node.model_fields:
        if field_name not in _BASE_NODE_FIELDS:
            value = getattr(node, field_name, None)
            # Зберігаємо тільки серіалізовані типи
            if value is not None and isinstance(value, (str, int, float, bool, list, dict)):
                custom_fields[field_name] = value

    return custom_fields


def _extract_edge_custom_fields(edge: Any) -> Dict[str, Any]:
    """
    Витягує кастомні поля з підкласу Edge для збереження.

    Працює з будь-яким підкласом Edge (CustomEdge, etc.)
    Зберігає тільки серіалізовані типи (str, int, float, bool, list, dict).

    Args:
        edge: Edge або підклас Edge

    Returns:
        Dict з кастомними полями або пустий dict
    """
    # Перевіряємо чи є це Pydantic модель з model_fields
    if not hasattr(edge, "model_fields"):
        return {}

    custom_fields = {}
    for field_name in edge.model_fields:
        if field_name not in _BASE_EDGE_FIELDS:
            value = getattr(edge, field_name, None)
            # Зберігаємо тільки серіалізовані типи
            if value is not None and isinstance(value, (str, int, float, bool, list, dict)):
                custom_fields[field_name] = value

    return custom_fields


class SQLiteEvictionStorage:
    """
    Спеціалізований SQLite storage для eviction operations.

    Використовується Graph у low_memory_mode для:
    - Збереження scanned нод при eviction
    - Завантаження нод по URL (lazy loading)
    - Збереження edges пов'язаних з evicted нодами

    Оптимізації:
    - WAL mode для concurrent read/write
    - Batch inserts для ефективного eviction
    - Indexed URL для швидкого lookup
    """

    def __init__(self, storage_path: str):
        """
        Ініціалізує eviction storage.

        Args:
            storage_path: Директорія для eviction.db
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.db_path = self.storage_path / "eviction.db"

        self._conn: Optional[sqlite3.Connection] = None
        self._init_database()

        logger.info("SQLiteEvictionStorage initialized: %s", self.db_path)

    def _get_connection(self) -> sqlite3.Connection:
        """Отримує connection з оптимальними налаштуваннями для ultra-fast writes."""
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,  # Allow multi-thread access
                isolation_level=None,  # Autocommit mode - керуємо транзакціями вручну
            )
            self._conn.row_factory = sqlite3.Row
            # WAL mode - найшвидший для concurrent writes
            self._conn.execute("PRAGMA journal_mode=WAL")

            # NORMAL sync - баланс швидкості та надійності
            # OFF - максимальна швидкість але ризик втрати даних при crash
            self._conn.execute("PRAGMA synchronous=NORMAL")

            # Великий cache для зменшення disk I/O
            self._conn.execute("PRAGMA cache_size=-102400")  # 100MB negative = KB

            # Temp tables в пам'яті
            self._conn.execute("PRAGMA temp_store=MEMORY")

            # Memory-mapped I/O - швидше читання
            self._conn.execute("PRAGMA mmap_size=536870912")  # 512MB mmap

            # Page size 8KB - кращий для великих batches
            # Note: Works only on new DB
            try:
                self._conn.execute("PRAGMA page_size=8192")
            except sqlite3.OperationalError:
                pass  # Ігноруємо якщо БД вже існує
            except Exception:
                pass  # Fallback для інших помилок SQLite

            # WAL auto-checkpoint кожні 10000 pages
            self._conn.execute("PRAGMA wal_autocheckpoint=10000")

            # Locking mode EXCLUSIVE - швидше для single-writer
            self._conn.execute("PRAGMA locking_mode=EXCLUSIVE")

        return self._conn

    def _init_database(self):
        """Ініціалізує схему бази даних."""
        conn = self._get_connection()

        conn.executescript("""
            -- Таблиця evicted нод
            CREATE TABLE IF NOT EXISTS evicted_nodes (
                url TEXT PRIMARY KEY,
                node_id TEXT NOT NULL,
                depth INTEGER NOT NULL,
                scanned INTEGER DEFAULT 0,
                response_status INTEGER,
                content_hash TEXT,
                simhash TEXT,
                priority INTEGER DEFAULT 0,
                metadata TEXT,
                user_data TEXT,
                created_at TEXT
            );

            -- Таблиця edges для evicted нод
            CREATE TABLE IF NOT EXISTS evicted_edges (
                edge_id TEXT PRIMARY KEY,
                source_node_id TEXT NOT NULL,
                target_node_id TEXT NOT NULL,
                metadata TEXT,
                created_at TEXT
            );

            -- Індекси для швидкого lookup
            CREATE INDEX IF NOT EXISTS idx_evicted_nodes_url ON evicted_nodes(url);
            CREATE INDEX IF NOT EXISTS idx_evicted_edges_source ON evicted_edges(source_node_id);
            CREATE INDEX IF NOT EXISTS idx_evicted_edges_target ON evicted_edges(target_node_id);
        """)

        logger.debug("Eviction database schema initialized")

    def save_nodes_sync(self, nodes: List[Any]) -> int:
        """
        ULTRA-FAST Batch INSERT нод (sync версія) v4.1.

        ОПТИМІЗАЦІЇ:
        1. Chunked processing - не тримаємо все в пам'яті
        2. Prepared data формування inline (менше memory copies)
        3. Одна велика транзакція з checkpoints
        4. Simplified JSON serialization
        5. Автоматичне збереження кастомних полів підкласів Node

        Args:
            nodes: Список Node об'єктів для збереження

        Returns:
            Кількість збережених нод
        """
        if not nodes:
            return 0

        conn = self._get_connection()
        total_saved = 0

        # SQL для batch insert
        insert_sql = """
            INSERT OR REPLACE INTO evicted_nodes
            (url, node_id, depth, scanned, response_status, content_hash,
             simhash, priority, metadata, user_data, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        conn.execute("BEGIN TRANSACTION")
        try:
            # Chunked processing для великих batches
            for i in range(0, len(nodes), _BATCH_CHUNK_SIZE):
                chunk = nodes[i : i + _BATCH_CHUNK_SIZE]

                # Формуємо data inline (без окремого list comprehension)
                data = []
                for node in chunk:
                    # Копіюємо user_data та додаємо кастомні поля
                    user_data = dict(node.user_data) if node.user_data else {}

                    # Витягуємо кастомні поля підкласу Node
                    custom_fields = _extract_custom_fields(node)
                    if custom_fields:
                        user_data["_custom_fields"] = custom_fields

                    data.append(
                        (
                            node.url,
                            node.node_id,
                            node.depth,
                            1 if node.scanned else 0,
                            getattr(node, "response_status", None),
                            getattr(node, "content_hash", None),
                            getattr(node, "simhash", None),
                            getattr(node, "priority", 0),
                            json.dumps(node.metadata) if node.metadata else None,
                            json.dumps(user_data) if user_data else None,
                            node.created_at.isoformat()
                            if hasattr(node, "created_at") and node.created_at
                            else None,
                        )
                    )

                conn.executemany(insert_sql, data)
                total_saved += len(chunk)

                # Checkpoint кожні 10k записів для великих batches
                if total_saved % 10000 == 0 and total_saved < len(nodes):
                    logger.debug("Eviction progress: %s/%s nodes", total_saved, len(nodes))

            conn.execute("COMMIT")

            logger.debug("Evicted %s nodes to disk", total_saved)
            return total_saved

        except Exception as e:
            conn.execute("ROLLBACK")
            logger.error("Failed to save nodes: %s", e)
            raise

    def save_edges_sync(self, edges: List[Any]) -> int:
        """
        ULTRA-FAST Batch INSERT edges (sync версія) v4.1.

        Підтримує кастомні поля підкласів Edge - зберігає їх в metadata['_custom_fields'].

        Args:
            edges: Список Edge об'єктів для збереження

        Returns:
            Кількість збережених edges
        """
        if not edges:
            return 0

        conn = self._get_connection()
        total_saved = 0

        insert_sql = """
            INSERT OR IGNORE INTO evicted_edges
            (edge_id, source_node_id, target_node_id, metadata, created_at)
            VALUES (?, ?, ?, ?, ?)
        """

        conn.execute("BEGIN TRANSACTION")
        try:
            # Chunked processing
            for i in range(0, len(edges), _BATCH_CHUNK_SIZE):
                chunk = edges[i : i + _BATCH_CHUNK_SIZE]

                data = []
                for edge in chunk:
                    # Копіюємо metadata та додаємо кастомні поля
                    metadata = (
                        dict(edge.metadata) if hasattr(edge, "metadata") and edge.metadata else {}
                    )

                    # Витягуємо кастомні поля підкласу Edge
                    custom_fields = _extract_edge_custom_fields(edge)
                    if custom_fields:
                        metadata["_custom_fields"] = custom_fields

                    data.append(
                        (
                            getattr(edge, "edge_id", str(id(edge))),
                            edge.source_node_id,
                            edge.target_node_id,
                            json.dumps(metadata) if metadata else None,
                            edge.created_at.isoformat()
                            if hasattr(edge, "created_at") and edge.created_at
                            else None,
                        )
                    )

                conn.executemany(insert_sql, data)
                total_saved += len(chunk)

            conn.execute("COMMIT")

            logger.debug("Saved %s edges to eviction storage", total_saved)
            return total_saved

        except Exception as e:
            conn.execute("ROLLBACK")
            logger.error("Failed to save edges: %s", e)
            raise

    def load_node_sync(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Завантажує ноду по URL (sync версія).

        Повертає Dict з даними ноди для реконструкції Node об'єкта.
        Якщо нода мала кастомні поля, вони будуть в user_data['_custom_fields'].

        Args:
            url: URL ноди для завантаження

        Returns:
            Dict з даними ноди або None якщо не знайдено
        """
        conn = self._get_connection()

        row = conn.execute("SELECT * FROM evicted_nodes WHERE url = ?", (url,)).fetchone()

        if not row:
            return None

        # Конвертуємо Row в dict
        user_data = json.loads(row["user_data"]) if row["user_data"] else {}

        node_data = {
            "url": row["url"],
            "node_id": row["node_id"],
            "depth": row["depth"],
            "scanned": bool(row["scanned"]),
            "response_status": row["response_status"],
            "content_hash": row["content_hash"],
            "simhash": row["simhash"],
            "priority": row["priority"] or 0,
            "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
            "user_data": user_data,
        }

        logger.debug("Loaded evicted node: %s", url)
        return node_data

    def load_node_without_metadata_sync(self, url: str) -> Optional[Dict[str, Any]]:
        """

        Економить RAM при завантаженні великої кількості нод.
        Metadata завантажуються окремо при першому доступі.

        Args:
            url: URL ноди для завантаження

        Returns:
            Dict з базовими даними ноди (без metadata та user_data)
        """
        conn = self._get_connection()

        row = conn.execute(
            """SELECT url, node_id, depth, scanned, response_status,
                      content_hash, simhash, priority
               FROM evicted_nodes WHERE url = ?""",
            (url,),
        ).fetchone()

        if not row:
            return None

        # Конвертуємо Row в dict БЕЗ metadata
        node_data = {
            "url": row["url"],
            "node_id": row["node_id"],
            "depth": row["depth"],
            "scanned": bool(row["scanned"]),
            "response_status": row["response_status"],
            "content_hash": row["content_hash"],
            "simhash": row["simhash"],
            "priority": row["priority"] or 0,
            "metadata": None,  # Lazy load
            "user_data": None,  # Lazy load
        }

        logger.debug("Loaded evicted node (no metadata): %s", url)
        return node_data

    def load_metadata_sync(self, url: str) -> Optional[Dict[str, Any]]:
        """

        Викликається при першому доступі до node.metadata якщо
        нода була завантажена без metadata.

        Args:
            url: URL ноди

        Returns:
            Dict з metadata або пустий dict
        """
        conn = self._get_connection()

        row = conn.execute("SELECT metadata FROM evicted_nodes WHERE url = ?", (url,)).fetchone()

        if not row or not row["metadata"]:
            return {}

        return json.loads(row["metadata"])

    def load_user_data_sync(self, url: str) -> Optional[Dict[str, Any]]:
        """

        Викликається при першому доступі до node.user_data якщо
        нода була завантажена без user_data.

        Args:
            url: URL ноди

        Returns:
            Dict з user_data або пустий dict
        """
        conn = self._get_connection()

        row = conn.execute("SELECT user_data FROM evicted_nodes WHERE url = ?", (url,)).fetchone()

        if not row or not row["user_data"]:
            return {}

        return json.loads(row["user_data"])

    def load_nodes_batch_sync(self, urls: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Batch завантаження нод по URLs.

        Args:
            urls: Список URLs для завантаження

        Returns:
            Dict[url, node_data] з кастомними полями в user_data['_custom_fields']
        """
        if not urls:
            return {}

        conn = self._get_connection()

        # Використовуємо параметризований запит для безпеки
        placeholders = ",".join("?" * len(urls))
        rows = conn.execute(
            f"SELECT * FROM evicted_nodes WHERE url IN ({placeholders})", urls
        ).fetchall()

        result = {}
        for row in rows:
            user_data = json.loads(row["user_data"]) if row["user_data"] else {}

            result[row["url"]] = {
                "url": row["url"],
                "node_id": row["node_id"],
                "depth": row["depth"],
                "scanned": bool(row["scanned"]),
                "response_status": row["response_status"],
                "content_hash": row["content_hash"],
                "simhash": row["simhash"],
                "priority": row["priority"] or 0,
                "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                "user_data": user_data,
            }

        logger.debug("Batch loaded %s evicted nodes", len(result))
        return result

    def get_all_evicted_urls(self) -> Set[str]:
        """
        Повертає всі evicted URLs.

        Returns:
            Set URLs що знаходяться в eviction storage
        """
        conn = self._get_connection()
        rows = conn.execute("SELECT url FROM evicted_nodes").fetchall()
        return {row["url"] for row in rows}

    def url_exists(self, url: str) -> bool:
        """

        Використовується як заміна Bloom Filter при low_memory_mode
        для перевірки унікальності URL.

        Складність: O(log n) завдяки індексу на url (PRIMARY KEY)

        Args:
            url: URL для перевірки

        Returns:
            True якщо URL знайдено в eviction storage
        """
        conn = self._get_connection()
        row = conn.execute("SELECT 1 FROM evicted_nodes WHERE url = ? LIMIT 1", (url,)).fetchone()
        return row is not None

    def urls_exist_batch(self, urls: List[str]) -> Set[str]:
        """

        Оптимізована версія для перевірки багатьох URLs одразу.

        Args:
            urls: Список URLs для перевірки

        Returns:
            Set URLs що знайдені в eviction storage
        """
        if not urls:
            return set()

        conn = self._get_connection()
        placeholders = ",".join("?" * len(urls))
        rows = conn.execute(
            f"SELECT url FROM evicted_nodes WHERE url IN ({placeholders})", urls
        ).fetchall()
        return {row["url"] for row in rows}

    def load_edges_sync(
        self, source_node_id: Optional[str] = None, target_node_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Завантажує edges з eviction storage.

        Якщо передано source_node_id - повертає всі edges з цього source.
        Якщо передано target_node_id - повертає всі edges до цього target.
        Якщо обидва None - повертає всі edges.

        Кастомні поля підкласів Edge зберігаються в metadata['_custom_fields'].

        Args:
            source_node_id: ID source node для фільтрації (optional)
            target_node_id: ID target node для фільтрації (optional)

        Returns:
            List of edge data dicts
        """
        conn = self._get_connection()

        if source_node_id and target_node_id:
            rows = conn.execute(
                "SELECT * FROM evicted_edges WHERE source_node_id = ? AND target_node_id = ?",
                (source_node_id, target_node_id),
            ).fetchall()
        elif source_node_id:
            rows = conn.execute(
                "SELECT * FROM evicted_edges WHERE source_node_id = ?", (source_node_id,)
            ).fetchall()
        elif target_node_id:
            rows = conn.execute(
                "SELECT * FROM evicted_edges WHERE target_node_id = ?", (target_node_id,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM evicted_edges").fetchall()

        result = []
        for row in rows:
            metadata = json.loads(row["metadata"]) if row["metadata"] else {}

            result.append(
                {
                    "edge_id": row["edge_id"],
                    "source_node_id": row["source_node_id"],
                    "target_node_id": row["target_node_id"],
                    "metadata": metadata,
                    "created_at": row["created_at"],
                }
            )

        logger.debug("Loaded %s edges from eviction storage", len(result))
        return result

    def load_all_edges_sync(self) -> List[Dict[str, Any]]:
        """
        Завантажує всі edges з eviction storage.

        Returns:
            List of all edge data dicts
        """
        return self.load_edges_sync()

    def get_evicted_count(self) -> int:
        """Повертає кількість evicted нод."""
        conn = self._get_connection()
        row = conn.execute("SELECT COUNT(*) as cnt FROM evicted_nodes").fetchone()
        return row["cnt"] if row else 0

    def get_stats(self) -> Dict[str, Any]:
        """
        Повертає статистику eviction storage.

        Returns:
            Dict зі статистикою
        """
        conn = self._get_connection()

        nodes_count = conn.execute("SELECT COUNT(*) as cnt FROM evicted_nodes").fetchone()["cnt"]

        edges_count = conn.execute("SELECT COUNT(*) as cnt FROM evicted_edges").fetchone()["cnt"]

        # Розмір файлу
        db_size_bytes = self.db_path.stat().st_size if self.db_path.exists() else 0
        db_size_mb = round(db_size_bytes / 1024 / 1024, 2)

        return {
            "evicted_nodes": nodes_count,
            "evicted_edges": edges_count,
            "db_size_mb": db_size_mb,
            "db_path": str(self.db_path),
        }

    def clear(self):
        """Очищає eviction storage."""
        conn = self._get_connection()
        conn.execute("DELETE FROM evicted_edges")
        conn.execute("DELETE FROM evicted_nodes")
        conn.execute("VACUUM")
        logger.info("Eviction storage cleared")

    def close(self):
        """Закриває з'єднання з БД."""
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.debug("Eviction storage connection closed")

    def cleanup(self, delete_files: bool = True):
        """
        Видаляє eviction storage після завершення краулінгу.

        Викликайте після завершення краулінгу для очищення диску.

        Args:
            delete_files: Якщо True - видаляє файли БД з диску

        Example:
            >>> # Після завершення краулінгу
            >>> graph.close_eviction_storage()
            >>> # або напряму
            >>> eviction_storage.cleanup()
        """
        self.close()

        if delete_files:
            import shutil

            try:
                # Видаляємо всю директорію з eviction даними
                if self.storage_path.exists():
                    shutil.rmtree(self.storage_path)
                    logger.info("Eviction storage deleted: %s", self.storage_path)
            except Exception as e:
                logger.warning("Failed to delete eviction storage: %s", e)

    def __del__(self):
        """Деструктор - закриває з'єднання (але НЕ видаляє файли)."""
        self.close()

    async def save_nodes_async(self, nodes: List[Any]) -> int:
        """
        Async версія batch INSERT нод (неблокуюча).

        Виконує sync операцію в thread pool executor.

        Args:
            nodes: Список Node об'єктів для збереження

        Returns:
            Кількість збережених нод
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_sqlite_executor, partial(self.save_nodes_sync, nodes))

    async def save_edges_async(self, edges: List[Any]) -> int:
        """
        Async версія batch INSERT edges (неблокуюча).

        Args:
            edges: Список Edge об'єктів для збереження

        Returns:
            Кількість збережених edges
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_sqlite_executor, partial(self.save_edges_sync, edges))

    async def load_node_async(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Async версія завантаження ноди по URL (неблокуюча).

        Args:
            url: URL ноди для завантаження

        Returns:
            Dict з даними ноди або None
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_sqlite_executor, partial(self.load_node_sync, url))

    async def load_nodes_batch_async(self, urls: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Async версія batch завантаження нод (неблокуюча).

        Args:
            urls: Список URLs для завантаження

        Returns:
            Dict[url, node_data]
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _sqlite_executor, partial(self.load_nodes_batch_sync, urls)
        )

    async def url_exists_async(self, url: str) -> bool:
        """
        Async версія перевірки існування URL (неблокуюча).

        Args:
            url: URL для перевірки

        Returns:
            True якщо URL знайдено
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_sqlite_executor, partial(self.url_exists, url))

    async def urls_exist_batch_async(self, urls: List[str]) -> Set[str]:
        """
        Async версія batch перевірки URLs (неблокуюча).

        Args:
            urls: Список URLs для перевірки

        Returns:
            Set URLs що знайдені
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_sqlite_executor, partial(self.urls_exist_batch, urls))


__all__ = ["SQLiteEvictionStorage"]
