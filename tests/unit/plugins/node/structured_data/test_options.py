"""Unit тести для StructuredDataOptions."""

import pytest
from graph_crawler.extensions.plugins.node.structured_data import (
    StructuredDataOptions,
)


class TestStructuredDataOptions:
    """Тести для StructuredDataOptions."""
    
    def test_default_options(self):
        """Тест дефолтних налаштувань."""
        options = StructuredDataOptions()
        
        # Дефолтні формати
        assert options.parse_jsonld is True
        assert options.parse_opengraph is True
        assert options.parse_twitter is True
        assert options.parse_microdata is True
        assert options.parse_rdfa is False  # Вимкнено за замовчуванням
        
        # Дефолтні ліміти
        assert options.max_jsonld_blocks == 10
        assert options.max_jsonld_size == 100_000
        assert options.max_microdata_items == 50
        assert options.max_nesting_depth == 5
        
        # Дефолтні опції
        assert options.fail_silently is True
        assert options.normalize_types is True
    
    def test_custom_options(self):
        """Тест кастомних налаштувань."""
        options = StructuredDataOptions(
            parse_rdfa=True,
            parse_twitter=False,
            max_jsonld_blocks=5,
            allowed_types=['Product', 'Article']
        )
        
        assert options.parse_rdfa is True
        assert options.parse_twitter is False
        assert options.max_jsonld_blocks == 5
        assert options.allowed_types == ['Product', 'Article']
    
    def test_allowed_types_deduplication(self):
        """Тест видалення дублікатів."""
        options = StructuredDataOptions(
            allowed_types=['Product', 'Article', 'Product']
        )
        assert options.allowed_types == ['Product', 'Article']
    
    def test_validation_limits(self):
        """Тест валідації лімітів."""
        # Мінімальні значення
        options = StructuredDataOptions(
            max_jsonld_blocks=1,
            max_nesting_depth=1
        )
        assert options.max_jsonld_blocks == 1
        assert options.max_nesting_depth == 1
