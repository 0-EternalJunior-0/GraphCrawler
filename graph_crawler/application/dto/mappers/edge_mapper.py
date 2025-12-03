"""Edge Mapper - конвертація між Domain Edge та EdgeDTO.

Забезпечує ізоляцію Domain Layer від зовнішніх шарів через DTO.
"""

from typing import Any, Dict, Optional, Type

from graph_crawler.application.dto import CreateEdgeDTO, EdgeDTO
from graph_crawler.domain.entities.edge import Edge


class EdgeMapper:
    """
    Mapper для конвертації Edge ↔ EdgeDTO.
    
    Відповідальність:
    - Domain → DTO: Серіалізація Edge в EdgeDTO
    - DTO → Domain: Десеріалізація EdgeDTO в Edge
    - CreateDTO → Domain: Створення нового Edge з мінімальних даних
    
    Edge не має складних залежностей (на відміну від Node),
    тому конвертація проста і не потребує context.
    
    Examples:
        >>> # Domain → DTO
        >>> edge = Edge(source_node_id="node1", target_node_id="node2")
        >>> edge_dto = EdgeMapper.to_dto(edge)
        >>> 
        >>> # DTO → Domain
        >>> edge = EdgeMapper.to_domain(edge_dto)
        >>> 
        >>> # CreateDTO → Domain
        >>> create_dto = CreateEdgeDTO(
        ...     source_node_id="node1",
        ...     target_node_id="node2"
        ... )
        >>> edge = EdgeMapper.from_create_dto(create_dto)
    """

    @staticmethod
    def to_dto(edge: Edge) -> EdgeDTO:
        """
        Конвертує Domain Edge в EdgeDTO для передачі між шарами.
        
        Args:
            edge: Domain Edge entity
            
        Returns:
            EdgeDTO з усіма даними Edge
            
        Example:
            >>> edge = Edge(
            ...     source_node_id="node1",
            ...     target_node_id="node2",
            ...     metadata={"link_type": ["internal"]}
            ... )
            >>> edge_dto = EdgeMapper.to_dto(edge)
            >>> edge_dto.source_node_id
            'node1'
        """
        from datetime import datetime
        
        # Edge не має created_at, використовуємо поточний час
        created_at = getattr(edge, 'created_at', None) or datetime.now()
        
        return EdgeDTO(
            edge_id=edge.edge_id,
            source_node_id=edge.source_node_id,
            target_node_id=edge.target_node_id,
            metadata=edge.metadata.copy() if edge.metadata else {},
            created_at=created_at,
        )

    @staticmethod
    def to_domain(edge_dto: EdgeDTO, edge_class: Type[Edge] = Edge) -> Edge:
        """
        Конвертує EdgeDTO в Domain Edge.
        
        Args:
            edge_dto: EdgeDTO для конвертації
            edge_class: Клас Edge для створення (за замовчуванням Edge)
            
        Returns:
            Domain Edge entity
            
        Example:
            >>> edge = EdgeMapper.to_domain(edge_dto)
            >>> 
            >>> # З кастомним Edge класом
            >>> class CustomEdge(Edge):
            ...     custom_field: str = ""
            >>> edge = EdgeMapper.to_domain(edge_dto, edge_class=CustomEdge)
        """
        # Створюємо Edge (Edge не має created_at в Domain, це тільки в DTO)
        edge = edge_class(
            edge_id=edge_dto.edge_id,
            source_node_id=edge_dto.source_node_id,
            target_node_id=edge_dto.target_node_id,
            metadata=edge_dto.metadata.copy() if edge_dto.metadata else {},
        )
        
        # Зберігаємо created_at як атрибут якщо потрібно
        if hasattr(edge, 'created_at'):
            edge.created_at = edge_dto.created_at
        
        return edge

    @staticmethod
    def from_create_dto(
        create_dto: CreateEdgeDTO, edge_class: Type[Edge] = Edge
    ) -> Edge:
        """
        Створює новий Domain Edge з CreateEdgeDTO.
        
        Використовується для створення нових edges з мінімальних даних.
        edge_id та created_at встановлюються автоматично.
        
        Args:
            create_dto: CreateEdgeDTO з мінімальними даними
            edge_class: Клас Edge для створення (за замовчуванням Edge)
            
        Returns:
            Новий Domain Edge entity
            
        Example:
            >>> create_dto = CreateEdgeDTO(
            ...     source_node_id="node1",
            ...     target_node_id="node2",
            ...     metadata={"link_type": ["internal"]}
            ... )
            >>> edge = EdgeMapper.from_create_dto(create_dto)
        """
        return edge_class(
            source_node_id=create_dto.source_node_id,
            target_node_id=create_dto.target_node_id,
            metadata=create_dto.metadata.copy() if create_dto.metadata else {},
        )

    @staticmethod
    def to_dto_list(edges: list[Edge]) -> list[EdgeDTO]:
        """
        Конвертує список Edge в список EdgeDTO.
        
        Корисно для batch операцій.
        
        Args:
            edges: Список Domain Edge entities
            
        Returns:
            Список EdgeDTO
            
        Example:
            >>> edges = [edge1, edge2, edge3]
            >>> edge_dtos = EdgeMapper.to_dto_list(edges)
        """
        return [EdgeMapper.to_dto(edge) for edge in edges]

    @staticmethod
    def to_domain_list(
        edge_dtos: list[EdgeDTO], edge_class: Type[Edge] = Edge
    ) -> list[Edge]:
        """
        Конвертує список EdgeDTO в список Edge.
        
        Корисно для batch операцій при завантаженні з storage.
        
        Args:
            edge_dtos: Список EdgeDTO
            edge_class: Клас Edge для створення
            
        Returns:
            Список Domain Edge entities
            
        Example:
            >>> edge_dtos = [dto1, dto2, dto3]
            >>> edges = EdgeMapper.to_domain_list(edge_dtos)
        """
        return [EdgeMapper.to_domain(dto, edge_class=edge_class) for dto in edge_dtos]
