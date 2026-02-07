"""Repository Pattern для unified interface для storage."""

from typing import Any, Dict, List, Optional

from graph_crawler.domain.entities.edge import Edge
from graph_crawler.domain.entities.graph import Graph
from graph_crawler.domain.entities.node import Node
from graph_crawler.infrastructure.persistence.base import BaseStorage


class StorageRepository:
    """
    Repository Pattern для абстракції роботи зі storage.

    Переваги:
    - Відокремлює бізнес-логіку від storage
    - Unified interface для всіх типів storage
    - Легко переключати storage (Memory → JSON → SQLite)
    - Краще тестування (mock storage)

    Приклад:
        storage = JSONStorage()
        repo = StorageRepository(storage)

        repo.save_graph(graph)
        loaded_graph = repo.load_graph()

        # Переключення storage
        repo.set_storage(SQLiteStorage())
    """

    def __init__(self, storage: BaseStorage):
        """
        Ініціалізує repository зі storage.

        Args:
            storage: Екземпляр BaseStorage
        """
        self._storage = storage

    def set_storage(self, storage: BaseStorage):
        """Змінює storage (Strategy Pattern)."""
        self._storage = storage

    def save_graph(self, graph: Graph) -> bool:
        """
        Зберігає граф у storage.

        Args:
            graph: Граф для збереження

        Returns:
            True якщо успішно

        docs: Реалізувати:
        - Виклик self._storage.save_graph(graph)
        - Обробку помилок
        - Логування
        """
        return self._storage.save_graph(graph)

    def load_graph(self) -> Optional[Graph]:
        """
        Завантажує граф зі storage.

        Returns:
            Граф або None

        docs: Реалізувати:
        - Виклик self._storage.load_graph()
        - Обробку помилок
        - Валідацію даних
        """
        return self._storage.load_graph()

    def save_partial(self, nodes: List[Node] = None, edges: List[Edge] = None) -> bool:
        """
        Інкрементальне збереження.

        Важливо для великих сайтів - зберігаємо поетапно.

        Args:
            nodes: Список вузлів для збереження
            edges: Список ребер для збереження

        Returns:
            True якщо успішно
        """
        nodes_dict = [node.to_dict() for node in nodes] if nodes else []
        edges_dict = [edge.to_dict() for edge in edges] if edges else []
        return self._storage.save_partial(nodes_dict, edges_dict)

    def clear(self) -> bool:
        """Очищує storage."""
        return self._storage.clear()

    def exists(self) -> bool:
        """Перевіряє чи існує збережений граф."""
        return self._storage.exists()

    def get_node_by_id(self, node_id: str) -> Optional[Node]:
        """
        Отримує вузол за ID зі storage.

        docs: Реалізувати запит до storage
        """
        pass

    def get_node_by_url(self, url: str) -> Optional[Node]:
        """
        Отримує вузол за URL зі storage.

        docs: Реалізувати запит до storage
        """
        pass

    def get_stats(self) -> Dict[str, Any]:
        """
        Повертає статистику storage.

        Returns:
            Словник зі статистикою

        docs: Реалізувати збір статистики
        """
        return {
            "storage_type": type(self._storage).__name__,
            "exists": self.exists(),
        }
