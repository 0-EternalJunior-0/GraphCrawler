"""Graph Mapper - конвертація між Domain Graph та GraphDTO."""

from typing import Any, Callable, Dict, Optional

from graph_crawler.application.dto.graph_dto import (
    GraphDTO,
    GraphStatsDTO,
    GraphSummaryDTO,
)
from graph_crawler.application.dto.mappers.edge_mapper import EdgeMapper
from graph_crawler.application.dto.mappers.node_mapper import NodeMapper
from graph_crawler.domain.entities.edge import Edge
from graph_crawler.domain.entities.graph import Graph
from graph_crawler.domain.entities.node import Node


class GraphMapper:
    """Mapper для конвертації Graph ↔ GraphDTO."""

    @staticmethod
    def to_dto(graph: Graph) -> GraphDTO:
        """
        Конвертує Domain Graph в GraphDTO для передачі між шарами.

        Args:
            graph: Domain Graph entity
        Returns:
            GraphDTO з усіма даними Graph
        Example:
            >>> graph = Graph()
            >>> # ... додаємо ноди та edges
            >>> graph_dto = GraphMapper.to_dto(graph)
            >>> graph_dto.stats.total_nodes
            100
        """
        # Конвертуємо ноди через NodeMapper (streaming через iter_nodes)
        nodes_dto = NodeMapper.to_dto_list(list(graph.iter_nodes()))

        # Конвертуємо edges через EdgeMapper (streaming через iter_edges)
        edges_dto = EdgeMapper.to_dto_list(list(graph.iter_edges()))

        # Обчислюємо статистику
        stats = GraphMapper.compute_stats(graph)

        return GraphDTO(nodes=nodes_dto, edges=edges_dto, stats=stats)

    @staticmethod
    def to_domain(
        graph_dto: GraphDTO,
        context: Optional[Dict[str, Any]] = None,
    ) -> Graph:
        """
        Конвертує GraphDTO в Domain Graph з відновленням залежностей.

        Args:
            graph_dto: GraphDTO для конвертації
            context: Контекст з налаштуваннями (опціонально):
                - 'plugin_manager': Plugin manager для Node
                - 'tree_parser': Tree parser для Node
                - 'hash_strategy': Hash strategy для Node
                - 'node_class': Клас Node (default: Node)
                - 'edge_class': Клас Edge (default: Edge)
                - 'default_merge_strategy': Стратегія для union операцій (default: 'last')
        Returns:
            Domain Graph entity з відновленими залежностями
        """
        # Якщо context не передано - отримуємо з DependencyRegistry
        if context is None:
            try:
                from graph_crawler.application.context.dependency_registry import (
                    DependencyRegistry,
                )

                context = DependencyRegistry.get_context()
            except ImportError:
                context = {}

        context = context or {}

        # Отримуємо класи Node та Edge з context
        node_class = context.get("node_class") or Node
        edge_class = context.get("edge_class") or Edge

        # Отримуємо default_merge_strategy з context (default: 'last')
        default_merge_strategy = context.get("default_merge_strategy", "last")

        # Створюємо Graph з вказаною стратегією
        graph = Graph(default_merge_strategy=default_merge_strategy)

        # Підготовка context для Node (без node_class, edge_class, default_merge_strategy)
        node_context = {
            k: v
            for k, v in context.items()
            if k not in ["node_class", "edge_class", "default_merge_strategy"]
        }

        # Конвертуємо ноди через NodeMapper
        nodes = NodeMapper.to_domain_list(
            graph_dto.nodes, context=node_context, node_class=node_class
        )

        # Додаємо ноди в граф
        for node in nodes:
            graph.add_node(node)

        # Конвертуємо edges через EdgeMapper
        edges = EdgeMapper.to_domain_list(graph_dto.edges, edge_class=edge_class)

        # Додаємо edges в граф
        for edge in edges:
            graph.add_edge(edge)

        return graph

    @staticmethod
    def compute_stats(graph: Graph) -> GraphStatsDTO:
        """
        Обчислює статистику графу для GraphStatsDTO.

        Args:
            graph: Domain Graph entity

        Returns:
            GraphStatsDTO зі статистикою

        Example:
            >>> stats = GraphMapper.compute_stats(graph)
            >>> stats.total_nodes
            100
            >>> stats.avg_depth
            2.5
        """
        stats = graph.get_stats()

        # Обчислюємо avg_depth та max_depth якщо їх немає (streaming через iter_nodes)
        depths = [node.depth for node in graph.iter_nodes()]
        avg_depth = stats.get("avg_depth", sum(depths) / len(depths) if depths else 0.0)
        max_depth = stats.get("max_depth", max(depths) if depths else 0)

        return GraphStatsDTO(
            total_nodes=stats["total_nodes"],
            scanned_nodes=stats["scanned_nodes"],
            unscanned_nodes=stats["unscanned_nodes"],
            total_edges=stats["total_edges"],
            avg_depth=avg_depth,
            max_depth=max_depth,
        )

    @staticmethod
    def to_summary_dto(
        graph: Graph, root_url: str, crawl_completed: bool = False
    ) -> GraphSummaryDTO:
        """
        Створює спрощений GraphSummaryDTO (для API responses).

        Args:
            graph: Domain Graph entity
            root_url: Кореневий URL початку краулінгу
            crawl_completed: Чи завершено краулінг
        Returns:
            GraphSummaryDTO з основними показниками
        Example:
            >>> summary = GraphMapper.to_summary_dto(
            ...     graph,
            ...     root_url="https://example.com",
            ...     crawl_completed=True
            ... )
            >>> summary.total_nodes
            100
        """
        stats = graph.get_stats()

        return GraphSummaryDTO(
            total_nodes=stats["total_nodes"],
            total_edges=stats["total_edges"],
            root_url=root_url,
            crawl_completed=crawl_completed,
        )

    @staticmethod
    def merge_graphs(
        graph_dto1: GraphDTO,
        graph_dto2: GraphDTO,
        merge_strategy: str = "last",
        context: Optional[Dict[str, Any]] = None,
    ) -> GraphDTO:
        """
        Об'єднує два GraphDTO з вказаною стратегією.

        Args:
            graph_dto1: Перший GraphDTO
            graph_dto2: Другий GraphDTO
            merge_strategy: Стратегія об'єднання (default: 'last')
            context: Контекст для відновлення залежностей
        Returns:
            Об'єднаний GraphDTO
        """
        # Конвертуємо DTO в Domain з вказаною стратегією
        context = context or {}
        context["default_merge_strategy"] = merge_strategy

        graph1 = GraphMapper.to_domain(graph_dto1, context=context)
        graph2 = GraphMapper.to_domain(graph_dto2, context=context)

        # Використовуємо Graph.__add__ (delegation до GraphOperations.union)
        merged_graph = graph1 + graph2

        # Конвертуємо назад в DTO
        return GraphMapper.to_dto(merged_graph)

    @staticmethod
    def filter_nodes_dto(
        graph_dto: GraphDTO,
        predicate: Callable[[Any], bool],
        context: Optional[Dict[str, Any]] = None,
    ) -> GraphDTO:
        """
        Фільтрує ноди в GraphDTO за предикатом.

        Args:
            graph_dto: GraphDTO для фільтрації
            predicate: Функція (NodeDTO) -> bool
            context: Контекст (не використовується, але залишений для сумісності)
        Returns:
            Новий GraphDTO з відфільтрованими нодами та edges
        """
        # Фільтруємо ноди
        filtered_nodes = [node for node in graph_dto.nodes if predicate(node)]

        # Збираємо ID відфільтрованих нод
        node_ids = {node.node_id for node in filtered_nodes}

        # Фільтруємо edges (залишаємо тільки ті що з'єднують відфільтровані ноди)
        filtered_edges = [
            edge
            for edge in graph_dto.edges
            if edge.source_node_id in node_ids and edge.target_node_id in node_ids
        ]

        # Обчислюємо нову статистику
        scanned_count = sum(1 for node in filtered_nodes if node.scanned)
        unscanned_count = len(filtered_nodes) - scanned_count
        depths = [node.depth for node in filtered_nodes]
        avg_depth = sum(depths) / len(depths) if depths else 0.0
        max_depth = max(depths) if depths else 0

        new_stats = GraphStatsDTO(
            total_nodes=len(filtered_nodes),
            scanned_nodes=scanned_count,
            unscanned_nodes=unscanned_count,
            total_edges=len(filtered_edges),
            avg_depth=avg_depth,
            max_depth=max_depth,
        )

        return GraphDTO(nodes=filtered_nodes, edges=filtered_edges, stats=new_stats)
