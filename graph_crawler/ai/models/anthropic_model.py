"""Anthropic Model - реалізація ILanguageModel для Anthropic Claude API.

Підтримує:
"""

import os
from typing import Optional, TypeVar

from pydantic import BaseModel

from graph_crawler.domain.interfaces import (
    LLMError,
    LLMRateLimitError,
    LLMTimeoutError,
)

T = TypeVar("T", bound=BaseModel)


class AnthropicModel:
    """
    Реалізація ILanguageModel для Anthropic Claude API.

    Підтримує Claude 3, Claude 3.5 та інші моделі Anthropic.

    Attributes:
        model: Назва моделі (claude-3-sonnet-20240229 за замовчуванням)
        temperature: Температура генерації (0.0 - 1.0)
        max_tokens: Максимальна кількість токенів у відповіді
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-sonnet-20240229",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        timeout: float = 60.0,
    ):
        """
        Ініціалізує Anthropic модель.

        Args:
            api_key: API ключ Anthropic (або з ANTHROPIC_API_KEY env)
            model: Назва моделі
            temperature: Температура генерації
            max_tokens: Максимальна кількість токенів
            timeout: Таймаут запиту в секундах
        """
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self._api_key:
            raise ValueError(
                "Anthropic API key is required. "
                "Pass api_key parameter or set ANTHROPIC_API_KEY environment variable."
            )

        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._timeout = timeout
        self._client = None

    def _get_client(self):
        """Lazy ініціалізація клієнта."""
        if self._client is None:
            try:
                from anthropic import AsyncAnthropic  # type: ignore[import-not-found]

                self._client = AsyncAnthropic(
                    api_key=self._api_key,
                    timeout=self._timeout,
                )
            except ImportError:
                raise LLMError(
                    "anthropic package is not installed. Install with: pip install anthropic",
                    model=self.model_name,
                )
        return self._client

    @property
    def model_name(self) -> str:
        """Унікальний ідентифікатор моделі."""
        return f"anthropic:{self._model}"

    async def complete(self, prompt: str) -> str:
        """
        Текстове завершення.

        Args:
            prompt: Текст запиту

        Returns:
            Відповідь моделі

        Raises:
            LLMError: При помилці API
            LLMRateLimitError: При rate limiting
            LLMTimeoutError: При таймауті
        """
        client = self._get_client()

        try:
            message = await client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                temperature=self._temperature,
                messages=[{"role": "user", "content": prompt}],
            )

            # Anthropic повертає список content blocks
            text_blocks = [block.text for block in message.content if hasattr(block, "text")]
            return "\n".join(text_blocks)

        except Exception as e:
            error_str = str(e).lower()

            if "rate_limit" in error_str or "rate limit" in error_str:
                raise LLMRateLimitError(
                    f"Anthropic rate limit exceeded: {e}", model=self.model_name
                )
            elif "timeout" in error_str:
                raise LLMTimeoutError(
                    f"Anthropic request timed out: {e}",
                    model=self.model_name,
                    timeout=self._timeout,
                )
            else:
                raise LLMError(f"Anthropic API error: {e}", model=self.model_name)

    async def complete_structured(
        self,
        prompt: str,
        output_schema: type[T],
    ) -> T:
        """
        Структуроване завершення з валідацією через Pydantic.

        Використовує tool use для отримання структурованої відповіді.

        Args:
            prompt: Текст запиту
            output_schema: Pydantic модель для валідації

        Returns:
            Об'єкт вказаного типу

        Raises:
            LLMError: При помилці API
            ValidationError: Якщо відповідь не відповідає схемі
        """
        client = self._get_client()

        # Генеруємо JSON schema з Pydantic моделі
        schema = output_schema.model_json_schema()

        # Видаляємо непідтримувані поля
        if "title" in schema:
            del schema["title"]
        if "$defs" in schema:
            del schema["$defs"]

        tool_def = {
            "name": "extract_data",
            "description": f"Extract data according to {output_schema.__name__} schema",
            "input_schema": schema,
        }

        try:
            message = await client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                temperature=0.1,  # Низька температура для точності
                tools=[tool_def],
                tool_choice={"type": "tool", "name": "extract_data"},
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "Extract the requested information and return it "
                            f"using the extract_data tool.\n\n{prompt}"
                        ),
                    }
                ],
            )

            # Шукаємо tool use block у відповіді
            for block in message.content:
                if hasattr(block, "type") and block.type == "tool_use":
                    if block.name == "extract_data":
                        return output_schema.model_validate(block.input)

            raise LLMError("No tool use in response", model=self.model_name)

        except Exception as e:
            if "ValidationError" in type(e).__name__:
                raise  # Re-raise Pydantic validation errors

            error_str = str(e).lower()
            if "rate_limit" in error_str or "rate limit" in error_str:
                raise LLMRateLimitError(
                    f"Anthropic rate limit exceeded: {e}", model=self.model_name
                )
            elif "timeout" in error_str:
                raise LLMTimeoutError(
                    f"Anthropic request timed out: {e}",
                    model=self.model_name,
                    timeout=self._timeout,
                )
            else:
                raise LLMError(f"Anthropic API error: {e}", model=self.model_name)

    def __repr__(self) -> str:
        return f"AnthropicModel(model={self._model}, temperature={self._temperature})"
