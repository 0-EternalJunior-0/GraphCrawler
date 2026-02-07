"""
Unit тести для VectorCrawlEnginePlugin.

Автор: AI Assistant
Дата: 2025-01
"""

import pytest
from graph_crawler.extensions.plugins.crawl_engine import (
    VectorCrawlEnginePlugin,
    EnginePluginContext,
    EnginePluginType,
)


class TestVectorCrawlEnginePluginInit:
    """Тести ініціалізації плагіну."""
    
    def test_initialization_with_keywords(self):
        """Тест базової ініціалізації."""
        plugin = VectorCrawlEnginePlugin(
            keywords=['test', 'keywords'],
            min_priority=1,
            max_priority=10
        )
        
        assert plugin.name == "VectorCrawlEnginePlugin"
        assert plugin.keywords == ['test', 'keywords']
        assert plugin.min_priority == 1
        assert plugin.max_priority == 10
        assert plugin.similarity_threshold == 0.35  # default
    
    def test_initialization_with_config(self):
        """Тест ініціалізації з конфігурацією."""
        plugin = VectorCrawlEnginePlugin(
            keywords=['job', 'vacancy'],
            min_priority=1,
            max_priority=6,
            config={'similarity_threshold': 0.5}
        )
        
        assert plugin.similarity_threshold == 0.5
    
    def test_initialization_without_keywords_raises_error(self):
        """Тест що порожній keywords викликає помилку."""
        with pytest.raises(ValueError, match="keywords не можуть бути порожніми"):
            VectorCrawlEnginePlugin(keywords=[])
    
    def test_plugin_type(self):
        """Тест типу плагіну."""
        plugin = VectorCrawlEnginePlugin(keywords=['test'])
        assert plugin.plugin_type == EnginePluginType.CALCULATE_PRIORITIES


class TestVectorCrawlEnginePluginSetup:
    """Тести завантаження моделі."""
    
    @pytest.fixture
    def plugin(self):
        """Створює плагін для тестів."""
        return VectorCrawlEnginePlugin(
            keywords=['python', 'developer', 'programming', 'engineer'],
            min_priority=1,
            max_priority=6,
            model_name='all-MiniLM-L6-v2',  # Швидша модель для тестів
            config={'similarity_threshold': 0.3}
        )
    
    def test_setup_loads_model(self, plugin):
        """Тест що setup завантажує модель."""
        plugin.setup()
        assert plugin._model is not None
        assert plugin._keywords_vector is not None
        assert len(plugin._keywords_vector) > 0


class TestVectorCrawlEnginePluginExtractPath:
    """Тести витягування PATH з URL."""
    
    @pytest.fixture
    def plugin(self):
        """Створює плагін для тестів."""
        return VectorCrawlEnginePlugin(
            keywords=['test'],
            min_priority=1,
            max_priority=6
        )
    
    def test_extract_path_basic(self, plugin):
        """Тест базового витягування."""
        test_cases = [
            ("https://example.com/jobs/developer", "/jobs/developer"),
            ("https://example.com/j-o-b-s/", "/j-o-b-s"),
            ("https://example.com/", "/"),
            ("https://example.com/path?query=1", "/path"),
        ]
        
        for url, expected_path in test_cases:
            path = plugin._extract_path(url)
            assert path == expected_path, f"URL: {url}"
    
    def test_extract_path_with_encoded_chars(self, plugin):
        """Тест URL з закодованими символами."""
        url = "https://example.com/path%20space"
        path = plugin._extract_path(url)
        assert path == "/path space"


class TestVectorCrawlEnginePluginPriorityCalculation:
    """Тести обчислення пріоритету."""
    
    @pytest.fixture
    def plugin(self):
        """Створює та ініціалізує плагін для тестів."""
        plugin = VectorCrawlEnginePlugin(
            keywords=['python', 'developer', 'programming', 'engineer'],
            min_priority=1,
            max_priority=6,
            model_name='all-MiniLM-L6-v2',
            config={'similarity_threshold': 0.3}
        )
        plugin.setup()
        return plugin
    
    def test_priority_calculation_high_relevance(self, plugin):
        """Тест високої релевантності."""
        context = EnginePluginContext(
            url="https://example.com/python-developer-engineer",
            depth=1
        )
        
        priority = plugin.calculate_url_priority(context)
        
        assert priority is not None
        assert plugin.min_priority <= priority <= plugin.max_priority
        assert priority >= 4, "Високорелевантний URL має мати високий пріоритет"
    
    def test_priority_calculation_low_relevance(self, plugin):
        """Тест низької релевантності."""
        context = EnginePluginContext(
            url="https://example.com/about-us-company",
            depth=1
        )
        
        priority = plugin.calculate_url_priority(context)
        
        # Може бути None якщо нижче threshold
        if priority is not None:
            assert priority <= 3, "Низькорелевантний URL має мати низький пріоритет"
    
    def test_skip_explicit_priority(self, plugin):
        """Тест що плагін пропускає URL з явним priority."""
        context = EnginePluginContext(
            url="https://example.com/python-jobs",
            depth=1,
            user_data={'explicit_priority': 8}
        )
        
        priority = plugin.calculate_url_priority(context)
        
        assert priority is None, "Має пропустити URL з явним priority"
        assert plugin.stats['skipped_has_priority'] > 0
    
    def test_skip_blocked_url(self, plugin):
        """Тест що плагін пропускає заблоковані URL."""
        context = EnginePluginContext(
            url="https://example.com/python-jobs",
            depth=1,
            user_data={'should_scan': False}
        )
        
        priority = plugin.calculate_url_priority(context)
        
        assert priority is None, "Має пропустити заблокований URL"
        assert plugin.stats['skipped_blocked'] > 0
    
    def test_skip_root_path(self, plugin):
        """Тест що плагін пропускає root path."""
        context = EnginePluginContext(
            url="https://example.com/",
            depth=1
        )
        
        priority = plugin.calculate_url_priority(context)
        
        assert priority is None, "Має пропустити root path"


class TestVectorCrawlEnginePluginBatch:
    """Тести batch обробки."""
    
    @pytest.fixture
    def plugin(self):
        """Створює та ініціалізує плагін для тестів."""
        plugin = VectorCrawlEnginePlugin(
            keywords=['python', 'developer', 'programming', 'engineer'],
            min_priority=1,
            max_priority=6,
            model_name='all-MiniLM-L6-v2',
            config={'similarity_threshold': 0.3}
        )
        plugin.setup()
        return plugin
    
    def test_batch_priorities(self, plugin):
        """Тест batch обробки."""
        contexts = [
            EnginePluginContext(url="https://example.com/python-developer", depth=1),
            EnginePluginContext(url="https://example.com/engineer-jobs", depth=1),
            EnginePluginContext(url="https://example.com/about", depth=1),
            EnginePluginContext(url="https://example.com/contact", depth=1),
        ]
        
        result = plugin.calculate_batch_priorities(contexts)
        
        assert isinstance(result, dict)
        assert len(result) >= 1, "Хоча б 1 URL має бути релевантним"
        
        # Перевіряємо що пріоритети в діапазоні
        for url, priority in result.items():
            assert plugin.min_priority <= priority <= plugin.max_priority


class TestVectorCrawlEnginePluginSimilarityConversion:
    """Тести конвертації similarity в priority."""
    
    @pytest.fixture
    def plugin(self):
        """Створює плагін для тестів."""
        return VectorCrawlEnginePlugin(
            keywords=['test'],
            min_priority=1,
            max_priority=6,
            config={'similarity_threshold': 0.3}
        )
    
    def test_similarity_to_priority_at_threshold(self, plugin):
        """Тест на порозі."""
        priority = plugin._similarity_to_priority(0.3)
        assert priority == 1  # На порозі → min_priority
    
    def test_similarity_to_priority_at_max(self, plugin):
        """Тест на максимумі."""
        priority = plugin._similarity_to_priority(1.0)
        assert priority == 6  # Максимум → max_priority
    
    def test_similarity_to_priority_middle(self, plugin):
        """Тест середнього значення."""
        priority = plugin._similarity_to_priority(0.65)
        assert 3 <= priority <= 4  # Середнє значення


class TestVectorCrawlEnginePluginStatistics:
    """Тести статистики."""
    
    @pytest.fixture
    def plugin(self):
        """Створює та ініціалізує плагін для тестів."""
        plugin = VectorCrawlEnginePlugin(
            keywords=['python', 'developer'],
            min_priority=1,
            max_priority=6,
            model_name='all-MiniLM-L6-v2',
            config={'similarity_threshold': 0.3}
        )
        plugin.setup()
        return plugin
    
    def test_statistics(self, plugin):
        """Тест статистики."""
        # Обробляємо кілька URL
        contexts = [
            EnginePluginContext(url="https://example.com/python-dev", depth=1),
            EnginePluginContext(url="https://example.com/about", depth=1),
            EnginePluginContext(
                url="https://example.com/blocked", 
                depth=1,
                user_data={'should_scan': False}
            ),
        ]
        
        for ctx in contexts:
            plugin.calculate_url_priority(ctx)
        
        stats = plugin.get_stats()
        
        assert stats['total_analyzed'] == 3
        assert stats['skipped_blocked'] == 1
        assert stats['vectorized'] >= 1
        assert 0 <= stats['vectorization_rate'] <= 1


class TestVectorPluginMultilingual:
    """Тести багатомовної підтримки."""
    
    @pytest.fixture
    def multilingual_plugin(self):
        """Створює багатомовний плагін."""
        plugin = VectorCrawlEnginePlugin(
            keywords=['робота', 'jobs', 'работа', 'vacancy', 'вакансія'],
            min_priority=1,
            max_priority=6,
            model_name='paraphrase-multilingual-MiniLM-L12-v2',
            config={'similarity_threshold': 0.3}
        )
        plugin.setup()
        return plugin
    
    def test_multilingual_support(self, multilingual_plugin):
        """Тест багатомовної підтримки."""
        plugin = multilingual_plugin
        
        test_urls = [
            "https://example.com/вакансії/senior",      # UA
            "https://example.com/j-o-b-s/developer",   # EN (нестандартне)
            "https://example.com/работа/engineer",     # RU
        ]
        
        priorities = []
        for url in test_urls:
            context = EnginePluginContext(url=url, depth=1)
            priority = plugin.calculate_url_priority(context)
            priorities.append(priority)
        
        # Хоча б деякі URL мають бути знайдені
        found = [p for p in priorities if p is not None]
        assert len(found) >= 1, f"Має знайти хоча б один багатомовний URL. Priorities: {priorities}"


class TestVectorCrawlEnginePluginRepr:
    """Тести string representation."""
    
    def test_repr(self):
        """Тест __repr__."""
        plugin = VectorCrawlEnginePlugin(
            keywords=['job', 'vacancy', 'career'],
            min_priority=1,
            max_priority=6,
            model_name='all-MiniLM-L6-v2'
        )
        
        repr_str = repr(plugin)
        
        assert "VectorCrawlEnginePlugin" in repr_str
        assert "keywords=3" in repr_str
        assert "priority=[1, 6]" in repr_str
        assert "all-MiniLM-L6-v2" in repr_str
