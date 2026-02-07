"""Unit тести для StructuredDataResult."""

import pytest
from graph_crawler.extensions.plugins.node.structured_data import (
    StructuredDataResult,
    SchemaType,
)


class TestStructuredDataResult:
    """Тести для StructuredDataResult."""
    
    def test_empty_result(self):
        """Тест порожнього результату."""
        result = StructuredDataResult.empty()
        assert result.has_data is False
        assert result.primary_type is None
        assert result.jsonld_count == 0
        assert result.microdata_count == 0
    
    def test_with_error(self):
        """Тест результату з помилкою."""
        result = StructuredDataResult.with_error("Test error")
        assert len(result.errors) == 1
        assert "Test error" in result.errors[0]
        assert result.has_data is False
    
    def test_has_data_with_jsonld(self):
        """Тест has_data з JSON-LD."""
        result = StructuredDataResult(
            jsonld=[{'@type': 'Product', 'name': 'Test'}]
        )
        assert result.has_data is True
        assert result.jsonld_count == 1
    
    def test_has_data_with_opengraph(self):
        """Тест has_data з Open Graph."""
        result = StructuredDataResult(
            opengraph={'title': 'Test', 'type': 'article'}
        )
        assert result.has_data is True
    
    def test_get_property_jsonld_priority(self):
        """JSON-LD має пріоритет над Open Graph."""
        result = StructuredDataResult(
            jsonld=[{'name': 'JSON-LD Name'}],
            opengraph={'title': 'OG Title'},
        )
        # 'name' з JSON-LD
        assert result.get_property('name') == 'JSON-LD Name'
        # 'title' fallback на OG
        assert result.get_property('title') == 'OG Title'
    
    def test_get_property_default(self):
        """Тест значення за замовчуванням."""
        result = StructuredDataResult()
        assert result.get_property('nonexistent') is None
        assert result.get_property('nonexistent', 'default') == 'default'
    
    def test_get_all_of_type(self):
        """Тест отримання об'єктів за типом."""
        result = StructuredDataResult(
            jsonld=[
                {'@type': 'Product', 'name': 'Product 1'},
                {'@type': 'Article', 'headline': 'Article'},
                {'@type': 'Product', 'name': 'Product 2'},
            ]
        )
        products = result.get_all_of_type('Product')
        assert len(products) == 2
        assert products[0]['name'] == 'Product 1'
        assert products[1]['name'] == 'Product 2'
    
    def test_has_type(self):
        """Тест перевірки наявності типу."""
        result = StructuredDataResult(all_types={'Product', 'Offer'})
        assert result.has_type('Product') is True
        assert result.has_type('Article') is False
    
    def test_get_type(self):
        """Тест отримання основного типу."""
        result = StructuredDataResult(
            primary_type='Product',
            all_types={'Product', 'Offer'}
        )
        assert result.get_type() == 'Product'
    
    def test_get_type_from_all_types(self):
        """Тест отримання типу з all_types."""
        result = StructuredDataResult(
            all_types={'Article'}
        )
        assert result.get_type() == 'Article'


class TestSchemaType:
    """Тести для SchemaType enum."""
    
    def test_schema_types_exist(self):
        """Перевірка основних типів."""
        assert SchemaType.ARTICLE == "Article"
        assert SchemaType.PRODUCT == "Product"
        assert SchemaType.JOB_POSTING == "JobPosting"
        assert SchemaType.RECIPE == "Recipe"
