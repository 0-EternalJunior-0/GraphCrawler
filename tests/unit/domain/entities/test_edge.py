"""
Тести для Edge entity.

Очікувана кількість: 20+ тестів
"""

import pytest
from graph_crawler.domain.entities.edge import Edge


class TestEdgeCreation:
    """Тести створення Edge."""
    
    def test_creates_edge_with_source_and_target(self):
        """Edge створюється з source та target."""
        edge = Edge(source_node_id="node1", target_node_id="node2")
        
        assert edge.source_node_id == "node1"
        assert edge.target_node_id == "node2"
    
    def test_edge_has_unique_id(self):
        """Edge має унікальний ID."""
        edge1 = Edge(source_node_id="node1", target_node_id="node2")
        edge2 = Edge(source_node_id="node1", target_node_id="node2")
        
        assert edge1.edge_id != edge2.edge_id
        assert len(edge1.edge_id) == 36  # UUID format
    
    def test_edge_default_metadata_empty(self):
        """Edge має порожні metadata."""
        edge = Edge(source_node_id="node1", target_node_id="node2")
        assert edge.metadata == {}
    
    def test_edge_with_custom_id(self):
        """Edge з кастомним ID."""
        edge = Edge(
            source_node_id="node1",
            target_node_id="node2",
            edge_id="custom-edge-id"
        )
        assert edge.edge_id == "custom-edge-id"


class TestEdgeMetadata:
    """Тести для metadata."""
    
    def test_add_metadata(self):
        """add_metadata() додає метадані."""
        edge = Edge(source_node_id="node1", target_node_id="node2")
        edge.add_metadata("anchor_text", "Click here")
        
        assert edge.metadata["anchor_text"] == "Click here"
    
    def test_add_multiple_metadata(self):
        """Додавання декількох метаданих."""
        edge = Edge(source_node_id="node1", target_node_id="node2")
        edge.add_metadata("anchor_text", "Click here")
        edge.add_metadata("rel", "nofollow")
        edge.add_metadata("target", "_blank")
        
        assert len(edge.metadata) == 3
        assert edge.metadata["anchor_text"] == "Click here"
        assert edge.metadata["rel"] == "nofollow"
        assert edge.metadata["target"] == "_blank"
    
    def test_overwrite_metadata(self):
        """Перезапис метаданих."""
        edge = Edge(source_node_id="node1", target_node_id="node2")
        edge.add_metadata("key", "value1")
        edge.add_metadata("key", "value2")
        
        assert edge.metadata["key"] == "value2"
    
    def test_get_meta_value(self):
        """get_meta_value() повертає значення."""
        edge = Edge(source_node_id="node1", target_node_id="node2")
        edge.add_metadata("anchor_text", "Click here")
        
        assert edge.get_meta_value("anchor_text") == "Click here"
    
    def test_get_meta_value_default(self):
        """get_meta_value() повертає default."""
        edge = Edge(source_node_id="node1", target_node_id="node2")
        
        assert edge.get_meta_value("nonexistent") is None
        assert edge.get_meta_value("nonexistent", "default") == "default"
    
    def test_metadata_various_types(self):
        """Метадані різних типів."""
        edge = Edge(source_node_id="node1", target_node_id="node2")
        edge.add_metadata("string", "text")
        edge.add_metadata("number", 42)
        edge.add_metadata("boolean", True)
        edge.add_metadata("list", [1, 2, 3])
        edge.add_metadata("dict", {"nested": "value"})
        
        assert edge.metadata["string"] == "text"
        assert edge.metadata["number"] == 42
        assert edge.metadata["boolean"] is True
        assert edge.metadata["list"] == [1, 2, 3]
        assert edge.metadata["dict"] == {"nested": "value"}


class TestEdgeSerialization:
    """Тести серіалізації."""
    
    def test_model_dump_returns_dict(self):
        """model_dump() повертає dict."""
        edge = Edge(source_node_id="node1", target_node_id="node2")
        data = edge.model_dump()
        
        assert isinstance(data, dict)
        assert data["source_node_id"] == "node1"
        assert data["target_node_id"] == "node2"
    
    def test_model_dump_contains_all_fields(self):
        """model_dump() містить всі поля."""
        edge = Edge(source_node_id="node1", target_node_id="node2")
        edge.add_metadata("key", "value")
        data = edge.model_dump()
        
        assert "source_node_id" in data
        assert "target_node_id" in data
        assert "edge_id" in data
        assert "metadata" in data
        assert data["metadata"]["key"] == "value"
    
    def test_round_trip_serialization(self):
        """Серіалізація → десеріалізація зберігає дані."""
        original = Edge(
            source_node_id="node1",
            target_node_id="node2",
            edge_id="test-edge"
        )
        original.add_metadata("anchor_text", "Click here")
        original.add_metadata("rel", "nofollow")
        
        # Серіалізація
        data = original.model_dump()
        
        # Десеріалізація
        restored = Edge.model_validate(data)
        
        assert restored.source_node_id == original.source_node_id
        assert restored.target_node_id == original.target_node_id
        assert restored.edge_id == original.edge_id
        assert restored.metadata == original.metadata


class TestEdgeRepr:
    """Тести __repr__."""
    
    def test_repr_contains_source(self):
        """__repr__ містить source."""
        edge = Edge(source_node_id="source123", target_node_id="target456")
        repr_str = repr(edge)
        
        assert "source12" in repr_str  # Перші 8 символів
    
    def test_repr_contains_target(self):
        """__repr__ містить target."""
        edge = Edge(source_node_id="source123", target_node_id="target456")
        repr_str = repr(edge)
        
        assert "target45" in repr_str  # Перші 8 символів


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
