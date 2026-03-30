"""
Тести для стратегій merge вузлів.

Перевіряємо що критичні metadata поля (canonical_url, title, тощо)
НЕ перезаписуються при merge з захистом від race condition.
"""

from datetime import datetime, timezone

import pytest

from graph_crawler.domain.entities.merge_strategies import (
    MergeStrategy,
    NodeMerger,
    get_available_strategies,
    merge_nodes,
)
from graph_crawler.domain.entities.node import Node

class TestNodeMerger:
    """Тести для NodeMerger класу."""

    def test_merge_intelligent_protects_canonical_url(self):
        """
        BUG FIX TEST: canonical_url НЕ повинен перезаписуватись при merge.

        Симулює ситуацію конкурентного краулінгу де metadata
        різних сторінок "перемішуються".
        """
        # Arrange: Два вузли з ОДНАКОВИМ URL але РІЗНИМИ canonical
        # (симулює помилку при конкурентному merge)
        node1 = Node(
            url="https://allright.com/en/job-for-teachers",
            scanned=True,
            metadata={
                "canonical_url": "https://allright.com/en/job-for-teachers",  # ПРАВИЛЬНИЙ
                "title": "Jobs for Teachers - EN",
                "h1": "Join Our Team",
            }
        )

        node2 = Node(
            url="https://allright.com/en/job-for-teachers",  # Той самий URL
            scanned=True,
            metadata={
                "canonical_url": "https://allright.com/de",  # НЕПРАВИЛЬНИЙ (з іншої сторінки!)
                "title": "German Page Title",  # Теж з іншої сторінки
                "description": "Some description",  # Це можна додати
            }
        )

        # Act
        merger = NodeMerger(strategy=MergeStrategy.MERGE)
        merged = merger.merge(node1, node2)

        # Assert: canonical_url ПОВИНЕН залишитись від node1!
        assert merged.metadata["canonical_url"] == "https://allright.com/en/job-for-teachers", \
            "canonical_url was incorrectly overwritten during merge!"

        # title теж повинен залишитись від node1
        assert merged.metadata["title"] == "Jobs for Teachers - EN", \
            "title was incorrectly overwritten during merge!"

        # h1 теж захищене поле
        assert merged.metadata["h1"] == "Join Our Team", \
            "h1 was incorrectly overwritten during merge!"

        # description можна додати (не було в node1)
        assert merged.metadata["description"] == "Some description", \
            "New metadata fields should be added"

    def test_merge_intelligent_allows_empty_to_filled(self):
        """
        Якщо node1 не має значення для критичного поля,
        node2 може його заповнити.
        """
        node1 = Node(
            url="https://example.com/page",
            scanned=False,
            metadata={}  # Порожні metadata
        )

        node2 = Node(
            url="https://example.com/page",
            scanned=True,
            metadata={
                "canonical_url": "https://example.com/page",
                "title": "Page Title",
            }
        )

        merger = NodeMerger(strategy=MergeStrategy.MERGE)
        merged = merger.merge(node1, node2)

        # Якщо node1 не мав значення - node2 може заповнити
        assert merged.metadata["canonical_url"] == "https://example.com/page"
        assert merged.metadata["title"] == "Page Title"

    def test_merge_intelligent_non_protected_fields_overwrite(self):
        """
        Некритичні metadata поля ПОВИННІ перезаписуватись (стандартна поведінка).
        """
        node1 = Node(
            url="https://example.com/page",
            scanned=True,
            metadata={
                "custom_field": "old_value",
                "language": "en",
            }
        )

        node2 = Node(
            url="https://example.com/page",
            scanned=True,
            metadata={
                "custom_field": "new_value",  # Повинно перезаписатись
                "extra_field": "extra",
            }
        )

        merger = NodeMerger(strategy=MergeStrategy.MERGE)
        merged = merger.merge(node1, node2)

        # Некритичні поля перезаписуються
        assert merged.metadata["custom_field"] == "new_value"
        assert merged.metadata["language"] == "en"  # Залишається
        assert merged.metadata["extra_field"] == "extra"  # Додається

    def test_merge_first_strategy(self):
        """Стратегія FIRST: повертає node1."""
        node1 = Node(url="https://example.com", scanned=True)
        node2 = Node(url="https://example.com", scanned=False)

        merger = NodeMerger(strategy=MergeStrategy.FIRST)
        merged = merger.merge(node1, node2)

        assert merged.scanned  # Значення від node1

    def test_merge_last_strategy(self):
        """Стратегія LAST: повертає node2."""
        node1 = Node(url="https://example.com", scanned=True)
        node2 = Node(url="https://example.com", scanned=False)

        merger = NodeMerger(strategy=MergeStrategy.LAST)
        merged = merger.merge(node1, node2)

        assert not merged.scanned  # Значення від node2

    def test_merge_different_urls_raises_error(self):
        """Merge вузлів з різними URL повинен кидати помилку."""
        node1 = Node(url="https://example.com/page1")
        node2 = Node(url="https://example.com/page2")

        merger = NodeMerger(strategy=MergeStrategy.MERGE)

        with pytest.raises(ValueError, match="Cannot merge nodes with different URLs"):
            merger.merge(node1, node2)

    def test_merge_newest_strategy(self):
        """Стратегія NEWEST: вибирає вузол з найновішим created_at."""
        older_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
        newer_time = datetime(2024, 6, 1, tzinfo=timezone.utc)

        node1 = Node(url="https://example.com", created_at=older_time, scanned=False)
        node2 = Node(url="https://example.com", created_at=newer_time, scanned=True)

        merger = NodeMerger(strategy=MergeStrategy.NEWEST)
        merged = merger.merge(node1, node2)

        assert merged.scanned  # node2 новіший

    def test_merge_oldest_strategy(self):
        """Стратегія OLDEST: вибирає вузол з найстарішим created_at."""
        older_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
        newer_time = datetime(2024, 6, 1, tzinfo=timezone.utc)

        node1 = Node(url="https://example.com", created_at=older_time, scanned=False)
        node2 = Node(url="https://example.com", created_at=newer_time, scanned=True)

        merger = NodeMerger(strategy=MergeStrategy.OLDEST)
        merged = merger.merge(node1, node2)

        assert not merged.scanned  # node1 старіший

    def test_custom_strategy(self):
        """Стратегія CUSTOM: використовує користувацьку функцію."""
        def custom_merge(n1, n2):
            # Завжди повертаємо node1 з модифікованим metadata
            result = n1.model_copy()
            result.metadata["custom_merged"] = True
            return result

        node1 = Node(url="https://example.com", metadata={"key": "value1"})
        node2 = Node(url="https://example.com", metadata={"key": "value2"})

        merger = NodeMerger(strategy=MergeStrategy.CUSTOM, custom_merge_fn=custom_merge)
        merged = merger.merge(node1, node2)

        assert merged.metadata["custom_merged"]
        assert merged.metadata["key"] == "value1"

    def test_invalid_strategy_raises_error(self):
        """Невалідна стратегія повинна кидати помилку."""
        with pytest.raises(ValueError, match="Invalid merge strategy"):
            NodeMerger(strategy="invalid_strategy")

    def test_custom_strategy_without_function_raises_error(self):
        """CUSTOM стратегія без функції повинна кидати помилку."""
        with pytest.raises(ValueError, match="custom_merge_fn required"):
            NodeMerger(strategy=MergeStrategy.CUSTOM)

class TestMergeNodesUtility:
    """Тести для утилітної функції merge_nodes."""

    def test_merge_nodes_function(self):
        """merge_nodes() працює як обгортка над NodeMerger."""
        node1 = Node(url="https://example.com", scanned=False)
        node2 = Node(url="https://example.com", scanned=True)

        merged = merge_nodes(node1, node2, strategy='merge')

        assert merged.scanned  # Логіка merge

class TestGetAvailableStrategies:
    """Тести для функції отримання списку стратегій."""

    def test_returns_all_strategies(self):
        """Повертає всі доступні стратегії з описами."""
        strategies = get_available_strategies()

        assert "first" in strategies
        assert "last" in strategies
        assert "merge" in strategies
        assert "newest" in strategies
        assert "oldest" in strategies
        assert "custom" in strategies

class TestProtectedMetadataFieldsConcurrency:
    """
    Тести що симулюють проблему конкурентного краулінгу
    де metadata перемішуються між вузлами.
    """

    def test_concurrent_crawl_metadata_isolation(self):
        """
        Симулює сценарій з bug report:
        - Краулер паралельно сканує багато сторінок
        - При merge metadata "витікають" між вузлами
        - canonical_url вказує на ІНШУ сторінку
        """
        # Симулюємо результати паралельного сканування
        # де через race condition node2 отримав metadata іншої сторінки

        pages = [
            ("https://allright.com/en/job-for-teachers", "https://allright.com/en/job-for-teachers"),
            ("https://allright.com/de/job-for-teachers", "https://allright.com/de/job-for-teachers"),
            ("https://allright.com/pl/job-for-teachers", "https://allright.com/pl/job-for-teachers"),
        ]

        for url, expected_canonical in pages:
            # node1 - коректно скановані дані
            node1 = Node(
                url=url,
                scanned=True,
                metadata={"canonical_url": expected_canonical}
            )

            # node2 - "забруднені" дані від іншої сторінки (bug simulation)
            node2 = Node(
                url=url,  # Той самий URL
                scanned=True,
                metadata={"canonical_url": "https://allright.com/de"}  # WRONG!
            )

            merger = NodeMerger(strategy=MergeStrategy.MERGE)
            merged = merger.merge(node1, node2)

            # ASSERT: canonical повинен залишитись правильним!
            assert merged.metadata["canonical_url"] == expected_canonical, \
                f"canonical_url corruption for {url}: expected {expected_canonical}, got {merged.metadata['canonical_url']}"

    def test_og_url_and_twitter_url_protected(self):
        """OpenGraph URL і Twitter URL теж захищені."""
        node1 = Node(
            url="https://example.com/page",
            metadata={
                "og:url": "https://example.com/page",
                "twitter:url": "https://example.com/page",
            }
        )

        node2 = Node(
            url="https://example.com/page",
            metadata={
                "og:url": "https://other.com/wrong",
                "twitter:url": "https://other.com/wrong",
            }
        )

        merger = NodeMerger(strategy=MergeStrategy.MERGE)
        merged = merger.merge(node1, node2)

        assert merged.metadata["og:url"] == "https://example.com/page"
        assert merged.metadata["twitter:url"] == "https://example.com/page"

class TestNodeUpdateFromContextIsolation:
    """
    Тести для перевірки ізоляції metadata при оновленні з context.

    Проблема: _update_from_context() робив пряме присвоєння
    self.metadata = context.metadata, що призводило до race condition
    коли той самий context.metadata dict використовувався для різних нод.
    """

    def test_metadata_copy_not_reference(self):
        """
        Перевіряє що node.metadata це КОПІЯ, а не посилання на context.metadata.

        Якщо це посилання - зміни в одному місці вплинуть на інше.
        """
        from graph_crawler.extensions.plugins.node.base import NodePluginContext

        # Створюємо shared metadata dict (симулює race condition)
        shared_metadata = {
            "canonical_url": "https://example.com/page1",
            "title": "Page 1"
        }

        # Створюємо context з shared metadata
        node1 = Node(url="https://example.com/page1")
        context = NodePluginContext(
            node=node1,
            url="https://example.com/page1",
            depth=0,
            should_scan=True,
            can_create_edges=True,
            metadata=shared_metadata
        )

        # Оновлюємо node1 з context
        node1._update_from_context(context)

        # Тепер змінюємо shared_metadata (симулює обробку іншої сторінки)
        shared_metadata["canonical_url"] = "https://example.com/page2"
        shared_metadata["title"] = "Page 2"

        # КРИТИЧНИЙ ТЕСТ: node1.metadata НЕ повинен змінитись!
        assert node1.metadata["canonical_url"] == "https://example.com/page1", \
            "node.metadata was modified through shared reference - race condition bug!"
        assert node1.metadata["title"] == "Page 1", \
            "node.metadata['title'] was modified through shared reference!"

    def test_multiple_nodes_same_context_metadata(self):
        """
        Симулює сценарій де один context.metadata dict
        використовується для оновлення кількох нод.
        """
        from graph_crawler.extensions.plugins.node.base import NodePluginContext

        # Shared metadata (помилкова поведінка - один об'єкт для кількох контекстів)
        shared_metadata = {}

        nodes = []
        urls = [
            "https://allright.com/en/page",
            "https://allright.com/de/page",
            "https://allright.com/pl/page",
        ]

        for i, url in enumerate(urls):
            # Оновлюємо shared_metadata для нової сторінки
            shared_metadata["canonical_url"] = url
            shared_metadata["title"] = f"Title {i}"

            node = Node(url=url)
            context = NodePluginContext(
                node=node,
                url=url,
                depth=0,
                should_scan=True,
                can_create_edges=True,
                metadata=shared_metadata
            )

            node._update_from_context(context)
            nodes.append(node)

        # Перевіряємо що кожна нода має СВІЙ canonical_url
        for node in nodes:
            assert node.metadata["canonical_url"] == node.url, \
                f"Node {node.url} has wrong canonical: {node.metadata['canonical_url']}"
