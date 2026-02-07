"""
Тести на ізоляцію Domain Layer через DTO.

Перевіряє, що:
1. Storage класи працюють тільки з DTO (не Domain entities)
2. Mappers правильно конвертують Domain ↔ DTO
3. Context System правильно відновлює залежності
4. Merge strategies працюють коректно
"""

import pytest
from datetime import datetime
from pathlib import Path
import tempfile
import os

# DTO та Mappers
from graph_crawler.application.dto import (
    NodeDTO,
    EdgeDTO,
    GraphDTO,
    CreateNodeDTO,
    CreateEdgeDTO,
    GraphStatsDTO,
)
from graph_crawler.application.dto.mappers import (
    NodeMapper,
    EdgeMapper,
    GraphMapper,
)

# Context System
from graph_crawler.application.context import (
    DependencyRegistry,
    GraphContext,
    with_merge_strategy,
)

# Storage (Infrastructure)
from graph_crawler.infrastructure.persistence.json_storage import JSONStorage
from graph_crawler.infrastructure.persistence.memory_storage import MemoryStorage

# Domain entities (тільки для перевірки ізоляції)
from graph_crawler.domain.entities.node import Node
from graph_crawler.domain.entities.edge import Edge
from graph_crawler.domain.entities.graph import Graph


class TestDomainIsolation:
    """Тести на ізоляцію Domain Layer."""

    def test_storage_type_hints_enforce_dto(self):
        """
        Тест: Storage класи мають type hints що вказують на DTO.
        
        КРИТИЧНО: Storage класи повинні працювати ТІЛЬКИ з DTO.
        """
        import inspect
        
        # Перевіряємо type hints для MemoryStorage.save_graph
        sig = inspect.signature(MemoryStorage.save_graph)
        param = sig.parameters['graph_dto']
        
        # Type hint має бути GraphDTO
        assert 'GraphDTO' in str(param.annotation)
        
        # Перевіряємо return type для load_graph
        sig = inspect.signature(MemoryStorage.load_graph)
        assert 'GraphDTO' in str(sig.return_annotation)

    @pytest.mark.asyncio
    async def test_storage_works_with_dto_only(self):
        """
        Тест: Storage класи працюють ТІЛЬКИ з DTO.
        
        Правильний workflow:
        1. Domain Graph → GraphMapper.to_dto() → GraphDTO
        2. GraphDTO → Storage.save_graph()
        3. Storage.load_graph() → GraphDTO
        4. GraphDTO → GraphMapper.to_domain() → Domain Graph
        """
        # Створюємо Domain Graph
        graph = Graph()
        node = Node(url="https://example.com", depth=0)
        graph.add_node(node)

        # Правильний шлях: Domain → DTO → Storage
        graph_dto = GraphMapper.to_dto(graph)
        
        # Storage приймає DTO
        storage = MemoryStorage()
        result = await storage.save_graph(graph_dto)
        
        assert result is True
        
        # Storage повертає DTO
        loaded_dto = await storage.load_graph()
        
        assert isinstance(loaded_dto, GraphDTO)
        assert len(loaded_dto.nodes) == 1
        assert loaded_dto.nodes[0].url == "https://example.com"

    @pytest.mark.asyncio
    async def test_json_storage_isolation(self):
        """
        Тест: JSONStorage працює тільки з DTO (ізоляція Domain Layer).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Створюємо Domain Graph
            graph = Graph()
            node1 = Node(url="https://example.com/page1", depth=0)
            node2 = Node(url="https://example.com/page2", depth=1)
            graph.add_node(node1)
            graph.add_node(node2)
            
            edge = Edge(
                source_node_id=node1.node_id,
                target_node_id=node2.node_id
            )
            graph.add_edge(edge)

            # Domain → DTO
            graph_dto = GraphMapper.to_dto(graph)

            # Зберігаємо DTO в JSON
            storage = JSONStorage(tmpdir)
            await storage.save_graph(graph_dto)

            # Завантажуємо DTO з JSON
            loaded_dto = await storage.load_graph()

            # Перевіряємо що завантажено DTO (не Domain)
            assert isinstance(loaded_dto, GraphDTO)
            assert len(loaded_dto.nodes) == 2
            assert len(loaded_dto.edges) == 1
            
            # Перевіряємо що в JSON файлі зберігається DTO структура
            json_file = Path(tmpdir) / "graph.json"
            import json
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            # Перевіряємо структуру DTO (не Domain)
            assert "nodes" in data
            assert "edges" in data
            assert "stats" in data
            assert isinstance(data["nodes"], list)
            assert len(data["nodes"]) == 2


class TestMapperCorrectness:
    """Тести на коректність Mappers."""

    def test_node_mapper_to_dto(self):
        """Тест: NodeMapper.to_dto() правильно конвертує Node → NodeDTO."""
        # Створюємо Node з даними
        node = Node(
            url="https://example.com",
            depth=2,
            should_scan=True,
            can_create_edges=True,
            priority=5,
        )
        node.scanned = True
        node.response_status = 200
        node.metadata = {"title": "Example"}
        node.content_hash = "abc123"

        # Конвертуємо в DTO
        node_dto = NodeMapper.to_dto(node)

        # Перевіряємо що всі поля збережені
        assert isinstance(node_dto, NodeDTO)
        assert node_dto.url == "https://example.com"
        assert node_dto.depth == 2
        assert node_dto.should_scan is True
        assert node_dto.can_create_edges is True
        assert node_dto.scanned is True
        assert node_dto.response_status == 200
        assert node_dto.priority == 5
        assert node_dto.metadata["title"] == "Example"
        assert node_dto.content_hash == "abc123"

        # Перевіряємо що залежності НЕ серіалізуються
        # (plugin_manager, tree_parser, hash_strategy не в DTO)
        dto_dict = node_dto.model_dump()
        assert "plugin_manager" not in dto_dict
        assert "tree_parser" not in dto_dict
        assert "hash_strategy" not in dto_dict

    def test_node_mapper_to_domain(self):
        """Тест: NodeMapper.to_domain() правильно конвертує NodeDTO → Node."""
        # Створюємо DTO
        node_dto = NodeDTO(
            node_id="test-123",
            url="https://example.com",
            depth=1,
            should_scan=True,
            can_create_edges=True,
            scanned=False,
            response_status=None,
            metadata={"title": "Test"},
            user_data={},
            content_hash=None,
            priority=None,
            created_at=datetime.now(),
            lifecycle_stage="url_stage",
        )

        # Конвертуємо в Domain
        node = NodeMapper.to_domain(node_dto)

        # Перевіряємо що всі поля відновлені
        assert isinstance(node, Node)
        assert node.node_id == "test-123"
        assert node.url == "https://example.com"
        assert node.depth == 1
        assert node.should_scan is True
        assert node.metadata["title"] == "Test"

    def test_graph_mapper_round_trip(self):
        """Тест: Graph → DTO → Graph (round trip) зберігає всі дані."""
        # Створюємо Domain Graph
        graph = Graph()
        node1 = Node(url="https://example.com/1", depth=0)
        node2 = Node(url="https://example.com/2", depth=1)
        graph.add_node(node1)
        graph.add_node(node2)

        edge = Edge(
            source_node_id=node1.node_id,
            target_node_id=node2.node_id,
            metadata={"link_type": ["internal"]}
        )
        graph.add_edge(edge)

        # Round trip: Domain → DTO → Domain
        graph_dto = GraphMapper.to_dto(graph)
        restored_graph = GraphMapper.to_domain(graph_dto)

        # Перевіряємо що дані збережені
        assert len(restored_graph.nodes) == 2
        assert len(restored_graph.edges) == 1
        assert node1.node_id in restored_graph.nodes
        assert node2.node_id in restored_graph.nodes

        # Перевіряємо edge
        restored_edge = restored_graph.edges[0]
        assert restored_edge.source_node_id == node1.node_id
        assert restored_edge.target_node_id == node2.node_id
        assert restored_edge.metadata["link_type"] == ["internal"]


class TestContextSystem:
    """Тести на Context System (DependencyRegistry, MergeContext)."""

    def test_dependency_registry_basic(self):
        """Тест: DependencyRegistry зберігає дефолтні залежності."""
        # Скидаємо registry перед тестом
        DependencyRegistry.reset()

        # Налаштовуємо дефолти
        DependencyRegistry.configure(
            default_merge_strategy='merge',
        )

        # Отримуємо context
        context = DependencyRegistry.get_context()

        assert context['default_merge_strategy'] == 'merge'

    def test_dependency_registry_override(self):
        """Тест: DependencyRegistry дозволяє override для конкретного випадку."""
        DependencyRegistry.reset()
        DependencyRegistry.configure(default_merge_strategy='last')

        # Override тільки стратегії
        context = DependencyRegistry.get_context(
            default_merge_strategy='newest'
        )

        assert context['default_merge_strategy'] == 'newest'

    def test_merge_strategy_context_manager(self):
        """Тест: with_merge_strategy() динамічно змінює стратегію."""
        # Створюємо два графи з однаковими node_id але різними даними
        graph1 = Graph(default_merge_strategy='last')
        node1 = Node(url="https://example.com", depth=0)
        node1.scanned = False
        node1.metadata = {"title": "Old Title"}
        graph1.add_node(node1)

        graph2 = Graph(default_merge_strategy='last')
        node2 = Node(node_id=node1.node_id, url="https://example.com", depth=0)
        node2.scanned = True
        node2.metadata = {"title": "New Title"}
        graph2.add_node(node2)

        # Default: 'last' - береться з graph2
        result_last = graph1 + graph2
        assert result_last.nodes[node1.node_id].metadata["title"] == "New Title"

        # З context: 'first' - береться з graph1
        with with_merge_strategy('first'):
            result_first = graph1 + graph2
            assert result_first.nodes[node1.node_id].metadata["title"] == "Old Title"

        # Після context повертається до 'last'
        result_after = graph1 + graph2
        assert result_after.nodes[node1.node_id].metadata["title"] == "New Title"

    def test_graph_context_fluent_api(self):
        """Тест: GraphContext fluent API для зручної конфігурації."""
        ctx = GraphContext(default_merge_strategy='last')

        # Fluent API
        ctx2 = ctx.with_merge_strategy_default('merge')

        assert ctx.default_merge_strategy == 'last'
        assert ctx2.default_merge_strategy == 'merge'


class TestMergeStrategies:
    """Тести на різні merge strategies."""

    def test_merge_strategy_last(self):
        """Тест: 'last' стратегія - береться node з другого графу."""
        graph1 = Graph(default_merge_strategy='last')
        node1 = Node(url="https://example.com", depth=0)
        node1.metadata = {"value": "first"}
        graph1.add_node(node1)

        graph2 = Graph(default_merge_strategy='last')
        node2 = Node(node_id=node1.node_id, url="https://example.com", depth=0)
        node2.metadata = {"value": "second"}
        graph2.add_node(node2)

        result = graph1 + graph2

        assert result.nodes[node1.node_id].metadata["value"] == "second"

    def test_merge_strategy_first(self):
        """Тест: 'first' стратегія - береться node з першого графу."""
        graph1 = Graph(default_merge_strategy='first')
        node1 = Node(url="https://example.com", depth=0)
        node1.metadata = {"value": "first"}
        graph1.add_node(node1)

        graph2 = Graph(default_merge_strategy='first')
        node2 = Node(node_id=node1.node_id, url="https://example.com", depth=0)
        node2.metadata = {"value": "second"}
        graph2.add_node(node2)

        result = graph1 + graph2

        assert result.nodes[node1.node_id].metadata["value"] == "first"

    def test_merge_strategy_merge(self):
        """Тест: 'merge' стратегія - об'єднується metadata."""
        graph1 = Graph(default_merge_strategy='merge')
        node1 = Node(url="https://example.com", depth=0)
        node1.metadata = {"field1": "value1", "common": "from_first"}
        graph1.add_node(node1)

        graph2 = Graph(default_merge_strategy='merge')
        node2 = Node(node_id=node1.node_id, url="https://example.com", depth=0)
        node2.metadata = {"field2": "value2", "common": "from_second"}
        graph2.add_node(node2)

        result = graph1 + graph2

        # Перевіряємо що metadata об'єднані
        merged_node = result.nodes[node1.node_id]
        assert "field1" in merged_node.metadata
        assert "field2" in merged_node.metadata
        assert merged_node.metadata["field1"] == "value1"
        assert merged_node.metadata["field2"] == "value2"
        # При конфлікті береться з другого
        assert merged_node.metadata["common"] == "from_second"


class TestDTOValidation:
    """Тести на Pydantic валідацію DTO."""

    def test_node_dto_url_validation(self):
        """Тест: NodeDTO валідує URL."""
        with pytest.raises(ValueError):
            NodeDTO(
                node_id="123",
                url="invalid-url",  # Невалідний URL
                depth=0,
                created_at=datetime.now(),
                lifecycle_stage="url_stage",
            )

    def test_node_dto_lifecycle_stage_validation(self):
        """Тест: NodeDTO валідує lifecycle_stage."""
        with pytest.raises(ValueError):
            NodeDTO(
                node_id="123",
                url="https://example.com",
                depth=0,
                created_at=datetime.now(),
                lifecycle_stage="invalid_stage",  # Невалідний stage
            )

    def test_create_node_dto_depth_validation(self):
        """Тест: CreateNodeDTO валідує depth >= 0."""
        with pytest.raises(ValueError):
            CreateNodeDTO(
                url="https://example.com",
                depth=-1,  # Негативна глибина
            )

    def test_create_node_dto_priority_validation(self):
        """Тест: CreateNodeDTO валідує priority (1-10)."""
        with pytest.raises(ValueError):
            CreateNodeDTO(
                url="https://example.com",
                priority=15,  # За межами 1-10
            )


class TestDTOSerialization:
    """Тести на серіалізацію/десеріалізацію DTO."""

    def test_node_dto_json_serialization(self):
        """Тест: NodeDTO серіалізується в JSON."""
        node_dto = NodeDTO(
            node_id="test-123",
            url="https://example.com",
            depth=0,
            should_scan=True,
            can_create_edges=True,
            scanned=False,
            metadata={"title": "Test"},
            user_data={},
            created_at=datetime.now(),
            lifecycle_stage="url_stage",
        )

        # Серіалізація
        json_str = node_dto.model_dump_json()
        assert isinstance(json_str, str)
        assert "test-123" in json_str

        # Десеріалізація
        import json
        data = json.loads(json_str)
        restored_dto = NodeDTO.model_validate(data)

        assert restored_dto.node_id == "test-123"
        assert restored_dto.url == "https://example.com"

    def test_graph_dto_json_serialization(self):
        """Тест: GraphDTO серіалізується в JSON."""
        node_dto = NodeDTO(
            node_id="test-123",
            url="https://example.com",
            depth=0,
            should_scan=True,
            can_create_edges=True,
            scanned=False,
            metadata={},
            user_data={},
            created_at=datetime.now(),
            lifecycle_stage="url_stage",
        )

        edge_dto = EdgeDTO(
            edge_id="edge-123",
            source_node_id="test-123",
            target_node_id="test-456",
            metadata={},
            created_at=datetime.now(),
        )

        stats = GraphStatsDTO(
            total_nodes=1,
            scanned_nodes=0,
            unscanned_nodes=1,
            total_edges=1,
            avg_depth=0.0,
            max_depth=0,
        )

        graph_dto = GraphDTO(
            nodes=[node_dto],
            edges=[edge_dto],
            stats=stats,
        )

        # Серіалізація
        json_str = graph_dto.model_dump_json()
        assert isinstance(json_str, str)

        # Десеріалізація
        import json
        data = json.loads(json_str)
        restored_dto = GraphDTO.model_validate(data)

        assert len(restored_dto.nodes) == 1
        assert len(restored_dto.edges) == 1
        assert restored_dto.stats.total_nodes == 1


# Запуск тестів
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
