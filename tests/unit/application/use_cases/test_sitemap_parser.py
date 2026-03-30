"""
Тести для SitemapParser.

Перевіряє:
1. Коректність імпортів (defusedxml.ElementTree + Element type hint)
2. Парсинг sitemap XML
3. Парсинг sitemap index
4. Обробку gzip sitemap
5. Валідацію URL
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import gzip


class TestSitemapParserImports:
    """Тести для перевірки коректності імпортів."""
    
    def test_defusedxml_import(self):
        """Перевіряє, що defusedxml імпортується правильно."""
        import defusedxml.ElementTree as ET
        assert hasattr(ET, 'fromstring'), "defusedxml.ElementTree повинен мати fromstring"
        assert hasattr(ET, 'parse'), "defusedxml.ElementTree повинен мати parse"
    
    def test_element_type_available(self):
        """Перевіряє, що Element тип доступний для type hints.
        
        ВАЖЛИВО: defusedxml.ElementTree НЕ має Element атрибуту!
        Потрібно імпортувати з xml.etree.ElementTree.
        """
        from xml.etree.ElementTree import Element
        assert Element is not None
        
        # Перевіряємо, що defusedxml дійсно НЕ має Element
        import defusedxml.ElementTree as ET
        assert not hasattr(ET, 'Element'), \
            "defusedxml.ElementTree не повинен мати Element (це особливість бібліотеки)"
    
    def test_sitemap_parser_import(self):
        """Перевіряє, що SitemapParser імпортується без помилок."""
        from graph_crawler.application.use_cases.crawling.sitemap_parser import SitemapParser
        assert SitemapParser is not None
    
    def test_sitemap_parser_type_hints(self):
        """Перевіряє, що type hints в SitemapParser коректні."""
        from graph_crawler.application.use_cases.crawling.sitemap_parser import SitemapParser
        import inspect
        
        # Отримуємо сигнатуру методів
        parser = SitemapParser()
        
        # Перевіряємо, що методи з Element type hint існують і викликаються
        assert hasattr(parser, '_parse_sitemap_index')
        assert hasattr(parser, '_parse_urlset')
        
        # Перевіряємо анотації (не повинно бути ET.Element)
        source = inspect.getsource(SitemapParser)
        assert 'ET.Element' not in source, \
            "Не використовуйте ET.Element - defusedxml не має цього атрибуту. Використовуйте Element з xml.etree.ElementTree"


class TestSitemapParserXMLParsing:
    """Тести для парсингу XML."""
    
    @pytest.fixture
    def parser(self):
        """Створює екземпляр SitemapParser."""
        from graph_crawler.application.use_cases.crawling.sitemap_parser import SitemapParser
        return SitemapParser()
    
    def test_parse_urlset_basic(self, parser):
        """Тест парсингу базового urlset."""
        xml_content = b'''<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url>
                <loc>https://example.com/page1</loc>
            </url>
            <url>
                <loc>https://example.com/page2</loc>
            </url>
        </urlset>'''
        
        result = parser._parse_sitemap_content_sync(xml_content, "https://example.com/sitemap.xml")
        
        assert len(result["urls"]) == 2
        assert "https://example.com/page1" in result["urls"]
        assert "https://example.com/page2" in result["urls"]
    
    def test_parse_sitemap_index(self, parser):
        """Тест парсингу sitemap index."""
        xml_content = b'''<?xml version="1.0" encoding="UTF-8"?>
        <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <sitemap>
                <loc>https://example.com/sitemap1.xml</loc>
            </sitemap>
            <sitemap>
                <loc>https://example.com/sitemap2.xml</loc>
            </sitemap>
        </sitemapindex>'''
        
        result = parser._parse_sitemap_content_sync(xml_content, "https://example.com/sitemap_index.xml")
        
        assert len(result["sitemap_indexes"]) == 2
        assert "https://example.com/sitemap1.xml" in result["sitemap_indexes"]
    
    def test_parse_gzip_sitemap(self, parser):
        """Тест парсингу gzip-стиснутого sitemap."""
        xml_content = b'''<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url>
                <loc>https://example.com/gzip-page</loc>
            </url>
        </urlset>'''
        
        gzipped = gzip.compress(xml_content)
        
        result = parser._parse_sitemap_content_sync(gzipped, "https://example.com/sitemap.xml.gz")
        
        assert len(result["urls"]) == 1
        assert "https://example.com/gzip-page" in result["urls"]
    
    def test_parse_urlset_without_namespace(self, parser):
        """Тест парсингу urlset без namespace."""
        xml_content = b'''<?xml version="1.0" encoding="UTF-8"?>
        <urlset>
            <url>
                <loc>https://example.com/no-ns-page</loc>
            </url>
        </urlset>'''
        
        result = parser._parse_sitemap_content_sync(xml_content, "https://example.com/sitemap.xml")
        
        assert len(result["urls"]) == 1
        assert "https://example.com/no-ns-page" in result["urls"]
    
    def test_normalize_relative_url(self, parser):
        """Тест нормалізації відносних URL."""
        assert parser._normalize_url("/page", "https://example.com") == "https://example.com/page"
        assert parser._normalize_url("https://example.com/abs", "https://other.com") == "https://example.com/abs"
        assert parser._normalize_url("", "https://example.com") == ""


class TestSitemapParserRobotsTxt:
    """Тести для парсингу robots.txt."""
    
    @pytest.fixture
    def parser(self):
        from graph_crawler.application.use_cases.crawling.sitemap_parser import SitemapParser
        return SitemapParser()
    
    def test_parse_robots_txt_with_sitemap(self, parser):
        """Тест знаходження sitemap в robots.txt."""
        robots_content = """
User-agent: *
Disallow: /private/

Sitemap: https://example.com/sitemap.xml
Sitemap: https://example.com/sitemap2.xml
"""
        
        result = parser._parse_robots_txt(robots_content, "https://example.com")
        
        assert len(result) == 2
        assert "https://example.com/sitemap.xml" in result
        assert "https://example.com/sitemap2.xml" in result
    
    def test_parse_robots_txt_relative_sitemap(self, parser):
        """Тест нормалізації відносного sitemap URL."""
        robots_content = """
User-agent: *
Sitemap: /sitemap.xml
"""
        
        result = parser._parse_robots_txt(robots_content, "https://example.com")
        
        assert len(result) == 1
        assert "https://example.com/sitemap.xml" in result


class TestSitemapParserErrorHandling:
    """Тести обробки помилок."""
    
    @pytest.fixture
    def parser(self):
        from graph_crawler.application.use_cases.crawling.sitemap_parser import SitemapParser
        return SitemapParser()
    
    def test_invalid_xml(self, parser):
        """Тест обробки невалідного XML."""
        invalid_xml = b"<not valid xml"
        
        result = parser._parse_sitemap_content_sync(invalid_xml, "https://example.com/sitemap.xml")
        
        assert result["urls"] == []
        assert result["sitemap_indexes"] == []
    
    def test_invalid_gzip(self, parser):
        """Тест обробки пошкодженого gzip."""
        invalid_gzip = b'\x1f\x8b' + b'corrupted data'
        
        result = parser._parse_sitemap_content_sync(invalid_gzip, "https://example.com/sitemap.xml.gz")
        
        assert result["urls"] == []
        assert result["sitemap_indexes"] == []
    
    def test_gz_extension_with_plain_xml(self, parser):
        """Тест: файл має .gz розширення, але насправді звичайний XML (не gzip).
        
        Це часта ситуація коли сервер віддає звичайний XML з .gz розширенням.
        Наприклад: https://careers.epam.com/sitemap.xml.gz віддає XML що починається з '<?'.
        """
        # Звичайний XML контент (не стиснутий), але URL з .gz
        xml_content = b'''<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url>
                <loc>https://example.com/plain-xml-in-gz-url</loc>
            </url>
        </urlset>'''
        
        result = parser._parse_sitemap_content_sync(xml_content, "https://example.com/sitemap.xml.gz")
        
        # Повинно успішно парсити як звичайний XML
        assert "https://example.com/plain-xml-in-gz-url" in result["urls"]
    
    def test_invalid_sitemap_url(self, parser):
        """Тест валідації URL sitemap."""
        result = parser.parse_sitemap("not-a-valid-url")
        
        assert result["urls"] == []
        assert result["sitemap_indexes"] == []
