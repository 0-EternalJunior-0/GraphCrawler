"""Тести для RetryLLMWrapper та CrawlContext в AIAgent.

Запуск:
    pytest tests/test_retry_and_context.py -v
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import BaseModel

from graph_crawler.domain.interfaces import LLMRateLimitError, LLMTimeoutError

class TestRetryLLMWrapper:
    """Тести для RetryLLMWrapper."""

    @pytest.fixture
    def mock_model(self):
        """Створює mock LLM модель."""
        model = MagicMock()
        model.model_name = "test-model"
        model.complete = AsyncMock(return_value="response")
        model.complete_structured = AsyncMock(return_value={"key": "value"})
        return model

    @pytest.mark.asyncio
    async def test_successful_request_no_retry(self, mock_model):
        """Успішний запит без retry."""
        from graph_crawler.ai.models.retry_wrapper import RetryLLMWrapper

        wrapper = RetryLLMWrapper(mock_model, max_retries=3)
        result = await wrapper.complete("test prompt")

        assert result == "response"
        assert mock_model.complete.call_count == 1
        assert wrapper.stats["total_retries"] == 0

    @pytest.mark.asyncio
    async def test_retry_on_rate_limit(self, mock_model):
        """Retry при rate limit помилці."""
        from graph_crawler.ai.models.retry_wrapper import RetryLLMWrapper

        # Перші 2 виклики - rate limit, третій - успіх
        mock_model.complete.side_effect = [
            LLMRateLimitError("Rate limit"),
            LLMRateLimitError("Rate limit"),
            "success after retry",
        ]

        wrapper = RetryLLMWrapper(mock_model, max_retries=3, base_delay=0.01)
        result = await wrapper.complete("test prompt")

        assert result == "success after retry"
        assert mock_model.complete.call_count == 3
        assert wrapper.stats["total_retries"] == 2
        assert wrapper.stats["successful_retries"] == 1

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, mock_model):
        """Помилка коли всі retry вичерпано."""
        from graph_crawler.ai.models.retry_wrapper import RetryLLMWrapper

        mock_model.complete.side_effect = LLMRateLimitError("Rate limit")

        wrapper = RetryLLMWrapper(mock_model, max_retries=2, base_delay=0.01)

        with pytest.raises(LLMRateLimitError):
            await wrapper.complete("test prompt")

        # 1 initial + 2 retries = 3 calls
        assert mock_model.complete.call_count == 3

    @pytest.mark.asyncio
    async def test_no_retry_on_other_errors(self, mock_model):
        """Не повторювати при інших помилках."""
        from graph_crawler.ai.models.retry_wrapper import RetryLLMWrapper

        mock_model.complete.side_effect = ValueError("Some error")

        wrapper = RetryLLMWrapper(mock_model, max_retries=3)

        with pytest.raises(ValueError):
            await wrapper.complete("test prompt")

        assert mock_model.complete.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_timeout_when_enabled(self, mock_model):
        """Retry на timeout якщо включено."""
        from graph_crawler.ai.models.retry_wrapper import RetryLLMWrapper

        mock_model.complete.side_effect = [
            LLMTimeoutError("Timeout"),
            "success",
        ]

        wrapper = RetryLLMWrapper(
            mock_model,
            max_retries=3,
            base_delay=0.01,
            retry_on_timeout=True
        )
        result = await wrapper.complete("test prompt")

        assert result == "success"
        assert mock_model.complete.call_count == 2

    @pytest.mark.asyncio
    async def test_structured_completion_retry(self, mock_model):
        """Retry для structured completion."""
        from graph_crawler.ai.models.retry_wrapper import RetryLLMWrapper

        class TestSchema(BaseModel):
            name: str

        mock_model.complete_structured.side_effect = [
            LLMRateLimitError("Rate limit"),
            TestSchema(name="test"),
        ]

        wrapper = RetryLLMWrapper(mock_model, max_retries=3, base_delay=0.01)
        result = await wrapper.complete_structured("prompt", TestSchema)

        assert result.name == "test"
        assert mock_model.complete_structured.call_count == 2

    def test_model_name_property(self, mock_model):
        """Перевірка model_name property."""
        from graph_crawler.ai.models.retry_wrapper import RetryLLMWrapper

        wrapper = RetryLLMWrapper(mock_model)
        assert wrapper.model_name == "test-model"

    def test_exponential_backoff_calculation(self, mock_model):
        """Перевірка розрахунку затримки."""
        from graph_crawler.ai.models.retry_wrapper import RetryLLMWrapper

        wrapper = RetryLLMWrapper(mock_model, base_delay=1.0, max_delay=10.0)

        assert wrapper._calculate_delay(0) == 1.0   # 1 * 2^0 = 1
        assert wrapper._calculate_delay(1) == 2.0   # 1 * 2^1 = 2
        assert wrapper._calculate_delay(2) == 4.0   # 1 * 2^2 = 4
        assert wrapper._calculate_delay(3) == 8.0   # 1 * 2^3 = 8
        assert wrapper._calculate_delay(4) == 10.0  # capped at max_delay

class TestAIAgentCrawlContext:
    """Тести для перевірки що AIAgent створює CrawlContext (BUG #2 fix)."""

    @pytest.mark.asyncio
    async def test_agent_creates_crawl_context_with_output(self):
        """AIAgent повинен створювати CrawlContext з result_schema."""
        from graph_crawler.ai.agent import AIAgent
        from graph_crawler.domain.context import CrawlContext

        # Mock модель
        mock_model = MagicMock()
        mock_model.model_name = "test-model"

        class TestOutput(BaseModel):
            name: str
            value: int

        agent = AIAgent(model=mock_model, max_pages=5)

        # Патчимо async_crawl щоб перевірити що crawl_context передається
        crawl_context_received = None

        async def mock_async_crawl(*args, **kwargs):
            nonlocal crawl_context_received
            crawl_context_received = kwargs.get('crawl_context')

            # Повертаємо мінімальний граф
            from graph_crawler.domain.entities.graph import Graph
            return Graph()

        with patch('graph_crawler.api.async_crawl', side_effect=mock_async_crawl):
            try:
                await agent.crawl(
                    url="https://example.com",
                    task="Find data",
                    output=TestOutput
                )
            except Exception:
                pass  # Ігноруємо помилки від extraction plugin

        # Головна перевірка: crawl_context був переданий і має правильну схему
        assert crawl_context_received is not None, "crawl_context should be passed to async_crawl"
        assert isinstance(crawl_context_received, CrawlContext), "Should be CrawlContext instance"
        assert crawl_context_received.result_schema == TestOutput, "result_schema should match output"

    @pytest.mark.asyncio
    async def test_agent_creates_empty_context_without_output(self):
        """AIAgent створює пустий CrawlContext якщо output не передано."""
        from graph_crawler.ai.agent import AIAgent
        from graph_crawler.domain.context import CrawlContext

        mock_model = MagicMock()
        mock_model.model_name = "test-model"

        agent = AIAgent(model=mock_model, max_pages=5)

        crawl_context_received = None

        async def mock_async_crawl(*args, **kwargs):
            nonlocal crawl_context_received
            crawl_context_received = kwargs.get('crawl_context')
            from graph_crawler.domain.entities.graph import Graph
            return Graph()

        with patch('graph_crawler.api.async_crawl', side_effect=mock_async_crawl):
            try:
                await agent.crawl(
                    url="https://example.com",
                    task="Find something",
                    output=None  # Без output schema
                )
            except Exception:
                pass

        assert crawl_context_received is not None
        assert isinstance(crawl_context_received, CrawlContext)
        assert crawl_context_received.result_schema is None

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
