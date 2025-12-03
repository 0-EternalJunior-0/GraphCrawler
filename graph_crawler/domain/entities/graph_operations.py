"""GraphOperations - операції теорії графів (SRP: складні операції винесено окремо)."""

import logging
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from graph_crawler.domain.entities.graph import Graph
    from graph_crawler.domain.entities.node import Node

logger = logging.getLogger(__name__)


class GraphOperations:
    """
    Static методи для складних операцій з графами.

        Відповідальність: арифметичні операції та операції теорії графів.
        Винесено з класу Graph для дотримання Single Responsibility Principle.

        Операції:
        - union() - об'єднання графів (A + B, A | B)
        - difference() - різниця графів (A - B)
        - intersection() - перетин графів (A & B)
        - symmetric_difference() - симетрична різниця (A ^ B)
        - is_subgraph() - перевірка підграфу (A <= B)
        - is_equal() - перевірка рівності (A == B)

        Приклад:
            >>> from graph_crawler.domain.entities.graph import Graph
            >>> from graph_crawler.domain.entities.graph_operations import GraphOperations
            >>>
            >>> g1 = Graph()
            >>> g2 = Graph()
            >>> g3 = GraphOperations.union(g1, g2)
            >>> g4 = GraphOperations.difference(g1, g2)
    """

    @staticmethod
    def union(
        g1: "Graph",
        g2: "Graph",
        merge_strategy: str = "last",
        custom_merge_fn: Optional[Callable[["Node", "Node"], "Node"]] = None,
    ) -> "Graph":
        """
        Об'єднання двох графів (A + B, A | B) з підтримкою merge strategies.

        Args:
            g1: Перший граф
            g2: Другий граф

        Raises:
            TypeError: Якщо g1 або g2 не є Graph інстансами
        """
        from graph_crawler.domain.entities.graph import Graph

        # Валідація типів
        if not isinstance(g1, Graph):
            raise TypeError(f"g1 must be Graph instance, got {type(g1).__name__}")
        if not isinstance(g2, Graph):
            raise TypeError(f"g2 must be Graph instance, got {type(g2).__name__}")

        """Об'єднання двох графів (A + B, A | B) з підтримкою merge strategies.

        Створює новий граф що містить всі вузли та ребра з обох графів.
        При конфлікті URL (однакові URL в обох графах) - використовується merge_strategy.

        Alpha 2.0 ЗМІНИ:
        - Додано merge_strategy для контролю як об'єднувати конфліктуючі вузли
        - Дефолтна стратегія змінена з 'first' на 'last' (більш інтуїтивно)
        - Повна підтримка інтелектуального merge для збереження всіх даних

        Args:
            g1: Перший граф
            g2: Другий граф
            merge_strategy: Стратегія merge для конфліктів URL
                - 'first': залишити node з g1 (старе)
                - 'last': взяти node з g2 (дефолт, нове)
                - 'merge': інтелектуальне об'єднання (рекомендовано)
                - 'newest': вибрати за найновішим timestamp
                - 'oldest': вибрати за найстарішим timestamp
                - 'custom': використати custom_merge_fn
            custom_merge_fn: Користувацька функція для 'custom' стратегії
                Signature: fn(node1: Node, node2: Node) -> Node

        Returns:
            Новий граф (union)

        Example:
            >>> # Дефолт: взяти новіші дані з g2
            >>> merged = GraphOperations.union(g1, g2)
            >>>
            >>> # Інтелектуальне об'єднання всіх даних
            >>> merged = GraphOperations.union(g1, g2, merge_strategy='merge')
            >>>
            >>> # Користувацька логіка
            >>> def my_merge(n1, n2):
            ...     return n1 if n1.scanned else n2
            >>> merged = GraphOperations.union(g1, g2, merge_strategy='custom',
            ...                                custom_merge_fn=my_merge)
        """
        from graph_crawler.domain.entities.edge import Edge
        from graph_crawler.domain.entities.graph import Graph
        from graph_crawler.domain.entities.merge_strategies import NodeMerger

        logger.debug(
            f"Union: g1={len(g1.nodes)} nodes, g2={len(g2.nodes)} nodes, "
            f"strategy={merge_strategy}"
        )

        # Створюємо merger зі стратегією
        merger = NodeMerger(strategy=merge_strategy, custom_merge_fn=custom_merge_fn)

        result = Graph()

        # Додаємо всі вузли з першого графу
        for node in g1._nodes.values():
            result.add_node(node)

        # НЕ додаємо ребра з g1 зараз - додамо пізніше з правильними node_id
        # (бо node_id можуть змінитись при merge)

        # Мапа для відстеження змін node_id після merge
        # Зберігаємо мапінг для ОБОХ графів: old_node_id -> new_node_id
        node_id_mapping = {}

        # Ініціалізуємо мапінг для g1 (поки що ідентичний)
        for node in g1._nodes.values():
            node_id_mapping[node.node_id] = node.node_id

        # Обробляємо вузли з другого графу
        conflicts_count = 0
        added_count = 0

        for node in g2._nodes.values():
            if node.url in result._url_to_node:
                # Конфлікт: URL вже існує в result
                conflicts_count += 1
                existing_node = result.get_node_by_url(node.url)
                old_existing_id = existing_node.node_id

                # Використовуємо merger для об'єднання
                merged_node = merger.merge(existing_node, node)

                # Якщо node_id змінився - оновлюємо словники
                if merged_node.node_id != old_existing_id:
                    # Видаляємо старий запис
                    del result._nodes[old_existing_id]
                    # Додаємо з новим ID
                    result._nodes[merged_node.node_id] = merged_node
                    result._url_to_node[merged_node.url] = merged_node
                    # Оновлюємо мапінг для старого g1 node_id
                    node_id_mapping[old_existing_id] = merged_node.node_id
                else:
                    # Той самий ID - просто оновлюємо дані
                    result._nodes[merged_node.node_id] = merged_node
                    result._url_to_node[merged_node.url] = merged_node

                # Зберігаємо мапінг: node_id з g2 -> node_id merged
                node_id_mapping[node.node_id] = merged_node.node_id
            else:
                # Немає конфлікту - просто додаємо
                added_count += 1
                result.add_node(node)
                # Мапінг: node залишається з тим же ID
                node_id_mapping[node.node_id] = node.node_id

        # Тепер додаємо ребра з ОБОХ графів з правильними node_id
        result_node_ids = set(result._nodes.keys())
        edges_added = 0
        edges_skipped = 0

        # Ребра з g1 (з оновленими node_id якщо були конфлікти)
        for edge in g1._edges:
            source_id = node_id_mapping.get(edge.source_node_id, edge.source_node_id)
            target_id = node_id_mapping.get(edge.target_node_id, edge.target_node_id)

            if source_id not in result_node_ids or target_id not in result_node_ids:
                edges_skipped += 1
                continue

            if not result.has_edge(source_id, target_id):
                new_edge = Edge(
                    source_node_id=source_id,
                    target_node_id=target_id,
                    metadata=edge.metadata.copy() if edge.metadata else {},
                )
                result.add_edge(new_edge)
                edges_added += 1

        # Ребра з g2
        for edge in g2._edges:
            source_id = node_id_mapping.get(edge.source_node_id, edge.source_node_id)
            target_id = node_id_mapping.get(edge.target_node_id, edge.target_node_id)

            if source_id not in result_node_ids or target_id not in result_node_ids:
                edges_skipped += 1
                continue

            if not result.has_edge(source_id, target_id):
                new_edge = Edge(
                    source_node_id=source_id,
                    target_node_id=target_id,
                    metadata=edge.metadata.copy() if edge.metadata else {},
                )
                result.add_edge(new_edge)
                edges_added += 1

        if edges_skipped > 0:
            logger.debug(f"Union: skipped {edges_skipped} edges with missing nodes")

        logger.info(
            f"Union completed: result={len(result.nodes)} nodes, "
            f"conflicts={conflicts_count}, added={added_count}, "
            f"edges_added={edges_added}"
        )

        return result

    @staticmethod
    def difference(g1: "Graph", g2: "Graph") -> "Graph":
        """
        Різниця двох графів (A - B).

        Створює новий граф що містить вузли з першого графу,
        які відсутні в другому графі (за URL).

        ВАЖЛИВО: Порівняння відбувається за URL, не за node_id!

        Args:
            g1: Перший граф
            g2: Граф для віднімання

        Returns:
            Новий граф (різниця)

        Raises:
            TypeError: Якщо g1 або g2 не є Graph інстансами
        """
        from graph_crawler.domain.entities.graph import Graph

        if not isinstance(g1, Graph):
            raise TypeError(f"g1 must be Graph instance, got {type(g1).__name__}")
        if not isinstance(g2, Graph):
            raise TypeError(f"g2 must be Graph instance, got {type(g2).__name__}")

        result = Graph()
        # Використовуємо url_to_node для O(1) lookup
        other_urls = set(g2._url_to_node.keys())

        # Додаємо тільки вузли з першого графу, яких немає в другому (за URL)
        for node in g1._nodes.values():
            if node.url not in other_urls:
                result.add_node(node)

        # Створюємо set node_id результату для перевірки ребер
        result_node_ids = set(result._nodes.keys())

        # Додаємо ребра де обидва кінці є в результаті
        for edge in g1._edges:
            if (
                edge.source_node_id in result_node_ids
                and edge.target_node_id in result_node_ids
            ):
                result.add_edge(edge)

        logger.debug(
            f"Difference completed: g1={len(g1.nodes)} - g2={len(g2.nodes)} = {len(result.nodes)} nodes, "
            f"{len(result.edges)} edges"
        )

        return result

    @staticmethod
    def intersection(g1: "Graph", g2: "Graph") -> "Graph":
        """
        Перетин двох графів (A & B).

        Створює новий граф що містить тільки спільні вузли (за URL).
        Ребра беруться з обох графів для спільних вузлів.

        ВАЖЛИВО: Порівняння відбувається за URL, не за node_id!
        Вузли з різних графів можуть мати різні node_id для того самого URL.

        Args:
            g1: Перший граф
            g2: Другий граф

        Returns:
            Новий граф (перетин) з ребрами з обох графів

        Raises:
            TypeError: Якщо g1 або g2 не є Graph інстансами
        """
        from graph_crawler.domain.entities.edge import Edge
        from graph_crawler.domain.entities.graph import Graph

        if not isinstance(g1, Graph):
            raise TypeError(f"g1 must be Graph instance, got {type(g1).__name__}")
        if not isinstance(g2, Graph):
            raise TypeError(f"g2 must be Graph instance, got {type(g2).__name__}")

        result = Graph()

        # Використовуємо set intersection для знаходження спільних URL
        g1_urls = set(g1._url_to_node.keys())
        g2_urls = set(g2._url_to_node.keys())
        common_urls = g1_urls & g2_urls  # Set intersection - O(min(len(g1), len(g2)))

        logger.debug(
            f"Intersection: g1={len(g1_urls)} urls, g2={len(g2_urls)} urls, common={len(common_urls)}"
        )

        # Додаємо тільки спільні вузли (беремо з g1)
        for url in common_urls:
            node = g1.get_node_by_url(url)
            if node:
                result.add_node(node)

        # Створюємо мапу URL -> node_id для результату
        # Це потрібно для перетворення ребер з g2 (де node_id інші)
        result_url_to_id = {node.url: node.node_id for node in result._nodes.values()}
        result_node_ids = set(result._nodes.keys())

        # Додаємо ребра з g1 (node_id співпадають)
        edges_from_g1 = 0
        for edge in g1._edges:
            if (
                edge.source_node_id in result_node_ids
                and edge.target_node_id in result_node_ids
            ):
                result.add_edge(edge)
                edges_from_g1 += 1

        # Додаємо ребра з g2 (потрібно перетворити node_id через URL)
        # Створюємо мапу g2_node_id -> URL для швидкого lookup
        g2_id_to_url = {node.node_id: node.url for node in g2._nodes.values()}

        edges_from_g2 = 0
        for edge in g2._edges:
            source_url = g2_id_to_url.get(edge.source_node_id)
            target_url = g2_id_to_url.get(edge.target_node_id)

            # Перевіряємо чи обидва кінці ребра є в спільних URL
            if source_url in common_urls and target_url in common_urls:
                # Перетворюємо node_id з g2 на node_id в result (через URL)
                new_source_id = result_url_to_id.get(source_url)
                new_target_id = result_url_to_id.get(target_url)

                if new_source_id and new_target_id:
                    # Перевіряємо чи таке ребро вже існує
                    if not result.has_edge(new_source_id, new_target_id):
                        new_edge = Edge(
                            source_node_id=new_source_id,
                            target_node_id=new_target_id,
                            metadata=edge.metadata.copy() if edge.metadata else {},
                        )
                        result.add_edge(new_edge)
                        edges_from_g2 += 1

        logger.info(
            f"Intersection completed: {len(result.nodes)} nodes, "
            f"edges from g1={edges_from_g1}, edges from g2={edges_from_g2}, "
            f"total edges={len(result.edges)}"
        )

        return result

    @staticmethod
    def symmetric_difference(g1: "Graph", g2: "Graph") -> "Graph":
        """
        Симетрична різниця графів (A ^ B).

        Вузли що присутні в одному графі але не в обох.
        Еквівалентно: (A - B) + (B - A)

        Args:
            g1: Перший граф
            g2: Другий граф

        Returns:
            Новий граф (симетрична різниця)
        """
        # (A - B) + (B - A)
        return GraphOperations.union(
            GraphOperations.difference(g1, g2), GraphOperations.difference(g2, g1)
        )

    @staticmethod
    def is_equal(g1: "Graph", g2: "Graph") -> bool:
        """
        Перевіряє рівність двох графів.

        Графи рівні якщо мають однакові набори URL вузлів.

        Args:
            g1: Перший граф
            g2: Другий граф

        Returns:
            True якщо графи рівні
        """
        return set(g1._url_to_node.keys()) == set(g2._url_to_node.keys())

    @staticmethod
    def is_subgraph(g1: "Graph", g2: "Graph", strict: bool = False) -> bool:
        """
        Перевіряє чи є g1 підграфом g2.

        Args:
            g1: Потенційний підграф
            g2: Потенційний надграф
            strict: Якщо True - строгий підграф (не рівний)

        Returns:
            True якщо g1 є підграфом g2
        """
        g1_urls = set(g1._url_to_node.keys())
        g2_urls = set(g2._url_to_node.keys())

        if strict:
            return g1_urls < g2_urls  # Строгий підграф
        else:
            return g1_urls <= g2_urls  # Підграф або рівний

    @staticmethod
    def is_supergraph(g1: "Graph", g2: "Graph", strict: bool = False) -> bool:
        """
        Перевіряє чи є g1 надграфом g2.

        Args:
            g1: Потенційний надграф
            g2: Потенційний підграф
            strict: Якщо True - строгий надграф (не рівний)

        Returns:
            True якщо g1 є надграфом g2
        """
        return GraphOperations.is_subgraph(g2, g1, strict=strict)
