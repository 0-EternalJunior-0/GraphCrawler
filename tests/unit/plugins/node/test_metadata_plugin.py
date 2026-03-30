"""Тести для MetadataExtractorPlugin.

Тестує витягування базових та SEO метаданих:
- title, description, keywords, h1
- canonical_url
- robots директиви
- hreflang альтернативи
"""

import pytest

from graph_crawler.extensions.plugins.node.base import NodePluginContext, NodePluginType
from graph_crawler.extensions.plugins.node.metadata import MetadataExtractorPlugin
from graph_crawler.infrastructure.adapters.beautifulsoup_adapter import BeautifulSoupAdapter

class MockNode:
    """Mock Node для тестів."""
    def __init__(self, url: str = "https://example.com/page"):
        self.url = url

@pytest.fixture
def plugin():
    """Створює екземпляр плагіну."""
    return MetadataExtractorPlugin()

@pytest.fixture
def parser():
    """Створює BeautifulSoup adapter."""
    return BeautifulSoupAdapter()

def create_context(html: str, url: str = "https://example.com/page") -> NodePluginContext:
    """Створює контекст з HTML."""
    parser = BeautifulSoupAdapter()
    parser.parse(html)

    return NodePluginContext(
        node=MockNode(url),
        url=url,
        depth=0,
        should_scan=True,
        can_create_edges=True,
        html=html,
        html_tree=parser.tree,
        parser=parser,
    )

class TestMetadataExtractorPluginBasic:
    """Тести базових метаданих."""

    def test_plugin_type(self, plugin):
        """Перевіряє тип плагіну."""
        assert plugin.plugin_type == NodePluginType.ON_HTML_PARSED

    def test_plugin_name(self, plugin):
        """Перевіряє назву плагіну."""
        assert plugin.name == "MetadataExtractorPlugin"

    def test_extract_title(self, plugin):
        """Тест витягування title."""
        html = "<html><head><title>Test Title</title></head></html>"
        context = create_context(html)

        result = plugin.execute(context)

        assert result.metadata.get("title") == "Test Title"

    def test_extract_description(self, plugin):
        """Тест витягування description."""
        html = '<html><head><meta name="description" content="Test description"></head></html>'
        context = create_context(html)

        result = plugin.execute(context)

        assert result.metadata.get("description") == "Test description"

    def test_extract_keywords(self, plugin):
        """Тест витягування keywords."""
        html = '<html><head><meta name="keywords" content="test, keywords, seo"></head></html>'
        context = create_context(html)

        result = plugin.execute(context)

        assert result.metadata.get("keywords") == "test, keywords, seo"

    def test_extract_h1(self, plugin):
        """Тест витягування h1."""
        html = "<html><body><h1>Main Heading</h1></body></html>"
        context = create_context(html)

        result = plugin.execute(context)

        assert result.metadata.get("h1") == "Main Heading"

class TestCanonicalUrl:
    """Тести для canonical URL."""

    def test_extract_canonical_absolute(self, plugin):
        """Тест витягування абсолютного canonical URL."""
        html = '''
        <html>
        <head>
            <link rel="canonical" href="https://example.com/canonical-page">
        </head>
        </html>
        '''
        context = create_context(html)

        result = plugin.execute(context)

        assert result.metadata.get("canonical_url") == "https://example.com/canonical-page"

    def test_extract_canonical_relative(self, plugin):
        """Тест витягування відносного canonical URL."""
        html = '''
        <html>
        <head>
            <link rel="canonical" href="/page/canonical">
        </head>
        </html>
        '''
        context = create_context(html, url="https://example.com/current")

        result = plugin.execute(context)

        assert result.metadata.get("canonical_url") == "https://example.com/page/canonical"

    def test_no_canonical(self, plugin):
        """Тест коли canonical відсутній."""
        html = "<html><head><title>No canonical</title></head></html>"
        context = create_context(html)

        result = plugin.execute(context)

        assert result.metadata.get("canonical_url") is None

class TestRobotsDirectives:
    """Тести для robots директив."""

    def test_extract_robots_noindex_nofollow(self, plugin):
        """Тест витягування noindex, nofollow."""
        html = '''
        <html>
        <head>
            <meta name="robots" content="noindex, nofollow">
        </head>
        </html>
        '''
        context = create_context(html)

        result = plugin.execute(context)
        robots = result.metadata.get("robots", {})

        assert robots.get("noindex") is True
        assert robots.get("nofollow") is True
        assert "noindex, nofollow" in robots.get("content", "")

    def test_extract_robots_none(self, plugin):
        """Тест директиви 'none' (= noindex + nofollow)."""
        html = '''
        <html>
        <head>
            <meta name="robots" content="none">
        </head>
        </html>
        '''
        context = create_context(html)

        result = plugin.execute(context)
        robots = result.metadata.get("robots", {})

        assert robots.get("noindex") is True
        assert robots.get("nofollow") is True

    def test_extract_robots_noarchive_nosnippet(self, plugin):
        """Тест витягування noarchive, nosnippet."""
        html = '''
        <html>
        <head>
            <meta name="robots" content="noarchive, nosnippet, noimageindex">
        </head>
        </html>
        '''
        context = create_context(html)

        result = plugin.execute(context)
        robots = result.metadata.get("robots", {})

        assert robots.get("noarchive") is True
        assert robots.get("nosnippet") is True
        assert robots.get("noimageindex") is True

    def test_extract_googlebot_specific(self, plugin):
        """Тест витягування googlebot специфічних директив."""
        html = '''
        <html>
        <head>
            <meta name="robots" content="index, follow">
            <meta name="googlebot" content="noindex, max-image-preview:large">
        </head>
        </html>
        '''
        context = create_context(html)

        result = plugin.execute(context)
        robots = result.metadata.get("robots", {})

        # Основні robots - index, follow
        assert robots.get("index") is True
        assert robots.get("follow") is True

        # Googlebot специфічні
        googlebot = robots.get("googlebot", {})
        assert googlebot.get("noindex") is True
        assert "max-image-preview:large" in googlebot.get("content", "")

    def test_extract_bingbot_specific(self, plugin):
        """Тест витягування bingbot специфічних директив."""
        html = '''
        <html>
        <head>
            <meta name="bingbot" content="noarchive, nocache">
        </head>
        </html>
        '''
        context = create_context(html)

        result = plugin.execute(context)
        robots = result.metadata.get("robots", {})

        bingbot = robots.get("bingbot", {})
        assert bingbot.get("noarchive") is True
        assert bingbot.get("nocache") is True

    def test_no_robots(self, plugin):
        """Тест коли robots директиви відсутні."""
        html = "<html><head><title>No robots</title></head></html>"
        context = create_context(html)

        result = plugin.execute(context)

        assert result.metadata.get("robots") is None or result.metadata.get("robots") == {}

class TestHreflang:
    """Тести для hreflang."""

    def test_extract_hreflang_multiple(self, plugin):
        """Тест витягування кількох hreflang."""
        html = '''
        <html>
        <head>
            <link rel="alternate" hreflang="en" href="https://example.com/en/page">
            <link rel="alternate" hreflang="uk" href="https://example.com/uk/page">
            <link rel="alternate" hreflang="de" href="https://example.com/de/page">
            <link rel="alternate" hreflang="x-default" href="https://example.com/page">
        </head>
        </html>
        '''
        context = create_context(html)

        result = plugin.execute(context)
        hreflang = result.metadata.get("hreflang", [])

        assert len(hreflang) == 4

        # Перевіряємо наявність всіх мов
        languages = {item["hreflang"] for item in hreflang}
        assert "en" in languages
        assert "uk" in languages
        assert "de" in languages
        assert "x-default" in languages

        # Перевіряємо URL
        en_item = next(item for item in hreflang if item["hreflang"] == "en")
        assert en_item["href"] == "https://example.com/en/page"

    def test_extract_hreflang_relative(self, plugin):
        """Тест витягування hreflang з відносними URL."""
        html = '''
        <html>
        <head>
            <link rel="alternate" hreflang="en" href="/en/page">
            <link rel="alternate" hreflang="uk" href="/uk/page">
        </head>
        </html>
        '''
        context = create_context(html, url="https://example.com/current")

        result = plugin.execute(context)
        hreflang = result.metadata.get("hreflang", [])

        assert len(hreflang) == 2

        en_item = next(item for item in hreflang if item["hreflang"] == "en")
        assert en_item["href"] == "https://example.com/en/page"

    def test_no_hreflang(self, plugin):
        """Тест коли hreflang відсутній."""
        html = "<html><head><title>No hreflang</title></head></html>"
        context = create_context(html)

        result = plugin.execute(context)

        hreflang = result.metadata.get("hreflang", [])
        assert hreflang == [] or hreflang is None

    def test_hreflang_without_href(self, plugin):
        """Тест hreflang без href (не має додаватися)."""
        html = '''
        <html>
        <head>
            <link rel="alternate" hreflang="en">
            <link rel="alternate" hreflang="uk" href="https://example.com/uk/page">
        </head>
        </html>
        '''
        context = create_context(html)

        result = plugin.execute(context)
        hreflang = result.metadata.get("hreflang", [])

        # Тільки один валідний запис
        assert len(hreflang) == 1
        assert hreflang[0]["hreflang"] == "uk"

class TestComplexPage:
    """Тести комплексної сторінки з усіма метаданими."""

    def test_extract_all_metadata(self, plugin):
        """Тест витягування всіх метаданих з комплексної сторінки."""
        html = '''
        <!DOCTYPE html>
        <html lang="en">
        '''
        context = create_context(html, url="https://example.com/page")

        result = plugin.execute(context)
        metadata = result.metadata

        # Базові метадані
        assert metadata.get("title") == "Complex Page Title"
        assert metadata.get("description") == "Complex page description for SEO"
        assert metadata.get("keywords") == "complex, seo, test"
        assert metadata.get("h1") == "Complex Page H1"

        # Canonical
        assert metadata.get("canonical_url") == "https://example.com/canonical"

        # Robots
        robots = metadata.get("robots", {})
        assert robots.get("index") is True
        assert robots.get("follow") is True
        assert robots.get("max_snippet") is True

        # Googlebot
        googlebot = robots.get("googlebot", {})
        assert googlebot.get("index") is True
        assert googlebot.get("max_image_preview") is True

        # Hreflang
        hreflang = metadata.get("hreflang", [])
        assert len(hreflang) == 3
        languages = {item["hreflang"] for item in hreflang}
        assert languages == {"en", "uk", "x-default"}

class TestEdgeCases:
    """Тести граничних випадків."""

    def test_skip_metadata_extraction(self, plugin):
        """Тест пропуску витягування метаданих."""
        html = "<html><head><title>Test</title></head></html>"
        context = create_context(html)
        context.skip_metadata_extraction = True

        result = plugin.execute(context)

        assert result.metadata.get("title") is None

    def test_no_parser(self, plugin):
        """Тест без parser."""
        context = NodePluginContext(
            node=MockNode(),
            url="https://example.com",
            depth=0,
            should_scan=True,
            can_create_edges=True,
            html="<html></html>",
            parser=None,
        )

        result = plugin.execute(context)

        # Не має бути помилки, просто порожні метадані
        assert result.metadata == {}

    def test_malformed_html(self, plugin):
        """Тест з пошкодженим HTML."""
        html = '''
        <html>
        <head>
            <title>Broken Title
            <meta name="description" content="Broken description
            <link rel="canonical" href="https://example.com/page"
        </head>
        <body>
            <h1>Broken H1
        </body>
        '''
        context = create_context(html)

        # Не має бути помилки
        result = plugin.execute(context)

        # BeautifulSoup має обробити навіть зламаний HTML
        assert result is not None

    def test_empty_html(self, plugin):
        """Тест з порожнім HTML."""
        html = ""
        parser = BeautifulSoupAdapter()
        parser.parse(html)

        context = NodePluginContext(
            node=MockNode(),
            url="https://example.com",
            depth=0,
            should_scan=True,
            can_create_edges=True,
            html=html,
            html_tree=parser.tree,
            parser=parser,
        )

        result = plugin.execute(context)

        # Порожні метадані, але без помилки
        assert result.metadata == {} or all(v is None for v in result.metadata.values())

    def test_sanitize_whitespace(self, plugin):
        """Тест санітизації пробілів."""
        html = '''
        <html>
        <head>
            <title>  Multiple    spaces   in   title  </title>
            <meta name="description" content="  Spaces   everywhere  ">
        </head>
        <body>
            <h1>  H1   with   spaces  </h1>
        </body>
        </html>
        '''
        context = create_context(html)

        result = plugin.execute(context)

        assert result.metadata.get("title") == "Multiple spaces in title"
        assert result.metadata.get("description") == "Spaces everywhere"
        assert result.metadata.get("h1") == "H1 with spaces"

class TestLanguageExtraction:
    """Тести для витягування language з <html lang="">."""

    def test_extract_language_simple(self, plugin):
        """Тест витягування простого language коду."""
        html = '<html lang="en"><head><title>Test</title></head></html>'
        context = create_context(html)

        result = plugin.execute(context)

        assert result.metadata.get("language") == "en"

    def test_extract_language_with_region(self, plugin):
        """Тест витягування language з регіоном."""
        html = '<html lang="en-US"><head><title>Test</title></head></html>'
        context = create_context(html)

        result = plugin.execute(context)

        assert result.metadata.get("language") == "en-us"

    def test_extract_language_ukrainian(self, plugin):
        """Тест витягування української мови."""
        html = '<html lang="uk"><head><title>Тест</title></head></html>'
        context = create_context(html)

        result = plugin.execute(context)

        assert result.metadata.get("language") == "uk"

    def test_extract_language_uppercase(self, plugin):
        """Тест нормалізації до lowercase."""
        html = '<html lang="EN-GB"><head><title>Test</title></head></html>'
        context = create_context(html)

        result = plugin.execute(context)

        assert result.metadata.get("language") == "en-gb"

    def test_no_language_attribute(self, plugin):
        """Тест коли lang атрибут відсутній."""
        html = '<html><head><title>Test</title></head></html>'
        context = create_context(html)

        result = plugin.execute(context)

        assert result.metadata.get("language") is None

    def test_empty_language_attribute(self, plugin):
        """Тест порожнього lang атрибуту."""
        html = '<html lang=""><head><title>Test</title></head></html>'
        context = create_context(html)

        result = plugin.execute(context)

        # Порожній рядок не повинен зберігатися
        lang = result.metadata.get("language")
        assert lang is None or lang == ""

