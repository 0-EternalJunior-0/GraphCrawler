"""ILanguageModel Protocol - абстракція для LLM провайдерів.

Phase 0: AI Agent Integration
"""

from typing import Optional, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@runtime_checkable
class ILanguageModel(Protocol):
    """
    Protocol для LLM провайдерів.

    Визначає мінімальний інтерфейс для інтеграції будь-якого LLM
    в систему краулінгу.

    Attributes:
        model_name: Унікальний ідентифікатор моделі для логування

    Methods:
        complete: Текстове завершення (вільний текст)
        complete_structured: Структуроване завершення (Pydantic модель)
    """

    @property
    def model_name(self) -> str:
        """
        Назва моделі для логування та моніторингу.

        Returns:
            Унікальний ідентифікатор, наприклад "openai:gpt-4" або "anthropic:claude-3"
        """
        ...

    async def complete(self, prompt: str) -> str:
        """
        Текстове завершення.

        Args:
            prompt: Текст запиту до моделі

        Returns:
            Відповідь моделі у вигляді тексту

        Raises:
            LLMError: При помилці API або таймауті
        """
        ...

    async def complete_structured(
        self,
        prompt: str,
        output_schema: type[T],
    ) -> T:
        """
        Структуроване завершення з валідацією через Pydantic.

        Args:
            prompt: Текст запиту до моделі
            output_schema: Pydantic модель для валідації відповіді

        Returns:
            Об'єкт вказаного типу з валідованими даними

        Raises:
            LLMError: При помилці API
            ValidationError: Якщо відповідь не відповідає схемі
        """
        ...


class LLMError(Exception):
    """Базова помилка LLM операцій."""

    def __init__(
        self,
        message: str,
        model: Optional[str] = None,
        retryable: bool = False,
    ):
        super().__init__(message)
        self.model = model
        self.retryable = retryable


class LLMRateLimitError(LLMError):
    """Помилка rate limiting."""

    def __init__(self, message: str, model: Optional[str] = None, retry_after: Optional[float] = None):
        super().__init__(message, model, retryable=True)
        self.retry_after = retry_after


class LLMTimeoutError(LLMError):
    """Помилка таймауту."""

    def __init__(self, message: str, model: Optional[str] = None, timeout: Optional[float] = None):
        super().__init__(message, model, retryable=True)
        self.timeout = timeout
