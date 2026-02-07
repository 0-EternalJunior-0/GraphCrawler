"""Graph Mapper - конвертація між Domain Graph та GraphDTO.

Забезпечує ізоляцію Domain Layer від зовнішніх шарів через DTO.
"""

from typing import Any, Dict, Optional, Type

from graph_crawler.application.dto import (
    EdgeDTO,
    GraphDTO,
    GraphStatsDTO,
    GraphSummaryDTO,
    NodeDTO,
)
from graph_crawler.application.dto.mappers.edge_mapper import EdgeMapper
from graph_crawler.application.dto.mappers.node_mapper import NodeMapper
from graph_crawler.domain.entities.edge import Edge
from graph_crawler.domain.entities.graph import Graph
from graph_crawler.domain.entities.node import Node


class GraphMapper:
    """
    Mapper для конвертації Graph ↔ GraphDTO.
    
    Відповідальність:
    - Domain → DTO: Серіалізація Graph в GraphDTO (з NodeDTO та EdgeDTO)
    - DTO → Domain: Десеріалізація GraphDTO в Graph (з відновленням залежностей)
    - Статистика: Обчислення GraphStatsDTO та GraphSummaryDTO
    
    ВАЖЛИВО:
    - При to_domain() context передається для відновлення залежностей Node
    - Підтримує кастомні Node та Edge класи через context
    - default_merge_strategy можна встановити при створенні Graph
    
    Examples:
        >>> # Domain → DTO (серіалізація для збереження)
        >>> graph = Graph()
        >>> graph.add_node(node1)
        >>> graph.add_edge(edge1)
        >>> graph_dto = GraphMapper.to_dto(graph)
        >>> 
        >>> # DTO → Domain (завантаження з відновленням залежностей)
        >>> context = {
        ...     'plugin_manager': pm,
        ...     'tree_parser': parser,
        ...     'node_class': CustomNode,
        ...     'edge_class': CustomEdge,
        ...     'default_merge_strategy': 'merge'
        ... }
        >>> graph = GraphMapper.to_domain(graph_dto, context=context)
    """

    @staticmethod
    def to_dto(graph: Graph) -> GraphDTO:
        """
        Конвертує Domain Graph в GraphDTO для передачі між шарами.
        
        Серіалізує весь граф включаючи:
        - Всі ноди (через NodeMapper)
        - Всі edges (через EdgeMapper)
        - Статистику графу
        
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
        # Конвертуємо ноди через NodeMapper
        nodes_dto = NodeMapper.to_dto_list(list(graph.nodes.values()))

        # Конвертуємо edges через EdgeMapper
        edges_dto = EdgeMapper.to_dto_list(graph.edges)

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
        
        ВАЖЛИВО: Context використовується для:
        - Відновлення залежностей Node (plugin_manager, tree_parser, hash_strategy)
        - Вказівки кастомних класів Node та Edge
        - Встановлення default_merge_strategy для Graph
        
        CONTEXT RESOLUTION:
        Якщо context=None, автоматично використовується DependencyRegistry.get_context()
        для отримання дефолтних залежностей.
        
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
            
        Example:
            >>> # Автоматичне використання DependencyRegistry
            >>> graph = GraphMapper.to_domain(graph_dto)
            >>> 
            >>> # Явний контекст з override
            >>> context = {
            ...     'plugin_manager': my_plugin_manager,
            ...     'default_merge_strategy': 'merge'
            ... }
            >>> graph = GraphMapper.to_domain(graph_dto, context=context)
            >>>
            >>> # Через GraphContext
            >>> from graph_crawler.application.context import get_graph_context
            >>> ctx = get_graph_context()
            >>> graph = GraphMapper.to_domain(graph_dto, context=ctx.to_dict())
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
        
        # Обчислюємо avg_depth та max_depth якщо їх немає
        depths = [node.depth for node in graph.nodes.values()]
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
    def to_summary_dto(graph: Graph, root_url: str, crawl_completed: bool = False) -> GraphSummaryDTO:
        """
        Створює спрощений GraphSummaryDTO (для API responses).
        
        Використовується коли потрібна легка версія без повних даних графу.
        
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
        
        Це utility метод для merge операцій на рівні DTO.
        
        СТРАТЕГІЇ:
        - 'last': При конфлікті залишається node з другого графу
        - 'first': При конфлікті залишається node з першого графу
        - 'merge': При конфлікті об'єднується metadata з обох нод
        - 'newest': При конфлікті залишається node з новішим created_at
        - 'oldest': При конфлікті залишається node з старішим created_at
        
        Args:
            graph_dto1: Перший GraphDTO
            graph_dto2: Другий GraphDTO
            merge_strategy: Стратегія об'єднання (default: 'last')
            context: Контекст для відновлення залежностей
            
        Returns:
            Об'єднаний GraphDTO
            
        Example:
            >>> # Базове об'єднання (стратегія 'last')
            >>> merged_dto = GraphMapper.merge_graphs(dto1, dto2)
            >>> 
            >>> # Об'єднання з 'merge' стратегією (об'єднує metadata)
            >>> merged_dto = GraphMapper.merge_graphs(
            ...     dto1, dto2, merge_strategy='merge'
            ... )
            >>> 
            >>> # Об'єднання з 'newest' (залишає новіші ноди)
            >>> merged_dto = GraphMapper.merge_graphs(
            ...     dto1, dto2, merge_strategy='newest'
            ... )
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
        predicate: callable,
        context: Optional[Dict[str, Any]] = None,
    ) -> GraphDTO:
        """
        Фільтрує ноди в GraphDTO за предикатом.
        
        Utility метод для фільтрації на рівні DTO без повної конвертації в Domain.
        
        Args:
            graph_dto: GraphDTO для фільтрації
            predicate: Функція (NodeDTO) -> bool
            context: Контекст (не використовується, але залишений для сумісності)
            
        Returns:
            Новий GraphDTO з відфільтрованими нодами та edges
            
        Example:
            >>> # Фільтруємо тільки просканованих нод
            >>> scanned_dto = GraphMapper.filter_nodes_dto(
            ...     graph_dto,
            ...     lambda node: node.scanned
            ... )
            >>> 
            >>> # Фільтруємо ноди по глибині
            >>> shallow_dto = GraphMapper.filter_nodes_dto(
            ...     graph_dto,
            ...     lambda node: node.depth <= 2
            ... )
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
