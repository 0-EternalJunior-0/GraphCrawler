"""Emergent Universal Model - використовує emergentintegrations для LLM.

Працює з Emergent Universal Key та підтримує різні провайдери:
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


class EmergentModel:
    """
    Реалізація ILanguageModel для Emergent Universal Key.

    Використовує emergentintegrations бібліотеку для роботи з різними LLM провайдерами
    через єдиний API ключ.

    Attributes:
        provider: Провайдер (openai, anthropic, gemini)
        model: Назва моделі
        temperature: Температура генерації
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        provider: str = "openai",
        model: str = "gpt-4o-mini",
        temperature: float = 0.7,
        timeout: float = 60.0,
    ):
        """
        Ініціалізує Emergent модель.

        Args:
            api_key: Emergent Universal Key (або з EMERGENT_LLM_KEY env)
            provider: Провайдер LLM (openai, anthropic, gemini)
            model: Назва моделі
            temperature: Температура генерації
            timeout: Таймаут запиту в секундах
        """
        self._api_key = api_key or os.environ.get("EMERGENT_LLM_KEY")
        if not self._api_key:
            raise ValueError(
                "Emergent LLM key is required. "
                "Pass api_key parameter or set EMERGENT_LLM_KEY environment variable."
            )

        self._provider = provider
        self._model = model
        self._temperature = temperature
        self._timeout = timeout
        self._chat = None
        self._session_counter = 0

    def _get_chat(self, session_suffix: str = ""):
        """Створює новий LlmChat інстанс."""
        try:
            from emergentintegrations.llm.chat import LlmChat

            self._session_counter += 1
            session_id = f"crawl-{self._session_counter}-{session_suffix}"

            chat = LlmChat(
                api_key=self._api_key or "",
                session_id=session_id,
                system_message="You are a helpful data extraction assistant. Extract only the information that is explicitly present in the provided content.",
            )
            chat.with_model(self._provider, self._model)
            return chat

        except ImportError:
            raise LLMError(
                "emergentintegrations package is not installed. "
                "Install with: pip install emergentintegrations",
                model=self.model_name,
            )

    @property
    def model_name(self) -> str:
        """Унікальний ідентифікатор моделі."""
        return f"emergent:{self._provider}:{self._model}"

    async def complete(self, prompt: str) -> str:
        """
        Текстове завершення.

        Args:
            prompt: Текст запиту

        Returns:
            Відповідь моделі

        Raises:
            LLMError: При помилці API
        """
        from emergentintegrations.llm.chat import UserMessage

        chat = self._get_chat("complete")

        try:
            user_message = UserMessage(text=prompt)
            response = await chat.send_message(user_message)
            return response or ""

        except Exception as e:
            error_str = str(e).lower()

            if "rate_limit" in error_str or "rate limit" in error_str:
                raise LLMRateLimitError(f"Rate limit exceeded: {e}", model=self.model_name)
            elif "timeout" in error_str:
                raise LLMTimeoutError(
                    f"Request timed out: {e}", model=self.model_name, timeout=self._timeout
                )
            else:
                raise LLMError(f"LLM API error: {e}", model=self.model_name)

    async def complete_structured(
        self,
        prompt: str,
        output_schema: type[T],
    ) -> T:
        """
        Структуроване завершення з валідацією через Pydantic.

        Args:
            prompt: Текст запиту
            output_schema: Pydantic модель для валідації

        Returns:
            Об'єкт вказаного типу

        Raises:
            LLMError: При помилці API
            ValidationError: Якщо відповідь не відповідає схемі
        """
        from emergentintegrations.llm.chat import UserMessage

        chat = self._get_chat("structured")

        # Генеруємо JSON schema з Pydantic моделі
        schema = output_schema.model_json_schema()

        # Створюємо спрощений опис полів
        fields_desc = []
        for prop_name, prop_info in schema.get("properties", {}).items():
            prop_type = prop_info.get("type", "string")
            required = prop_name in schema.get("required", [])
            fields_desc.append(
                f'  "{prop_name}": <{prop_type}>{" (required)" if required else " (optional)"}'
            )

        fields_str = ",\n".join(fields_desc)

        structured_prompt = f"""{prompt}

IMPORTANT: Extract the actual data and respond with a JSON object in this format:
{{
{fields_str}
}}

Rules:
1. Extract ACTUAL VALUES from the content, not the schema structure
2. For required fields that cannot be found, use reasonable defaults or "Unknown"
3. For optional fields that cannot be found, use null
4. Respond ONLY with the JSON object, no additional text"""

        response: str = ""
        try:
            user_message = UserMessage(text=structured_prompt)
            response = await chat.send_message(user_message)

            # Парсимо JSON з відповіді
            response_text = (response or "").strip()

            # Видаляємо можливі markdown code blocks
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            elif response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]

            response_text = response_text.strip()

            data = json.loads(response_text)
            return output_schema.model_validate(data)

        except json.JSONDecodeError as e:
            raise LLMError(
                f"Failed to parse JSON response: {e}. Response: {response[:500] if response else 'empty'}",
                model=self.model_name,
            )
        except Exception as e:
            if "ValidationError" in type(e).__name__:
                raise  # Re-raise Pydantic validation errors

            error_str = str(e).lower()
            if "rate_limit" in error_str or "rate limit" in error_str:
                raise LLMRateLimitError(f"Rate limit exceeded: {e}", model=self.model_name)
            elif "timeout" in error_str:
                raise LLMTimeoutError(
                    f"Request timed out: {e}", model=self.model_name, timeout=self._timeout
                )
            else:
                raise LLMError(f"LLM API error: {e}", model=self.model_name)

    def __repr__(self) -> str:
        return f"EmergentModel(provider={self._provider}, model={self._model})"
