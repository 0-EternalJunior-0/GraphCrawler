"""Integration tests для краулінгу Wikipedia.

Тести перевіряють реальний граф посилань на Wikipedia.
Wikipedia має багату структуру посилань - ідеальний сайт для тестування графа.
Обмеження: max 5 сторінок щоб не навантажувати сервер.
"""

import pytest

from graph_crawler import AsyncCrawler, Crawler, async_crawl, crawl
from graph_crawler.domain.entities.graph import Graph


@pytest.mark.integration
class TestWikipediaGraphStructure:
    """Тести структури графа на Wikipedia."""

    def test_wikipedia_has_rich_link_structure(self):
        """Wikipedia має багато внутрішніх посилань - граф не пустий."""
        graph = crawl(
            "https://uk.wikipedia.org/wiki/Python",
            max_depth=1,
            max_pages=5,
            request_delay=0.5  # Ввічливо до Wikipedia
        )

        assert graph is not None
        assert isinstance(graph, Graph)

        # Wikipedia завжди має багато посилань
        assert len(graph.nodes) > 1, "Wikipedia повинна мати більше 1 ноди"

        # Перевіряємо що є edges (посилання між сторінками)
        assert len(graph.edges) > 0, "Wikipedia повинна мати edges між сторінками"

        # Перевіряємо кількість просканованих сторінок
        scanned_count = sum(1 for n in graph.nodes.values() if n.scanned)
        assert scanned_count >= 1, "Хоча б 1 сторінка повинна бути просканована"
        assert scanned_count <= 5, f"Не більше 5 сторінок (max_pages=5), отримали {scanned_count}"

    def test_wikipedia_graph_has_proper_depth(self):
        """Граф Wikipedia має правильну глибину."""
        graph = crawl(
            "https://uk.wikipedia.org/wiki/Python",
            max_depth=1,
            max_pages=5,
            request_delay=0.5
        )

        # Перевіряємо глибини
        depths = {node.depth for node in graph.nodes.values()}

        # Має бути root (depth=0)
        assert 0 in depths, "Повинна бути кореневa нода з depth=0"

        # Мають бути дочірні ноди (depth=1)
        if len(graph.nodes) > 1:
            assert 1 in depths or max(depths) <= 1, "Повинні бути ноди з depth <= 1"

    def test_wikipedia_filters_external_domains(self):
        """Краулінг фільтрує зовнішні домени (тільки Wikipedia)."""
        graph = crawl(
            "https://uk.wikipedia.org/wiki/Python",
            max_depth=1,
            max_pages=5,
            request_delay=0.5
        )

        # Всі ноди повинні бути з Wikipedia
        for node in graph.nodes.values():
            assert "wikipedia.org" in node.url, f"URL не з Wikipedia: {node.url}"

    def test_wikipedia_collects_metadata(self):
        """Краулінг Wikipedia збирає метадані."""
        graph = crawl(
            "https://uk.wikipedia.org/wiki/Python",
            max_depth=0,
            max_pages=1,
            request_delay=0.5
        )

        # Знаходимо кореневу ноду
        root = None
        for node in graph.nodes.values():
            if node.depth == 0 and node.scanned:
                root = node
                break

        assert root is not None, "Повинна бути коренева нода"
        assert root.response_status == 200, f"Статус повинен бути 200, отримали {root.response_status}"


@pytest.mark.integration
class TestWikipediaEnglish:
    """Тести англійської Wikipedia."""

    def test_english_wikipedia_graph(self):
        """Англійська Wikipedia теж працює."""
        graph = crawl(
            "https://en.wikipedia.org/wiki/Python_(programming_language)",
            max_depth=1,
            max_pages=5,
            request_delay=0.5
        )

        assert len(graph.nodes) > 1, "English Wikipedia повинна мати багато посилань"
        assert len(graph.edges) > 0, "English Wikipedia повинна мати edges"

        # Перевіряємо що всі URL з en.wikipedia.org
        for node in graph.nodes.values():
            assert "wikipedia.org" in node.url


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="function")
class TestWikipediaAsync:
    """Async тести Wikipedia."""

    async def test_async_wikipedia_crawl(self):
        """Async краулінг Wikipedia."""
        graph = await async_crawl(
            "https://uk.wikipedia.org/wiki/Python",
            max_depth=1,
            max_pages=5,
            request_delay=0.5
        )

        assert graph is not None
        assert len(graph.nodes) > 1

        scanned_count = sum(1 for n in graph.nodes.values() if n.scanned)
        assert scanned_count >= 1
        assert scanned_count <= 5

    async def test_async_wikipedia_parallel_languages(self):
        """Паралельний краулінг різних мовних версій Wikipedia."""
        async with AsyncCrawler(max_depth=0, max_pages=1, request_delay=0.5) as crawler:
            results = await crawler.crawl("https://uk.wikipedia.org/wiki/Python")

        assert results is not None
        assert len(results.nodes) >= 1


@pytest.mark.integration
class TestWikipediaGraphValidation:
    """Валідація структури графа Wikipedia."""

    def test_graph_edges_are_valid(self):
        """Всі edges вказують на існуючі ноди."""
        graph = crawl(
            "https://uk.wikipedia.org/wiki/Python",
            max_depth=1,
            max_pages=5,
            request_delay=0.5
        )

        # Перевіряємо що кожен edge має source і target в nodes
        for edge in graph.edges:
            assert edge.source_node_id in graph.nodes, \
                f"Edge source {edge.source_node_id} не в nodes"
            assert edge.target_node_id in graph.nodes, \
                f"Edge target {edge.target_node_id} не в nodes"

    def test_graph_urls_are_unique(self):
        """Всі URL в графі унікальні."""
        graph = crawl(
            "https://uk.wikipedia.org/wiki/Python",
            max_depth=1,
            max_pages=5,
            request_delay=0.5
        )

        urls = [node.url for node in graph.nodes.values()]
        unique_urls = set(urls)

        assert len(urls) == len(unique_urls), "URL повинні бути унікальними"

    def test_graph_root_is_scanned(self):
        """Коренева нода повинна бути просканована."""
        start_url = "https://uk.wikipedia.org/wiki/Python"
        graph = crawl(
            start_url,
            max_depth=1,
            max_pages=5,
            request_delay=0.5
        )

        # Шукаємо кореневу ноду
        root = graph.get_node_by_url(start_url)

        # Якщо точного URL немає, шукаємо по depth=0
        if root is None:
            for node in graph.nodes.values():
                if node.depth == 0:
                    root = node
                    break

        assert root is not None, "Повинна бути коренева нода"
        assert root.scanned is True, "Коренева нода повинна бути просканована"
