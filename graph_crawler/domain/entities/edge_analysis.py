"""
Edge Analysis - методи для аналізу edges та графу.

Модуль надає функціонал для аналізу edges та структури графу:
- Популярні nodes (топ за incoming edges)
- Статистика edges по типах
- Виявлення циклів в графі
- Фільтрація edges по типах
"""

import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class EdgeAnalysis:
    """
    Статичні методи для аналізу edges та структури графу.

    Відповідальність: аналіз edges, пошук популярних nodes, виявлення циклів.
    Працює з Graph об'єктом як з абстракцією.

    Методи:
        - get_popular_nodes() - топ N nodes з найбільше incoming edges
        - get_edge_statistics() - детальна статистика edges по типах
        - find_cycles() - виявлення циклів в графі (DFS)
        - get_edges_by_type() - фільтрація edges по типу
    """

    @staticmethod
    def get_popular_nodes(graph, top_n: int = 10, by: str = "in_degree") -> List:
        """
        Повертає топ N найпопулярніших nodes.
        Оптимізовано - heapq.nlargest() O(n log k) замість sort() O(n log n)

        Args:
            graph: Граф для аналізу
            top_n: Кількість топ nodes
            by: Критерій сортування:
                - 'in_degree' (default) - за кількістю incoming edges
                - 'out_degree' - за кількістю outgoing edges
                - 'total_degree' - за загальною кількістю edges

        Returns:
            Список Node об'єктів, відсортованих за критерієм

        Example:
            >>> popular = EdgeAnalysis.get_popular_nodes(graph, top_n=10)
            >>> for node in popular:
            >>>     print(f"{node.url}: {graph.get_in_degree(node.node_id)} incoming")
        """
        import heapq

        if not graph.nodes:
            logger.warning("Graph is empty, no popular nodes")
            return []

        # Вибираємо функцію для обчислення degree
        degree_funcs = {
            "in_degree": graph.get_in_degree,
            "out_degree": graph.get_out_degree,
            "total_degree": graph.get_degree,
        }

        if by not in degree_funcs:
            raise ValueError(
                f"Invalid 'by' parameter: {by}. Use 'in_degree', 'out_degree', or 'total_degree'"
            )

        get_degree = degree_funcs[by]

        # Швидше для top_n << len(nodes) (streaming через iter_nodes)
        node_degrees = ((get_degree(node.node_id), node) for node in graph.iter_nodes())
        popular_nodes = [
            node for _, node in heapq.nlargest(top_n, node_degrees, key=lambda x: x[0])
        ]

        logger.info("Found top %s popular nodes by %s", len(popular_nodes), by)
        return popular_nodes

    @staticmethod
    def get_edge_statistics(graph) -> Dict[str, Any]:
        """
        Повертає детальну статистику edges по типах.

        Args:
            graph: Граф для аналізу
        Returns:
            Словник зі статистикою
        Example:
            >>> stats = EdgeAnalysis.get_edge_statistics(graph)
            >>> print(f"Internal links: {stats['by_type']['internal']}")
            >>> print(f"Average depth diff: {stats['avg_depth_diff']}")
        """
        # Використовуємо len(list(iter_edges())) для streaming-сумісності
        edges_list = list(graph.iter_edges())
        if not edges_list:
            logger.warning("Graph has no edges")
            return {
                "total_edges": 0,
                "by_type": {},
                "avg_depth_diff": 0.0,
                "with_anchor_text": 0,
                "without_anchor_text": 0,
                "to_scanned": 0,
                "to_unscanned": 0,
            }

        # Ініціалізуємо лічильники
        type_counts = defaultdict(int)
        depth_diffs = []
        with_anchor = 0
        without_anchor = 0
        to_scanned = 0
        to_unscanned = 0

        # Використовуємо iter_edges() для streaming доступу
        for edge in graph.iter_edges():
            # Рахуємо типи (edge може мати список типів)
            link_types = edge.get_meta_value("link_type", [])
            if isinstance(link_types, list):
                for link_type in link_types:
                    type_counts[link_type] += 1
            elif isinstance(link_types, str):
                # Якщо одиночний string
                type_counts[link_types] += 1

            # Depth diff
            depth_diff = edge.get_meta_value("depth_diff")
            if depth_diff is not None:
                depth_diffs.append(depth_diff)

            # Anchor text
            anchor_text = edge.get_meta_value("anchor_text")
            if anchor_text:
                with_anchor += 1
            else:
                without_anchor += 1

            # Target node scanned status
            target_node = graph.get_node_by_id(edge.target_node_id)
            if target_node:
                if target_node.scanned:
                    to_scanned += 1
                else:
                    to_unscanned += 1

        # Рахуємо середню різницю глибини
        avg_depth_diff = sum(depth_diffs) / len(depth_diffs) if depth_diffs else 0.0

        stats = {
            "total_edges": len(edges_list),
            "by_type": dict(type_counts),
            "avg_depth_diff": round(avg_depth_diff, 2),
            "with_anchor_text": with_anchor,
            "without_anchor_text": without_anchor,
            "to_scanned": to_scanned,
            "to_unscanned": to_unscanned,
        }

        logger.info("Edge statistics: %s edges, %s types", stats['total_edges'], len(type_counts))
        return stats

    @staticmethod
    def find_cycles(graph, max_cycles: Optional[int] = None) -> List[List[str]]:
        """
        Знаходить цикли в графі використовуючи DFS.

        Універсальний алгоритм для виявлення всіх циклів в орієнтованому графі.
        Використовує DFS з відстеженням стану вузлів (white/gray/black).

        Args:
            graph: Граф для аналізу
            max_cycles: Максимальна кількість циклів для пошуку (None = всі)

        Returns:
            Список циклів, де кожен цикл - список node_id

        Example:
            >>> cycles = EdgeAnalysis.find_cycles(graph, max_cycles=10)
            >>> for cycle in cycles:
            >>>     print(f"Cycle: {' -> '.join(cycle)}")
        """
        # Перевіряємо через len() property (делегує до backend)
        if not graph.nodes:
            logger.info("Graph is empty or has no edges, no cycles")
            return []

        # Перевіряємо edges через iter_edges
        edges_exist = False
        for _ in graph.iter_edges():
            edges_exist = True
            break
        if not edges_exist:
            logger.info("Graph has no edges, no cycles")
            return []

        # Побудова adjacency list
        # Використовуємо iter_edges() для streaming доступу
        adj_list = defaultdict(list)
        for edge in graph.iter_edges():
            adj_list[edge.source_node_id].append(edge.target_node_id)

        # Стани вузлів: white (не відвіданий), gray (в процесі), black (завершений)
        WHITE, GRAY, BLACK = 0, 1, 2
        # Використовуємо iter_nodes() для streaming доступу до node_id
        color = {node.node_id: WHITE for node in graph.iter_nodes()}

        cycles = []
        parent = {}

        def dfs(node_id: str, path: List[str]):
            """DFS з виявленням циклів."""
            nonlocal cycles

            # Перевіряємо ліміт циклів
            if max_cycles and len(cycles) >= max_cycles:
                return

            color[node_id] = GRAY
            path.append(node_id)

            for neighbor in adj_list[node_id]:
                if color[neighbor] == WHITE:
                    # Не відвіданий - продовжуємо DFS
                    parent[neighbor] = node_id
                    dfs(neighbor, path.copy())
                elif color[neighbor] == GRAY:
                    # Знайдено цикл (back edge)
                    # Витягуємо цикл з path
                    cycle_start_idx = path.index(neighbor)
                    cycle = path[cycle_start_idx:] + [neighbor]
                    cycles.append(cycle)

                    logger.debug("Cycle found: %s", ' -> '.join(str(nid) for nid in cycle))

            color[node_id] = BLACK

        # Запускаємо DFS з кожного непройденого вузла
        # Ітеруємо по ключах color замість graph.nodes.keys()
        for node_id in color:
            if color[node_id] == WHITE:
                dfs(node_id, [])

        logger.info("Found %s cycles in graph", len(cycles))
        return cycles

    @staticmethod
    def get_edges_by_type(graph, link_types: List[str], match_mode: str = "any") -> List:
        """
        Фільтрує edges по типу посилання.

        Args:
            graph: Граф для фільтрації
            link_types: Список типів для фільтрації
                (наприклад: ['internal', 'deeper'])
            match_mode: Режим фільтрації:
                - 'any' (default) - edge має хоча б один з типів (OR)
                - 'all' - edge має всі типи (AND)
                - 'exact' - edge має точно ці типи і більше нічого
        Returns:
            Список Edge об'єктів що відповідають критеріям
        Example:
            >>> # Всі internal та deeper edges (OR)
            >>> edges = EdgeAnalysis.get_edges_by_type(
            ...     graph, ['internal', 'deeper'], match_mode='any'
            ... )
            >>>
            >>> # Тільки edges що є і internal І deeper одночасно (AND)
            >>> edges = EdgeAnalysis.get_edges_by_type(
            ...     graph, ['internal', 'deeper'], match_mode='all'
            ... )
        """
        if not link_types:
            logger.warning("No link types provided, returning all edges")
            return list(graph.iter_edges())

        filtered_edges = []

        # Використовуємо iter_edges() для streaming доступу
        for edge in graph.iter_edges():
            edge_types = edge.get_meta_value("link_type", [])

            # Конвертуємо в set для зручності
            if isinstance(edge_types, str):
                edge_types_set = {edge_types}
            elif isinstance(edge_types, list):
                edge_types_set = set(edge_types)
            else:
                edge_types_set = set()

            link_types_set = set(link_types)

            # Перевіряємо згідно match_mode
            if match_mode == "any":
                # OR - хоча б один тип співпадає
                if edge_types_set & link_types_set:
                    filtered_edges.append(edge)
            elif match_mode == "all":
                # AND - всі типи присутні
                if link_types_set.issubset(edge_types_set):
                    filtered_edges.append(edge)
            elif match_mode == "exact":
                # EXACT - точно ці типи
                if edge_types_set == link_types_set:
                    filtered_edges.append(edge)
            else:
                raise ValueError(f"Invalid match_mode: {match_mode}. Use 'any', 'all', or 'exact'")

        # Підраховуємо загальну кількість edges через iter
        total_edges = sum(1 for _ in graph.iter_edges())
        logger.info(
            f"Filtered {len(filtered_edges)}/{total_edges} edges "
            f"by types {link_types} ({match_mode})"
        )
        return filtered_edges
