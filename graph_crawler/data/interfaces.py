"""
IGraphBackend - Core Interface для Data Layer.

Визначає контракт для всіх backend імплементацій (Memory, SQLite, PostgreSQL, MongoDB).
Це Single Source of Truth для зберігання нод та ребер графу.

Принципи проектування:
1. Async First - всі основні методи async, sync через _sync suffix
2. Streaming - iter_* методи для роботи з великими даними
3. Batch Operations - *_batch методи для ефективності
4. Pluggable - легко додати новий backend

Usage:
    >>> class MyBackend(IGraphBackend):
    ...     async def insert_node(self, node: Node) -> None:
    ...         # implementation
    ...         pass
"""

from abc import abstractmethod
from typing import (
    Any,
    AsyncIterator,
    Dict,
    Iterator,
    List,
    Optional,
    Protocol,
    Set,
    Tuple,
    runtime_checkable,
)

# Forward references для уникнення circular imports
# Реальні типи будуть перевірені при використанні
NodeType = Any  # graph_crawler.domain.entities.node.Node
EdgeType = Any  # graph_crawler.domain.entities.edge.Edge


@runtime_checkable
class IGraphBackend(Protocol):
    """
    Core Interface для Graph Data Storage.

    """

    # ═══════════════════════════════════════════════════════════════════════════
    # LIFECYCLE METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    @abstractmethod
    async def open(self) -> None:
        """
        Відкриває з'єднання з backend (БД, файл, тощо).

        Викликається один раз при створенні Graph.
        Для MemoryBackend - no-op.

        Raises:
            ConnectionError: Якщо не вдалося підключитися
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """
        Закриває з'єднання з backend.

        Викликається при завершенні роботи з Graph.
        Звільняє ресурси (connections, file handles).

        Note:
            Після close() backend не можна використовувати без повторного open().
        """
        ...

    @abstractmethod
    async def transaction(self) -> Any:
        """
        Context manager для транзакцій.

        Гарантує atomicity для batch операцій.

        Example:
            >>> async with backend.transaction():
            ...     await backend.insert_node(node1)
            ...     await backend.insert_node(node2)
            ...     # commit при виході, rollback при exception

        Returns:
            Context manager для транзакції
        """
        ...

    @abstractmethod
    async def checkpoint(self) -> None:
        """
        Примусовий flush даних на диск.

        Для SQLite: PRAGMA wal_checkpoint
        Для PostgreSQL: CHECKPOINT
        Для Memory: no-op

        Використовується для гарантії durability при довгих операціях.
        """
        ...

    # ═══════════════════════════════════════════════════════════════════════════
    # NODE OPERATIONS - ASYNC
    # ═══════════════════════════════════════════════════════════════════════════

    @abstractmethod
    async def insert_node(self, node: NodeType) -> NodeType:
        """
        Додає ноду до backend.

        URL автоматично нормалізується.
        Якщо нода з таким URL існує - повертає існуючу (без перезапису).

        Args:
            node: Node для додавання

        Returns:
            Додана нода (або існуюча якщо URL вже є)
        """
        ...

    @abstractmethod
    async def insert_node_overwrite(self, node: NodeType) -> NodeType:
        """
        Додає або перезаписує ноду.

        Args:
            node: Node для додавання/перезапису

        Returns:
            Додана нода
        """
        ...

    @abstractmethod
    async def insert_nodes_batch(self, nodes: List[NodeType]) -> int:
        """
        Batch insert нод (оптимізовано для великих обсягів).

        Args:
            nodes: Список нод для додавання

        Returns:
            Кількість успішно доданих нод
        """
        ...

    @abstractmethod
    async def get_node_by_url(self, url: str) -> Optional[NodeType]:
        """
        Отримує ноду за URL.

        URL автоматично нормалізується перед пошуком.

        Args:
            url: URL для пошуку

        Returns:
            Node або None якщо не знайдено
        """
        ...

    @abstractmethod
    async def get_node_by_id(self, node_id: str) -> Optional[NodeType]:
        """
        Отримує ноду за node_id.

        Args:
            node_id: ID ноди

        Returns:
            Node або None якщо не знайдено
        """
        ...

    @abstractmethod
    async def get_nodes_batch(self, urls: List[str]) -> Dict[str, NodeType]:
        """
        Batch отримання нод за URLs.

        Args:
            urls: Список URLs

        Returns:
            Dict[url, Node] для знайдених нод
        """
        ...

    @abstractmethod
    async def update_node(self, node: NodeType) -> bool:
        """
        Оновлює існуючу ноду.

        Args:
            node: Node з оновленими даними (шукає за node_id)

        Returns:
            True якщо ноду оновлено, False якщо не знайдено
        """
        ...

    @abstractmethod
    async def delete_node(self, node_id: str) -> bool:
        """
        Видаляє ноду та пов'язані ребра.

        Args:
            node_id: ID ноди для видалення

        Returns:
            True якщо ноду видалено, False якщо не знайдено
        """
        ...

    @abstractmethod
    async def url_exists(self, url: str) -> bool:
        """
        Перевіряє чи URL існує в backend.

        Оптимізовано для швидкої перевірки (не завантажує всю ноду).

        Args:
            url: URL для перевірки

        Returns:
            True якщо URL існує
        """
        ...

    @abstractmethod
    async def urls_exist_batch(self, urls: List[str]) -> Set[str]:
        """
        Batch перевірка існування URLs.

        Args:
            urls: Список URLs для перевірки

        Returns:
            Set URLs що існують
        """
        ...

    # ═══════════════════════════════════════════════════════════════════════════
    # EDGE OPERATIONS - ASYNC
    # ═══════════════════════════════════════════════════════════════════════════

    @abstractmethod
    async def insert_edge(self, edge: EdgeType) -> EdgeType:
        """
        Додає ребро до backend.

        Args:
            edge: Edge для додавання

        Returns:
            Додане ребро
        """
        ...

    @abstractmethod
    async def insert_edges_batch(self, edges: List[EdgeType]) -> int:
        """
        Batch insert ребер.

        Args:
            edges: Список ребер

        Returns:
            Кількість доданих ребер
        """
        ...

    @abstractmethod
    async def get_edges_from(self, source_node_id: str) -> List[EdgeType]:
        """
        Отримує всі ребра ВІД ноди (outgoing).

        Args:
            source_node_id: ID source ноди

        Returns:
            Список outgoing ребер
        """
        ...

    @abstractmethod
    async def get_edges_to(self, target_node_id: str) -> List[EdgeType]:
        """
        Отримує всі ребра ДО ноди (incoming).

        Args:
            target_node_id: ID target ноди

        Returns:
            Список incoming ребер
        """
        ...

    @abstractmethod
    async def edge_exists(self, source_node_id: str, target_node_id: str) -> bool:
        """
        Перевіряє чи існує ребро між нодами.

        Args:
            source_node_id: ID source ноди
            target_node_id: ID target ноди

        Returns:
            True якщо ребро існує
        """
        ...

    @abstractmethod
    async def delete_edges_for_node(self, node_id: str) -> int:
        """
        Видаляє всі ребра пов'язані з нодою.

        Args:
            node_id: ID ноди

        Returns:
            Кількість видалених ребер
        """
        ...

    # ═══════════════════════════════════════════════════════════════════════════
    # QUERY OPERATIONS - ASYNC
    # ═══════════════════════════════════════════════════════════════════════════

    @abstractmethod
    async def count_nodes(self) -> int:
        """
        Повертає загальну кількість нод.

        Returns:
            Кількість нод в backend
        """
        ...

    @abstractmethod
    async def count_edges(self) -> int:
        """
        Повертає загальну кількість ребер.

        Returns:
            Кількість ребер в backend
        """
        ...

    @abstractmethod
    async def count_nodes_by_status(self, scanned: bool) -> int:
        """
        Повертає кількість нод за статусом scanned.

        Args:
            scanned: True для scanned нод, False для unscanned

        Returns:
            Кількість нод з даним статусом
        """
        ...

    @abstractmethod
    async def get_stats(self) -> Dict[str, Any]:
        """
        Повертає статистику backend.

        Returns:
            Dict зі статистикою:
            - total_nodes: int
            - total_edges: int
            - scanned_nodes: int
            - unscanned_nodes: int
            - memory_usage_mb: float (якщо застосовно)
            - db_size_mb: float (якщо застосовно)
        """
        ...

    # ═══════════════════════════════════════════════════════════════════════════
    # STREAMING OPERATIONS - ASYNC ITERATORS
    # ═══════════════════════════════════════════════════════════════════════════

    @abstractmethod
    def iter_nodes(self, batch_size: int = 1000) -> AsyncIterator[NodeType]:
        """
        Streaming ітератор по всіх нодах.

        НЕ завантажує все в RAM - читає batch_size нод за раз.

        Args:
            batch_size: Розмір batch для читання

        Yields:
            Node objects

        Example:
            >>> async for node in backend.iter_nodes(batch_size=1000):
            ...     process(node)
        """
        ...

    @abstractmethod
    def iter_edges(self, batch_size: int = 1000) -> AsyncIterator[EdgeType]:
        """
        Streaming ітератор по всіх ребрах.

        Args:
            batch_size: Розмір batch для читання

        Yields:
            Edge objects
        """
        ...

    @abstractmethod
    def iter_unscanned_nodes(self, batch_size: int = 100) -> AsyncIterator[NodeType]:
        """
        Streaming ітератор по unscanned нодах.

        Для scheduler - отримання наступних URLs для сканування.

        Args:
            batch_size: Розмір batch

        Yields:
            Unscanned Node objects
        """
        ...

    @abstractmethod
    def iter_nodes_at_depth(self, depth: int, batch_size: int = 1000) -> AsyncIterator[NodeType]:
        """
        Streaming ітератор по нодах на певній глибині.

        Args:
            depth: Глибина для фільтрації
            batch_size: Розмір batch

        Yields:
            Node objects з depth == depth
        """
        ...

    # ═══════════════════════════════════════════════════════════════════════════
    # SYNC WRAPPERS (для backward compatibility)
    # ═══════════════════════════════════════════════════════════════════════════

    def insert_node_sync(self, node: NodeType) -> NodeType:
        """Sync wrapper для insert_node()."""
        import asyncio

        return asyncio.get_event_loop().run_until_complete(self.insert_node(node))

    def get_node_by_url_sync(self, url: str) -> Optional[NodeType]:
        """Sync wrapper для get_node_by_url()."""
        import asyncio

        return asyncio.get_event_loop().run_until_complete(self.get_node_by_url(url))

    def get_node_by_id_sync(self, node_id: str) -> Optional[NodeType]:
        """Sync wrapper для get_node_by_id()."""
        import asyncio

        return asyncio.get_event_loop().run_until_complete(self.get_node_by_id(node_id))

    def url_exists_sync(self, url: str) -> bool:
        """Sync wrapper для url_exists()."""
        import asyncio

        return asyncio.get_event_loop().run_until_complete(self.url_exists(url))

    def count_nodes_sync(self) -> int:
        """Sync wrapper для count_nodes()."""
        import asyncio

        return asyncio.get_event_loop().run_until_complete(self.count_nodes())

    def count_edges_sync(self) -> int:
        """Sync wrapper для count_edges()."""
        import asyncio

        return asyncio.get_event_loop().run_until_complete(self.count_edges())

    def iter_nodes_sync(self, batch_size: int = 1000) -> Iterator[NodeType]:
        """
        Sync streaming ітератор по нодах.

        Args:
            batch_size: Розмір batch

        Yields:
            Node objects
        """
        import asyncio

        async def _collect():
            result = []
            async for node in self.iter_nodes(batch_size):
                result.append(node)
            return result

        nodes = asyncio.get_event_loop().run_until_complete(_collect())
        yield from nodes


@runtime_checkable
class IQueueStorage(Protocol):
    """
    Interface для Queue Storage (Scheduler).

    Окремий інтерфейс для черги сканування.
    Може бути частиною IGraphBackend або окремим storage.

    Methods:
        push_urls: Додати URLs до черги
        pop_urls: Отримати та видалити URLs з черги
        url_in_queue: Перевірити чи URL в черзі
        queue_size: Розмір черги
    """

    @abstractmethod
    async def push_urls(self, urls: List[Tuple[str, int, int]]) -> int:
        """
        Додає URLs до черги.

        Args:
            urls: Список (url, depth, priority) tuples

        Returns:
            Кількість доданих URLs
        """
        ...

    @abstractmethod
    async def pop_urls(self, limit: int = 100) -> List[Tuple[str, int]]:
        """
        Отримує та видаляє URLs з черги (за пріоритетом).

        Args:
            limit: Максимальна кількість URLs

        Returns:
            Список (url, depth) tuples
        """
        ...

    @abstractmethod
    async def url_in_queue(self, url: str) -> bool:
        """
        Перевіряє чи URL в черзі.

        Args:
            url: URL для перевірки

        Returns:
            True якщо URL в черзі
        """
        ...

    @abstractmethod
    async def queue_size(self) -> int:
        """
        Повертає розмір черги.

        Returns:
            Кількість URLs в черзі
        """
        ...

    @abstractmethod
    async def clear_queue(self) -> None:
        """Очищує чергу."""
        ...


# Type aliases для зручності
BackendType = IGraphBackend
QueueType = IQueueStorage
