"""Unit тести для JSON-LD парсера."""

import pytest
from graph_crawler.extensions.plugins.node.structured_data import (
    JsonLdParser,
    StructuredDataOptions,
)


class TestJsonLdParser:
    """Тести для JsonLdParser."""
    
    def setup_method(self):
        """Ініціалізація перед кожним тестом."""
        self.parser = JsonLdParser()
        self.options = StructuredDataOptions()
    
    def test_parser_name(self):
        """Тест імені парсера."""
        assert self.parser.name == "jsonld"
    
    def test_can_parse_valid_html(self):
        """Тест can_parse для валідного HTML."""
        html = '<script type="application/ld+json">{}</script>'
        assert self.parser.can_parse(html) is True
    
    def test_can_parse_invalid_html(self):
        """Тест can_parse для невалідного HTML."""
        html = '<html><body>No JSON-LD</body></html>'
        assert self.parser.can_parse(html) is False
    
    def test_parse_simple_jsonld(self):
        """Тест парсингу простого JSON-LD."""
        html = '''
        <html>
        <head>
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "Article",
                "headline": "Test Article",
                "author": "John Doe"
            }
            </script>
        </head>
        </html>
        '''
        
        results = self.parser.parse(html, self.options)
        
        assert len(results) == 1
        assert results[0]['@type'] == 'Article'
        assert results[0]['headline'] == 'Test Article'
    
    def test_parse_multiple_jsonld(self):
        """Тест парсингу кількох JSON-LD блоків."""
        html = '''
        <html>
        <head>
            <script type="application/ld+json">
            {"@type": "Article", "headline": "First"}
            </script>
            <script type="application/ld+json">
            {"@type": "Product", "name": "Second"}
            </script>
        </head>
        </html>
        '''
        
        results = self.parser.parse(html, self.options)
        
        assert len(results) == 2
        assert results[0]['@type'] == 'Article'
        assert results[1]['@type'] == 'Product'
    
    def test_parse_invalid_json(self):
        """Тест обробки невалідного JSON."""
        html = '''
        <script type="application/ld+json">
        {invalid json}
        </script>
        '''
        
        results = self.parser.parse(html, self.options)
        assert len(results) == 0  # Невалідний JSON пропускається
    
    def test_max_blocks_limit(self):
        """Тест ліміту блоків."""
        # Створюємо 15 блоків
        blocks = ''.join([
            f'<script type="application/ld+json">{{"@type": "Item{i}"}}</script>'
            for i in range(15)
        ])
        html = f'<html>{blocks}</html>'
        
        options = StructuredDataOptions(max_jsonld_blocks=5)
        results = self.parser.parse(html, options)
        
        assert len(results) == 5  # Обмежено до 5
