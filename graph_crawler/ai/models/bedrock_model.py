"""AWS Bedrock Model - реалізація ILanguageModel для Amazon Bedrock.

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


class BedrockModel:
    """
    Реалізація ILanguageModel для AWS Bedrock.

    Підтримує Amazon Nova, Claude через Bedrock, Titan та інші моделі.

    Attributes:
        model_name: Назва моделі (eu.amazon.nova-lite-v1:0 за замовчуванням)
        temperature: Температура генерації (0.0 - 1.0)
        max_tokens: Максимальна кількість токенів у відповіді
    """

    def __init__(
        self,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_session_token: Optional[str] = None,
        region_name: Optional[str] = None,
        model_name: str = "eu.amazon.nova-lite-v1:0",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        timeout: float = 60.0,
    ):
        """
        Ініціалізує Bedrock модель.

        Args:
            aws_access_key_id: AWS Access Key ID (або з AWS_ACCESS_KEY_ID env)
            aws_secret_access_key: AWS Secret Access Key (або з AWS_SECRET_ACCESS_KEY env)
            aws_session_token: AWS Session Token (або з AWS_SESSION_TOKEN env)
            region_name: AWS Region (або з AWS_REGION env, за замовчуванням us-east-1)
            model_name: Назва моделі в Bedrock
            temperature: Температура генерації
            max_tokens: Максимальна кількість токенів
            timeout: Таймаут запиту в секундах
        """
        self._aws_access_key_id = aws_access_key_id or os.environ.get("AWS_ACCESS_KEY_ID")
        self._aws_secret_access_key = aws_secret_access_key or os.environ.get(
            "AWS_SECRET_ACCESS_KEY"
        )
        self._aws_session_token = aws_session_token or os.environ.get("AWS_SESSION_TOKEN")
        self._region_name = region_name or os.environ.get("AWS_REGION", "us-east-1")

        if not self._aws_access_key_id or not self._aws_secret_access_key:
            raise ValueError(
                "AWS credentials are required. "
                "Pass aws_access_key_id and aws_secret_access_key parameters "
                "or set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables."
            )

        self._model_name = model_name
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._timeout = timeout
        self._client = None

    def _get_client(self):
        """Lazy ініціалізація клієнта Bedrock."""
        if self._client is None:
            try:
                import boto3
                from botocore.config import Config

                config = Config(
                    read_timeout=self._timeout,
                    connect_timeout=self._timeout,
                    retries={"max_attempts": 3},
                )

                session_kwargs = {
                    "aws_access_key_id": self._aws_access_key_id,
                    "aws_secret_access_key": self._aws_secret_access_key,
                    "region_name": self._region_name,
                }

                if self._aws_session_token:
                    session_kwargs["aws_session_token"] = self._aws_session_token

                session = boto3.Session(**session_kwargs)
                self._client = session.client(service_name="bedrock-runtime", config=config)

            except ImportError:
                raise LLMError(
                    "boto3 package is not installed. Install with: pip install boto3",
                    model=self.model_name,
                )
        return self._client

    @property
    def model_name(self) -> str:
        """Унікальний ідентифікатор моделі."""
        return f"bedrock:{self._model_name}"

    def _is_nova_model(self) -> bool:
        """Перевіряє чи це Nova модель."""
        return "nova" in self._model_name.lower()

    def _is_claude_model(self) -> bool:
        """Перевіряє чи це Claude модель через Bedrock."""
        return "claude" in self._model_name.lower() or "anthropic" in self._model_name.lower()

    def _is_titan_model(self) -> bool:
        """Перевіряє чи це Titan модель."""
        return "titan" in self._model_name.lower()

    def _build_request_body(self, prompt: str, structured: bool = False) -> dict:
        """
        Створює тіло запиту в залежності від типу моделі.

        Args:
            prompt: Текст запиту
            structured: Чи це структурований запит

        Returns:
            Словник з тілом запиту
        """
        temperature = 0.1 if structured else self._temperature

        if self._is_nova_model():
            # Amazon Nova формат
            return {
                "messages": [{"role": "user", "content": [{"text": prompt}]}],
                "inferenceConfig": {
                    "temperature": temperature,
                    "maxTokens": self._max_tokens,
                },
            }
        elif self._is_claude_model():
            # Claude через Bedrock формат
            return {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": self._max_tokens,
                "temperature": temperature,
                "messages": [{"role": "user", "content": prompt}],
            }
        elif self._is_titan_model():
            # Amazon Titan формат
            return {
                "inputText": prompt,
                "textGenerationConfig": {
                    "temperature": temperature,
                    "maxTokenCount": self._max_tokens,
                },
            }
        else:
            # Дефолтний формат (Nova-сумісний)
            return {
                "messages": [{"role": "user", "content": [{"text": prompt}]}],
                "inferenceConfig": {
                    "temperature": temperature,
                    "maxTokens": self._max_tokens,
                },
            }

    def _parse_response(self, response_body: dict) -> str:
        """
        Парсить відповідь в залежності від типу моделі.

        Args:
            response_body: Тіло відповіді від Bedrock

        Returns:
            Текст відповіді
        """
        if self._is_nova_model():
            # Nova формат відповіді
            output = response_body.get("output", {})
            message = output.get("message", {})
            content = message.get("content", [])
            if content and isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and "text" in item:
                        return item["text"]
            return ""

        elif self._is_claude_model():
            # Claude через Bedrock формат відповіді
            content = response_body.get("content", [])
            text_parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
            return "\n".join(text_parts)

        elif self._is_titan_model():
            # Titan формат відповіді
            results = response_body.get("results", [])
            if results:
                return results[0].get("outputText", "")
            return ""
        else:
            # Дефолтний парсинг (Nova-сумісний)
            output = response_body.get("output", {})
            message = output.get("message", {})
            content = message.get("content", [])
            if content and isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and "text" in item:
                        return item["text"]
            return ""

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
        import asyncio

        client = self._get_client()
        request_body = self._build_request_body(prompt)

        try:
            # boto3 синхронний, тому використовуємо run_in_executor
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: client.invoke_model(
                    modelId=self._model_name,
                    body=json.dumps(request_body),
                    contentType="application/json",
                    accept="application/json",
                ),
            )

            response_body = json.loads(response["body"].read())
            return self._parse_response(response_body)

        except Exception as e:
            error_str = str(e).lower()

            if "throttling" in error_str or "rate" in error_str:
                raise LLMRateLimitError(f"Bedrock rate limit exceeded: {e}", model=self.model_name)
            elif "timeout" in error_str or "timed out" in error_str:
                raise LLMTimeoutError(
                    f"Bedrock request timed out: {e}", model=self.model_name, timeout=self._timeout
                )
            else:
                raise LLMError(f"Bedrock API error: {e}", model=self.model_name)

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
        # Генеруємо JSON schema з Pydantic моделі
        schema = output_schema.model_json_schema()
        schema_description = json.dumps(schema, indent=2, ensure_ascii=False)

        structured_prompt = f"""{prompt}

IMPORTANT: You MUST respond with a valid JSON object that matches this exact schema:
{schema_description}

Respond ONLY with the JSON object, no additional text, markdown formatting, or explanations.
If a field cannot be found in the content, omit it from the response (for optional fields) or use null."""

        response: str = ""
        try:
            response = await self.complete(structured_prompt)

            # Парсимо JSON з відповіді
            response_text = response.strip()

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
            if "throttling" in error_str or "rate" in error_str:
                raise LLMRateLimitError(f"Bedrock rate limit exceeded: {e}", model=self.model_name)
            elif "timeout" in error_str or "timed out" in error_str:
                raise LLMTimeoutError(
                    f"Bedrock request timed out: {e}", model=self.model_name, timeout=self._timeout
                )
            else:
                raise LLMError(f"Bedrock API error: {e}", model=self.model_name)

    def __repr__(self) -> str:
        return f"BedrockModel(model={self._model_name}, region={self._region_name})"
