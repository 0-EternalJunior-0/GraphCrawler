"""OpenAI Model - реалізація ILanguageModel для OpenAI API.

Підтримує:
"""

import json
import os
from typing import Optional, TypeVar

from pydantic import BaseModel

from graph_crawler.domain.interfaces import (
    LLMError,
    LLMRateLimitError,
    LLMTimeoutError,
)

T = TypeVar("T", bound=BaseModel)


class OpenAIModel:
    """
    Реалізація ILanguageModel для OpenAI API.

    Підтримує GPT-4, GPT-4o, GPT-4o-mini та інші моделі OpenAI.

    Attributes:
        model: Назва моделі (gpt-4o-mini за замовчуванням)
        temperature: Температура генерації (0.0 - 2.0)
        max_tokens: Максимальна кількість токенів у відповіді
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        timeout: float = 60.0,
    ):
        """
        Ініціалізує OpenAI модель.

        Args:
            api_key: API ключ OpenAI (або з OPENAI_API_KEY env)
            model: Назва моделі
            temperature: Температура генерації
            max_tokens: Максимальна кількість токенів
            timeout: Таймаут запиту в секундах
        """
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self._api_key:
            raise ValueError(
                "OpenAI API key is required. "
                "Pass api_key parameter or set OPENAI_API_KEY environment variable."
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
                from openai import AsyncOpenAI

                self._client = AsyncOpenAI(
                    api_key=self._api_key,
                    timeout=self._timeout,
                )
            except ImportError:
                raise LLMError(
                    "openai package is not installed. Install with: pip install openai",
                    model=self.model_name,
                )
        return self._client

    @property
    def model_name(self) -> str:
        """Унікальний ідентифікатор моделі."""
        return f"openai:{self._model}"

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
            response = await client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self._temperature,
                max_tokens=self._max_tokens,
            )
            return response.choices[0].message.content or ""

        except Exception as e:
            error_str = str(e).lower()

            if "rate_limit" in error_str or "rate limit" in error_str:
                raise LLMRateLimitError(f"OpenAI rate limit exceeded: {e}", model=self.model_name)
            elif "timeout" in error_str:
                raise LLMTimeoutError(
                    f"OpenAI request timed out: {e}", model=self.model_name, timeout=self._timeout
                )
            else:
                raise LLMError(f"OpenAI API error: {e}", model=self.model_name)

    async def complete_structured(
        self,
        prompt: str,
        output_schema: type[T],
    ) -> T:
        """
        Структуроване завершення з валідацією через Pydantic.

        Використовує function calling для отримання структурованої відповіді.

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

        function_def = {
            "name": "extract_data",
            "description": f"Extract data according to {output_schema.__name__} schema",
            "parameters": schema,
        }

        try:
            response = await client.chat.completions.create(
                model=self._model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a data extraction assistant. "
                            "Extract the requested information and return it in the specified format. "
                            "Only include fields that you can confidently extract from the content."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                functions=[function_def],  # type: ignore[arg-type]
                function_call={"name": "extract_data"},
                temperature=0.1,  # Низька температура для точності
                max_tokens=self._max_tokens,
            )

            # Парсимо function call response
            function_call = response.choices[0].message.function_call
            if function_call and function_call.arguments:
                data = json.loads(function_call.arguments)
                return output_schema.model_validate(data)
            else:
                raise LLMError("No function call in response", model=self.model_name)

        except json.JSONDecodeError as e:
            raise LLMError(f"Failed to parse JSON response: {e}", model=self.model_name)
        except Exception as e:
            if "ValidationError" in type(e).__name__:
                raise  # Re-raise Pydantic validation errors

            error_str = str(e).lower()
            if "rate_limit" in error_str or "rate limit" in error_str:
                raise LLMRateLimitError(f"OpenAI rate limit exceeded: {e}", model=self.model_name)
            elif "timeout" in error_str:
                raise LLMTimeoutError(
                    f"OpenAI request timed out: {e}", model=self.model_name, timeout=self._timeout
                )
            else:
                raise LLMError(f"OpenAI API error: {e}", model=self.model_name)

    def __repr__(self) -> str:
        return f"OpenAIModel(model={self._model}, temperature={self._temperature})"
