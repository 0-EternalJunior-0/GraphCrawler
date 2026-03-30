"""GraphStatistics - статистика та аналіз графів (SRP: аналітика винесена окремо)."""

from typing import TYPE_CHECKING, Dict, List

if TYPE_CHECKING:
    from graph_crawler.domain.entities.graph import Graph
    from graph_crawler.domain.entities.node import Node


class GraphStatistics:
    """
    Static методи для аналізу та статистики графів.

    """

    @staticmethod
    def get_stats(graph: "Graph") -> Dict[str, int]:
        """
        Повертає статистику графу.

        Args:
            graph: Граф для аналізу
        Returns:
            Словник зі статистикою:
            - total_nodes: загальна кількість вузлів (RAM only, без evicted)
            - scanned_nodes: кількість просканованих вузлів в RAM
            - unscanned_nodes: кількість непросканованих вузлів в RAM
            - total_edges: кількість ребер
        """
        # Крок 32: Backend-compatible - використовуємо iter_nodes() та nodes property
        scanned = sum(1 for node in graph.iter_nodes() if node.scanned)
        total_nodes = len(graph.nodes)
        return {
            "total_nodes": total_nodes,
            "scanned_nodes": scanned,
            "unscanned_nodes": total_nodes - scanned,
            "total_edges": len(graph.edges),
        }

    @staticmethod
    def get_degree(graph: "Graph", node_id: str) -> int:
        """
        Повертає ступінь вузла (кількість інцидентних ребер).

        Args:
            graph: Граф
            node_id: ID вузла

        Returns:
            Ступінь вузла (in_degree + out_degree)
        """
        in_degree = GraphStatistics.get_in_degree(graph, node_id)
        out_degree = GraphStatistics.get_out_degree(graph, node_id)
        return in_degree + out_degree

    @staticmethod
    def get_in_degree(graph: "Graph", node_id: str) -> int:
        """
                Повертає вхідний ступінь вузла.

        O(1) замість O(E) використовуючи adjacency list.

                Args:
                    graph: Граф
                    node_id: ID вузла

                Returns:
                    Кількість вхідних ребер
        """
        # O(1) lookup замість O(E) ітерації
        return len(graph._adjacency_list_in.get(node_id, set()))

    @staticmethod
    def get_out_degree(graph: "Graph", node_id: str) -> int:
        """
                Повертає вихідний ступінь вузла.

        O(1) замість O(E) використовуючи adjacency list.

                Args:
                    graph: Граф
                    node_id: ID вузла

                Returns:
                    Кількість вихідних ребер
        """
        # O(1) lookup замість O(E) ітерації
        return len(graph._adjacency_list_out.get(node_id, set()))

    @staticmethod
    def get_neighbors(graph: "Graph", node_id: str) -> List["Node"]:
        """
                Повертає всіх сусідів вузла.

        O(1) замість O(E) використовуючи adjacency lists.
                Прискорення: 1000-10000x для великих графів!

                Args:
                    graph: Граф
                    node_id: ID вузла

                Returns:
                    Список сусідніх вузлів
        """
        # O(1) lookup замість O(E) ітерації через всі edges!
        # Об'єднуємо вхідних та вихідних сусідів
        neighbor_ids = graph._adjacency_list_out.get(node_id, set()) | graph._adjacency_list_in.get(
            node_id, set()
        )

        # Крок 32: Backend-compatible - використовуємо nodes property
        return [graph.nodes[nid] for nid in neighbor_ids if nid in graph.nodes]

    @staticmethod
    def is_connected(graph: "Graph") -> bool:
        """
        Перевіряє чи є граф зв'язаним.

        Граф зв'язаний якщо існує шлях між будь-якими двома вузлами.
        Використовує BFS алгоритм. Оптимізовано - deque.popleft() O(1) замість list.pop(0) O(n)

        Args:
            graph: Граф для перевірки

        Returns:
            True якщо граф зв'язаний
        """
        # Крок 32: Backend-compatible - використовуємо nodes property
        if not graph.nodes:
            return True

        # BFS для перевірки зв'язності
        from collections import deque

        visited = set()
        # Крок 32: Backend-compatible - використовуємо iter_nodes() для отримання першого node_id
        first_node = next(graph.iter_nodes(), None)
        if first_node is None:
            return True
        queue = deque([first_node.node_id])  # Почати з першого вузла

        while queue:
            node_id = queue.popleft()  # O(1) замість O(n)!
            if node_id in visited:
                continue
            visited.add(node_id)

            # Додати всіх сусідів (використовуємо adjacency list - O(1))
            neighbor_ids = graph._adjacency_list_out.get(
                node_id, set()
            ) | graph._adjacency_list_in.get(node_id, set())
            queue.extend(nid for nid in neighbor_ids if nid not in visited)

        return len(visited) == len(graph.nodes)

    @staticmethod
    def get_nodes_by_depth(graph: "Graph", depth: int) -> List["Node"]:
        """
        Повертає всі вузли на певній глибині.

        Args:
            graph: Граф
            depth: Глибина для пошуку

        Returns:
            Список вузлів на заданій глибині
        """
        # Крок 32: Backend-compatible - використовуємо iter_nodes()
        return [node for node in graph.iter_nodes() if node.depth == depth]

    @staticmethod
    def get_unscanned_nodes(graph: "Graph") -> List["Node"]:
        """
        Повертає список непросканованих вузлів.

        Args:
            graph: Граф

        Returns:
            Список вузлів зі scanned=False
        """
        # Крок 32: Backend-compatible - використовуємо iter_nodes()
        return [node for node in graph.iter_nodes() if not node.scanned]
