"""Node Mapper - конвертація між Domain Node та NodeDTO.

Забезпечує ізоляцію Domain Layer від зовнішніх шарів через DTO.
"""

from functools import lru_cache
from typing import Any, Dict, FrozenSet, Optional, Type

from graph_crawler.application.dto.node_dto import (
    CreateNodeDTO,
    NodeDTO,
    NodeMetadataDTO,
)
from graph_crawler.domain.entities.node import Node
from graph_crawler.domain.value_objects.lifecycle import NodeLifecycle
from graph_crawler.domain.value_objects.models import ContentType


class NodeMapper:
    """
    Mapper для конвертації Node ↔ NodeDTO.

    Відповідальність:
    - Domain → DTO: Серіалізація Node в NodeDTO (без залежностей)
    - DTO → Domain: Десеріалізація NodeDTO в Node (з відновленням залежностей)
    - CreateDTO → Domain: Створення нового Node з мінімальних даних

    ВАЖЛИВО про залежності:
    - plugin_manager, tree_parser, hash_strategy НЕ серіалізуються в DTO
    - При to_domain() вони передаються через context або використовуються дефолтні
    - Це забезпечує гнучкість: можна завантажити Node і потім налаштувати залежності

    Examples:
        >>> # Domain → DTO (серіалізація)
        >>> node = Node(url="https://example.com", depth=0)
        >>> node_dto = NodeMapper.to_dto(node)
        >>>
        >>> # DTO → Domain (десеріалізація з контекстом)
        >>> context = {
        ...     'plugin_manager': my_plugin_manager,
        ...     'tree_parser': my_parser,
        ...     'hash_strategy': my_hash_strategy
        ... }
        >>> node = NodeMapper.to_domain(node_dto, context=context)
        >>>
        >>> # CreateDTO → Domain (створення нового)
        >>> create_dto = CreateNodeDTO(url="https://example.com", depth=0)
        >>> node = NodeMapper.from_create_dto(create_dto, context=context)
    """

    # Базові поля Node які є в NodeDTO (не треба дублювати в _custom_fields)
    _BASE_NODE_FIELDS: FrozenSet[str] = frozenset({
        'url', 'node_id', 'depth', 'should_scan', 'can_create_edges',
        'created_at', 'metadata', 'user_data', 'scanned', 'response_status',
        'content_hash', 'simhash', 'priority', 'lifecycle_stage', 'content_type',
        'plugin_manager', 'tree_parser', 'hash_strategy', 'simhash_strategy'
    })

    @staticmethod
    @lru_cache(maxsize=32)
    def _get_custom_fields(node_class: Type[Node]) -> FrozenSet[str]:
        """
        Кешує список кастомних полів для класу Node.
        """
        return frozenset(
            field_name
            for field_name in node_class.model_fields.keys()
            if field_name not in NodeMapper._BASE_NODE_FIELDS
        )

    @staticmethod
    def to_dto(node: Node) -> NodeDTO:
        """
        Конвертує Domain Node в NodeDTO для передачі між шарами.

        Серіалізує всі поля Node, ОКРІМ:
        - plugin_manager (не серіалізується)
        - tree_parser (не серіалізується)
        - hash_strategy (не серіалізується)

        Кастомні Pydantic поля підкласів Node автоматично зберігаються
        в user_data['_custom_fields'] для збереження через DTO pipeline.

        Args:
            node: Domain Node entity

        Returns:
            NodeDTO з усіма даними Node

        Example:
            >>> node = Node(url="https://example.com", depth=0)
            >>> await node.process_html("<html>...</html>")
            >>> node_dto = NodeMapper.to_dto(node)
            >>> node_dto.url
            'https://example.com'
        """
        # Конвертуємо lifecycle_stage enum в string
        lifecycle_stage_str = (
            node.lifecycle_stage.value
            if isinstance(node.lifecycle_stage, NodeLifecycle)
            else node.lifecycle_stage
        )

        # Конвертуємо content_type enum в string
        content_type_str = (
            node.content_type.value
            if isinstance(node.content_type, ContentType)
            else node.content_type
        )

        # Копіюємо user_data
        user_data = node.user_data.copy()

        # Автоматично зберігаємо кастомні Pydantic поля підкласів Node
        custom_field_names = NodeMapper._get_custom_fields(type(node))
        if custom_field_names:
            custom_fields = {}
            for field_name in custom_field_names:
                value = getattr(node, field_name, None)
                # Зберігаємо тільки серіалізовані типи
                if value is not None and isinstance(value, (str, int, float, bool, list, dict)):
                    custom_fields[field_name] = value

            if custom_fields:
                user_data['_custom_fields'] = custom_fields

        return NodeDTO(
            node_id=node.node_id,
            url=node.url,
            depth=node.depth,
            should_scan=node.should_scan,
            can_create_edges=node.can_create_edges,
            scanned=node.scanned,
            response_status=node.response_status,
            metadata=node.metadata.copy(),
            user_data=user_data,
            content_hash=node.content_hash,
            simhash=node.simhash,
            priority=node.priority,
            created_at=node.created_at,
            lifecycle_stage=lifecycle_stage_str,
            content_type=content_type_str,
        )

    @staticmethod
    def to_domain(
            node_dto: NodeDTO,
            context: Optional[Dict[str, Any]] = None,
            node_class: Type[Node] = Node,
    ) -> Node:
        """
        Конвертує NodeDTO в Domain Node з відновленням залежностей.

        ВАЖЛИВО: Залежності (plugin_manager, tree_parser, hash_strategy)
        передаються через context. Якщо context=None, вони будуть None.
        Користувач може відновити їх пізніше через node.restore_dependencies().

        Кастомні Pydantic поля відновлюються з user_data['_custom_fields']
        якщо node_class їх підтримує.

        Args:
            node_dto: NodeDTO для конвертації
            context: Контекст з залежностями:
                - 'plugin_manager': Plugin manager для Node
                - 'tree_parser': Tree parser (BeautifulSoup, lxml, etc.)
                - 'hash_strategy': Стратегія обчислення hash
            node_class: Клас Node для створення (за замовчуванням Node,
                       може бути CustomNode для розширень)

        Returns:
            Domain Node entity з відновленими залежностями

        Example:
            >>> # Без context (залежності будуть None)
            >>> node = NodeMapper.to_domain(node_dto)
            >>>
            >>> # З context (залежності відновлені)
            >>> context = {'plugin_manager': pm, 'tree_parser': parser}
            >>> node = NodeMapper.to_domain(node_dto, context=context)
            >>>
            >>> # З кастомним Node класом
            >>> class CustomNode(Node):
            ...     text: Optional[str] = None
            >>> node = NodeMapper.to_domain(node_dto, node_class=CustomNode)
        """
        context = context or {}

        # Конвертуємо string lifecycle_stage в enum
        lifecycle_stage = (
            NodeLifecycle(node_dto.lifecycle_stage)
            if isinstance(node_dto.lifecycle_stage, str)
            else node_dto.lifecycle_stage
        )

        # Конвертуємо string content_type в enum
        content_type = (
            ContentType(node_dto.content_type)
            if isinstance(node_dto.content_type, str)
            else node_dto.content_type
        )

        # Копіюємо user_data та витягуємо _custom_fields
        user_data = node_dto.user_data.copy()
        custom_fields = user_data.pop('_custom_fields', {})

        # Базові параметри для створення Node
        node_kwargs = {
            'node_id': node_dto.node_id,
            'url': node_dto.url,
            'depth': node_dto.depth,
            'should_scan': node_dto.should_scan,
            'can_create_edges': node_dto.can_create_edges,
            'scanned': node_dto.scanned,
            'response_status': node_dto.response_status,
            'metadata': node_dto.metadata.copy(),
            'user_data': user_data,
            'content_hash': node_dto.content_hash,
            'simhash': node_dto.simhash,
            'priority': node_dto.priority,
            'created_at': node_dto.created_at,
            'lifecycle_stage': lifecycle_stage,
            'content_type': content_type,
            # Залежності з context (можуть бути None)
            'plugin_manager': context.get("plugin_manager"),
            'tree_parser': context.get("tree_parser"),
            'hash_strategy': context.get("hash_strategy"),
            'simhash_strategy': context.get("simhash_strategy"),
        }

        # Відновлюємо кастомні поля якщо node_class їх підтримує
        if custom_fields and node_class is not Node:
            for field_name, value in custom_fields.items():
                if field_name in node_class.model_fields:
                    node_kwargs[field_name] = value

        # Створюємо Node (або CustomNode)
        node = node_class(**node_kwargs)

        return node

    @staticmethod
    def from_create_dto(
            create_dto: CreateNodeDTO,
            context: Optional[Dict[str, Any]] = None,
            node_class: Type[Node] = Node,
    ) -> Node:
        """
        Створює новий Domain Node з CreateNodeDTO.

        Використовується для створення нових нод з мінімальних даних.
        Інші поля (node_id, created_at, metadata, etc.) встановлюються автоматично.

        Args:
            create_dto: CreateNodeDTO з мінімальними даними
            context: Контекст з залежностями (plugin_manager, tree_parser, hash_strategy)
            node_class: Клас Node для створення (за замовчуванням Node)

        Returns:
            Новий Domain Node entity

        Example:
            >>> create_dto = CreateNodeDTO(
            ...     url="https://example.com",
            ...     depth=0,
            ...     should_scan=True
            ... )
            >>> context = {'plugin_manager': pm}
            >>> node = NodeMapper.from_create_dto(create_dto, context=context)
        """
        context = context or {}

        # Створюємо новий Node з мінімальних даних
        # node_id, created_at, metadata, user_data встановляться автоматично
        node = node_class(
            url=create_dto.url,
            depth=create_dto.depth,
            should_scan=create_dto.should_scan,
            can_create_edges=create_dto.can_create_edges,
            priority=create_dto.priority,
            # Залежності з context
            plugin_manager=context.get("plugin_manager"),
            tree_parser=context.get("tree_parser"),
            hash_strategy=context.get("hash_strategy"),
        )

        return node

    @staticmethod
    def to_metadata_dto(node: Node) -> NodeMetadataDTO:
        """
        Конвертує Node в спрощений NodeMetadataDTO (для API responses).

        Використовується коли потрібна легка версія без повних даних.
        Містить тільки основні поля для відображення.

        Args:
            node: Domain Node entity

        Returns:
            NodeMetadataDTO з основними полями

        Example:
            >>> node = Node(url="https://example.com", depth=0)
            >>> await node.process_html("<html><title>Example</title></html>")
            >>> metadata_dto = NodeMapper.to_metadata_dto(node)
            >>> metadata_dto.title
            'Example'
        """
        return NodeMetadataDTO(
            node_id=node.node_id,
            url=node.url,
            title=node.get_title(),
            description=node.get_description(),
            h1=node.get_h1(),
            keywords=node.get_keywords(),
            canonical_url=node.get_canonical_url(),
            language=node.get_language(),
        )

    @staticmethod
    def to_dto_list(nodes: list[Node]) -> list[NodeDTO]:
        """
        Конвертує список Node в список NodeDTO.

        Корисно для batch операцій.

        Args:
            nodes: Список Domain Node entities

        Returns:
            Список NodeDTO

        Example:
            >>> nodes = [node1, node2, node3]
            >>> node_dtos = NodeMapper.to_dto_list(nodes)
        """
        return [NodeMapper.to_dto(node) for node in nodes]

    @staticmethod
    def to_domain_list(
            node_dtos: list[NodeDTO],
            context: Optional[Dict[str, Any]] = None,
            node_class: Type[Node] = Node,
    ) -> list[Node]:
        """
        Конвертує список NodeDTO в список Node.

        Корисно для batch операцій при завантаженні з storage.

        Args:
            node_dtos: Список NodeDTO
            context: Контекст з залежностями (спільний для всіх нод)
            node_class: Клас Node для створення

        Returns:
            Список Domain Node entities

        Example:
            >>> node_dtos = [dto1, dto2, dto3]
            >>> context = {'plugin_manager': pm}
            >>> nodes = NodeMapper.to_domain_list(node_dtos, context=context)
        """
        return [
            NodeMapper.to_domain(dto, context=context, node_class=node_class)
            for dto in node_dtos
        ]
