"""
Тести для нових features в Graph entity (останні 5 комітів).

Тестує:
1. Batch Operations (filter, remove_where, update_where, count_where)
2. Export Nodes (export_nodes з node_fields та transform)
3. Cascade Query API (query_cascade)
4. JSON-LD Schema Filter (filter_by_schema, get_nodes_by_schema)
5. Canonical URL Deduplication (deduplicate_by_url, get_language_versions)
"""

import json
import os
import tempfile

import pytest

from graph_crawler.domain.entities.graph import CascadeResult, Graph
from graph_crawler.domain.entities.node import Node
@pytest.fixture
def graph_with_nodes():
    """Граф з базовими нодами для тестування."""
    graph = Graph()

    # Створюємо 10 нод
    for i in range(10):
        node = Node(url=f"https://example.com/page{i}", depth=i % 3)
        node.scanned = i % 2 == 0
        node.response_status = 200 if i % 3 != 0 else 429
        graph.add_node(node)

    return graph

@pytest.fixture
def graph_with_structured_data():
    """Граф з нодами що мають structured_data (JSON-LD schema)."""
    graph = Graph()

    # Мокаємо structured_data для тестування schema filter
    class MockStructuredData:
        def __init__(self, types):
            self.all_types = set(types)

        def has_type(self, schema_type):
            return schema_type in self.all_types

    # JobPosting ноди
    for i in range(5):
        node = Node(url=f"https://example.com/jobs/{i}", depth=1)
        node.scanned = True
        node.user_data['structured_data'] = MockStructuredData(['JobPosting'])
        graph.add_node(node)

    # BlogPosting ноди
    for i in range(3):
        node = Node(url=f"https://example.com/blog/{i}", depth=1)
        node.scanned = True
        node.user_data['structured_data'] = MockStructuredData(['BlogPosting', 'Article'])
        graph.add_node(node)

    # Ноди без schema
    for i in range(2):
        node = Node(url=f"https://example.com/about/{i}", depth=1)
        node.scanned = True
        graph.add_node(node)

    return graph

@pytest.fixture
def graph_with_language_versions():
    """Граф з мовними версіями сторінок."""
    graph = Graph()

    # Англійська версія
    node_en = Node(url="https://example.com/en/jobs/developer", depth=1)
    node_en.scanned = True
    node_en.metadata['canonical_url'] = "https://example.com/en/jobs/developer"
    graph.add_node(node_en)

    # Польська версія
    node_pl = Node(url="https://example.com/pl/jobs/developer", depth=1)
    node_pl.scanned = True
    graph.add_node(node_pl)

    # Німецька версія
    node_de = Node(url="https://example.com/de/jobs/developer", depth=1)
    node_de.scanned = False
    graph.add_node(node_de)

    # Інша сторінка
    node_about = Node(url="https://example.com/en/about", depth=1)
    node_about.scanned = True
    graph.add_node(node_about)

    return graph
class TestBatchOperations:
    """Тести для batch operations (filter, remove_where, update_where, count_where)."""

    def test_filter_returns_matching_nodes(self, graph_with_nodes):
        """filter() повертає ноди що відповідають predicate."""
        result = graph_with_nodes.filter(lambda n: n.scanned)

        assert len(result) == 5  # 0, 2, 4, 6, 8 - парні індекси
        for node in result:
            assert node.scanned is True

    def test_filter_returns_empty_list_when_no_match(self, graph_with_nodes):
        """filter() повертає порожній список коли немає збігів."""
        result = graph_with_nodes.filter(lambda n: n.depth > 100)

        assert result == []

    def test_filter_with_complex_predicate(self, graph_with_nodes):
        """filter() працює з складним predicate."""
        result = graph_with_nodes.filter(
            lambda n: n.scanned and n.response_status == 200
        )

        assert len(result) > 0
        for node in result:
            assert node.scanned is True
            assert node.response_status == 200

    def test_remove_where_removes_matching_nodes(self, graph_with_nodes):
        """remove_where() видаляє ноди що відповідають predicate."""
        initial_count = len(graph_with_nodes)

        removed_count = graph_with_nodes.remove_where(
            lambda n: n.response_status == 429
        )

        assert removed_count > 0
        assert len(graph_with_nodes) == initial_count - removed_count

        # Перевіряємо що 429 ноди видалені
        for node in graph_with_nodes:
            assert node.response_status != 429

    def test_remove_where_returns_zero_when_no_match(self, graph_with_nodes):
        """remove_where() повертає 0 коли немає збігів."""
        removed = graph_with_nodes.remove_where(lambda n: n.depth > 100)

        assert removed == 0

    def test_update_where_updates_matching_nodes(self, graph_with_nodes):
        """update_where() оновлює ноди що відповідають predicate."""
        # Скидаємо scanned для 429 нод
        updated_count = graph_with_nodes.update_where(
            predicate=lambda n: n.response_status == 429,
            updates={'scanned': False, 'response_status': None}
        )

        assert updated_count > 0

        # Перевіряємо оновлення
        for node in graph_with_nodes:
            if node.response_status is None:
                assert node.scanned is False

    def test_update_where_with_update_fn(self, graph_with_nodes):
        """update_where() працює з update_fn."""
        updated_count = graph_with_nodes.update_where(
            predicate=lambda n: n.depth == 0,
            update_fn=lambda n: setattr(n, 'priority', 10)
        )

        assert updated_count > 0

        for node in graph_with_nodes.filter(lambda n: n.depth == 0):
            assert getattr(node, 'priority', None) == 10

    def test_update_where_raises_without_updates_or_fn(self, graph_with_nodes):
        """update_where() викидає ValueError без updates/update_fn."""
        with pytest.raises(ValueError):
            graph_with_nodes.update_where(predicate=lambda n: True)

    def test_count_where_counts_matching_nodes(self, graph_with_nodes):
        """count_where() підраховує ноди що відповідають predicate."""
        scanned_count = graph_with_nodes.count_where(lambda n: n.scanned)

        assert scanned_count == 5

    def test_count_where_returns_zero_when_no_match(self, graph_with_nodes):
        """count_where() повертає 0 коли немає збігів."""
        count = graph_with_nodes.count_where(lambda n: n.depth > 100)

        assert count == 0
class TestExportNodes:
    """Тести для export_nodes() - метод deprecated в Clean Architecture.

    ПРИМІТКА: export_nodes() тепер викидає NotImplementedError.
    Для експорту нод слід використовувати GraphExportUseCase з Application layer.
    """

    def test_export_nodes_to_json_with_all_fields(self, graph_with_nodes):
        """export_nodes() викидає NotImplementedError (deprecated)."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            filepath = f.name

        try:
            with pytest.raises(NotImplementedError):
                graph_with_nodes.export_nodes(filepath, format='json')
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)

    def test_export_nodes_to_json_with_selected_fields(self, graph_with_nodes):
        """export_nodes() викидає NotImplementedError (deprecated)."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            filepath = f.name

        try:
            with pytest.raises(NotImplementedError):
                graph_with_nodes.export_nodes(
                    filepath,
                    format='json',
                    node_fields=['url', 'depth', 'scanned']
                )
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)

    def test_export_nodes_with_transform(self, graph_with_nodes):
        """export_nodes() викидає NotImplementedError (deprecated)."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            filepath = f.name

        try:
            with pytest.raises(NotImplementedError):
                graph_with_nodes.export_nodes(
                    filepath,
                    format='json',
                    transform_node=lambda n: {
                        'custom_url': n.url.upper(),
                        'is_scanned': n.scanned,
                    }
                )
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)

    def test_export_nodes_with_predicate(self, graph_with_nodes):
        """export_nodes() викидає NotImplementedError (deprecated)."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            filepath = f.name

        try:
            with pytest.raises(NotImplementedError):
                graph_with_nodes.export_nodes(
                    filepath,
                    format='json',
                    predicate=lambda n: n.scanned
                )
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)

    def test_export_nodes_to_csv(self, graph_with_nodes):
        """export_nodes() викидає NotImplementedError (deprecated)."""
        with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as f:
            filepath = f.name

        try:
            with pytest.raises(NotImplementedError):
                graph_with_nodes.export_nodes(filepath, format='csv')
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)

    def test_export_nodes_raises_for_unsupported_format(self, graph_with_nodes):
        """export_nodes() викидає NotImplementedError (deprecated)."""
        # Метод викидає NotImplementedError незалежно від формату
        with pytest.raises(NotImplementedError):
            graph_with_nodes.export_nodes('test.xml', format='xml')
class TestCascadeQueryAPI:
    """Тести для query_cascade() - каскадний запит з fallback."""

    def test_query_cascade_returns_first_level_match(self, graph_with_nodes):
        """query_cascade() повертає результат з першого рівня якщо є збіг."""
        result = graph_with_nodes.query_cascade([
            lambda n: n.depth == 0,  # Level 0 - має бути збіг
            lambda n: n.depth == 1,  # Level 1
            lambda n: n.depth == 2,  # Level 2
        ])

        assert isinstance(result, CascadeResult)
        assert result.found is True
        assert result.level == 0
        assert result.is_primary_level is True
        assert result.is_fallback is False

    def test_query_cascade_falls_back_to_next_level(self, graph_with_nodes):
        """query_cascade() переходить на наступний рівень якщо немає збігу."""
        result = graph_with_nodes.query_cascade([
            lambda n: n.depth > 100,  # Level 0 - немає збігу
            lambda n: n.depth == 0,   # Level 1 - є збіг
        ])

        assert result.found is True
        assert result.level == 1
        assert result.is_fallback is True

    def test_query_cascade_returns_empty_when_no_match(self, graph_with_nodes):
        """query_cascade() повертає пустий результат коли немає збігів."""
        result = graph_with_nodes.query_cascade([
            lambda n: n.depth > 100,
            lambda n: n.depth > 200,
        ])

        assert result.found is False
        assert result.level == -1
        assert len(result) == 0

    def test_query_cascade_min_matches(self, graph_with_nodes):
        """query_cascade() з min_matches продовжує якщо недостатньо збігів."""
        result = graph_with_nodes.query_cascade(
            predicates=[
                lambda n: n.depth == 0,  # ~3-4 ноди
                lambda n: n.scanned,     # 5 нод
            ],
            min_matches=5,  # Потрібно мінімум 5
        )

        # Повинен знайти рівень з >= 5 нодами
        assert result.found is True
        assert len(result.nodes) >= 5

    def test_query_cascade_stop_at_first_false(self, graph_with_nodes):
        """query_cascade() з stop_at_first=False збирає всі унікальні ноди."""
        result = graph_with_nodes.query_cascade(
            predicates=[
                lambda n: n.depth == 0,
                lambda n: n.depth == 1,
            ],
            stop_at_first=False,
        )

        # Має зібрати ноди з обох рівнів
        assert result.found is True
        # Результат має включати ноди з depth 0 і depth 1
        depths = {n.depth for n in result.nodes}
        assert 0 in depths or 1 in depths

    def test_cascade_result_properties(self):
        """CascadeResult має правильні властивості."""
        nodes = [Node(url="https://test.com", depth=0)]
        result = CascadeResult(
            nodes=nodes,
            level=2,
            levels_tried=3,
            total_predicates=5,
        )

        assert result.count == 1
        assert result.found is True
        assert result.is_primary_level is False
        assert result.is_fallback is True
        assert len(result) == 1
        assert list(result) == nodes

    def test_cascade_result_repr(self):
        """CascadeResult.__repr__() працює."""
        result = CascadeResult([], -1, 3, 3)

        assert "CascadeResult" in repr(result)
        assert "level=-1" in repr(result)
class TestSchemaFilter:
    """Тести для filter_by_schema() та пов'язаних методів."""

    def test_filter_by_schema_include(self, graph_with_structured_data):
        """filter_by_schema() з include повертає тільки вказані типи."""
        result = graph_with_structured_data.filter_by_schema(include=['JobPosting'])

        assert len(result) == 5
        for node in result:
            sd = node.user_data.get('structured_data')
            assert sd is not None
            assert 'JobPosting' in sd.all_types

    def test_filter_by_schema_exclude(self, graph_with_structured_data):
        """filter_by_schema() з exclude видаляє вказані типи."""
        result = graph_with_structured_data.filter_by_schema(
            exclude=['BlogPosting', 'Article']
        )

        # 5 JobPosting + 2 without schema = 7
        assert len(result) == 7

        for node in result:
            sd = node.user_data.get('structured_data')
            if sd and sd.all_types:
                assert 'BlogPosting' not in sd.all_types
                assert 'Article' not in sd.all_types

    def test_filter_by_schema_include_and_exclude(self, graph_with_structured_data):
        """filter_by_schema() з include + exclude."""
        result = graph_with_structured_data.filter_by_schema(
            include=['JobPosting'],
            exclude=['BlogPosting']
        )

        assert len(result) == 5

    def test_filter_by_schema_fallback_keep(self, graph_with_structured_data):
        """filter_by_schema() з fallback='keep' залишає ноди без schema."""
        result = graph_with_structured_data.filter_by_schema(
            exclude=['BlogPosting'],
            fallback='keep'
        )

        # 5 JobPosting + 2 without schema = 7
        assert len(result) == 7

    def test_filter_by_schema_fallback_remove(self, graph_with_structured_data):
        """filter_by_schema() з fallback='remove' видаляє ноди без schema."""
        result = graph_with_structured_data.filter_by_schema(
            include=['JobPosting'],
            fallback='remove'
        )

        # Тільки 5 JobPosting
        assert len(result) == 5

        for node in result:
            assert node.user_data.get('structured_data') is not None

    def test_get_nodes_by_schema(self, graph_with_structured_data):
        """get_nodes_by_schema() - shortcut для filter_by_schema."""
        jobs = graph_with_structured_data.get_nodes_by_schema('JobPosting')

        assert len(jobs) == 5

    def test_get_schema_stats(self, graph_with_structured_data):
        """get_schema_stats() повертає статистику типів."""
        stats = graph_with_structured_data.get_schema_stats()

        assert stats.get('JobPosting', 0) == 5
        assert stats.get('BlogPosting', 0) == 3
        assert stats.get('Article', 0) == 3  # BlogPosting теж має Article

    def test_has_schema_type(self, graph_with_structured_data):
        """has_schema_type() перевіряє наявність типу."""
        assert graph_with_structured_data.has_schema_type('JobPosting') is True
        assert graph_with_structured_data.has_schema_type('Product') is False
class TestCanonicalDeduplication:
    """Тести для deduplicate_by_url() та get_language_versions()."""

    def test_deduplicate_by_url_groups_similar_urls(self, graph_with_language_versions):
        """deduplicate_by_url() групує схожі URL."""
        import re

        def remove_lang_prefix(url):
            return re.sub(r'/[a-z]{2}/', '/', url)

        result = graph_with_language_versions.deduplicate_by_url(
            extract_base_url=remove_lang_prefix,
            select_best='first',
        )

        # 3 мовні версії jobs/developer + 1 about
        assert len(result['unique_nodes']) == 2
        assert result['stats']['duplicate_groups'] >= 1

    def test_deduplicate_by_url_select_canonical(self, graph_with_language_versions):
        """deduplicate_by_url() вибирає ноду з canonical."""
        import re

        def remove_lang_prefix(url):
            return re.sub(r'/[a-z]{2}/', '/', url)

        result = graph_with_language_versions.deduplicate_by_url(
            extract_base_url=remove_lang_prefix,
            select_best='canonical',
        )

        # Повинна вибрати ноду з canonical_url == url
        unique_urls = [n.url for n in result['unique_nodes']]
        # Англійська версія має canonical
        assert any('/en/' in url for url in unique_urls)

    def test_deduplicate_by_url_select_language_priority(self, graph_with_language_versions):
        """deduplicate_by_url() вибирає за language_priority."""
        import re

        def remove_lang_prefix(url):
            return re.sub(r'/[a-z]{2}/', '/', url)

        result = graph_with_language_versions.deduplicate_by_url(
            extract_base_url=remove_lang_prefix,
            select_best='language',
            language_priority=['pl', 'en', 'de'],  # Польська перша
        )

        unique_urls = [n.url for n in result['unique_nodes']]
        # Повинна вибрати польську версію
        assert any('/pl/' in url for url in unique_urls)

    def test_deduplicate_by_url_remove_duplicates(self, graph_with_language_versions):
        """deduplicate_by_url() видаляє дублікати коли remove_duplicates=True."""
        import re

        def remove_lang_prefix(url):
            return re.sub(r'/[a-z]{2}/', '/', url)

        initial_count = len(graph_with_language_versions)

        result = graph_with_language_versions.deduplicate_by_url(
            extract_base_url=remove_lang_prefix,
            select_best='first',
            remove_duplicates=True,
        )

        # Дублікати видалені
        assert len(graph_with_language_versions) < initial_count
        assert result['removed_count'] > 0

    def test_deduplicate_by_url_stats(self, graph_with_language_versions):
        """deduplicate_by_url() повертає статистику."""
        import re

        def remove_lang_prefix(url):
            return re.sub(r'/[a-z]{2}/', '/', url)

        result = graph_with_language_versions.deduplicate_by_url(
            extract_base_url=remove_lang_prefix,
            select_best='first',
        )

        assert 'stats' in result
        assert 'total_nodes' in result['stats']
        assert 'unique_base_urls' in result['stats']
        assert 'duplicate_groups' in result['stats']
        assert 'largest_group' in result['stats']

    def test_get_language_versions_finds_all_versions(self, graph_with_language_versions):
        """get_language_versions() знаходить всі мовні версії."""
        node = graph_with_language_versions.get_node_by_url(
            "https://example.com/en/jobs/developer"
        )

        versions = graph_with_language_versions.get_language_versions(node)

        # Має знайти en, pl, de версії
        assert len(versions) >= 2

        urls = [v.url for v in versions]
        # Всі версії jobs/developer
        for url in urls:
            assert 'jobs/developer' in url

    def test_get_language_versions_empty_for_unique_page(self, graph_with_language_versions):
        """get_language_versions() для унікальної сторінки."""
        node = graph_with_language_versions.get_node_by_url(
            "https://example.com/en/about"
        )

        versions = graph_with_language_versions.get_language_versions(node)

        # Тільки сама сторінка (немає інших мовних версій)
        assert len(versions) == 1
class TestEdgeCases:
    """Тести для крайніх випадків."""

    def test_operations_on_empty_graph(self):
        """Операції на порожньому графі."""
        graph = Graph()

        assert graph.filter(lambda n: True) == []
        assert graph.remove_where(lambda n: True) == 0
        assert graph.count_where(lambda n: True) == 0

        result = graph.query_cascade([lambda n: True])
        assert result.found is False

        assert graph.filter_by_schema(include=['JobPosting']) == []

    def test_predicate_exception_handling(self, graph_with_nodes):
        """Обробка помилок в predicate."""
        def bad_predicate(n):
            raise RuntimeError("Test error")

        # query_cascade повинен обробити помилку
        result = graph_with_nodes.query_cascade([bad_predicate])
        # Не повинен впасти, але й не знайде результатів
        assert result.found is False

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
