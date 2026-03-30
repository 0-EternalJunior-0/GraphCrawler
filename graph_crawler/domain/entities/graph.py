"""
Менеджер графу для управління вузлами та ребрами.

Складні операції винесено в окремі класи:
- GraphOperations - арифметичні операції та операції теорії графів
- GraphStatistics - статистика та аналіз графа

Включає asyncio.Lock для thread-safety при конкурентному доступі.
"""

import asyncio
import logging
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterator,
    Dict,
    Iterator,
    List,
    Optional,
    Set,
    Tuple,
    Union,
)
from urllib.parse import urlparse

if TYPE_CHECKING:
    from graph_crawler.data.interfaces import IGraphBackend

from graph_crawler.domain.entities.edge import Edge
from graph_crawler.domain.entities.edge_analysis import EdgeAnalysis
from graph_crawler.domain.entities.graph_operations import GraphOperations
from graph_crawler.domain.entities.graph_statistics import GraphStatistics
from graph_crawler.domain.entities.node import Node

logger = logging.getLogger(__name__)


class Graph:
    """Менеджер графу - CRUD операції над вузлами та ребрами."""

    # Type stubs для динамічно доданих методів (IDE support)
    if TYPE_CHECKING:

        def filter_by_schema(
            self,
            include: Optional[List[str]] = None,
            exclude: Optional[List[str]] = None,
            fallback: str = "keep",
        ) -> List["Node"]:
            """Фільтрує ноди за JSON-LD schema типами."""
            ...

        def get_nodes_by_schema(self, schema_type: str) -> List["Node"]:
            """Повертає всі ноди з вказаним schema типом."""
            ...

        def get_schema_stats(self) -> Dict[str, int]:
            """Повертає статистику schema типів у графі."""
            ...

        def has_schema_type(self, schema_type: str) -> bool:
            """Перевіряє чи є в графі хоча б одна нода з вказаним schema типом."""
            ...

    def __init__(
        self,
        backend: Optional["IGraphBackend"] = None,
        default_merge_strategy: Optional[str] = None,
        # LOW-MEMORY MODE параметри
        low_memory_mode: bool = False,
        evict_threshold: int = 500,
        evict_batch_size: int = 100,
        storage_path: Optional[str] = None,
        eviction_storage: Optional[Any] = None,
        eviction_strategy: str = "balanced",
        eviction_trigger_multiplier: float = 1.5,
        eviction_target_multiplier: float = 1.0,
        eviction_memory_threshold_percent: float = 75.0,
        # URL DEDUPLICATION параметри
        url_deduplication_enabled: bool = True,
        normalize_protocol: bool = True,  # http → https
        normalize_www: bool = True,  # www.example.com → example.com
        normalize_trailing_slash: bool = True,  # /path/ → /path
        normalize_query_params: bool = False,  # Сортувати query параметри
    ):
        """
        Ініціалізує новий граф.

        Args:
            default_merge_strategy: Дефолтна стратегія для union операцій.
                Доступні: 'first', 'last', 'merge', 'newest', 'oldest', 'custom'.
                За замовчуванням: 'last' (якщо None, використовується 'last').
        Example:
            >>> # Стандартний режим (все в RAM)
            >>> graph = Graph()
        """
        self._backend = backend
        self._use_backend = backend is not None

        self._nodes: Dict[str, Node] = {}
        self._edges: List[Edge] = []
        self._url_to_node: Dict[str, Node] = {}
        self._default_merge_strategy: str = default_merge_strategy or "last"

        # Зберігає (source_node_id, target_node_id) пари для швидкої перевірки наявності edge
        self._edge_index: Set[tuple] = set()

        # Замість O(E) проходу через всі edges, маємо O(1) lookup
        # _adjacency_list_out: source_id -> {target_ids}
        # _adjacency_list_in: target_id -> {source_ids}
        from collections import defaultdict

        self._adjacency_list_out: Dict[str, Set[str]] = defaultdict(set)
        self._adjacency_list_in: Dict[str, Set[str]] = defaultdict(set)

        # Замість одного глобального lock - кілька locks по hash(url)
        # Це дозволяє паралельний доступ до різних частин графа
        self._num_shards = 16  # 16 шардів для балансу між contention та overhead
        self._locks = [asyncio.Lock() for _ in range(self._num_shards)]

        # Backward compatibility: глобальний lock для операцій
        # що потребують atomic доступ до всього графа
        self._global_lock = asyncio.Lock()

        # Інвалідується при додаванні/видаленні нод з simhash
        self._lsh_index_cache: Optional[Dict[int, Dict[int, List[Node]]]] = None
        self._lsh_index_node_count: int = 0  # Для детекції змін
        self._low_memory_mode = low_memory_mode
        self._evict_threshold = evict_threshold
        self._evict_batch_size = evict_batch_size
        self._eviction_strategy = eviction_strategy
        self._eviction_trigger_multiplier = eviction_trigger_multiplier
        self._eviction_target_multiplier = eviction_target_multiplier
        self._eviction_memory_threshold_percent = eviction_memory_threshold_percent

        # Pre-calculate multipliers based on strategy
        self._trigger_mult, self._target_mult = self._get_strategy_multipliers()

        # Економія: 8 bytes per hash vs 100+ bytes per URL string
        # При 1M URLs: ~8MB замість ~150MB
        self._evicted_url_hashes: Set[int] = set()  # hash(url) для evicted нод

        # DEPRECATED: Залишено для backward compatibility
        # self._url_to_disk_map: Set[str] = set()  # URLs що evicted на диск
        self._eviction_storage = None
        self._eviction_lock = asyncio.Lock()
        self._current_depth: int = 0  # Поточна глибина краулінгу

        # Статистика eviction
        self._eviction_stats = {
            "total_evicted": 0,
            "total_loaded": 0,
            "eviction_calls": 0,
            "strategy": eviction_strategy,
        }

        # URL Deduplication налаштування
        self._url_deduplication_enabled = url_deduplication_enabled
        self._normalize_protocol = normalize_protocol
        self._normalize_www = normalize_www
        self._normalize_trailing_slash = normalize_trailing_slash
        self._normalize_query_params = normalize_query_params
        
        if url_deduplication_enabled:
            logger.info(
                "URL deduplication ENABLED: protocol=%s, www=%s, trailing_slash=%s, query_params=%s",
                normalize_protocol, normalize_www, normalize_trailing_slash, normalize_query_params
            )

        if low_memory_mode:
            if eviction_storage is not None:
                # Clean Architecture: Domain receives abstraction via DI
                self._eviction_storage = eviction_storage
            elif storage_path:
                raise ValueError(
                    "storage_path parameter is removed (Clean Architecture violation). "
                    "Use eviction_storage parameter with IEvictionStorage implementation. "
                    "Example: Graph(low_memory_mode=True, "
                    "eviction_storage=SQLiteEvictionStorage(path))"
                )
            else:
                raise ValueError(
                    "low_memory_mode=True requires eviction_storage (IEvictionStorage). "
                    "Example: Graph(low_memory_mode=True, "
                    "eviction_storage=SQLiteEvictionStorage('/tmp/eviction'))"
                )

            logger.info(
                "Graph initialized in LOW-MEMORY mode: "
                "strategy=%s, threshold=%d, trigger_mult=%.2f, target_mult=%.2f, storage=%s",
                eviction_strategy,
                evict_threshold,
                self._trigger_mult,
                self._target_mult,
                type(self._eviction_storage).__name__,
            )

    @property
    def nodes(self) -> Dict[str, Node]:
        """Read-only доступ до вузлів. Модифікація тільки через add_node().

        ВАЖЛИВО: Повертає Dict[str, Node] де ключі = node_id (strings).
        Для ітерації по Node об'єктах використовуйте:
            - for node in graph: ...  (рекомендовано)
            - for node in graph.iter_nodes(): ...
            - for node in graph.nodes.values(): ...

        Backend Delegation:
            Якщо Graph створено з backend параметром, делегує до backend.nodes.
            Це забезпечує backward compatibility - старий код продовжує працювати.
        """
        if self._use_backend and hasattr(self._backend, "nodes"):
            return self._backend.nodes  # type: ignore
        return self._nodes

    def iter_nodes(self) -> Iterator[Node]:
        """
        Ітератор по всіх нодах графу.

        Використовуйте цей метод замість прямої ітерації по graph.nodes,
        яка повертає node_id (strings), а не Node об'єкти.

        Example:
            >>> for node in graph.iter_nodes():
            ...     print(node.url)

        Returns:
            Iterator[Node]: Ітератор по Node об'єктах

        Backend Delegation:
            Якщо Graph створено з backend параметром, делегує до backend.iter_nodes_sync().
        """
        if self._use_backend and hasattr(self._backend, "iter_nodes_sync"):
            return self._backend.iter_nodes_sync()  # type: ignore
        return iter(self._nodes.values())

    async def iter_nodes_async(self, batch_size: int = 1000) -> AsyncIterator[Node]:
        """
        Async streaming ітератор по всіх нодах графу (Крок 46).

        Memory-efficient: не завантажує всі ноди в RAM одночасно.
        Використовуйте для великих графів та з SQLiteBackend.

        Example:
            >>> async for node in graph.iter_nodes_async():
            ...     await process(node)

        Args:
            batch_size: Розмір batch для streaming (default: 1000)

        Yields:
            Node: Ноди графу по одній

        Backend Delegation:
            Якщо Graph створено з backend параметром, делегує до backend.iter_nodes().
        """
        if self._use_backend and hasattr(self._backend, "iter_nodes"):
            async for node in self._backend.iter_nodes(batch_size=batch_size):  # type: ignore
                yield node
        else:
            # For non-backend mode, yield from RAM
            for node in self._nodes.values():
                yield node

    def iter_edges(self) -> Iterator[Edge]:
        """
        Ітератор по всіх ребрах графу.

        Example:
            >>> for edge in graph.iter_edges():
            ...     print(f"{edge.source_node_id} -> {edge.target_node_id}")

        Returns:
            Iterator[Edge]: Ітератор по Edge об'єктах

        Backend Delegation:
            Якщо Graph створено з backend параметром, делегує до backend.iter_edges_sync().
        """
        if self._use_backend and hasattr(self._backend, "iter_edges_sync"):
            return self._backend.iter_edges_sync()  # type: ignore
        return iter(self._edges)

    async def iter_edges_async(self, batch_size: int = 1000) -> AsyncIterator[Edge]:
        """
        Async streaming ітератор по всіх ребрах графу (Крок 46).

        Memory-efficient: не завантажує всі ребра в RAM одночасно.
        Використовуйте для великих графів та з SQLiteBackend.

        Example:
            >>> async for edge in graph.iter_edges_async():
            ...     await process(edge)

        Args:
            batch_size: Розмір batch для streaming (default: 1000)

        Yields:
            Edge: Ребра графу по одному

        Backend Delegation:
            Якщо Graph створено з backend параметром, делегує до backend.iter_edges().
        """
        if self._use_backend and hasattr(self._backend, "iter_edges"):
            async for edge in self._backend.iter_edges(batch_size=batch_size):  # type: ignore
                yield edge
        else:
            # For non-backend mode, yield from RAM
            for edge in self._edges:
                yield edge

    def _normalize_url(self, url: str) -> str:
        """
        Нормалізує URL для уникнення дублікатів.
        
        Нормалізація включає (залежно від налаштувань):
        - http → https (normalize_protocol)
        - www.example.com → example.com (normalize_www)
        - /path/ → /path (normalize_trailing_slash)
        - Сортування query параметрів (normalize_query_params)
        
        Приклади еквівалентних URL:
            http://www.example.com/ == https://example.com
            https://example.com/page/ == https://example.com/page
            
        Args:
            url: URL для нормалізації
        Returns:
            Нормалізований URL
        """
        # Якщо дедуплікація вимкнена - повертаємо URL без змін
        if not self._url_deduplication_enabled:
            return url
            
        parsed = urlparse(url)
        
        # Нормалізація протоколу: http → https
        scheme = parsed.scheme.lower()
        if self._normalize_protocol and scheme == "http":
            scheme = "https"
        
        # Lowercase hostname and strip trailing backslashes
        netloc = parsed.netloc.lower().rstrip("\\")
        
        # Нормалізація www: www.example.com → example.com
        if self._normalize_www:
            if netloc.startswith("www."):
                netloc = netloc[4:]  # Видаляємо "www."

        # Normalize path:
        # 1. Replace backslashes with forward slashes
        # 2. Collapse multiple slashes into one
        # 3. Remove trailing slash (якщо увімкнено)
        path = parsed.path
        # Replace backslashes with forward slashes (browser-like behavior)
        path = path.replace("\\", "/")
        # Collapse multiple slashes into single slash
        import re
        path = re.sub(r"/+", "/", path)
        
        # Remove trailing slash (якщо увімкнено)
        if self._normalize_trailing_slash:
            path = path.rstrip("/")
        # If path was only slashes, it's now empty - leave it empty (root without trailing slash)

        # Reconstruct without fragment
        normalized = f"{scheme}://{netloc}{path}"
        
        # Query параметри
        if parsed.query:
            if self._normalize_query_params:
                # Сортуємо query параметри для консистентності
                from urllib.parse import parse_qsl, urlencode
                sorted_params = sorted(parse_qsl(parsed.query))
                if sorted_params:
                    normalized += f"?{urlencode(sorted_params)}"
            else:
                normalized += f"?{parsed.query}"
                
        return normalized

    @property
    def edges(self) -> List[Edge]:
        """Read-only доступ до ребер. Модифікація тільки через add_edge().

        Backend Delegation:
            Якщо Graph створено з backend параметром, делегує до backend.edges.
        """
        if self._use_backend and hasattr(self._backend, "edges"):
            return self._backend.edges  # type: ignore
        return self._edges

    @property
    def url_to_node(self) -> Dict[str, Node]:
        """Read-only доступ до URL мапи. Автоматично синхронізується з nodes.

        Backend Delegation:
            Якщо Graph створено з backend параметром, делегує до backend.url_to_node.
        """
        if self._use_backend and hasattr(self._backend, "url_to_node"):
            return self._backend.url_to_node  # type: ignore
        return self._url_to_node

    @property
    def _url_to_disk_map(self) -> Set[str]:
        """

        DEPRECATED: Використовуйте is_url_evicted() замість цього.

        Повертає пустий set для backward compatibility.
        Реальна перевірка тепер через _evicted_url_hashes або SQLite.
        """
        # Для backward compatibility повертаємо пустий set
        # Код що покладається на цей property повинен бути оновлений
        logger.warning(
            "DEPRECATED: _url_to_disk_map is deprecated. "
            "Use is_url_evicted() or get_evicted_urls_count() instead."
        )
        return set()

    @property
    def default_merge_strategy(self) -> str:
        """Повертає дефолтну стратегію merge для цього графа."""
        return self._default_merge_strategy

    @default_merge_strategy.setter
    def default_merge_strategy(self, value: str) -> None:
        """Встановлює дефолтну стратегію merge для цього графа."""
        valid_strategies = ["first", "last", "merge", "newest", "oldest", "custom"]
        if value not in valid_strategies:
            raise ValueError(f"Invalid merge strategy: {value}. Valid: {valid_strategies}")
        self._default_merge_strategy = value

    def _get_effective_merge_strategy(self) -> tuple:
        """
        Отримує ефективну стратегію merge з урахуванням контексту.

        ПРІОРИТЕТ (від вищого до нижчого):
        1. Локальний MergeContext (with with_merge_strategy('...'))
        2. default_merge_strategy графа self
        3. Глобальний DependencyRegistry default

                The MergeContextManager is imported lazily only when used, and the code
        handles ImportError gracefully for backward compatibility.

        Returns:
            Tuple (strategy_name, custom_merge_fn)
        """
        # Merge context should be passed via DI or method parameters
        # For backward compatibility, we only use graph's default_merge_strategy
        return self._default_merge_strategy, None

    def _get_shard_index(self, url: str) -> int:
        """

        Використовує hash для рівномірного розподілу URLs по шардах.

        Args:
            url: URL для хешування

        Returns:
            Індекс шарда (0 до _num_shards-1)
        """
        return hash(url) % self._num_shards

    def add_node(self, node: Node, overwrite: bool = False) -> Node:
        """
        Додає вузол до графу (sync версія).

        URL автоматично нормалізується для уникнення дублікатів:
        - Видаляється trailing slash
        - Hostname переводиться в lowercase
        - Видаляються фрагменти (#...)

        Args:
            node: Вузол для додавання
            overwrite: Якщо True - перезаписує існуючий вузол з тим самим URL

        Returns:
            Доданий або існуючий вузол
        """
        if self._use_backend:
            if overwrite:
                # Backend не має overwrite, але insert повертає existing
                return self._backend.insert_node_sync(node)  # type: ignore
            return self._backend.insert_node_sync(node)  # type: ignore
        # Нормалізуємо URL для уникнення дублікатів
        original_url = node.url
        normalized_url = self._normalize_url(original_url)

        # Оновлюємо URL ноди якщо змінився
        if original_url != normalized_url:
            node.url = normalized_url
            # Зберігаємо оригінальний URL в metadata
            if not hasattr(node, "metadata") or node.metadata is None:
                node.metadata = {}
            node.metadata["_original_url"] = original_url

        if self._low_memory_mode and self._is_url_evicted(normalized_url):
            # URL був evicted - видаляємо з hash set, повертаємо в RAM
            self._evicted_url_hashes.discard(hash(normalized_url))

        if normalized_url in self._url_to_node:
            existing = self._url_to_node[normalized_url]
            if overwrite:
                # Перезаписуємо існуючий вузол
                logger.debug("Node overwritten: %s", normalized_url)
                self._nodes[existing.node_id] = node
                self._url_to_node[normalized_url] = node
                return node
            else:
                # Повертаємо існуючий вузол
                return existing

        self._nodes[node.node_id] = node
        self._url_to_node[normalized_url] = node

        # Оновлюємо current_depth для eviction
        if hasattr(node, "depth") and node.depth > self._current_depth:
            self._current_depth = node.depth

        if node.simhash:
            self._invalidate_lsh_cache()

        # LOW-MEMORY MODE: НЕ викликаємо eviction тут!
        # Eviction викликається централізовано в CrawlCoordinator
        # після сканування нод. Це значно зменшує overhead.

        return node

    async def add_node_async(self, node: Node, overwrite: bool = False) -> Node:
        """

        Використовує шардований lock для зменшення contention при batch mode.
        URLs розподіляються по шардах через hash(), дозволяючи паралельний доступ.

        Args:
            node: Вузол для додавання
            overwrite: Якщо True - перезаписує існуючий вузол з тим самим URL

        Returns:
            Доданий або існуючий вузол
        """
        if self._use_backend:
            if overwrite:
                return await self._backend.insert_node_overwrite(node)  # type: ignore
            return await self._backend.insert_node(node)  # type: ignore
        shard_idx = self._get_shard_index(node.url)
        async with self._locks[shard_idx]:
            return self.add_node(node, overwrite)

    def get_node_by_url(self, url: str, load_from_disk: bool = True) -> Optional[Node]:
        """
        Отримує вузол за URL з підтримкою lazy loading.

        Args:
            url: URL ноди для пошуку
            load_from_disk: Чи завантажувати evicted ноду з диску в RAM (default: True)
        Returns:
            Node об'єкт або None
        """
        if self._use_backend:
            return self._backend.get_node_by_url_sync(url)  # type: ignore
        # Normalize URL before lookup
        url = self._normalize_url(url)

        # 1. RAM first (швидкий шлях)
        if url in self._url_to_node:
            return self._url_to_node[url]

        # 2. LOW-MEMORY MODE: завантажити з диска якщо evicted
        if self._low_memory_mode and load_from_disk and self._is_url_evicted(url):
            node = self._load_node_from_disk(url)
            if node:
                return node

        return None

    def _is_url_evicted(self, url: str) -> bool:
        """

        Використовує hash(url) для O(1) перевірки замість повних URL strings.

        Args:
            url: URL для перевірки

        Returns:
            True якщо URL evicted на диск
        """
        return hash(url) in self._evicted_url_hashes

    def _load_node_from_disk(self, url: str, lazy_metadata: bool = False) -> Optional[Node]:
        """
        Завантажує ноду з eviction storage.

        Повертає ноду в RAM cache та видаляє з evicted hash set.
        Якщо нода була підкласом Node (наприклад JobsNode),
        кастомні поля відновлюються з user_data['_custom_fields'].

        Args:
            url: URL ноди для завантаження
            lazy_metadata: Якщо True - не завантажувати metadata

        Returns:
            Node об'єкт або None
        """
        if not self._eviction_storage:
            return None

        if lazy_metadata and hasattr(self._eviction_storage, "load_node_without_metadata_sync"):
            node_data = self._eviction_storage.load_node_without_metadata_sync(url)
        else:
            node_data = self._eviction_storage.load_node_sync(url)

        if not node_data:
            logger.warning("Node %s not found in eviction storage", url)
            self._evicted_url_hashes.discard(hash(url))
            return None

        # Витягуємо кастомні поля з user_data якщо є
        user_data = node_data.get("user_data") or {}
        custom_fields = user_data.pop("_custom_fields", {}) if isinstance(user_data, dict) else {}

        # Реконструюємо Node об'єкт з кастомними полями
        node_kwargs = {
            "url": node_data["url"],
            "node_id": node_data["node_id"],
            "depth": node_data["depth"],
            "scanned": node_data["scanned"],
        }

        # Додаємо кастомні поля до kwargs якщо вони є
        # Це дозволяє підкласам Node отримати свої поля назад
        node_kwargs.update(custom_fields)

        node = Node(**node_kwargs)

        # Відновлюємо додаткові поля
        if node_data.get("response_status"):
            node.response_status = node_data["response_status"]
        if node_data.get("content_hash"):
            node.content_hash = node_data["content_hash"]
        if node_data.get("simhash"):
            node.simhash = node_data["simhash"]
        if node_data.get("priority"):
            node.priority = node_data["priority"]

        if node_data.get("metadata") is not None:
            node.metadata = node_data["metadata"]
        elif lazy_metadata:
            # Позначаємо що metadata потрібно lazy load
            node._lazy_metadata_url = url
            node._eviction_storage_ref = self._eviction_storage

        if user_data:
            node.user_data = user_data
        elif lazy_metadata:
            # Позначаємо що user_data потрібно lazy load
            node._lazy_user_data_url = url

        # Повертаємо в RAM cache
        self._nodes[node.node_id] = node
        self._url_to_node[url] = node
        self._evicted_url_hashes.discard(hash(url))

        self._eviction_stats["total_loaded"] += 1
        custom_keys = list(custom_fields.keys()) if custom_fields else []
        logger.debug(
            "Loaded node from disk: %s (lazy_metadata=%s, custom_fields=%s)",
            url,
            lazy_metadata,
            custom_keys,
        )

        return node

    def get_node_by_id(self, node_id: str) -> Optional[Node]:
        """Отримує вузол за ID."""
        if self._use_backend:
            return self._backend.get_node_by_id_sync(node_id)  # type: ignore

        return self._nodes.get(node_id)

    def update_node_simhash(self, node_id: str, simhash: str) -> bool:
        """

        Цей метод ОБОВ'ЯЗКОВО слід використовувати при оновленні simhash
        після add_node(), наприклад в process_html(). Прямий доступ
        node.simhash = '...' НЕ інвалідує кеш!

        Args:
            node_id: ID ноди
            simhash: Нове значення simhash (hex string)

        Returns:
            True якщо ноду оновлено, False якщо не знайдено
        """
        node = self._nodes.get(node_id)
        if not node:
            return False

        old_simhash = node.simhash
        node.simhash = simhash

        if simhash != old_simhash:
            self._invalidate_lsh_cache()
            logger.debug("Node %s simhash updated, LSH cache invalidated", node_id)

        return True

    async def update_node_simhash_async(self, node_id: str, simhash: str) -> bool:
        """

        Args:
            node_id: ID ноди
            simhash: Нове значення simhash (hex string)

        Returns:
            True якщо ноду оновлено, False якщо не знайдено
        """
        node = self._nodes.get(node_id)
        if not node:
            return False

        shard_idx = self._get_shard_index(node.url)
        async with self._locks[shard_idx]:
            return self.update_node_simhash(node_id, simhash)

    def add_edge(self, edge: Edge) -> Edge:
        """
        Додає ребро до графу (sync версія).

        Args:
            edge: Ребро для додавання

        Returns:
            Додане ребро
        """
        if self._use_backend:
            import asyncio

            # Sync wrapper для async backend method
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Використовуємо sync insert на backend напряму
                    self._backend._edges.append(edge)  # type: ignore
                    self._backend._edge_index.add((edge.source_node_id, edge.target_node_id))  # type: ignore
                    self._backend._adjacency_out[edge.source_node_id].add(edge.target_node_id)  # type: ignore
                    self._backend._adjacency_in[edge.target_node_id].add(edge.source_node_id)  # type: ignore
                    return edge
                return loop.run_until_complete(self._backend.insert_edge(edge))  # type: ignore
            except RuntimeError:
                # No event loop - create one
                return asyncio.run(self._backend.insert_edge(edge))  # type: ignore
        self._edges.append(edge)
        # Оновлюємо edge index для O(1) lookup
        self._edge_index.add((edge.source_node_id, edge.target_node_id))
        # Оновлюємо adjacency lists
        self._adjacency_list_out[edge.source_node_id].add(edge.target_node_id)
        self._adjacency_list_in[edge.target_node_id].add(edge.source_node_id)
        return edge

    async def add_edge_async(self, edge: Edge) -> Edge:
        """

        Використовує шардований lock на основі source_node_id для зменшення contention.
        При batch mode та asyncio.gather() це дозволяє паралельне додавання edges
        з різних source nodes.

        Args:
            edge: Ребро для додавання

        Returns:
            Додане ребро
        """
        if self._use_backend:
            return await self._backend.insert_edge(edge)  # type: ignore
        shard_idx = self._get_shard_index(edge.source_node_id)
        async with self._locks[shard_idx]:
            return self.add_edge(edge)

    def has_edge(self, source_node_id: str, target_node_id: str) -> bool:
        """
        Перевіряє наявність ребра за O(1) замість O(n).

                Args:
                    source_node_id: ID вузла-джерела
                    target_node_id: ID цільового вузла

                Returns:
                    True якщо ребро існує

                Example:
                    >>> graph.has_edge('node1', 'node2')
        """
        return (source_node_id, target_node_id) in self._edge_index

    def remove_node(self, node_id: str) -> bool:
        """
        Видаляє вузол з графу за node_id.

        Також видаляє всі ребра пов'язані з цим вузлом.

        Args:
            node_id: ID вузла для видалення

        Returns:
            True якщо вузол був видалений, False якщо не знайдено

        Example:
            >>> graph.remove_node('node-123')
        """
        node = self._nodes.get(node_id)
        if not node:
            return False

        # Видаляємо вузол
        del self._nodes[node_id]
        del self._url_to_node[node.url]

        # Видаляємо ребра та оновлюємо edge_index + adjacency lists одночасно
        edges_to_keep = []
        for edge in self._edges:
            if edge.source_node_id == node_id or edge.target_node_id == node_id:
                # Видаляємо з edge_index
                self._edge_index.discard((edge.source_node_id, edge.target_node_id))
                # Видаляємо з adjacency lists
                self._adjacency_list_out[edge.source_node_id].discard(edge.target_node_id)
                self._adjacency_list_in[edge.target_node_id].discard(edge.source_node_id)
            else:
                edges_to_keep.append(edge)

        self._edges = edges_to_keep

        # Видаляємо порожні записи з adjacency lists
        if node_id in self._adjacency_list_out:
            del self._adjacency_list_out[node_id]
        if node_id in self._adjacency_list_in:
            del self._adjacency_list_in[node_id]

        if node.simhash:
            self._invalidate_lsh_cache()

        logger.debug("Node removed: %s (id=%s)", node.url, node_id)
        return True

    def handle_redirect(
        self, original_node: Node, final_url: str, redirect_chain: Optional[list[str]] = None
    ) -> Optional[Node]:
        """
        Обробляє HTTP редірект - переспрямовує граф на реальний URL (sync версія).

        Args:
            original_node: Вузол який редірить (буде видалений якщо final існує)
            final_url: Фінальний URL після редіректу
            redirect_chain: Список проміжних URL редіректів (optional)
        Returns:
            Node: Вузол для final_url (новий або існуючий)
            None: Якщо original_node не в графі
        Examples:
            >>> # /page1 редірить на /404
            >>> original = graph.get_node_by_url("/page1")
            >>> final_node = graph.handle_redirect(original, "/404")
            >>> # Тепер всі edges що вели на /page1 ведуть на /404
            >>> # з metadata: was_redirect=True, original_url="/page1"
        """
        if not original_node or original_node.node_id not in self._nodes:
            logger.warning("Cannot handle redirect: original_node not in graph")
            return None

        original_url = original_node.url
        redirect_chain = redirect_chain or []
        if final_url == original_url:
            logger.debug("No redirect: %s -> %s", original_url, final_url)
            return original_node

        logger.info("Handling redirect: %s -> %s", original_url, final_url)

        # Крок 1: Знаходимо або створюємо вузол для final_url
        final_node = self.get_node_by_url(final_url)

        if final_node:
            # Final вузол вже існує - переспрямовуємо edges і видаляємо original
            logger.debug("Final node exists: %s, redirecting edges", final_url)

            # Переспрямовуємо incoming edges з original на final
            self._redirect_incoming_edges(
                original_node=original_node,
                final_node=final_node,
                original_url=original_url,
                redirect_chain=redirect_chain,
            )

            # Видаляємо original_node з графу
            # (outgoing edges теж видаляються, що правильно - вони з редірект-сторінки)
            self.remove_node(original_node.node_id)

            return final_node
        else:
            # Final вузол НЕ існує - перетворюємо original на final
            logger.debug(
                "Final node doesn't exist, transforming original: %s -> %s",
                original_url,
                final_url,
            )

            # Оновлюємо URL оригінального вузла
            del self._url_to_node[original_url]
            original_node.url = final_url
            self._url_to_node[final_url] = original_node

            # Додаємо redirect info в metadata вузла
            original_node.metadata["was_redirected_from"] = original_url
            original_node.metadata["redirect_chain"] = redirect_chain

            # Оновлюємо metadata всіх incoming edges
            for edge in self._edges:
                if edge.target_node_id == original_node.node_id:
                    edge.set_redirect_info(
                        original_url=original_url,
                        final_url=final_url,
                        redirect_chain=redirect_chain,
                    )

            return original_node

    def _redirect_incoming_edges(
        self,
        original_node: Node,
        final_node: Node,
        original_url: str,
        redirect_chain: list[str],
    ) -> int:
        """
        Переспрямовує всі incoming edges з original_node на final_node.

        Внутрішній метод для handle_redirect().

        Args:
            original_node: Вузол з якого переспрямовуємо
            final_node: Вузол на який переспрямовуємо
            original_url: Оригінальний URL (для metadata)
            redirect_chain: Ланцюжок редіректів (для metadata)

        Returns:
            Кількість переспрямованих edges
        """
        redirected_count = 0
        original_id = original_node.node_id
        final_id = final_node.node_id

        for edge in self._edges:
            if edge.target_node_id == original_id:
                # Оновлюємо target на final
                old_target = edge.target_node_id
                edge.target_node_id = final_id

                # Оновлюємо edge_index
                self._edge_index.discard((edge.source_node_id, old_target))
                self._edge_index.add((edge.source_node_id, final_id))

                # Оновлюємо adjacency lists
                self._adjacency_list_in[old_target].discard(edge.source_node_id)
                self._adjacency_list_in[final_id].add(edge.source_node_id)
                self._adjacency_list_out[edge.source_node_id].discard(old_target)
                self._adjacency_list_out[edge.source_node_id].add(final_id)

                # Додаємо redirect info в metadata
                edge.set_redirect_info(
                    original_url=original_url,
                    final_url=final_node.url,
                    redirect_chain=redirect_chain,
                )

                redirected_count += 1
                logger.debug("Redirected edge: %s... -> %s", edge.source_node_id[:8], final_node.url)

        if redirected_count > 0:
            logger.info(
                "Redirected %d edges from %s to %s",
                redirected_count,
                original_url,
                final_node.url,
            )

        return redirected_count

    async def handle_redirect_async(
        self, original_node: Node, final_url: str, redirect_chain: list[str] = None
    ) -> Optional[Node]:
        """

        Використовує глобальний lock оскільки redirect може впливати на багато edges
        та потребує atomic операції над усім графом.

        Args:
            original_node: Вузол який редірить (буде видалений якщо final існує)
            final_url: Фінальний URL після редіректу
            redirect_chain: Список проміжних URL редіректів (optional)

        Returns:
            Node: Вузол для final_url (новий або існуючий)
            None: Якщо original_node не в графі
        """
        async with self._global_lock:
            return self.handle_redirect(original_node, final_url, redirect_chain)

    def get_unscanned_nodes(self) -> List[Node]:
        """
        Повертає список непросканованих вузлів.
        Делеговано GraphStatistics.

        Returns:
            Список вузлів зі scanned=False
        """
        return GraphStatistics.get_unscanned_nodes(self)

    def get_failed_nodes(self, status_codes: List[int] = None) -> List[Node]:
        """
        Повертає вузли з помилковими статус кодами (429, 500, 502, 503, 504).

        Args:
            status_codes: Список статус кодів для фільтрації.
                         За замовчуванням: [429, 500, 502, 503, 504]

        Returns:
            Список вузлів з відповідними статусами

        Example:
            >>> # Отримати всі failed nodes
            >>> failed = graph.get_failed_nodes()
            >>>
            >>> # Тільки 429 (rate limited)
            >>> rate_limited = graph.get_failed_nodes([429])
        """
        if status_codes is None:
            status_codes = [429, 500, 502, 503, 504]
        # Використовуємо iter_nodes() для streaming доступу
        return [node for node in self.iter_nodes() if node.response_status in status_codes]

    def get_nodes_by_status(self, status_code: int) -> List[Node]:
        """
        Повертає вузли з конкретним HTTP статус кодом.

        Args:
            status_code: HTTP статус код

        Returns:
            Список вузлів з цим статусом

        Example:
            >>> ok_nodes = graph.get_nodes_by_status(200)
            >>> rate_limited = graph.get_nodes_by_status(429)
        """
        # Використовуємо iter_nodes() для streaming доступу
        return [node for node in self.iter_nodes() if node.response_status == status_code]

    def prepare_for_rescan(self, nodes: List[Node] = None, status_codes: List[int] = None) -> int:
        """
        Готує вузли для повторного сканування (rescan).

        Args:
            nodes: Список вузлів для rescan (якщо None - використовує status_codes)
            status_codes: Статус коди для автоматичного вибору вузлів.
                         За замовчуванням: [429] (rate limited)
        Returns:
            Кількість підготовлених вузлів
        Example:
            >>> # Підготувати всі 429 вузли для rescan
            >>> count = graph.prepare_for_rescan()
            >>> print(f"Prepared {count} nodes for rescan")
            >>>
            >>> # Або конкретні вузли
            >>> failed = graph.get_failed_nodes([429, 500])
            >>> graph.prepare_for_rescan(nodes=failed)
        """
        if nodes is None:
            if status_codes is None:
                status_codes = [429]
            nodes = self.get_failed_nodes(status_codes)

        count = 0
        for node in nodes:
            node.scanned = False
            node.response_status = None
            count += 1
            logger.debug("Prepared for rescan: %s", node.url)

        if count > 0:
            logger.info("Prepared %d nodes for rescan", count)

        return count

    def get_nodes_by_depth(self, depth: int) -> List[Node]:
        """
        Повертає всі вузли на певній глибині.
        Делеговано GraphStatistics.
        """
        return GraphStatistics.get_nodes_by_depth(self, depth)

    def get_stats(self) -> Dict[str, int]:
        """
        Повертає статистику графу.
        Делеговано GraphStatistics.

        Returns:
            Словник зі статистикою

        ВАЖЛИВО для low_memory_mode:
        - scanned_nodes/unscanned_nodes - тільки ноди в RAM
        - evicted_to_disk - майже всі з них scanned=True (eviction пріоритезує scanned)
        - Для фільтрації НЕ використовуйте scanned атрибут на нодах з RAM!
          Scanned ноди evicted на диск, тому в RAM лишаються тільки unscanned.
        """
        stats = GraphStatistics.get_stats(self)

        if self._low_memory_mode:
            evicted_count = len(self._evicted_url_hashes)
            stats["evicted_to_disk"] = evicted_count
            stats["total_nodes_including_evicted"] = len(self._nodes) + evicted_count
            # Note: evicted nodes are almost always scanned=True
            # Eviction пріоритезує scanned ноди для звільнення RAM
            stats["evicted_scanned_estimate"] = evicted_count  # Приблизна оцінка
            stats["eviction_stats"] = self._eviction_stats.copy()
            if self._eviction_storage:
                stats["eviction_storage"] = self._eviction_storage.get_stats()

        return stats

    def _get_strategy_multipliers(self) -> tuple:
        """
        Повертає (trigger_multiplier, target_multiplier) для поточної стратегії.

        Стратегії eviction:
        - aggressive: Trigger при 1.2x, target 0.8x (максимальна економія RAM)
        - balanced: Trigger при 1.5x, target 1.0x (оптимальний баланс)
        - lazy: Trigger при 2.0x, target 1.2x (мінімізація I/O)
        - memory_adaptive: Динамічно, базовані на balanced
        - custom: Користувацькі значення

        Returns:
            Tuple (trigger_multiplier, target_multiplier)
        """
        strategy_configs = {
            "aggressive": (1.2, 0.8),  # Trigger швидко, evict багато
            "balanced": (1.5, 1.0),  # Оптимальний баланс (DEFAULT)
            "lazy": (2.0, 1.2),  # Trigger пізно, тримати більше в RAM
            "memory_adaptive": (1.5, 1.0),  # Base values, adjusted dynamically
            "custom": (self._eviction_trigger_multiplier, self._eviction_target_multiplier),
        }

        return strategy_configs.get(self._eviction_strategy, strategy_configs["balanced"])

    def _should_evict(self) -> bool:
        """
        Визначає чи потрібен eviction на основі стратегії.

        Returns:
            True якщо потрібен eviction
        """
        if not self._low_memory_mode:
            return False

        current_nodes = len(self._nodes)

        if self._eviction_strategy == "memory_adaptive":
            return self._should_evict_memory_adaptive(current_nodes)

        # Для інших стратегій - перевіряємо threshold * trigger_multiplier
        evict_trigger = int(self._evict_threshold * self._trigger_mult)
        return current_nodes > evict_trigger

    def _should_evict_memory_adaptive(self, current_nodes: int) -> bool:
        """
        Memory-adaptive стратегія: враховує реальний RAM usage.

        Використовує psutil для моніторингу системної пам'яті.
        Fallback до balanced якщо psutil недоступний.

        Args:
            current_nodes: Поточна кількість нод в RAM

        Returns:
            True якщо потрібен eviction
        """
        try:
            import psutil

            memory = psutil.virtual_memory()
            memory_percent = memory.percent

            # Evict якщо RAM usage > threshold%
            if memory_percent > self._eviction_memory_threshold_percent:
                logger.debug(
                    "Memory-adaptive eviction triggered: RAM %.1f%% > %.1f%%",
                    memory_percent,
                    self._eviction_memory_threshold_percent,
                )
                return True

            # Також evict якщо nodes > threshold * 2 (safety net)
            if current_nodes > self._evict_threshold * 2:
                logger.debug(
                    "Memory-adaptive safety eviction: nodes %d > %d",
                    current_nodes,
                    self._evict_threshold * 2,
                )
                return True

            return False

        except ImportError:
            # psutil не встановлено - fallback до balanced
            logger.warning(
                "psutil not installed, falling back to balanced strategy. "
                "Install psutil for memory_adaptive: pip install psutil"
            )
            evict_trigger = int(self._evict_threshold * 1.5)
            return current_nodes > evict_trigger

    def _calculate_eviction_target(self) -> int:
        """
        Розраховує target кількість нод після eviction.

        Returns:
            Target кількість нод в RAM після eviction
        """
        if self._eviction_strategy == "memory_adaptive":
            # Для memory_adaptive - evict до 70% threshold
            return int(self._evict_threshold * 0.7)

        return int(self._evict_threshold * self._target_mult)

    def _maybe_evict(self) -> None:
        """
        Перевіряє чи потрібен eviction та виконує його.

        Викликається автоматично при add_node() та після scan в low_memory_mode.
        Sync версія для backward compatibility.

        PROFESSIONAL EVICTION STRATEGIES:
        - aggressive: Trigger при 1.2x threshold, evict до 0.8x threshold
        - balanced: Trigger при 1.5x threshold, evict до 1.0x threshold (DEFAULT)
        - lazy: Trigger при 2.0x threshold, evict до 1.2x threshold
        - memory_adaptive: Динамічна адаптація до реального RAM usage
        - custom: Користувацькі multipliers
        """
        if not self._should_evict():
            return

        evictable = self._find_evictable_nodes_fast()

        if not evictable:
            logger.debug("Cannot evict: %d nodes in RAM but none scanned.", len(self._nodes))
            return

        # Розраховуємо target на основі стратегії
        target_size = self._calculate_eviction_target()
        nodes_to_evict = len(self._nodes) - target_size

        if nodes_to_evict <= 0:
            return

        # Evict стільки скільки потрібно, але не більше наявних
        batch_size = min(nodes_to_evict, len(evictable))
        batch = evictable[:batch_size]

        logger.info(
            "[%s] Evicting %d nodes. RAM: %d -> ~%d (target: %d)",
            self._eviction_strategy,
            len(batch),
            len(self._nodes),
            len(self._nodes) - len(batch),
            target_size,
        )

        self._evict_nodes_sync(batch)

    def _find_evictable_nodes(self) -> List[Node]:
        """
        Знаходить ноди які можна безпечно evict-нути.

        СТРАТЕГІЯ (LRU-like з пріоритетом):
        1. Scanned ноди - evict спочатку (вони вже оброблені)
        2. Unscanned ноди - evict якщо scanned недостатньо

        Returns:
            Список нод для eviction, scanned спочатку, потім unscanned
        """
        return self._find_evictable_nodes_fast()

    def _find_evictable_nodes_fast(self) -> List[Node]:
        """
        ОПТИМІЗОВАНА версія: O(n) замість O(n log n).

        Не сортує - просто збирає scanned ноди першими.
        Для eviction порядок не критичний, важлива швидкість.

        Returns:
            Список нод: scanned спочатку, потім unscanned
        """
        scanned = []
        unscanned = []
        # Використовуємо iter_nodes() для streaming доступу
        # Примітка: в low_memory_mode без backend _url_to_node - це RAM, тому ОК
        for node in self.iter_nodes():
            if node.scanned:
                scanned.append(node)
            else:
                unscanned.append(node)

        return scanned + unscanned

    def _has_pending_references(self, node: Node) -> bool:
        """
        DEPRECATED: Цей метод більше не використовується для eviction.

        Залишено для backward compatibility та можливого використання
        в інших контекстах.

        Перевіряє чи є pending references до ноди.

        Args:
            node: Нода для перевірки

        Returns:
            True якщо є pending references
        """
        source_ids = self._adjacency_list_in.get(node.node_id, set())

        for source_id in source_ids:
            source_node = self._nodes.get(source_id)
            if source_node and not source_node.scanned:
                # Є нода яка ще не просканована і посилається на нашу
                return True

        return False

    def _evict_nodes_sync(self, nodes: List[Node]) -> None:
        """
        Синхронно evict-ить ноди на диск.

        Процес:
        1. Зберігає ноди в SQLite
        2. Зберігає edges пов'язані з нодами
        3. Batch видалення нод з _nodes та _url_to_node (GC optimized)
        4. Видаляє edges з RAM
        5. Додає URL hashes до evicted set
        6. Очищає adjacency lists

        Args:
            nodes: Список нод для eviction
        """
        import gc

        if not nodes or not self._eviction_storage:
            return

        gc_was_enabled = gc.isenabled()
        if gc_was_enabled:
            gc.disable()

        try:
            node_ids_to_evict = {n.node_id for n in nodes}
            urls_to_evict = {n.url for n in nodes}

            # 1. Зберігаємо ноди (ШВИДКО - batch insert)
            self._eviction_storage.save_nodes_sync(nodes)

            # Edges будуть перебудовані при load якщо потрібно
            # Це критично для швидкості - 84k edges = bottleneck
            edge_keys_to_remove = set()
            edges_removed = 0

            # Тільки якщо batch малий (<1000) - зберігаємо edges
            # Для великих batches - просто видаляємо edges з RAM
            EDGE_SAVE_THRESHOLD = 1000

            if len(nodes) <= EDGE_SAVE_THRESHOLD:
                # Малий batch - зберігаємо edges на диск
                for node_id in node_ids_to_evict:
                    for target_id in self._adjacency_list_out.get(node_id, set()):
                        edge_key = (node_id, target_id)
                        if edge_key in self._edge_index:
                            edge_keys_to_remove.add(edge_key)
                    for source_id in self._adjacency_list_in.get(node_id, set()):
                        edge_key = (source_id, node_id)
                        if edge_key in self._edge_index:
                            edge_keys_to_remove.add(edge_key)

                if edge_keys_to_remove:
                    edge_map = {(e.source_node_id, e.target_node_id): e for e in self._edges}
                    edges_to_save = [
                        edge_map[key] for key in edge_keys_to_remove if key in edge_map
                    ]
                    if edges_to_save:
                        self._eviction_storage.save_edges_sync(edges_to_save)
            else:
                # ВЕЛИКИЙ batch - швидке видалення edges БЕЗ збереження
                # Edges для scanned нод не потрібні (граф вже побудований)
                for node_id in node_ids_to_evict:
                    for target_id in self._adjacency_list_out.get(node_id, set()):
                        edge_keys_to_remove.add((node_id, target_id))
                    for source_id in self._adjacency_list_in.get(node_id, set()):
                        edge_keys_to_remove.add((source_id, node_id))

            # 3. Batch delete нод з RAM
            self._batch_remove_nodes(node_ids_to_evict, urls_to_evict)

            if edge_keys_to_remove:
                # Фільтруємо edge_keys через edge_index (може бути менше)
                edge_keys_to_remove &= self._edge_index

                if edge_keys_to_remove:
                    # Видаляємо з edge_index (O(k))
                    self._edge_index -= edge_keys_to_remove
                    edges_removed = len(edge_keys_to_remove)

                    # Перебудовуємо _edges list (O(E) але один раз)
                    self._edges = [
                        e
                        for e in self._edges
                        if (e.source_node_id, e.target_node_id) in self._edge_index
                    ]

            self._evicted_url_hashes.update(hash(url) for url in urls_to_evict)

            # 6. Очищаємо adjacency lists
            self._cleanup_adjacency_lists_for_evicted(node_ids_to_evict)

            # Оновлюємо статистику
            self._eviction_stats["total_evicted"] += len(nodes)
            self._eviction_stats["eviction_calls"] += 1
            edges_evicted = self._eviction_stats.get("edges_evicted", 0)
            self._eviction_stats["edges_evicted"] = edges_evicted + edges_removed

            # Інвалідуємо LSH кеш
            self._invalidate_lsh_cache()

            logger.debug(
                "Evicted %d nodes, %d edges to disk. RAM: %d nodes, %d edges, Disk: %d nodes",
                len(nodes),
                edges_removed,
                len(self._nodes),
                len(self._edges),
                len(self._evicted_url_hashes),
            )

        finally:
            if gc_was_enabled:
                gc.enable()
                gc.collect(generation=0)  # Тільки молоді об'єкти

    def _batch_remove_nodes(self, node_ids: Set[str], urls: Set[str]) -> None:
        """
        Batch видалення нод з мінімальним GC impact.

        Args:
            node_ids: Set node_id для видалення
            urls: Set URLs для видалення
        """
        # Один раз перебудовуємо словники замість поодиноких del
        # Це O(n) але з меншим GC overhead ніж n операцій del
        self._nodes = {k: v for k, v in self._nodes.items() if k not in node_ids}
        self._url_to_node = {k: v for k, v in self._url_to_node.items() if k not in urls}

    async def _evict_nodes_async(self, nodes: List[Node]) -> None:
        """
        Асинхронно evict-ить ноди на диск (не блокує event loop).

        - Використовує asyncio.to_thread() для I/O операцій
        - Event loop НЕ блокується під час eviction
        - Паралельні tasks продовжують працювати

        Args:
            nodes: Список нод для eviction
        """
        if not nodes or not self._eviction_storage:
            return

        # Запускаємо sync eviction в thread pool (не блокує event loop)
        await asyncio.to_thread(self._evict_nodes_sync, nodes)

    async def maybe_evict_async(self) -> None:
        """
        Асинхронна версія _maybe_evict().

        Використовуйте в async контексті (CrawlCoordinator) замість _maybe_evict().
        Не блокує event loop під час eviction.
        """
        if not self._should_evict():
            return

        evictable = self._find_evictable_nodes_fast()

        if not evictable:
            logger.debug("Cannot evict: %d nodes in RAM but none scanned.", len(self._nodes))
            return

        target_size = self._calculate_eviction_target()
        nodes_to_evict = len(self._nodes) - target_size

        if nodes_to_evict <= 0:
            return

        batch_size = min(nodes_to_evict, len(evictable))
        batch = evictable[:batch_size]

        logger.info(
            "[%s] Async evicting %d nodes. RAM: %d -> ~%d (target: %d)",
            self._eviction_strategy,
            len(batch),
            len(self._nodes),
            len(self._nodes) - len(batch),
            target_size,
        )

        await self._evict_nodes_async(batch)

    def _cleanup_adjacency_lists_for_evicted(self, evicted_node_ids: Set[str]) -> None:
        """

        СТАРИЙ КОД (O(N * M) - ДУЖЕ ПОВІЛЬНО):
        - Для кожної evicted ноди проходив через ВСІ adjacency lists
        - При eviction 35k нод з 50k total: 35000 * 50000 = 1.75 billion операцій!

        НОВИЙ КОД (O(E_evicted) - ШВИДКО):
        - Використовує зворотні посилання з adjacency_list_in/out
        - Тільки оновлює записи що реально посилаються на evicted ноди
        - При eviction 35k нод: ~70k операцій (2 adjacency lists на ноду)

        Args:
            evicted_node_ids: Set node_id що були evicted
        """
        # Збираємо всі ноди що потрібно оновити (зворотні посилання)
        # Ноди в adjacency_list_out які посилаються на evicted
        nodes_to_update_out: Set[str] = set()
        # Ноди в adjacency_list_in які посилаються на evicted
        nodes_to_update_in: Set[str] = set()

        for node_id in evicted_node_ids:
            # Знаходимо хто посилається НА цю ноду (через adjacency_list_in)
            # Ці ноди мають запис в adjacency_list_out що треба очистити
            if node_id in self._adjacency_list_in:
                nodes_to_update_out.update(self._adjacency_list_in[node_id])

            # Знаходимо на кого посилається ЦЯ нода (через adjacency_list_out)
            # Ці ноди мають запис в adjacency_list_in що треба очистити
            if node_id in self._adjacency_list_out:
                nodes_to_update_in.update(self._adjacency_list_out[node_id])

        # Виключаємо evicted ноди - їх видалимо повністю
        nodes_to_update_out -= evicted_node_ids
        nodes_to_update_in -= evicted_node_ids

        # Batch видалення посилань НА evicted ноди з adjacency_list_out
        for source_id in nodes_to_update_out:
            if source_id in self._adjacency_list_out:
                self._adjacency_list_out[source_id] -= evicted_node_ids

        # Batch видалення посилань ВІД evicted нод з adjacency_list_in
        for target_id in nodes_to_update_in:
            if target_id in self._adjacency_list_in:
                self._adjacency_list_in[target_id] -= evicted_node_ids

        # Видаляємо самі evicted ноди з adjacency lists
        for node_id in evicted_node_ids:
            self._adjacency_list_out.pop(node_id, None)
            self._adjacency_list_in.pop(node_id, None)

    def set_current_depth(self, depth: int) -> None:
        """
        Встановлює поточну глибину краулінгу.

        Використовується для визначення які ноди можна evict-нути.
        Ноди на поточній глибині та на 1 рівень вище не evict-яться.

        Args:
            depth: Поточна глибина краулінгу
        """
        self._current_depth = depth

    def get_total_nodes_count(self) -> int:
        """
        Повертає загальну кількість нод (RAM + Disk).

        В low_memory_mode враховує evicted ноди.

        Returns:
            Загальна кількість нод
        """
        if self._low_memory_mode:
            return len(self._nodes) + len(self._evicted_url_hashes)
        return len(self._nodes)

    def is_url_known(self, url: str) -> bool:
        """
        Перевіряє чи URL вже відомий графу (в RAM або на диску).

        Args:
            url: URL для перевірки

        Returns:
            True якщо URL вже є в графі
        """
        url = self._normalize_url(url)
        if url in self._url_to_node:
            return True
        if self._low_memory_mode and self._is_url_evicted(url):
            return True
        return False

    def get_url_status(self, url: str) -> Tuple[bool, Optional[Node]]:
        """

        Замінює два окремих виклики:
        - scheduler.has_url(url)
        - graph.get_node_by_url(url)

        Один lookup замість двох = 2x швидше.

        Args:
            url: URL для перевірки

        Returns:
            Tuple[bool, Optional[Node]]:
                - (True, Node) - URL відомий, нода в RAM
                - (True, None) - URL відомий, але evicted на диск
                - (False, None) - URL невідомий
        """
        url = self._normalize_url(url)
        # 1. Перевірка RAM (найшвидша)
        node = self._url_to_node.get(url)
        if node:
            return True, node

        # 2. Перевірка evicted (low_memory_mode)
        if self._low_memory_mode and self._is_url_evicted(url):
            return True, None  # Відомий, але evicted

        return False, None  # Невідомий URL

    def check_urls_batch(self, urls: List[str]) -> Dict[str, Tuple[bool, Optional[Node]]]:
        """

        Перевіряє багато URLs за один раз замість N окремих викликів.
        Оптимізовано для обробки links зі сторінки (100+ URLs).

        Args:
            urls: Список URLs для перевірки

        Returns:
            Dict[url, Tuple[is_known, node]]:
                - url: URL що перевірявся
                - is_known: True якщо URL відомий
                - node: Node якщо в RAM, None якщо evicted або невідомий
        """
        result: Dict[str, Tuple[bool, Optional[Node]]] = {}
        unknown_urls: List[str] = []

        # Normalize all URLs first
        normalized_urls = [self._normalize_url(url) for url in urls]

        # 1. Спочатку RAM (швидко) - O(n)
        for url in normalized_urls:
            node = self._url_to_node.get(url)
            if node:
                result[url] = (True, node)
            else:
                unknown_urls.append(url)

        if not unknown_urls:
            return result

        # 2. Для low_memory_mode - batch перевірка evicted URLs
        if self._low_memory_mode and self._eviction_storage:
            # Batch query до SQLite (один запит замість N)
            evicted_urls = self._eviction_storage.urls_exist_batch(unknown_urls)

            for url in unknown_urls:
                if url in evicted_urls:
                    result[url] = (True, None)  # Evicted
                else:
                    result[url] = (False, None)  # Невідомий
        else:
            # Без low_memory_mode - всі unknown є невідомими
            for url in unknown_urls:
                result[url] = (False, None)

        return result

    def get_evicted_urls_count(self) -> int:
        """

        Замінює len(self._url_to_disk_map) для backward compatibility.

        Returns:
            Кількість evicted URLs
        """
        return len(self._evicted_url_hashes)

    def load_all_from_disk(self) -> int:
        """
        Завантажує всі evicted ноди назад в RAM.

        Використовується для фіналізації графа або серіалізації.

        Returns:
            Кількість завантажених нод
        """
        if not self._low_memory_mode or not self._evicted_url_hashes:
            return 0

        if not self._eviction_storage:
            return 0

        loaded = 0
        urls_to_load = self._eviction_storage.get_all_evicted_urls()

        for url in urls_to_load:
            node = self._load_node_from_disk(url)
            if node:
                loaded += 1

        logger.info("Loaded %d nodes from disk to RAM", loaded)
        return loaded

    def close_eviction_storage(self) -> None:
        """Закриває eviction storage (БД залишається на диску)."""
        if self._eviction_storage:
            self._eviction_storage.close()
            self._eviction_storage = None

    def cleanup_eviction_storage(self) -> None:
        """
        Видаляє eviction storage з диску після завершення краулінгу.

        ВАЖЛИВО: Викликайте цей метод після завершення краулінгу,
        щоб не накопичувались дані на диску!

        Example:
            >>> # Після завершення краулінгу
            >>> graph.save("final_graph.json")
            >>> graph.cleanup_eviction_storage()  # Видаляє eviction.db
        """
        if self._eviction_storage:
            if hasattr(self._eviction_storage, "cleanup"):
                self._eviction_storage.cleanup(delete_files=True)
            else:
                self._eviction_storage.close()
            self._eviction_storage = None
            self._evicted_url_hashes.clear()
            logger.info("Eviction storage cleaned up")

    def to_dict(self) -> Dict[str, Any]:
        """
        Серіалізує весь граф у словник.

        Використовує Pydantic model_dump() для автоматичної серіалізації
        всіх полів (включаючи кастомні поля в підкласах Node/Edge).

         ВАЖЛИВО про url_to_node мапу:
        - url_to_node НЕ серіалізується (це допоміжна структура)
        - При десеріалізації мапа відновлюється автоматично через add_node()
        - Не потрібно зберігати url_to_node окремо
        - Мапа завжди синхронізована з nodes словником

        Backend Delegation:
            Використовує iter_nodes() для streaming доступу до нод.
        """
        # Використовуємо iter_nodes() замість _nodes.values() для backend підтримки
        return {
            "nodes": [node.model_dump() for node in self.iter_nodes()],
            "edges": [edge.model_dump() for edge in self.iter_edges()],
        }

    def clear(self):
        """Очищає граф."""
        self._nodes.clear()
        self._edges.clear()
        self._url_to_node.clear()
        # Очищаємо edge_index
        self._edge_index.clear()
        # Очищаємо adjacency lists
        self._adjacency_list_out.clear()
        self._adjacency_list_in.clear()

    def __repr__(self):
        stats = self.get_stats()
        total = stats["total_nodes"]
        edges = stats["total_edges"]
        scanned = stats["scanned_nodes"]
        return f"Graph(nodes={total}, edges={edges}, scanned={scanned})"

    def __len__(self) -> int:
        """
        Повертає кількість вузлів у графі.

        Returns:
            Кількість вузлів

        Example:
            >>> graph = Graph()
            >>> len(graph)
            0
        """
        if self._use_backend:
            return self._backend.count_nodes_sync()  # type: ignore

        return len(self._nodes)

    def __iter__(self) -> Iterator[Node]:
        """
        Дозволяє ітерацію по вузлах графу.

        Yields:
            Node об'єкти

        Example:
            >>> for node in graph:
            >>>     print(node.url)
        """
        if self._use_backend:
            return self._backend.iter_nodes_sync()  # type: ignore

        return iter(self._nodes.values())

    def __contains__(self, item: Union[str, Node]) -> bool:
        """
        Перевіряє наявність вузла в графі.

        Args:
            item: URL (str) або Node об'єкт

        Returns:
            True якщо вузол присутній у графі

        Example:
            >>> 'https://example.com' in graph
            >>> node in graph
        """
        if isinstance(item, str):
            # Normalize URL before lookup
            item = self._normalize_url(item)
            return item in self._url_to_node
        elif isinstance(item, Node):
            return item.node_id in self._nodes
        return False

    def __getitem__(self, key: Union[str, int]) -> Node:
        """
        Доступ до вузла за URL або індексом.

        Args:
            key: URL (str) або індекс (int)

        Returns:
            Node об'єкт

        Raises:
            KeyError: Якщо вузол не знайдено
            IndexError: Якщо індекс за межами

        Example:
            >>> node = graph['https://example.com']
            >>> node = graph[0]
        """
        if isinstance(key, str):
            # Normalize URL before lookup
            key = self._normalize_url(key)
            # Доступ за URL
            node = self._url_to_node.get(key)
            if node is None:
                raise KeyError(f"Node with URL '{key}' not found")
            return node
        elif isinstance(key, int):
            # Доступ за індексом
            # Використовуємо iter_nodes() для streaming доступу
            if key < 0:
                raise IndexError(f"Negative index {key} not supported with backend")
            for i, node in enumerate(self.iter_nodes()):
                if i == key:
                    return node
            raise IndexError(f"Index {key} out of range")
        else:
            raise TypeError(f"Key must be str or int, not {type(key)}")

    def __add__(self, other: "Graph") -> "Graph":
        """
        Об'єднання двох графів (union).
        Делеговано GraphOperations.union().
        Args:
            other: Інший граф для об'єднання
        Returns:
            Новий граф (union)
        Example:
            >>> g1 = Graph(default_merge_strategy='merge')
            >>> g2 = Graph()
            >>> g3 = g1 + g2  # Використає 'merge' стратегію з g1
            >>>
            >>> # Або через контекст
            >>> from graph_crawler.application.context import with_merge_strategy
            >>> with with_merge_strategy('newest'):
            ...     g3 = g1 + g2  # Використає 'newest'
        """
        if not isinstance(other, Graph):
            raise TypeError(f"Cannot add Graph and {type(other)}")
        strategy, custom_fn = self._get_effective_merge_strategy()

        return GraphOperations.union(
            self,
            other,
            merge_strategy=strategy,
            custom_merge_fn=custom_fn,
        )

    def __sub__(self, other: "Graph") -> "Graph":
        """
        Різниця двох графів (difference).
        Делеговано GraphOperations.difference().

        Args:
            other: Граф для віднімання

        Returns:
            Новий граф (різниця)

        Example:
            >>> g3 = g1 - g2
        """
        if not isinstance(other, Graph):
            raise TypeError(f"Cannot subtract {type(other)} from Graph")
        return GraphOperations.difference(self, other)

    def __and__(self, other: "Graph") -> "Graph":
        """
        Перетин двох графів (intersection).
        Делеговано GraphOperations.intersection().

        Args:
            other: Інший граф

        Returns:
            Новий граф (перетин)

        Example:
            >>> g3 = g1 & g2
        """
        if not isinstance(other, Graph):
            raise TypeError(f"Cannot intersect Graph and {type(other)}")
        return GraphOperations.intersection(self, other)

    def __or__(self, other: "Graph") -> "Graph":
        """
        Об'єднання графів (альтернатива __add__).
        Делеговано GraphOperations.union().
        Args:
            other: Інший граф
        Returns:
            Новий граф (union)
        Example:
            >>> g1 = Graph(default_merge_strategy='merge')
            >>> g2 = Graph()
            >>> g3 = g1 | g2  # Використає 'merge' стратегію з g1
            >>>
            >>> # Або через контекст
            >>> from graph_crawler.application.context import with_merge_strategy
            >>> with with_merge_strategy('newest'):
            ...     g3 = g1 | g2  # Використає 'newest'
        """
        if not isinstance(other, Graph):
            raise TypeError(f"Cannot OR Graph and {type(other)}")
        strategy, custom_fn = self._get_effective_merge_strategy()

        return GraphOperations.union(
            self,
            other,
            merge_strategy=strategy,
            custom_merge_fn=custom_fn,
        )

    def __xor__(self, other: "Graph") -> "Graph":
        """
        Симетрична різниця графів.
        Делеговано GraphOperations.symmetric_difference().

        Args:
            other: Інший граф

        Returns:
            Новий граф (симетрична різниця)

        Example:
            >>> g3 = g1 ^ g2
        """
        if not isinstance(other, Graph):
            raise TypeError(f"Cannot XOR Graph and {type(other)}")
        return GraphOperations.symmetric_difference(self, other)

    def __eq__(self, other: object) -> bool:
        """
        Перевіряє рівність двох графів.
        Делеговано GraphOperations.is_equal().

        Args:
            other: Інший граф

        Returns:
            True якщо графи рівні

        Example:
            >>> g1 == g2
        """
        if not isinstance(other, Graph):
            return False
        return GraphOperations.is_equal(self, other)

    def __ne__(self, other: object) -> bool:
        """Перевіряє нерівність графів."""
        return not self.__eq__(other)

    def __lt__(self, other: "Graph") -> bool:
        """
        Перевіряє чи є цей граф строгим підграфом іншого.
        Делеговано GraphOperations.is_subgraph(strict=True).

        Args:
            other: Інший граф

        Returns:
            True якщо self є строгим підграфом other

        Example:
            >>> g1 < g2  # g1 є підграфом g2
        """
        if not isinstance(other, Graph):
            raise TypeError(f"Cannot compare Graph and {type(other)}")
        return GraphOperations.is_subgraph(self, other, strict=True)

    def __le__(self, other: "Graph") -> bool:
        """
        Перевіряє чи є підграфом або рівним.
        Делеговано GraphOperations.is_subgraph(strict=False).
        """
        if not isinstance(other, Graph):
            raise TypeError(f"Cannot compare Graph and {type(other)}")
        return GraphOperations.is_subgraph(self, other, strict=False)

    def __gt__(self, other: "Graph") -> bool:
        """
        Перевіряє чи є цей граф строгим надграфом іншого.
        Делеговано GraphOperations.is_supergraph(strict=True).
        """
        if not isinstance(other, Graph):
            raise TypeError(f"Cannot compare Graph and {type(other)}")
        return GraphOperations.is_supergraph(self, other, strict=True)

    def __ge__(self, other: "Graph") -> bool:
        """
        Перевіряє чи є надграфом або рівним.
        Делеговано GraphOperations.is_supergraph(strict=False).
        """
        if not isinstance(other, Graph):
            raise TypeError(f"Cannot compare Graph and {type(other)}")
        return GraphOperations.is_supergraph(self, other, strict=False)

    def is_subgraph(self, other: "Graph") -> bool:
        """
        Перевіряє чи є цей граф підграфом іншого.
        Делеговано GraphOperations.is_subgraph().

        Args:
            other: Інший граф

        Returns:
            True якщо self є підграфом other
        """
        return GraphOperations.is_subgraph(self, other, strict=False)

    def get_degree(self, node_id: str) -> int:
        """
        Повертає ступінь вузла (кількість інцидентних ребер).
        Делеговано GraphStatistics.get_degree().

        Args:
            node_id: ID вузла

        Returns:
            Ступінь вузла (in_degree + out_degree)
        """
        return GraphStatistics.get_degree(self, node_id)

    def get_in_degree(self, node_id: str) -> int:
        """
        Повертає вхідний ступінь вузла.
        Делеговано GraphStatistics.get_in_degree().
        """
        return GraphStatistics.get_in_degree(self, node_id)

    def get_out_degree(self, node_id: str) -> int:
        """
        Повертає вихідний ступінь вузла.
        Делеговано GraphStatistics.get_out_degree().
        """
        return GraphStatistics.get_out_degree(self, node_id)

    def get_neighbors(self, node_id: str) -> List[Node]:
        """
        Повертає всіх сусідів вузла.
        Делеговано GraphStatistics.get_neighbors().

        Args:
            node_id: ID вузла

        Returns:
            Список сусідніх вузлів
        """
        return GraphStatistics.get_neighbors(self, node_id)

    def is_connected(self) -> bool:
        """
        Перевіряє чи є граф зв'язаним.
        Делеговано GraphStatistics.is_connected().

        Returns:
            True якщо граф зв'язаний
        """
        return GraphStatistics.is_connected(self)

    def copy(self) -> "Graph":
        """
        Створює глибоку копію графу.
        Раніше використовувався shallow copy, що призводило до того що
        модифікація нод в копії впливала на оригінал.

        Returns:
            Новий граф з НЕЗАЛЕЖНИМИ копіями вузлів та ребер
        """

        result = Graph(default_merge_strategy=self._default_merge_strategy)
        # Використовуємо iter_nodes() для streaming доступу
        for node in self.iter_nodes():
            # Pydantic v2 deep copy - копіює всі вкладені структури
            node_copy = node.model_copy(deep=True)
            result.add_node(node_copy)
        for edge in self.iter_edges():
            edge_copy = edge.model_copy(deep=True)
            result.add_edge(edge_copy)

        return result

    def get_popular_nodes(self, top_n: int = 10, by: str = "in_degree") -> List[Node]:
        """Повертає топ N найпопулярніших nodes.

        Делеговано EdgeAnalysis.get_popular_nodes().

        Args:
            top_n: Кількість топ nodes
            by: Критерій ('in_degree', 'out_degree', 'total_degree')

        Returns:
            Список найпопулярніших Node об'єктів

        Example:
            >>> popular = graph.get_popular_nodes(top_n=10)
            >>> for node in popular:
            >>>     print(f"{node.url}: {graph.get_in_degree(node.node_id)} incoming")
        """
        return EdgeAnalysis.get_popular_nodes(self, top_n, by)

    def get_edge_statistics(self) -> Dict[str, Any]:
        """Повертає детальну статистику edges по типах.

        Делеговано EdgeAnalysis.get_edge_statistics().

        Returns:
            Словник зі статистикою (total_edges, by_type, avg_depth_diff, тощо)

        Example:
            >>> stats = graph.get_edge_statistics()
            >>> print(f"Internal links: {stats['by_type']['internal']}")
        """
        return EdgeAnalysis.get_edge_statistics(self)

    def find_cycles(self, max_cycles: Optional[int] = None) -> List[List[str]]:
        """Знаходить цикли в графі (DFS алгоритм).

        Делеговано EdgeAnalysis.find_cycles().

        Args:
            max_cycles: Максимальна кількість циклів (None = всі)

        Returns:
            Список циклів (кожен цикл - список node_id)

        Example:
            >>> cycles = graph.find_cycles(max_cycles=10)
            >>> for cycle in cycles:
            >>>     print(f"Cycle: {' -> '.join(cycle)}")
        """
        return EdgeAnalysis.find_cycles(self, max_cycles)

    def get_edges_by_type(self, link_types: List[str], match_mode: str = "any") -> List[Edge]:
        """Фільтрує edges по типу посилання.

        Делеговано EdgeAnalysis.get_edges_by_type().

        Args:
            link_types: Список типів для фільтрації
            match_mode: Режим ('any', 'all', 'exact')

        Returns:
            Список Edge об'єктів

        Example:
            >>> # Всі internal та deeper edges (OR)
            >>> edges = graph.get_edges_by_type(['internal', 'deeper'], match_mode='any')
            >>>
            >>> # Тільки edges що є і internal І deeper (AND)
            >>> edges = graph.get_edges_by_type(['internal', 'deeper'], match_mode='all')
        """
        return EdgeAnalysis.get_edges_by_type(self, link_types, match_mode)

    def export_edges(self, filepath: str, format: str = "json", **kwargs) -> Any:
        """Експортує edges в файл.

        Підтримує формати: json, csv, dot
        Args:
            filepath: Шлях до файлу
            format: Формат ('json', 'csv', 'dot')
            **kwargs: Додаткові параметри для експортера
        Returns:
            Результат експорту (залежить від формату)
        Raises:
            NotImplementedError: This method is deprecated in Clean Architecture
        """
        raise NotImplementedError(
            "export_edges() is deprecated (Clean Architecture violation). "
            "Use GraphExportUseCase from Application layer:\n"
            "  from graph_crawler.application.use_cases import GraphExportUseCase\n"
            "  exporter = GraphExportUseCase(edge_exporter=EdgeExporter)\n"
            "  exporter.export_edges(graph, filepath, format='json')"
        )

    def export_nodes(
        self,
        filepath: str,
        format: str = "json",
        node_fields: Optional[List[str]] = None,
        transform_node: Optional[callable] = None,
        predicate: Optional[callable] = None,
        **kwargs,
    ) -> Any:
        """Експортує ноди в файл з вибором полів та трансформацією.

        Підтримує формати: json, csv
        Args:
            filepath: Шлях до файлу
            format: Формат ('json', 'csv')
            node_fields: Список полів для включення (dot notation: 'metadata.title')
            transform_node: Функція трансформації (node) -> dict
            predicate: Фільтр нод (node) -> bool
            **kwargs: Додаткові параметри
        Raises:
            NotImplementedError: This method is deprecated in Clean Architecture
        """
        raise NotImplementedError(
            "export_nodes() is deprecated (Clean Architecture violation). "
            "Use GraphExportUseCase from Application layer:\n"
            "  from graph_crawler.application.use_cases import GraphExportUseCase\n"
            "  exporter = GraphExportUseCase(node_exporter=NodeExporter)\n"
            "  exporter.export_nodes(graph, filepath, format='json')"
        )

    def _build_lsh_index(self, force_rebuild: bool = False) -> Dict[int, Dict[int, List[Node]]]:
        """

        Будує LSH індекс для швидкого пошуку подібних нод.
        Розбиває 64-бітний simhash на 4 бенди по 16 біт.

        Args:
            force_rebuild: Примусово перебудувати індекс (ігнорувати кеш)

        Returns:
            Dict[band_idx][band_value] = [nodes]
        """
        current_node_count = len(self._nodes)

        if (
            not force_rebuild
            and self._lsh_index_cache is not None
            and self._lsh_index_node_count == current_node_count
        ):
            # Кеш валідний - повертаємо його
            return self._lsh_index_cache

        # Будуємо новий індекс
        num_bands = 4
        band_size = 16

        buckets: Dict[int, Dict[int, List[Node]]] = {i: {} for i in range(num_bands)}
        # Використовуємо iter_nodes() для streaming доступу
        for node in self.iter_nodes():
            if not node.simhash:
                continue

            try:
                if isinstance(node.simhash, str):
                    simhash_int = int(node.simhash, 16)
                else:
                    simhash_int = node.simhash
            except (ValueError, TypeError):
                continue

            for band_idx in range(num_bands):
                shift = band_idx * band_size
                band_value = (simhash_int >> shift) & ((1 << band_size) - 1)

                if band_value not in buckets[band_idx]:
                    buckets[band_idx][band_value] = []
                buckets[band_idx][band_value].append(node)

        # Зберігаємо в кеш
        self._lsh_index_cache = buckets
        self._lsh_index_node_count = current_node_count

        logger.debug("LSH index rebuilt: %d nodes", current_node_count)

        return buckets

    def _invalidate_lsh_cache(self) -> None:
        """Інвалідує кеш LSH індексу."""
        self._lsh_index_cache = None
        self._lsh_index_node_count = 0

    def find_similar_nodes(
        self, node: Node, max_distance: int = 10, limit: Optional[int] = None
    ) -> List[Tuple[Node, int]]:
        """

        Замість O(n) порівнянь з усіма нодами, використовує LSH індекс
        Args:
            node: Нода для порівняння (повинна мати simhash)
            max_distance: Максимальна Hamming distance (default: 10)
            limit: Максимальна кількість результатів (None = всі)
        Returns:
            Список tuple (Node, distance) відсортований за distance
        Example:
            >>> node = graph.get_node_by_url("https://example.com/page1")
            >>> similar = graph.find_similar_nodes(node, max_distance=5)
            >>> for similar_node, distance in similar:
            ...     print(f"{similar_node.url}: distance={distance}")
        """
        if not node.simhash:
            logger.warning("Node %s has no simhash, cannot find similar nodes", node.url)
            return []

        try:
            node_simhash_int = (
                int(node.simhash, 16) if isinstance(node.simhash, str) else node.simhash
            )
        except (ValueError, TypeError):
            logger.warning("Invalid simhash for node %s", node.url)
            return []

        num_bands = 4
        band_size = 16

        # Збираємо кандидатів з LSH бакетів
        candidates: Set[str] = set()
        lsh_index = self._build_lsh_index()

        for band_idx in range(num_bands):
            shift = band_idx * band_size
            band_value = (node_simhash_int >> shift) & ((1 << band_size) - 1)

            if band_value in lsh_index[band_idx]:
                for candidate in lsh_index[band_idx][band_value]:
                    if candidate.node_id != node.node_id:
                        candidates.add(candidate.node_id)
        results = []

        for candidate_id in candidates:
            other = self._nodes.get(candidate_id)
            if not other or not other.simhash:
                continue

            # Обчислюємо Hamming distance
            distance = Node.hamming_distance(node.simhash, other.simhash)

            if distance <= max_distance:
                results.append((other, distance))

        # Сортуємо за distance (менша = більш схожі)
        results.sort(key=lambda x: x[1])

        # Обмежуємо кількість якщо вказано limit
        if limit is not None:
            results = results[:limit]

        return results

    def find_duplicates(self, max_distance: int = 3) -> List[List[Node]]:
        """

        Використовує кешований LSH індекс замість побудови нового при кожному виклику.
        Args:
            max_distance: Максимальна Hamming distance для дублікатів (default: 3)
        Returns:
            Список груп дублікатів (кожна група - список Node)
        Example:
            >>> duplicates = graph.find_duplicates(max_distance=3)
            >>> print(f"Found {len(duplicates)} duplicate groups")
            >>> for group in duplicates:
            ...     print(f"Group of {len(group)} duplicates:")
            ...     for node in group:
            ...         print(f"  - {node.url}")
        """
        # Збираємо ноди з simhash
        # Використовуємо iter_nodes() для streaming доступу
        nodes_with_simhash = [node for node in self.iter_nodes() if node.simhash]

        if not nodes_with_simhash:
            return []

        # OPTIMIZATION-001: Використовуємо кешований LSH індекс
        lsh_index = self._build_lsh_index()

        # Збираємо кандидатів для порівняння з кешованого індексу
        candidate_pairs: Set[Tuple[str, str]] = set()

        for band_buckets in lsh_index.values():
            for bucket_nodes in band_buckets.values():
                if len(bucket_nodes) > 1:
                    # Додаємо всі пари з цього бакету як кандидатів
                    for i, node1 in enumerate(bucket_nodes):
                        for node2 in bucket_nodes[i + 1 :]:
                            # Сортуємо ID щоб уникнути дублікатів пар
                            pair = tuple(sorted([node1.node_id, node2.node_id]))
                            candidate_pairs.add(pair)
        # Будуємо граф подібності
        similarity_graph: Dict[str, Set[str]] = {}

        for node1_id, node2_id in candidate_pairs:
            node1 = self._nodes.get(node1_id)
            node2 = self._nodes.get(node2_id)

            if not node1 or not node2 or not node1.simhash or not node2.simhash:
                continue

            distance = Node.hamming_distance(node1.simhash, node2.simhash)

            if distance <= max_distance:
                if node1_id not in similarity_graph:
                    similarity_graph[node1_id] = set()
                if node2_id not in similarity_graph:
                    similarity_graph[node2_id] = set()

                similarity_graph[node1_id].add(node2_id)
                similarity_graph[node2_id].add(node1_id)

        # Групуємо за компонентами зв'язності (Union-Find)
        processed: Set[str] = set()
        groups: List[List[Node]] = []

        for node_id in similarity_graph:
            if node_id in processed:
                continue

            # BFS для знаходження компоненти зв'язності
            group_ids: List[str] = []
            queue = [node_id]

            while queue:
                current_id = queue.pop(0)
                if current_id in processed:
                    continue

                processed.add(current_id)
                group_ids.append(current_id)

                for neighbor_id in similarity_graph.get(current_id, []):
                    if neighbor_id not in processed:
                        queue.append(neighbor_id)

            # Конвертуємо ID в Node об'єкти
            if len(group_ids) > 1:
                group = [self._nodes[nid] for nid in group_ids if nid in self._nodes]
                if len(group) > 1:
                    groups.append(group)

        # Сортуємо групи за розміром (більші спочатку)
        groups.sort(key=len, reverse=True)

        return groups

    def get_duplicate_stats(self, max_distance: int = 3) -> Dict[str, Any]:
        """
        Повертає статистику дублікатів у графі.

        Args:
            max_distance: Максимальна Hamming distance для дублікатів

        Returns:
            Словник зі статистикою:
            - total_nodes: Загальна кількість нод
            - nodes_with_simhash: Кількість нод з simhash
            - duplicate_groups: Кількість груп дублікатів
            - total_duplicates: Загальна кількість дублюючих нод
            - largest_group_size: Розмір найбільшої групи
            - duplicate_rate: Відсоток дублікатів

        Example:
            >>> stats = graph.get_duplicate_stats()
            >>> print(f"Duplicate rate: {stats['duplicate_rate']:.1f}%")
        """
        duplicates = self.find_duplicates(max_distance)
        # Використовуємо iter_nodes() для streaming доступу
        nodes_with_simhash = sum(1 for n in self.iter_nodes() if n.simhash)
        total_duplicates = sum(len(group) for group in duplicates)
        largest_group = max((len(g) for g in duplicates), default=0)

        duplicate_rate = (
            (total_duplicates / nodes_with_simhash * 100) if nodes_with_simhash > 0 else 0
        )

        return {
            "total_nodes": len(self._nodes),
            "nodes_with_simhash": nodes_with_simhash,
            "duplicate_groups": len(duplicates),
            "total_duplicates": total_duplicates,
            "largest_group_size": largest_group,
            "duplicate_rate": round(duplicate_rate, 2),
        }

    def deduplicate_by_url(
        self,
        extract_base_url: callable,
        select_best: str = "canonical",
        language_priority: Optional[List[str]] = None,
        remove_duplicates: bool = False,
    ) -> Dict[str, Any]:
        """
        Дедуплікує ноди за canonical/base URL.

        Returns:
            Словник з результатами:
            - groups: Dict[base_url, List[Node]] - групи дублікатів
            - unique_nodes: List[Node] - унікальні ноди (найкращі з груп)
            - removed_count: int - кількість видалених (якщо remove_duplicates=True)
            - stats: Dict - статистика
        """

        # Групуємо ноди за base URL
        groups: Dict[str, List[Node]] = {}
        # Використовуємо iter_nodes() для streaming доступу
        for node in self.iter_nodes():
            try:
                base_url = extract_base_url(node.url)
            except Exception as e:
                logger.warning("Error extracting base URL for %s: %s", node.url, e)
                base_url = node.url

            if base_url not in groups:
                groups[base_url] = []
            groups[base_url].append(node)

        # Вибираємо найкращу ноду з кожної групи
        unique_nodes = []
        removed_nodes = []

        for base_url, group_nodes in groups.items():
            if len(group_nodes) == 1:
                unique_nodes.append(group_nodes[0])
                continue

            # Вибираємо найкращу
            best = self._select_best_node(group_nodes, select_best, language_priority)
            unique_nodes.append(best)

            # Інші - дублікати
            for node in group_nodes:
                if node.node_id != best.node_id:
                    removed_nodes.append(node)

        # Видаляємо дублікати якщо потрібно
        removed_count = 0
        if remove_duplicates:
            for node in removed_nodes:
                if self.remove_node(node.node_id):
                    removed_count += 1

        # Статистика
        duplicate_groups = [g for g in groups.values() if len(g) > 1]

        stats = {
            "total_nodes": len(self._nodes) + removed_count,
            "unique_base_urls": len(groups),
            "duplicate_groups": len(duplicate_groups),
            "total_duplicates": len(removed_nodes),
            "removed": removed_count,
            "largest_group": max((len(g) for g in groups.values()), default=0),
        }

        if removed_count > 0:
            logger.info(
                f"Canonical dedup: removed {removed_count} duplicates, "
                f"{len(unique_nodes)} unique nodes remain"
            )

        return {
            "groups": groups,
            "unique_nodes": unique_nodes,
            "removed_count": removed_count,
            "stats": stats,
        }

    def _select_best_node(
        self, nodes: List[Node], strategy: str, language_priority: Optional[List[str]] = None
    ) -> Node:
        """
        Вибирає найкращу ноду з групи дублікатів.

        Args:
            nodes: Список нод-дублікатів
            strategy: Стратегія вибору
            language_priority: Пріоритет мов

        Returns:
            Найкраща нода
        """
        import re

        if strategy == "canonical":
            # Шукаємо self-referencing canonical
            for node in nodes:
                canonical = node.metadata.get("canonical_url") or node.get_canonical_url()
                if canonical and canonical == node.url:
                    return node
            # Fallback - перша просканована
            for node in nodes:
                if node.scanned:
                    return node
            return nodes[0]

        elif strategy == "language" and language_priority:
            # Вибираємо за пріоритетом мов
            for lang in language_priority:
                pattern = rf"[/\-_]{lang}[/\-_]|^/{lang}/|/{lang}$"
                for node in nodes:
                    if re.search(pattern, node.url, re.IGNORECASE):
                        return node
            return nodes[0]

        elif strategy == "scanned":
            for node in nodes:
                if node.scanned:
                    return node
            return nodes[0]

        else:  # 'first' or default
            return nodes[0]

    def get_language_versions(self, node: Node) -> List[Node]:
        """
        Знаходить всі мовні версії сторінки.

        Шукає ноди з однаковим URL path але різними мовними префіксами.

        Args:
            node: Нода для пошуку версій

        Returns:
            Список нод - мовних версій (включаючи оригінальну)

        Example:
            >>> node = graph.get_node_by_url("https://example.com/en/jobs")
            >>> versions = graph.get_language_versions(node)
            >>> for v in versions:
            ...     print(v.url)  # /en/jobs, /pl/jobs, /de/jobs
        """
        import re
        from urllib.parse import urlparse

        parsed = urlparse(node.url)
        path = parsed.path

        # Видаляємо мовний prefix
        base_path = re.sub(r"^/[a-z]{2}(-[a-z]{2})?/", "/", path)
        base_path = re.sub(r"^/[a-z]{2}(-[a-z]{2})?$", "", base_path)

        versions = []
        # Використовуємо iter_nodes() для streaming доступу
        for n in self.iter_nodes():
            n_parsed = urlparse(n.url)
            if n_parsed.netloc != parsed.netloc:
                continue

            n_path = n_parsed.path
            n_base = re.sub(r"^/[a-z]{2}(-[a-z]{2})?/", "/", n_path)
            n_base = re.sub(r"^/[a-z]{2}(-[a-z]{2})?$", "", n_base)

            if n_base == base_path or n_base == base_path.rstrip("/"):
                versions.append(n)

        return versions

    def filter(self, predicate: callable) -> List[Node]:
        """
        Фільтрує ноди за умовою (predicate).

        Args:
            predicate: Функція (node) -> bool

        Returns:
            Список нод що відповідають умові

        Example:
            >>> # Всі просканані ноди
            >>> scanned = graph.filter(lambda n: n.scanned)
            >>>
            >>> # Ноди з JobPosting схемою
            >>> jobs = graph.filter(lambda n: n.user_data.get('structured_data', {}).has_type('JobPosting'))
        """
        # Використовуємо iter_nodes() для streaming доступу
        return [node for node in self.iter_nodes() if predicate(node)]

    def remove_where(self, predicate: callable) -> int:
        """
        Видаляє ноди що відповідають умові.

        Args:
            predicate: Функція (node) -> bool. Ноди де True будуть видалені.
        Returns:
            Кількість видалених нод
        Example:
            >>> # Видалити всі blog posts
            >>> removed = graph.remove_where(
            ...     lambda n: 'BlogPosting' in (n.user_data.get('structured_data', {}).all_types or set())
            ... )
            >>> print(f"Removed {removed} blog posts")
            >>>
            >>> # Видалити непросканані ноди
            >>> removed = graph.remove_where(lambda n: not n.scanned)
        """
        # Використовуємо iter_nodes() для streaming доступу
        nodes_to_remove = [node for node in self.iter_nodes() if predicate(node)]

        for node in nodes_to_remove:
            self.remove_node(node.node_id)

        if nodes_to_remove:
            logger.info("Batch removed %d nodes", len(nodes_to_remove))

        return len(nodes_to_remove)

    def update_where(
        self, predicate: callable, updates: Dict[str, Any] = None, update_fn: callable = None
    ) -> int:
        """
        Оновлює ноди що відповідають умові.

        Args:
            predicate: Функція (node) -> bool. Ноди де True будуть оновлені.
            updates: Словник {field: value} для оновлення
            update_fn: Функція (node) -> None для кастомного оновлення
        Returns:
            Кількість оновлених нод
        """
        if updates is None and update_fn is None:
            raise ValueError("Either 'updates' dict or 'update_fn' must be provided")

        count = 0
        # Використовуємо iter_nodes() для streaming доступу
        for node in self.iter_nodes():
            if predicate(node):
                if updates:
                    for field, value in updates.items():
                        if hasattr(node, field):
                            setattr(node, field, value)
                        else:
                            node.user_data[field] = value

                if update_fn:
                    update_fn(node)

                count += 1

        if count > 0:
            logger.info("Batch updated %d nodes", count)

        return count

    def count_where(self, predicate: callable) -> int:
        """
        Підраховує ноди що відповідають умові.

        Args:
            predicate: Функція (node) -> bool

        Returns:
            Кількість нод

        Example:
            >>> # Кількість JobPosting сторінок
            >>> job_count = graph.count_where(
            ...     lambda n: n.user_data.get('structured_data', {}).has_type('JobPosting')
            ... )
        """
        # Використовуємо iter_nodes() для streaming доступу
        return sum(1 for node in self.iter_nodes() if predicate(node))

    def query_cascade(
        self,
        predicates: List[callable],
        min_matches: int = 1,
        stop_at_first: bool = True,
    ) -> "CascadeResult":
        """
        Каскадний запит нод з fallback логікою.

        Args:
            predicates: Список predicate функцій в порядку пріоритету.
                        Перший predicate - найнадійніший, останній - fallback.
            min_matches: Мінімальна кількість нод на рівні для зупинки.
                        Якщо менше - продовжуємо до наступного рівня.
            stop_at_first: Зупинитись на першому непустому рівні (True)
                          або зібрати всі унікальні ноди з усіх рівнів (False)
        Returns:
            CascadeResult з нодами та інформацією про рівень
        """

        all_nodes: List[Node] = []
        matched_node_ids: Set[str] = set()
        result_level = -1
        levels_tried = 0

        for level, predicate in enumerate(predicates):
            levels_tried += 1
            level_nodes = []
            # Використовуємо iter_nodes() для streaming доступу
            for node in self.iter_nodes():
                if node.node_id not in matched_node_ids:
                    try:
                        if predicate(node):
                            level_nodes.append(node)
                            if not stop_at_first:
                                matched_node_ids.add(node.node_id)
                    except Exception as e:
                        logger.warning("Predicate error at level %d for %s: %s", level, node.url, e)
                        continue

            if level_nodes:
                if stop_at_first and len(level_nodes) >= min_matches:
                    # Зупиняємось на цьому рівні
                    return CascadeResult(
                        nodes=level_nodes,
                        level=level,
                        levels_tried=levels_tried,
                        total_predicates=len(predicates),
                    )
                elif not stop_at_first:
                    all_nodes.extend(level_nodes)
                    if result_level == -1:
                        result_level = level
        # повертаємо останній непустий рівень або пустий результат
        if stop_at_first:
            # Шукаємо останній непустий рівень
            for level, predicate in enumerate(predicates):
                level_nodes = []
                # Використовуємо iter_nodes() для streaming доступу
                for node in self.iter_nodes():
                    try:
                        if predicate(node):
                            level_nodes.append(node)
                    except Exception as e:
                        logger.warning("Predicate error at level %d for %s: %s", level, node.url, e)
                        continue
                if level_nodes:
                    return CascadeResult(
                        nodes=level_nodes,
                        level=level,
                        levels_tried=len(predicates),
                        total_predicates=len(predicates),
                    )

            return CascadeResult(
                nodes=[],
                level=-1,
                levels_tried=len(predicates),
                total_predicates=len(predicates),
            )

        return CascadeResult(
            nodes=all_nodes,
            level=result_level,
            levels_tried=levels_tried,
            total_predicates=len(predicates),
        )


class CascadeResult:
    """
    Результат каскадного запиту.

    Атрибути:
        nodes: Список знайдених нод
        level: Рівень на якому знайдено (0 = найвищий пріоритет, -1 = не знайдено)
        levels_tried: Кількість перевірених рівнів
        total_predicates: Загальна кількість predicates
    """

    def __init__(
        self,
        nodes: List[Node],
        level: int,
        levels_tried: int,
        total_predicates: int,
    ):
        self.nodes = nodes
        self.level = level
        self.levels_tried = levels_tried
        self.total_predicates = total_predicates

    @property
    def count(self) -> int:
        """Кількість знайдених нод."""
        return len(self.nodes)

    @property
    def found(self) -> bool:
        """Чи знайдено хоч одну ноду."""
        return len(self.nodes) > 0

    @property
    def is_primary_level(self) -> bool:
        """Чи знайдено на найвищому рівні (level 0)."""
        return self.level == 0

    @property
    def is_fallback(self) -> bool:
        """Чи використано fallback рівень (не перший)."""
        return self.level > 0

    def __len__(self) -> int:
        return len(self.nodes)

    def __iter__(self):
        return iter(self.nodes)

    def __repr__(self) -> str:
        return (
            f"CascadeResult(count={self.count}, level={self.level}, "
            f"levels_tried={self.levels_tried}/{self.total_predicates})"
        )


# Ці методи додаються окремо для зручності фільтрації по JSON-LD схемах


def _add_schema_filter_methods():
    """Додає методи фільтрації по JSON-LD схемах до класу Graph."""

    def filter_by_schema(
        self,
        include: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
        fallback: str = "keep",
    ) -> List["Node"]:
        """
        Фільтрує ноди за JSON-LD schema типами.

        Args:
            include: Список schema типів для включення (OR логіка).
                    Якщо вказано - повертає тільки ноди з цими типами.
            exclude: Список schema типів для виключення.
                    Ноди з цими типами будуть видалені з результату.
            fallback: Що робити з нодами без schema:
                    - 'keep': залишити в результаті (default)
                    - 'remove': видалити з результату
        Returns:
            Список нод що відповідають критеріям
        """
        results = []
        # Використовуємо iter_nodes() для streaming доступу
        for node in self.iter_nodes():
            sd = node.user_data.get("structured_data")
            if sd is None or not hasattr(sd, "all_types"):
                # (вони не можуть мати вказаний тип)
                if include:
                    continue
                # Інакше - дивимось на fallback
                if fallback == "keep":
                    results.append(node)
                continue

            node_types = sd.all_types or set()

            # Перевірка include
            if include:
                has_include = any(t in node_types for t in include)
                if not has_include:
                    continue

            # Перевірка exclude
            if exclude:
                has_exclude = any(t in node_types for t in exclude)
                if has_exclude:
                    continue

            results.append(node)

        return results

    def get_nodes_by_schema(self, schema_type: str) -> List["Node"]:
        """
        Повертає всі ноди з вказаним schema типом.

        Shortcut для filter_by_schema(include=[schema_type]).

        Args:
            schema_type: Schema.org тип (наприклад 'JobPosting', 'Product')

        Returns:
            Список нод з цим типом

        Example:
            >>> jobs = graph.get_nodes_by_schema('JobPosting')
            >>> products = graph.get_nodes_by_schema('Product')
        """
        return self.filter_by_schema(include=[schema_type])

    def get_schema_stats(self) -> Dict[str, int]:
        """
        Повертає статистику schema типів у графі.

        Returns:
            Словник {schema_type: count}

        Example:
            >>> stats = graph.get_schema_stats()
            >>> print(f"JobPosting: {stats.get('JobPosting', 0)}")
            >>> print(f"BlogPosting: {stats.get('BlogPosting', 0)}")
        """
        from collections import Counter

        type_counter = Counter()
        # Використовуємо iter_nodes() для streaming доступу
        for node in self.iter_nodes():
            sd = node.user_data.get("structured_data")
            if sd and hasattr(sd, "all_types") and sd.all_types:
                for schema_type in sd.all_types:
                    type_counter[schema_type] += 1

        return dict(type_counter)

    def has_schema_type(self, schema_type: str) -> bool:
        """
        Перевіряє чи є в графі хоча б одна нода з вказаним schema типом.

        Args:
            schema_type: Schema.org тип

        Returns:
            True якщо є хоча б одна нода
        """
        # Використовуємо iter_nodes() для streaming доступу
        for node in self.iter_nodes():
            sd = node.user_data.get("structured_data")
            if sd and hasattr(sd, "has_type") and sd.has_type(schema_type):
                return True
        return False

    # Додаємо методи до класу Graph
    Graph.filter_by_schema = filter_by_schema
    Graph.get_nodes_by_schema = get_nodes_by_schema
    Graph.get_schema_stats = get_schema_stats
    Graph.has_schema_type = has_schema_type


# Виконуємо при імпорті модуля
_add_schema_filter_methods()
