"""
Тести для Node entity.

Очікувана кількість: 50+ тестів
"""

import pytest
from datetime import datetime
from graph_crawler.domain.entities.node import Node
from graph_crawler.domain.value_objects.lifecycle import NodeLifecycle, NodeLifecycleError
from graph_crawler.shared.exceptions import InvalidURLError


class TestNodeCreation:
    """Тести створення Node."""
    
    def test_creates_node_with_valid_url(self):
        """Node створюється з валідним URL."""
        node = Node(url="https://example.com", depth=0)
        
        assert node.url == "https://example.com"
        assert node.depth == 0
        assert node.scanned is False
        assert node.should_scan is True
        assert node.can_create_edges is True
    
    def test_creates_node_with_http_url(self):
        """Node створюється з HTTP URL."""
        node = Node(url="http://example.com", depth=0)
        assert node.url == "http://example.com"
    
    def test_creates_node_with_path(self):
        """Node створюється з URL з path."""
        node = Node(url="https://example.com/page/1", depth=1)
        assert node.url == "https://example.com/page/1"
        assert node.depth == 1
    
    def test_creates_node_with_query_params(self):
        """Node створюється з URL з query параметрами."""
        node = Node(url="https://example.com/search?q=test&page=1", depth=0)
        assert "?q=test&page=1" in node.url
    
    def test_node_has_unique_id(self):
        """Node має унікальний ID."""
        node1 = Node(url="https://example.com/1", depth=0)
        node2 = Node(url="https://example.com/2", depth=0)
        
        assert node1.node_id != node2.node_id
        assert len(node1.node_id) == 36  # UUID format
    
    def test_node_has_created_at(self):
        """Node має час створення."""
        node = Node(url="https://example.com", depth=0)
        
        assert isinstance(node.created_at, datetime)
        assert node.created_at <= datetime.now()
    
    def test_node_default_lifecycle_is_url_stage(self):
        """Node починається з URL_STAGE."""
        node = Node(url="https://example.com", depth=0)
        assert node.lifecycle_stage == NodeLifecycle.URL_STAGE
    
    def test_node_default_metadata_empty(self):
        """Node має порожні metadata."""
        node = Node(url="https://example.com", depth=0)
        assert node.metadata == {}
    
    def test_node_default_user_data_empty(self):
        """Node має порожні user_data."""
        node = Node(url="https://example.com", depth=0)
        assert node.user_data == {}


class TestNodeValidation:
    """Тести валідації Node."""
    
    def test_rejects_empty_url(self):
        """Node не створюється з порожнім URL."""
        with pytest.raises(InvalidURLError, match="cannot be empty"):
            Node(url="", depth=0)
    
    def test_rejects_url_without_protocol(self):
        """Node не створюється без http/https."""
        with pytest.raises(InvalidURLError, match="must start with"):
            Node(url="example.com", depth=0)
    
    def test_rejects_ftp_url(self):
        """Node не створюється з FTP URL."""
        with pytest.raises(InvalidURLError, match="must start with"):
            Node(url="ftp://example.com", depth=0)
    
    def test_rejects_url_without_domain(self):
        """Node не створюється без домену."""
        with pytest.raises(InvalidURLError, match="valid domain"):
            Node(url="https://", depth=0)
    
    def test_rejects_negative_depth(self):
        """Node не створюється з негативною глибиною."""
        with pytest.raises(ValueError):
            Node(url="https://example.com", depth=-1)
    
    def test_accepts_zero_depth(self):
        """Node створюється з глибиною 0."""
        node = Node(url="https://example.com", depth=0)
        assert node.depth == 0
    
    def test_accepts_large_depth(self):
        """Node створюється з великою глибиною."""
        node = Node(url="https://example.com", depth=100)
        assert node.depth == 100


class TestNodePriority:
    """Тести для priority поля."""
    
    def test_default_priority_is_none(self):
        """Priority за замовчуванням None."""
        node = Node(url="https://example.com", depth=0)
        assert node.priority is None
    
    def test_can_set_priority(self):
        """Priority можна встановити."""
        node = Node(url="https://example.com", depth=0, priority=5)
        assert node.priority == 5
    
    def test_priority_min_value(self):
        """Priority мінімум 1."""
        with pytest.raises(ValueError):
            Node(url="https://example.com", depth=0, priority=0)
    
    def test_priority_max_value(self):
        """Priority максимум 10."""
        with pytest.raises(ValueError):
            Node(url="https://example.com", depth=0, priority=11)
    
    def test_priority_valid_range(self):
        """Priority в діапазоні 1-10."""
        for p in range(1, 11):
            node = Node(url=f"https://example.com/{p}", depth=0, priority=p)
            assert node.priority == p


class TestNodeShouldScan:
    """Тести для should_scan поля."""
    
    def test_default_should_scan_true(self):
        """should_scan за замовчуванням True."""
        node = Node(url="https://example.com", depth=0)
        assert node.should_scan is True
    
    def test_can_set_should_scan_false(self):
        """should_scan можна встановити False."""
        node = Node(url="https://example.com", depth=0, should_scan=False)
        assert node.should_scan is False
    
    def test_can_update_should_scan(self):
        """should_scan можна оновити."""
        node = Node(url="https://example.com", depth=0)
        node.should_scan = False
        assert node.should_scan is False


class TestNodeCanCreateEdges:
    """Тести для can_create_edges поля."""
    
    def test_default_can_create_edges_true(self):
        """can_create_edges за замовчуванням True."""
        node = Node(url="https://example.com", depth=0)
        assert node.can_create_edges is True
    
    def test_can_set_can_create_edges_false(self):
        """can_create_edges можна встановити False."""
        node = Node(url="https://example.com", depth=0, can_create_edges=False)
        assert node.can_create_edges is False


class TestNodeMarkAsScanned:
    """Тести для mark_as_scanned()."""
    
    def test_mark_as_scanned(self):
        """mark_as_scanned() встановлює scanned=True."""
        node = Node(url="https://example.com", depth=0)
        assert node.scanned is False
        
        node.mark_as_scanned()
        assert node.scanned is True
    
    def test_mark_as_scanned_idempotent(self):
        """mark_as_scanned() можна викликати декілька разів."""
        node = Node(url="https://example.com", depth=0)
        node.mark_as_scanned()
        node.mark_as_scanned()
        assert node.scanned is True


class TestNodeMetadataHelpers:
    """Тести для Law of Demeter helpers."""
    
    def test_get_title_returns_none_when_empty(self):
        """get_title() повертає None коли порожньо."""
        node = Node(url="https://example.com", depth=0)
        assert node.get_title() is None
    
    def test_get_title_returns_value(self):
        """get_title() повертає значення."""
        node = Node(url="https://example.com", depth=0)
        node.metadata["title"] = "Test Title"
        assert node.get_title() == "Test Title"
    
    def test_get_description(self):
        """get_description() працює."""
        node = Node(url="https://example.com", depth=0)
        node.metadata["description"] = "Test Description"
        assert node.get_description() == "Test Description"
    
    def test_get_h1(self):
        """get_h1() працює."""
        node = Node(url="https://example.com", depth=0)
        node.metadata["h1"] = "Main Heading"
        assert node.get_h1() == "Main Heading"
    
    def test_get_keywords(self):
        """get_keywords() працює."""
        node = Node(url="https://example.com", depth=0)
        node.metadata["keywords"] = "test, example, keywords"
        assert node.get_keywords() == "test, example, keywords"
    
    def test_get_canonical_url(self):
        """get_canonical_url() працює."""
        node = Node(url="https://example.com", depth=0)
        node.metadata["canonical_url"] = "https://example.com/canonical"
        assert node.get_canonical_url() == "https://example.com/canonical"
    
    def test_get_language(self):
        """get_language() працює."""
        node = Node(url="https://example.com", depth=0)
        node.metadata["language"] = "uk"
        assert node.get_language() == "uk"
    
    def test_get_meta_value_with_default(self):
        """get_meta_value() повертає default."""
        node = Node(url="https://example.com", depth=0)
        assert node.get_meta_value("nonexistent", "default") == "default"
    
    def test_get_meta_value_custom_key(self):
        """get_meta_value() працює з кастомним ключем."""
        node = Node(url="https://example.com", depth=0)
        node.metadata["custom_field"] = "custom_value"
        assert node.get_meta_value("custom_field") == "custom_value"


class TestNodeSerialization:
    """Тести серіалізації."""
    
    def test_model_dump_returns_dict(self):
        """model_dump() повертає dict."""
        node = Node(url="https://example.com", depth=0)
        data = node.model_dump()
        
        assert isinstance(data, dict)
        assert data["url"] == "https://example.com"
        assert data["depth"] == 0
    
    def test_model_dump_excludes_plugin_manager(self):
        """model_dump() не містить plugin_manager."""
        node = Node(url="https://example.com", depth=0)
        data = node.model_dump()
        
        assert "plugin_manager" not in data
    
    def test_model_dump_excludes_tree_parser(self):
        """model_dump() не містить tree_parser."""
        node = Node(url="https://example.com", depth=0)
        data = node.model_dump()
        
        assert "tree_parser" not in data
    
    def test_model_dump_contains_lifecycle_as_string(self):
        """model_dump() містить lifecycle_stage як string."""
        node = Node(url="https://example.com", depth=0)
        data = node.model_dump()
        
        assert data["lifecycle_stage"] == "url_stage"
    
    def test_model_dump_contains_created_at_as_iso(self):
        """model_dump() містить created_at як ISO string."""
        node = Node(url="https://example.com", depth=0)
        data = node.model_dump()
        
        assert isinstance(data["created_at"], str)
        # Перевіряємо що це валідна ISO дата
        datetime.fromisoformat(data["created_at"])
    
    def test_round_trip_serialization(self):
        """Серіалізація → десеріалізація зберігає дані."""
        original = Node(
            url="https://example.com/page",
            depth=2,
            should_scan=False,
            priority=5
        )
        original.metadata["title"] = "Test Page"
        original.user_data["custom"] = "value"
        
        # Серіалізація
        data = original.model_dump()
        
        # Десеріалізація
        restored = Node.model_validate(data)
        
        assert restored.url == original.url
        assert restored.depth == original.depth
        assert restored.should_scan == original.should_scan
        assert restored.priority == original.priority
        assert restored.metadata["title"] == "Test Page"
        assert restored.user_data["custom"] == "value"


class TestNodeRepr:
    """Тести __repr__."""
    
    def test_repr_contains_url(self):
        """__repr__ містить URL."""
        node = Node(url="https://example.com", depth=0)
        repr_str = repr(node)
        
        assert "https://example.com" in repr_str
    
    def test_repr_contains_lifecycle(self):
        """__repr__ містить lifecycle."""
        node = Node(url="https://example.com", depth=0)
        repr_str = repr(node)
        
        assert "url_stage" in repr_str
    
    def test_repr_contains_scanned(self):
        """__repr__ містить scanned."""
        node = Node(url="https://example.com", depth=0)
        repr_str = repr(node)
        
        assert "scanned=False" in repr_str


class TestNodeRestoreDependencies:
    """Тести restore_dependencies()."""
    
    def test_restore_plugin_manager(self):
        """Відновлення plugin_manager."""
        node = Node(url="https://example.com", depth=0)
        assert node.plugin_manager is None
        
        mock_pm = object()
        node.restore_dependencies(plugin_manager=mock_pm)
        
        assert node.plugin_manager is mock_pm
    
    def test_restore_tree_parser(self):
        """Відновлення tree_parser."""
        node = Node(url="https://example.com", depth=0)
        assert node.tree_parser is None
        
        mock_parser = object()
        node.restore_dependencies(tree_parser=mock_parser)
        
        assert node.tree_parser is mock_parser
    
    def test_restore_hash_strategy(self):
        """Відновлення hash_strategy."""
        node = Node(url="https://example.com", depth=0)
        assert node.hash_strategy is None
        
        mock_strategy = object()
        node.restore_dependencies(hash_strategy=mock_strategy)
        
        assert node.hash_strategy is mock_strategy
    
    def test_restore_multiple_dependencies(self):
        """Відновлення декількох залежностей."""
        node = Node(url="https://example.com", depth=0)
        
        mock_pm = object()
        mock_parser = object()
        
        node.restore_dependencies(
            plugin_manager=mock_pm,
            tree_parser=mock_parser
        )
        
        assert node.plugin_manager is mock_pm
        assert node.tree_parser is mock_parser


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
