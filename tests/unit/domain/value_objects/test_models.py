"""
Тести для value objects - models.

Очікувана кількість: 20+ тестів
"""

import pytest
from graph_crawler.domain.value_objects.models import (
    DomainFilterConfig,
    PathFilterConfig,
    URLRule,
    EdgeCreationStrategy,
)


class TestEdgeCreationStrategy:
    """Тести для EdgeCreationStrategy enum."""
    
    def test_all_strategy(self):
        """ALL strategy."""
        assert EdgeCreationStrategy.ALL.value == "all"
    
    def test_new_only_strategy(self):
        """NEW_ONLY strategy."""
        assert EdgeCreationStrategy.NEW_ONLY.value == "new_only"
    
    def test_max_in_degree_strategy(self):
        """MAX_IN_DEGREE strategy."""
        assert EdgeCreationStrategy.MAX_IN_DEGREE.value == "max_in_degree"
    
    def test_same_depth_only_strategy(self):
        """SAME_DEPTH_ONLY strategy."""
        assert EdgeCreationStrategy.SAME_DEPTH_ONLY.value == "same_depth_only"
    
    def test_deeper_only_strategy(self):
        """DEEPER_ONLY strategy."""
        assert EdgeCreationStrategy.DEEPER_ONLY.value == "deeper_only"
    
    def test_first_encounter_only_strategy(self):
        """FIRST_ENCOUNTER_ONLY strategy."""
        assert EdgeCreationStrategy.FIRST_ENCOUNTER_ONLY.value == "first_encounter_only"


class TestDomainFilterConfig:
    """Тести для DomainFilterConfig."""
    
    def test_creates_with_base_domain(self):
        """Створюється з base_domain."""
        config = DomainFilterConfig(base_domain="example.com")
        
        assert config.base_domain == "example.com"
    
    def test_with_allowed_domains(self):
        """З списком дозволених доменів."""
        config = DomainFilterConfig(
            base_domain="example.com",
            allowed_domains=["example.com", "test.com"]
        )
        
        assert len(config.allowed_domains) == 2
    
    def test_with_blocked_domains(self):
        """З списком заблокованих доменів."""
        config = DomainFilterConfig(
            base_domain="example.com",
            blocked_domains=["spam.com"]
        )
        
        assert "spam.com" in config.blocked_domains
    
    def test_default_allowed_domains(self):
        """Значення allowed_domains за замовчуванням."""
        config = DomainFilterConfig(base_domain="example.com")
        
        assert "domain+subdomains" in config.allowed_domains
    
    def test_is_wildcard_allowed(self):
        """is_wildcard_allowed() метод."""
        config = DomainFilterConfig(
            base_domain="example.com",
            allowed_domains=["*"]
        )
        
        assert config.is_wildcard_allowed() is True


class TestPathFilterConfig:
    """Тести для PathFilterConfig."""
    
    def test_default_values(self):
        """Значення за замовчуванням."""
        config = PathFilterConfig()
        
        assert config.excluded_patterns == []
        assert config.included_patterns == []
    
    def test_with_excluded_patterns(self):
        """З списком excluded патернів."""
        config = PathFilterConfig(
            excluded_patterns=["/admin/*", "/private/*"]
        )
        
        assert len(config.excluded_patterns) == 2
        assert "/admin/*" in config.excluded_patterns
    
    def test_with_included_patterns(self):
        """З списком included патернів."""
        config = PathFilterConfig(
            included_patterns=["/blog/*"]
        )
        
        assert "/blog/*" in config.included_patterns


class TestURLRule:
    """Тести для URLRule."""
    
    def test_creates_with_pattern(self):
        """Створюється з патерном."""
        rule = URLRule(pattern="/blog/*")
        
        assert rule.pattern == "/blog/*"
    
    def test_default_priority(self):
        """priority за замовчуванням 5."""
        rule = URLRule(pattern="/blog/*")
        
        # За замовчуванням priority = 5
        assert rule.priority == 5
    
    def test_with_priority(self):
        """З пріоритетом."""
        rule = URLRule(pattern="/priority/*", priority=10)
        
        assert rule.priority == 10
    
    def test_with_should_scan(self):
        """З should_scan."""
        rule = URLRule(pattern="/skip/*", should_scan=False)
        
        assert rule.should_scan is False
    
    def test_with_should_follow_links(self):
        """З should_follow_links."""
        rule = URLRule(pattern="/external/*", should_follow_links=False)
        
        assert rule.should_follow_links is False
    
    def test_with_create_edge(self):
        """З create_edge."""
        rule = URLRule(pattern="/no-edge/*", create_edge=False)
        
        assert rule.create_edge is False
    
    def test_default_should_scan_none(self):
        """should_scan за замовчуванням None."""
        rule = URLRule(pattern="/test/*")
        
        assert rule.should_scan is None
    
    def test_default_should_follow_links_none(self):
        """should_follow_links за замовчуванням None."""
        rule = URLRule(pattern="/test/*")
        
        assert rule.should_follow_links is None
    
    def test_default_create_edge_none(self):
        """create_edge за замовчуванням None."""
        rule = URLRule(pattern="/test/*")
        
        assert rule.create_edge is None
    
    def test_repr(self):
        """__repr__ метод."""
        rule = URLRule(pattern="/test/*", priority=8, should_scan=True)
        
        repr_str = repr(rule)
        assert "URLRule" in repr_str
        assert "/test/*" in repr_str


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
