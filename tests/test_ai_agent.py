"""Тести для AI Agent Integration.

Перевіряє:
- OpenAIModel та AnthropicModel
- AIExtractionPlugin
- AIAgent
- Інтеграцію з CrawlContext та StopConditions
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import BaseModel

from graph_crawler.ai import AIAgent, OpenAIModel, AnthropicModel, AIExtractionPlugin
from graph_crawler.domain.interfaces import (
    ILanguageModel,
    LLMError,
    LLMRateLimitError,
    LLMTimeoutError,
    SchemaCompleteStopCondition,
    MaxPagesStopCondition,
    TargetFoundStopCondition,
)
from graph_crawler.domain.context import CrawlContext
from graph_crawler.extensions.plugins.node.base import NodePluginContext, NodePluginType
class ProductInfo(BaseModel):
    """Тестова схема продукту."""
    name: str
    price: float
    description: str = None

class CompanyInfo(BaseModel):
    """Тестова схема компанії."""
    name: str
    employees: int
    headquarters: str = None
class MockLLM:
    """Mock реалізація ILanguageModel для тестування."""

    def __init__(self, responses: dict = None):
        self.responses = responses or {}
        self.calls = []

    @property
    def model_name(self) -> str:
        return "mock:test"

    async def complete(self, prompt: str) -> str:
        self.calls.append(("complete", prompt))
        return self.responses.get("complete", "Mock response")

    async def complete_structured(self, prompt: str, output_schema):
        self.calls.append(("complete_structured", prompt, output_schema))
        data = self.responses.get("structured", {"name": "Test", "price": 99.99})
        return output_schema.model_validate(data)
class TestCrawlContext:
    """Тести для CrawlContext."""

    def test_basic_operations(self):
        """Тест базових операцій."""
        ctx = CrawlContext()

        # set/get
        ctx.set("key", "value")
        assert ctx.get("key") == "value"
        assert ctx.get("missing", "default") == "default"

        # increment
        ctx.increment("counter")
        assert ctx.get("counter") == 1
        ctx.increment("counter", 5)
        assert ctx.get("counter") == 6

        # append_to_list
        ctx.append_to_list("items", "a")
        ctx.append_to_list("items", "b")
        assert ctx.get("items") == ["a", "b"]

    def test_predefined_properties(self):
        """Тест предвизначених властивостей."""
        ctx = CrawlContext()

        assert ctx.pages_visited == 0
        ctx.increment_pages_visited()
        assert ctx.pages_visited == 1

        assert ctx.target_found is False
        ctx.target_found = True
        assert ctx.target_found is True

        ctx.add_error("Test error", url="http://test.com")
        assert len(ctx.errors) == 1
        assert ctx.errors[0]["error"] == "Test error"

    def test_result_aggregation(self):
        """Тест агрегації результатів."""
        ctx = CrawlContext(result_schema=ProductInfo)

        # Додаємо частинки даних
        ctx.add_extracted_data({"name": "iPhone"}, source_url="http://a.com")
        ctx.add_extracted_data({"price": 999.0}, source_url="http://b.com")

        # Перевіряємо completeness
        assert ctx.result_completeness > 0.5
        assert ctx.result_complete is True  # name та price заповнені
        assert "description" in ctx.get_missing_fields()

        # Перевіряємо результат
        result = ctx.result
        assert result is not None
        assert result.name == "iPhone"
        assert result.price == 999.0

    def test_observers(self):
        """Тест observers."""
        ctx = CrawlContext()
        changes = []

        def observer(key, old, new):
            changes.append((key, old, new))

        unsubscribe = ctx.observe(observer)

        ctx.set("test", "value1")
        ctx.set("test", "value2")

        assert len(changes) == 2
        assert changes[0] == ("test", None, "value1")
        assert changes[1] == ("test", "value1", "value2")

        unsubscribe()
        ctx.set("test", "value3")
        assert len(changes) == 2  # Observer не викликаний
class TestStopConditions:
    """Тести для StopConditions."""

    def test_target_found_condition(self):
        """Тест TargetFoundStopCondition."""
        ctx = CrawlContext()
        condition = TargetFoundStopCondition()

        assert not condition.should_stop(ctx)

        ctx.target_found = True
        assert condition.should_stop(ctx)
        assert "Target" in condition.get_reason()

    def test_max_pages_condition(self):
        """Тест MaxPagesStopCondition."""
        ctx = CrawlContext()
        condition = MaxPagesStopCondition(5)

        for i in range(4):
            ctx.increment_pages_visited()
            assert not condition.should_stop(ctx)

        ctx.increment_pages_visited()  # 5th page
        assert condition.should_stop(ctx)

    def test_schema_complete_condition(self):
        """Тест SchemaCompleteStopCondition."""
        ctx = CrawlContext()
        condition = SchemaCompleteStopCondition(ProductInfo)

        # Неповні дані
        ctx.set("extracted_data", {"name": "Test"})
        assert not condition.should_stop(ctx)

        # Повні дані
        ctx.set("extracted_data", {"name": "Test", "price": 99.99})
        assert condition.should_stop(ctx)
class TestAIExtractionPlugin:
    """Тести для AIExtractionPlugin."""

    def test_plugin_properties(self):
        """Тест властивостей плагіну."""
        mock_llm = MockLLM()
        plugin = AIExtractionPlugin(
            model=mock_llm,
            task="Extract product info",
            output_schema=ProductInfo
        )

        assert plugin.name == "AIExtractionPlugin"
        assert plugin.plugin_type == NodePluginType.ON_HTML_PARSED

    @pytest.mark.asyncio
    async def test_extraction_with_schema(self):
        """Тест extraction з Pydantic схемою."""
        mock_llm = MockLLM(responses={
            "structured": {"name": "iPhone 15", "price": 999.0}
        })

        plugin = AIExtractionPlugin(
            model=mock_llm,
            task="Extract product info",
            output_schema=ProductInfo
        )

        ctx = CrawlContext(result_schema=ProductInfo)
        node_ctx = NodePluginContext(
            node=MagicMock(),
            url="http://test.com",
            depth=0,
            should_scan=True,
            can_create_edges=True,
            html="<html><body><h1>iPhone 15</h1><p>Price: $999</p></body></html>",
            crawl_context=ctx,
        )

        result = await plugin.execute(node_ctx)

        assert len(mock_llm.calls) == 1
        assert mock_llm.calls[0][0] == "complete_structured"
        assert "ai_extracted" in result.user_data

    @pytest.mark.asyncio
    async def test_extraction_without_html(self):
        """Тест extraction без HTML."""
        mock_llm = MockLLM()
        plugin = AIExtractionPlugin(
            model=mock_llm,
            task="Extract data"
        )

        node_ctx = NodePluginContext(
            node=MagicMock(),
            url="http://test.com",
            depth=0,
            should_scan=True,
            can_create_edges=True,
            html=None,
        )

        _ = await plugin.execute(node_ctx)

        # Не має бути викликів до LLM
        assert len(mock_llm.calls) == 0

    def test_markdown_generator_converts_html(self):
        """Тест конвертації HTML в Markdown через MarkdownGenerator."""
        from graph_crawler.shared.utils.markdown.generator import MarkdownGenerator
        from graph_crawler.shared.utils.markdown.options import MarkdownOptions

        options = MarkdownOptions(
            include_links=True,
            remove_nav=True,
            remove_header=True,
            remove_footer=True,
        )
        generator = MarkdownGenerator(options)

        html = """
        <html>
        <head><title>Test</title><script>alert('x')</script></head>
        <body>
            <h1>Hello World</h1>
            <p>This is a <b>test</b> page.</p>
            <style>.hidden{display:none}</style>
        </body>
        </html>
        """

        result = generator.generate_from_html(html)
        markdown = result.fit_markdown

        assert "Hello World" in markdown
        assert "test" in markdown
        assert "alert" not in markdown  # script видалено
        assert ".hidden" not in markdown  # style видалено
class TestAIAgent:
    """Тести для AIAgent."""

    def test_agent_initialization(self):
        """Тест ініціалізації агента."""
        mock_llm = MockLLM()
        agent = AIAgent(model=mock_llm, max_pages=30, max_depth=2)

        assert agent.max_pages == 30
        assert agent.max_depth == 2
        assert agent.model == mock_llm

    def test_agent_has_expected_attributes(self):
        """Тест що агент має очікувані атрибути."""
        mock_llm = MockLLM()
        agent = AIAgent(model=mock_llm, max_pages=50)

        # Перевіряємо наявність основних атрибутів
        assert hasattr(agent, 'model')
        assert hasattr(agent, 'max_pages')
        assert hasattr(agent, 'max_depth')
        assert hasattr(agent, 'crawl')

        # Перевіряємо значення
        assert agent.max_pages == 50
        assert agent.model == mock_llm
class TestIntegration:
    """Інтеграційні тести."""

    def test_context_with_plugin_context(self):
        """Тест інтеграції CrawlContext з NodePluginContext."""
        crawl_ctx = CrawlContext(result_schema=ProductInfo)

        node_ctx = NodePluginContext(
            node=MagicMock(),
            url="http://test.com",
            depth=0,
            should_scan=True,
            can_create_edges=True,
            crawl_context=crawl_ctx,
        )

        # Тестуємо helper методи
        node_ctx.set_in_crawl_context("test_key", "test_value")
        assert node_ctx.get_from_crawl_context("test_key") == "test_value"

        # Тестуємо add_extracted_to_context
        node_ctx.add_extracted_to_context({"name": "iPhone", "price": 999.0})

        assert crawl_ctx.result_complete is True
        result = crawl_ctx.result
        assert result.name == "iPhone"
        assert result.price == 999.0
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
