"""GraphOperations - операції теорії графів (SRP: складні операції винесено окремо)."""

import logging
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from graph_crawler.data.interfaces import IGraphBackend
    from graph_crawler.domain.entities.graph import Graph
    from graph_crawler.domain.entities.node import Node

logger = logging.getLogger(__name__)


class GraphOperations:
    """
    Static методи для складних операцій з графами.

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
        Returns:
            Новий граф (union)
        """
        from graph_crawler.domain.entities.edge import Edge
        from graph_crawler.domain.entities.graph import Graph
        from graph_crawler.domain.entities.merge_strategies import NodeMerger

        logger.debug(
            f"Union: g1={len(g1.nodes)} nodes, g2={len(g2.nodes)} nodes, strategy={merge_strategy}"
        )
        merger = NodeMerger(strategy=merge_strategy, custom_merge_fn=custom_merge_fn)

        result = Graph()

        # Додаємо всі вузли з першого графу (Крок 27: use iter_nodes)
        for node in g1.iter_nodes():
            result.add_node(node)

        # НЕ додаємо ребра з g1 зараз - додамо пізніше з правильними node_id
        # (бо node_id можуть змінитись при merge)

        # Мапа для відстеження змін node_id після merge
        # Зберігаємо мапінг для ОБОХ графів: old_node_id -> new_node_id
        node_id_mapping = {}
        for node in g1.iter_nodes():
            node_id_mapping[node.node_id] = node.node_id

        # Обробляємо вузли з другого графу
        conflicts_count = 0
        added_count = 0

        for node in g2.iter_nodes():  # Крок 27: use iter_nodes
            if node.url in result.url_to_node:  # Крок 27: use url_to_node property
                # Конфлікт: URL вже існує в result
                conflicts_count += 1
                existing_node = result.get_node_by_url(node.url)
                old_existing_id = existing_node.node_id

                # Використовуємо merger для об'єднання
                merged_node = merger.merge(existing_node, node)
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
        # Крок 27: use iter_nodes() для streaming доступу замість .nodes.keys()
        result_node_ids = {node.node_id for node in result.iter_nodes()}
        edges_added = 0
        edges_skipped = 0

        # Ребра з g1 (з оновленими node_id якщо були конфлікти)
        for edge in g1.iter_edges():  # Крок 27: use iter_edges() для streaming
            source_id = node_id_mapping.get(edge.source_node_id, edge.source_node_id)
            target_id = node_id_mapping.get(edge.target_node_id, edge.target_node_id)

            if source_id not in result_node_ids or target_id not in result_node_ids:
                edges_skipped += 1
                continue

            if not result.has_edge(source_id, target_id):
                import copy as copy_module

                new_edge = Edge(
                    source_node_id=source_id,
                    target_node_id=target_id,
                    metadata=copy_module.deepcopy(edge.metadata) if edge.metadata else {},
                )
                result.add_edge(new_edge)
                edges_added += 1

        # Ребра з g2 (Крок 27: use iter_edges() для streaming)
        for edge in g2.iter_edges():
            source_id = node_id_mapping.get(edge.source_node_id, edge.source_node_id)
            target_id = node_id_mapping.get(edge.target_node_id, edge.target_node_id)

            if source_id not in result_node_ids or target_id not in result_node_ids:
                edges_skipped += 1
                continue

            if not result.has_edge(source_id, target_id):
                import copy as copy_module

                new_edge = Edge(
                    source_node_id=source_id,
                    target_node_id=target_id,
                    metadata=copy_module.deepcopy(edge.metadata) if edge.metadata else {},
                )
                result.add_edge(new_edge)
                edges_added += 1

        if edges_skipped > 0:
            logger.debug("Union: skipped %s edges with missing nodes", edges_skipped)

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
        # Використовуємо url_to_node для O(1) lookup (Крок 28: use property)
        other_urls = set(g2.url_to_node.keys())

        # Додаємо тільки вузли з першого графу, яких немає в другому (за URL)
        # Крок 28: use iter_nodes()
        for node in g1.iter_nodes():
            if node.url not in other_urls:
                result.add_node(node)
        # Крок 28: use iter_nodes() для streaming доступу замість .nodes.keys()
        result_node_ids = {node.node_id for node in result.iter_nodes()}

        # Додаємо ребра де обидва кінці є в результаті (Крок 28: use iter_edges() для streaming)
        for edge in g1.iter_edges():
            if edge.source_node_id in result_node_ids and edge.target_node_id in result_node_ids:
                result.add_edge(edge)

        logger.debug(
            f"Difference completed: g1={len(g1.nodes)} - g2={len(g2.nodes)} = {len(result.nodes)} nodes, "
            f"{sum(1 for _ in result.iter_edges())} edges"
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

        # Використовуємо set intersection для знаходження спільних URL (Крок 29: use url_to_node property)
        g1_urls = set(g1.url_to_node.keys())
        g2_urls = set(g2.url_to_node.keys())
        common_urls = g1_urls & g2_urls  # Set intersection - O(min(len(g1), len(g2)))

        logger.debug(
            f"Intersection: g1={len(g1_urls)} urls, g2={len(g2_urls)} urls, common={len(common_urls)}"
        )

        # Додаємо тільки спільні вузли (беремо з g1)
        for url in common_urls:
            node = g1.get_node_by_url(url)
            if node:
                result.add_node(node)
        # Це потрібно для перетворення ребер з g2 (де node_id інші)
        result_url_to_id = {node.url: node.node_id for node in result.iter_nodes()}
        # Крок 29: use iter_nodes() для streaming доступу замість .nodes.keys()
        result_node_ids = {node.node_id for node in result.iter_nodes()}

        # Додаємо ребра з g1 (node_id співпадають) (Крок 29: use iter_edges() для streaming)
        edges_from_g1 = 0
        for edge in g1.iter_edges():
            if edge.source_node_id in result_node_ids and edge.target_node_id in result_node_ids:
                result.add_edge(edge)
                edges_from_g1 += 1

        # Додаємо ребра з g2 (потрібно перетворити node_id через URL)
        g2_id_to_url = {node.node_id: node.url for node in g2.iter_nodes()}

        edges_from_g2 = 0
        for edge in g2.iter_edges():  # Крок 29: use iter_edges() для streaming
            source_url = g2_id_to_url.get(edge.source_node_id)
            target_url = g2_id_to_url.get(edge.target_node_id)
            if source_url in common_urls and target_url in common_urls:
                # Перетворюємо node_id з g2 на node_id в result (через URL)
                new_source_id = result_url_to_id.get(source_url)
                new_target_id = result_url_to_id.get(target_url)

                if new_source_id and new_target_id:
                    if not result.has_edge(new_source_id, new_target_id):
                        import copy as copy_module

                        new_edge = Edge(
                            source_node_id=new_source_id,
                            target_node_id=new_target_id,
                            metadata=copy_module.deepcopy(edge.metadata) if edge.metadata else {},
                        )
                        result.add_edge(new_edge)
                        edges_from_g2 += 1

        logger.info(
            f"Intersection completed: {len(result.nodes)} nodes, "
            f"edges from g1={edges_from_g1}, edges from g2={edges_from_g2}, "
            f"total edges={sum(1 for _ in result.iter_edges())}"
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
        return set(g1.url_to_node.keys()) == set(g2.url_to_node.keys())

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
        g1_urls = set(g1.url_to_node.keys())
        g2_urls = set(g2.url_to_node.keys())

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

    # ═══════════════════════════════════════════════════════════════════════════
    # STREAMING OPERATIONS (Крок 47: Memory-efficient for large graphs)
    # ═══════════════════════════════════════════════════════════════════════════

    @staticmethod
    async def union_streaming(
        g1: "Graph",
        g2: "Graph",
        result_backend: "IGraphBackend",
        merge_strategy: str = "last",
    ) -> "Graph":
        """
        Memory-efficient union для великих графів (Крок 47).

        Args:
            g1: Перший граф (може бути з backend або RAM)
            g2: Другий граф (може бути з backend або RAM)
            result_backend: Backend для результуючого графу
            merge_strategy: Стратегія merge ('first', 'last', 'merge')
        Returns:
            Новий Graph з result_backend як storage
        """
        from graph_crawler.domain.entities.graph import Graph

        logger.info("Streaming union started: strategy=%s", merge_strategy)
        result = Graph(backend=result_backend)

        # Phase 1: Stream всі ноди з g1
        nodes_from_g1 = 0
        async for node in g1.iter_nodes_async():
            await result_backend.insert_node(node)
            nodes_from_g1 += 1
            if nodes_from_g1 % 10000 == 0:
                logger.debug("Streaming union: processed %s nodes from g1", nodes_from_g1)

        logger.debug("Phase 1 complete: %s nodes from g1", nodes_from_g1)

        # Phase 2: Stream ноди з g2 (з перевіркою дублікатів)
        nodes_from_g2 = 0
        conflicts = 0
        async for node in g2.iter_nodes_async():
            existing = await result_backend.get_node_by_url(node.url)
            if existing:
                conflicts += 1
                if merge_strategy == "last":
                    # Overwrite з g2
                    await result_backend.insert_node_overwrite(node)
                # 'first' - залишаємо existing, нічого не робимо
            else:
                await result_backend.insert_node(node)
                nodes_from_g2 += 1
                if nodes_from_g2 % 10000 == 0:
                    logger.debug("Streaming union: processed %s new nodes from g2", nodes_from_g2)

        logger.debug("Phase 2 complete: %s new nodes from g2, %s conflicts", nodes_from_g2, conflicts)

        # Phase 3: Stream edges з g1
        edges_from_g1 = 0
        async for edge in g1.iter_edges_async():
            source_exists = (
                await result_backend.url_exists(
                    (await result_backend.get_node_by_id(edge.source_node_id)).url
                    if await result_backend.get_node_by_id(edge.source_node_id)
                    else ""
                )
                if await result_backend.get_node_by_id(edge.source_node_id)
                else False
            )

            if source_exists or await result_backend.get_node_by_id(edge.source_node_id):
                target_node = await result_backend.get_node_by_id(edge.target_node_id)
                if target_node:
                    if not await result_backend.edge_exists(
                        edge.source_node_id, edge.target_node_id
                    ):
                        await result_backend.insert_edge(edge)
                        edges_from_g1 += 1

        logger.debug("Phase 3 complete: %s edges from g1", edges_from_g1)

        # Phase 4: Stream edges з g2
        edges_from_g2 = 0
        async for edge in g2.iter_edges_async():
            source_node = await result_backend.get_node_by_id(edge.source_node_id)
            target_node = await result_backend.get_node_by_id(edge.target_node_id)

            if source_node and target_node:
                if not await result_backend.edge_exists(edge.source_node_id, edge.target_node_id):
                    await result_backend.insert_edge(edge)
                    edges_from_g2 += 1

        logger.debug("Phase 4 complete: %s edges from g2", edges_from_g2)

        total_nodes = await result_backend.count_nodes()
        total_edges = await result_backend.count_edges()

        logger.info(
            f"Streaming union complete: "
            f"total_nodes={total_nodes}, total_edges={total_edges}, "
            f"conflicts={conflicts}"
        )

        return result

    @staticmethod
    async def difference_streaming(
        g1: "Graph",
        g2: "Graph",
        result_backend: "IGraphBackend",
    ) -> "Graph":
        """
        Memory-efficient difference для великих графів.

        Повертає ноди з g1 яких немає в g2.

        Args:
            g1: Перший граф
            g2: Граф для віднімання
            result_backend: Backend для результату

        Returns:
            Новий Graph з різницею
        """
        from graph_crawler.domain.entities.graph import Graph

        logger.info("Streaming difference started")

        result = Graph(backend=result_backend)

        # Збираємо URLs з g2 (може бути великий, але тільки URLs)
        g2_urls = set()
        async for node in g2.iter_nodes_async():
            g2_urls.add(node.url)

        logger.debug("Collected %s URLs from g2", len(g2_urls))

        # Stream g1, додаємо тільки ті що не в g2
        added = 0
        async for node in g1.iter_nodes_async():
            if node.url not in g2_urls:
                await result_backend.insert_node(node)
                added += 1

        logger.info("Streaming difference complete: %s nodes", added)

        return result
