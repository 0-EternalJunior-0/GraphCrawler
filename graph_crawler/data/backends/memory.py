"""
MemoryBackend - In-Memory Implementation of IGraphBackend.

"""

import asyncio
import logging
import re
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Iterator, List, Optional, Set, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class MemoryBackend:
    """
    In-Memory Backend для Graph Storage.

    Емулює поточну поведінку Graph._nodes, Graph._edges.
    Дозволяє поступову міграцію без breaking changes.

    Data Structures:
        _nodes: Dict[node_id, Node]
        _edges: List[Edge]
        _url_to_node: Dict[url, Node]
        _edge_index: Set[(source_id, target_id)]
        _adjacency_out: Dict[node_id, Set[target_ids]]
        _adjacency_in: Dict[node_id, Set[source_ids]]

    Thread Safety:
        Використовує asyncio.Lock для async операцій.
        Для sync операцій - caller відповідає за thread safety.
    """

    def __init__(self):
        """Ініціалізує MemoryBackend."""
        # Primary storage
        self._nodes: Dict[str, Any] = {}  # node_id -> Node
        self._edges: List[Any] = []  # List of Edge

        # Indexes
        self._url_to_node: Dict[str, Any] = {}  # url -> Node
        self._edge_index: Set[Tuple[str, str]] = set()  # (source_id, target_id)

        # Adjacency lists for fast graph traversal
        self._adjacency_out: Dict[str, Set[str]] = defaultdict(set)  # source -> {targets}
        self._adjacency_in: Dict[str, Set[str]] = defaultdict(set)  # target -> {sources}

        # Async lock for thread safety
        self._lock = asyncio.Lock()

        # Status
        self._is_open = False

        logger.debug("MemoryBackend initialized")

    # ═══════════════════════════════════════════════════════════════════════════
    # LIFECYCLE
    # ═══════════════════════════════════════════════════════════════════════════

    async def open(self) -> None:
        """Opens the backend (no-op for memory)."""
        self._is_open = True
        logger.debug("MemoryBackend opened")

    async def close(self) -> None:
        """Closes the backend and clears data."""
        self._is_open = False
        # Optionally clear data on close
        # self._clear_all()
        logger.debug("MemoryBackend closed")

    @asynccontextmanager
    async def transaction(self):
        """
        Context manager для транзакцій.

        Для MemoryBackend - просто lock для atomicity.
        """
        async with self._lock:
            yield

    async def checkpoint(self) -> None:
        """No-op for memory backend."""
        pass

    # ═══════════════════════════════════════════════════════════════════════════
    # URL NORMALIZATION (copied from Graph for consistency)
    # ═══════════════════════════════════════════════════════════════════════════

    def _normalize_url(self, url: str) -> str:
        """
        Нормалізує URL для уникнення дублікатів.

        Operations:
        - Lowercase hostname
        - Remove trailing slash
        - Remove fragment (#...)
        - Normalize path (collapse multiple slashes)
        """
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
    # NODE OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════════

    async def insert_node(self, node: Any) -> Any:
        """Додає ноду (без перезапису існуючої)."""
        async with self._lock:
            return self._insert_node_internal(node, overwrite=False)

    async def insert_node_overwrite(self, node: Any) -> Any:
        """Додає або перезаписує ноду."""
        async with self._lock:
            return self._insert_node_internal(node, overwrite=True)

    def _insert_node_internal(self, node: Any, overwrite: bool) -> Any:
        """Internal insert logic (not locked)."""
        # Normalize URL
        original_url = node.url
        normalized_url = self._normalize_url(original_url)

        if original_url != normalized_url:
            node.url = normalized_url
            if not hasattr(node, "metadata") or node.metadata is None:
                node.metadata = {}
            node.metadata["_original_url"] = original_url

        # Check existing
        if normalized_url in self._url_to_node:
            existing = self._url_to_node[normalized_url]
            if overwrite:
                self._nodes[existing.node_id] = node
                self._url_to_node[normalized_url] = node
                return node
            else:
                return existing

        # Add new
        self._nodes[node.node_id] = node
        self._url_to_node[normalized_url] = node
        return node

    async def insert_nodes_batch(self, nodes: List[Any]) -> int:
        """Batch insert нод."""
        async with self._lock:
            count = 0
            for node in nodes:
                existing = self._url_to_node.get(self._normalize_url(node.url))
                if existing is None:
                    self._insert_node_internal(node, overwrite=False)
                    count += 1
            return count

    async def get_node_by_url(self, url: str) -> Optional[Any]:
        """Отримує ноду за URL."""
        normalized = self._normalize_url(url)
        return self._url_to_node.get(normalized)

    async def get_node_by_id(self, node_id: str) -> Optional[Any]:
        """Отримує ноду за ID."""
        return self._nodes.get(node_id)

    async def get_nodes_batch(self, urls: List[str]) -> Dict[str, Any]:
        """Batch отримання нод за URLs."""
        result = {}
        for url in urls:
            normalized = self._normalize_url(url)
            node = self._url_to_node.get(normalized)
            if node:
                result[url] = node
        return result

    async def update_node(self, node: Any) -> bool:
        """Оновлює існуючу ноду."""
        async with self._lock:
            if node.node_id not in self._nodes:
                return False
            self._nodes[node.node_id] = node
            self._url_to_node[node.url] = node
            return True

    async def delete_node(self, node_id: str) -> bool:
        """Видаляє ноду та пов'язані ребра."""
        async with self._lock:
            node = self._nodes.get(node_id)
            if not node:
                return False

            # Remove node
            del self._nodes[node_id]
            del self._url_to_node[node.url]

            # Remove related edges
            edges_to_keep = []
            for edge in self._edges:
                if edge.source_node_id == node_id or edge.target_node_id == node_id:
                    self._edge_index.discard((edge.source_node_id, edge.target_node_id))
                    self._adjacency_out[edge.source_node_id].discard(edge.target_node_id)
                    self._adjacency_in[edge.target_node_id].discard(edge.source_node_id)
                else:
                    edges_to_keep.append(edge)
            self._edges = edges_to_keep

            # Cleanup adjacency
            self._adjacency_out.pop(node_id, None)
            self._adjacency_in.pop(node_id, None)

            return True

    async def url_exists(self, url: str) -> bool:
        """Перевіряє чи URL існує."""
        normalized = self._normalize_url(url)
        return normalized in self._url_to_node

    async def urls_exist_batch(self, urls: List[str]) -> Set[str]:
        """Batch перевірка існування URLs."""
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
            self._edges.append(edge)
            self._edge_index.add((edge.source_node_id, edge.target_node_id))
            self._adjacency_out[edge.source_node_id].add(edge.target_node_id)
            self._adjacency_in[edge.target_node_id].add(edge.source_node_id)
            return edge

    async def insert_edges_batch(self, edges: List[Any]) -> int:
        """Batch insert ребер."""
        async with self._lock:
            count = 0
            for edge in edges:
                key = (edge.source_node_id, edge.target_node_id)
                if key not in self._edge_index:
                    self._edges.append(edge)
                    self._edge_index.add(key)
                    self._adjacency_out[edge.source_node_id].add(edge.target_node_id)
                    self._adjacency_in[edge.target_node_id].add(edge.source_node_id)
                    count += 1
            return count

    async def get_edges_from(self, source_node_id: str) -> List[Any]:
        """Отримує всі ребра ВІД ноди."""
        return [e for e in self._edges if e.source_node_id == source_node_id]

    async def get_edges_to(self, target_node_id: str) -> List[Any]:
        """Отримує всі ребра ДО ноди."""
        return [e for e in self._edges if e.target_node_id == target_node_id]

    async def edge_exists(self, source_node_id: str, target_node_id: str) -> bool:
        """Перевіряє чи існує ребро."""
        return (source_node_id, target_node_id) in self._edge_index

    async def delete_edges_for_node(self, node_id: str) -> int:
        """Видаляє всі ребра для ноди."""
        async with self._lock:
            count = 0
            edges_to_keep = []
            for edge in self._edges:
                if edge.source_node_id == node_id or edge.target_node_id == node_id:
                    self._edge_index.discard((edge.source_node_id, edge.target_node_id))
                    count += 1
                else:
                    edges_to_keep.append(edge)
            self._edges = edges_to_keep
            return count

    # ═══════════════════════════════════════════════════════════════════════════
    # QUERY OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════════

    async def count_nodes(self) -> int:
        """Повертає кількість нод."""
        return len(self._nodes)

    async def count_edges(self) -> int:
        """Повертає кількість ребер."""
        return len(self._edges)

    async def count_nodes_by_status(self, scanned: bool) -> int:
        """Повертає кількість нод за статусом."""
        return sum(1 for n in self._nodes.values() if n.scanned == scanned)

    async def get_stats(self) -> Dict[str, Any]:
        """Повертає статистику."""
        total = len(self._nodes)
        scanned = sum(1 for n in self._nodes.values() if n.scanned)

        return {
            "backend_type": "memory",
            "total_nodes": total,
            "total_edges": len(self._edges),
            "scanned_nodes": scanned,
            "unscanned_nodes": total - scanned,
            "unique_urls": len(self._url_to_node),
            "edge_index_size": len(self._edge_index),
        }

    # ═══════════════════════════════════════════════════════════════════════════
    # STREAMING OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════════

    async def iter_nodes(self, batch_size: int = 1000) -> AsyncIterator[Any]:
        """Streaming ітератор по нодах."""
        nodes_list = list(self._nodes.values())
        for i in range(0, len(nodes_list), batch_size):
            batch = nodes_list[i : i + batch_size]
            for node in batch:
                yield node

    async def iter_edges(self, batch_size: int = 1000) -> AsyncIterator[Any]:
        """Streaming ітератор по ребрах."""
        for i in range(0, len(self._edges), batch_size):
            batch = self._edges[i : i + batch_size]
            for edge in batch:
                yield edge

    async def iter_unscanned_nodes(self, batch_size: int = 100) -> AsyncIterator[Any]:
        """Streaming ітератор по unscanned нодах."""
        count = 0
        for node in self._nodes.values():
            if not node.scanned:
                yield node
                count += 1
                if count >= batch_size:
                    # Allow other tasks to run
                    await asyncio.sleep(0)
                    count = 0

    async def iter_nodes_at_depth(self, depth: int, batch_size: int = 1000) -> AsyncIterator[Any]:
        """Streaming ітератор по нодах на глибині."""
        count = 0
        for node in self._nodes.values():
            if node.depth == depth:
                yield node
                count += 1
                if count >= batch_size:
                    await asyncio.sleep(0)
                    count = 0

    # ═══════════════════════════════════════════════════════════════════════════
    # SYNC WRAPPERS
    # ═══════════════════════════════════════════════════════════════════════════

    def insert_node_sync(self, node: Any) -> Any:
        """Sync версія insert_node."""
        # Direct call without lock for performance
        return self._insert_node_internal(node, overwrite=False)

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
        """Sync streaming ітератор по нодах."""
        yield from self._nodes.values()

    def iter_edges_sync(self, batch_size: int = 1000) -> Iterator[Any]:
        """Sync streaming ітератор по ребрах."""
        yield from self._edges

    # ═══════════════════════════════════════════════════════════════════════════
    # INTERNAL HELPERS
    # ═══════════════════════════════════════════════════════════════════════════

    def _clear_all(self) -> None:
        """Очищає всі дані."""
        self._nodes.clear()
        self._edges.clear()
        self._url_to_node.clear()
        self._edge_index.clear()
        self._adjacency_out.clear()
        self._adjacency_in.clear()

    # ═══════════════════════════════════════════════════════════════════════════
    # DIRECT ACCESS (for backward compatibility with Graph internals)
    # ═══════════════════════════════════════════════════════════════════════════

    @property
    def nodes(self) -> Dict[str, Any]:
        """Direct access to _nodes (backward compat)."""
        return self._nodes

    @property
    def edges(self) -> List[Any]:
        """Direct access to _edges (backward compat)."""
        return self._edges

    @property
    def url_to_node(self) -> Dict[str, Any]:
        """Direct access to _url_to_node (backward compat)."""
        return self._url_to_node

    @property
    def edge_index(self) -> Set[Tuple[str, str]]:
        """Direct access to _edge_index (backward compat)."""
        return self._edge_index

    @property
    def adjacency_out(self) -> Dict[str, Set[str]]:
        """Direct access to adjacency list (outgoing)."""
        return self._adjacency_out

    @property
    def adjacency_in(self) -> Dict[str, Set[str]]:
        """Direct access to adjacency list (incoming)."""
        return self._adjacency_in


__all__ = ["MemoryBackend"]
