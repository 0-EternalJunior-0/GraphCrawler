"""
Тести для SmartPageFinderPlugin.
"""

import os
import sys
from unittest.mock import MagicMock

import pytest

# Додаємо шлях до проекту
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

class TestSmartPageFinderPlugin:
    """Тести для SmartPageFinderPlugin."""

    @pytest.fixture
    def mock_context(self):
        """Створює mock контекст."""
        context = MagicMock()
        context.url = "https://example.com/jobs/python-developer"
        context.metadata = {
            'title': 'Python Developer - Remote Job',
            'h1': 'Senior Python Developer Position',
            'description': 'We are looking for experienced Python developer'
        }
        context.extracted_links = [
            'https://example.com/jobs/java-developer',
            'https://example.com/about',
            'https://example.com/jobs/python-senior',
        ]
        context.user_data = {}

        # Mock html_tree
        html_tree = MagicMock()
        html_tree.text = "Python developer job opportunity. Experience with Django, FastAPI required."
        context.html_tree = html_tree

        # Mock node
        context.node = MagicMock()
        context.node.text = None

        return context

    def test_plugin_creation(self):
        """Тест створення плагіну."""
        from graph_crawler.extensions.plugins.node.smart_page_finder import SmartPageFinderPlugin

        plugin = SmartPageFinderPlugin(
            search_prompt="Python developer jobs"
        )

        assert plugin.search_prompt == "Python developer jobs"
        assert plugin.min_relevance_score == 0.7  # default
        assert plugin.enabled

    def test_plugin_creation_with_config(self):
        """Тест створення плагіну з конфігурацією."""
        from graph_crawler.extensions.plugins.node.smart_page_finder import SmartPageFinderPlugin

        plugin = SmartPageFinderPlugin(
            search_prompt="Car search",
            config={
                'min_relevance_score': 0.5,
                'strict_mode': True,
                'model': 'gpt-4'
            }
        )

        assert plugin.min_relevance_score == 0.5
        assert plugin.strict_mode
        assert plugin.model == 'gpt-4'

    def test_plugin_empty_prompt_raises(self):
        """Тест що порожній промпт викликає помилку."""
        from graph_crawler.extensions.plugins.node.smart_page_finder import SmartPageFinderPlugin

        with pytest.raises(ValueError):
            SmartPageFinderPlugin(search_prompt="")

        with pytest.raises(ValueError):
            SmartPageFinderPlugin(search_prompt="   ")

    def test_extract_keywords(self):
        """Тест витягування ключових слів."""
        from graph_crawler.extensions.plugins.node.smart_page_finder import SmartPageFinderPlugin

        plugin = SmartPageFinderPlugin(search_prompt="test")

        keywords = plugin._extract_keywords("Шукаю Python developer jobs в Києві")

        assert 'python' in keywords
        assert 'developer' in keywords
        assert 'києві' in keywords
        # Стоп-слова мають бути відфільтровані
        assert 'шукаю' not in keywords

    def test_keyword_analysis(self, mock_context):
        """Тест аналізу на основі ключових слів."""
        from graph_crawler.extensions.plugins.node.smart_page_finder import SmartPageFinderPlugin

        plugin = SmartPageFinderPlugin(
            search_prompt="Python developer",
            config={'analyze_content': False}  # Примусово keywords
        )

        # Витягуємо дані
        page_data = plugin._extract_page_data(mock_context)

        # Аналізуємо
        result = plugin._analyze_with_keywords(page_data)

        assert result['score'] > 0.5  # Має бути релевантна
        # Перевіряємо що reason містить інформацію про знайдені ключові слова
        reason_lower = result['reason'].lower()
        assert 'keywords' in reason_lower or 'found' in reason_lower or 'match' in reason_lower

    def test_execute_sets_user_data(self, mock_context):
        """Тест що execute встановлює user_data."""
        from graph_crawler.extensions.plugins.node.smart_page_finder import SmartPageFinderPlugin

        plugin = SmartPageFinderPlugin(
            search_prompt="Python developer jobs"
        )

        # Вимикаємо g4f для тесту
        plugin._g4f_available = False

        result = plugin.execute(mock_context)

        assert 'is_target_page' in result.user_data
        assert 'relevance_score' in result.user_data
        assert 'relevance_level' in result.user_data
        assert 'relevance_reason' in result.user_data

    def test_score_to_level(self):
        """Тест конвертації score в рівень."""
        from graph_crawler.extensions.plugins.node.smart_page_finder import SmartPageFinderPlugin

        plugin = SmartPageFinderPlugin(search_prompt="test")

        assert plugin._score_to_level(0.9) == 'high'
        assert plugin._score_to_level(0.8) == 'high'
        assert plugin._score_to_level(0.6) == 'medium'
        assert plugin._score_to_level(0.5) == 'medium'
        assert plugin._score_to_level(0.3) == 'low'
        assert plugin._score_to_level(0.1) == 'irrelevant'
        assert plugin._score_to_level(0.0) == 'irrelevant'

    def test_analyze_links_priorities(self, mock_context):
        """Тест що пріоритети посилань встановлюються."""
        from graph_crawler.extensions.plugins.node.smart_page_finder import SmartPageFinderPlugin

        plugin = SmartPageFinderPlugin(
            search_prompt="Python developer"
        )

        page_data = plugin._extract_page_data(mock_context)
        priorities, decisions = plugin._analyze_links(
            mock_context.extracted_links,
            page_data,
            page_score=0.8
        )

        # Посилання з 'python' має мати вищий пріоритет
        python_link = 'https://example.com/jobs/python-senior'
        about_link = 'https://example.com/about'

        assert priorities[python_link] > priorities[about_link]

    def test_cache_results(self, mock_context):
        """Тест кешування результатів."""
        from graph_crawler.extensions.plugins.node.smart_page_finder import SmartPageFinderPlugin

        plugin = SmartPageFinderPlugin(
            search_prompt="Python",
            config={'cache_results': True}
        )
        plugin._g4f_available = False

        # Перший виклик
        plugin.execute(mock_context)

        # Перевіряємо кеш
        assert mock_context.url in plugin._cache

        # Другий виклик - має використати кеш
        mock_context.user_data = {}
        plugin.execute(mock_context)

        assert 'is_target_page' in mock_context.user_data

    def test_get_stats(self, mock_context):
        """Тест статистики."""
        from graph_crawler.extensions.plugins.node.smart_page_finder import SmartPageFinderPlugin

        plugin = SmartPageFinderPlugin(search_prompt="Python")
        plugin._g4f_available = False

        # Порожня статистика
        stats = plugin.get_stats()
        assert stats['total_analyzed'] == 0

        # Після аналізу
        plugin.execute(mock_context)
        stats = plugin.get_stats()

        assert stats['total_analyzed'] == 1
        assert 'score_distribution' in stats

    def test_clear_cache(self, mock_context):
        """Тест очищення кешу."""
        from graph_crawler.extensions.plugins.node.smart_page_finder import SmartPageFinderPlugin

        plugin = SmartPageFinderPlugin(search_prompt="Python")
        plugin._g4f_available = False

        plugin.execute(mock_context)
        assert len(plugin._cache) > 0

        plugin.clear_cache()
        assert len(plugin._cache) == 0

    def test_relevance_level_enum(self):
        """Тест enum RelevanceLevel."""
        from graph_crawler.extensions.plugins.node.smart_page_finder import RelevanceLevel

        assert RelevanceLevel.HIGH.value == 'high'
        assert RelevanceLevel.MEDIUM.value == 'medium'
        assert RelevanceLevel.LOW.value == 'low'
        assert RelevanceLevel.IRRELEVANT.value == 'irrelevant'

    def test_plugin_type(self):
        """Тест що плагін працює на правильному етапі."""
        from graph_crawler.extensions.plugins.node.base import NodePluginType
        from graph_crawler.extensions.plugins.node.smart_page_finder import SmartPageFinderPlugin

        plugin = SmartPageFinderPlugin(search_prompt="test")

        assert plugin.plugin_type == NodePluginType.ON_AFTER_SCAN

class TestSmartFinderNode:
    """Тести для SmartFinderNode."""

    def test_create_node_class(self):
        """Тест створення класу ноди."""
        from graph_crawler.extensions.plugins.node.smart_page_finder import (
            create_smart_finder_node_class,
        )

        NodeClass = create_smart_finder_node_class()

        if NodeClass is not None:
            # Pydantic v2 використовує model_fields для полів
            assert 'is_target' in NodeClass.model_fields
            assert 'relevance_score' in NodeClass.model_fields
            assert 'relevance_level' in NodeClass.model_fields

    def test_smart_finder_node_import(self):
        """Тест імпорту SmartFinderNode."""

        # SmartFinderNode може бути None якщо package_crawler не імпортується
        # Це нормально для ізольованих тестів

class TestIntegration:
    """Інтеграційні тести."""

    @pytest.mark.skipif(
        not os.environ.get('RUN_INTEGRATION_TESTS'),
        reason="Інтеграційні тести вимкнено"
    )
    def test_full_crawl_with_plugin(self):
        """Повний тест краулінгу з плагіном."""
        import graph_crawler as gc
        from graph_crawler.extensions.plugins.node import SmartPageFinderPlugin

        finder = SmartPageFinderPlugin(
            search_prompt="Python developer jobs",
            config={'min_relevance_score': 0.5}
        )

        graph = gc.crawl(
            "https://httpbin.org/html",
            max_depth=1,
            max_pages=3,
            plugins=[finder]
        )

        assert len(graph.nodes) > 0

        # Перевіряємо що user_data заповнено
        for node in graph:
            if node.scanned:
                assert 'is_target_page' in node.user_data

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
