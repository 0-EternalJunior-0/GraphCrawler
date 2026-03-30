"""Retry wrapper для LLM моделей з exponential backoff.

Захищає від тимчасових помилок rate limit при використанні LLM API.

Приклад використання:
    ```python
    from graph_crawler.ai.models import OpenAIModel
    from graph_crawler.ai.models.retry_wrapper import RetryLLMWrapper

    model = OpenAIModel(api_key="sk-...")
    wrapped_model = RetryLLMWrapper(model, max_retries=3)

    # Використовуємо як звичайну модель
    result = await wrapped_model.complete("Hello!")
    ```
"""

import asyncio
import logging
from typing import Any, Optional, Type

from graph_crawler.domain.interfaces import ILanguageModel, LLMRateLimitError, LLMTimeoutError

logger = logging.getLogger(__name__)


class RetryLLMWrapper:
    """
    Wrapper для ILanguageModel з автоматичним retry при rate limit.

    Використовує exponential backoff: 1s, 2s, 4s, 8s...

    Attributes:
        _model: Обгорнута LLM модель
        _max_retries: Максимальна кількість спроб
        _base_delay: Базова затримка в секундах
        _max_delay: Максимальна затримка в секундах
    """

    def __init__(
        self,
        model: ILanguageModel,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        retry_on_timeout: bool = False,
    ):
        """
        Ініціалізує RetryLLMWrapper.

        Args:
            model: ILanguageModel для обгортання
            max_retries: Максимальна кількість повторних спроб (default: 3)
            base_delay: Базова затримка між спробами в секундах (default: 1.0)
            max_delay: Максимальна затримка між спробами (default: 60.0)
            retry_on_timeout: Чи повторювати при timeout помилках (default: False)
        """
        self._model = model
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._retry_on_timeout = retry_on_timeout

        # Статистика
        self._total_retries = 0
        self._successful_retries = 0

    def _should_retry(self, error: Exception) -> bool:
        """Перевіряє чи варто повторювати запит."""
        if isinstance(error, LLMRateLimitError):
            return True
        if self._retry_on_timeout and isinstance(error, LLMTimeoutError):
            return True
        return False

    def _calculate_delay(self, attempt: int) -> float:
        """Розраховує затримку з exponential backoff."""
        delay = self._base_delay * (2**attempt)
        return min(delay, self._max_delay)

    async def complete(self, prompt: str, **kwargs) -> str:
        """
        Виконує completion з автоматичним retry.

        Args:
            prompt: Текст промпту
            **kwargs: Додаткові параметри для моделі

        Returns:
            Відповідь моделі

        Raises:
            LLMRateLimitError: Якщо всі спроби вичерпано
        """
        last_error: Optional[Exception] = None

        for attempt in range(self._max_retries + 1):
            try:
                result = await self._model.complete(prompt, **kwargs)

                # Успішний retry
                if attempt > 0:
                    self._successful_retries += 1
                    logger.info("Request succeeded after %s retries", attempt)

                return result

            except Exception as e:
                last_error = e

                if not self._should_retry(e):
                    raise

                if attempt == self._max_retries:
                    logger.error("All %s retries exhausted", self._max_retries)
                    raise

                delay = self._calculate_delay(attempt)
                self._total_retries += 1

                logger.warning(
                    f"Rate limit hit, retry {attempt + 1}/{self._max_retries} "
                    f"after {delay:.1f}s delay"
                )

                await asyncio.sleep(delay)

        # Не повинно дійти сюди, але на всяк випадок
        raise last_error  # type: ignore

    async def complete_structured(
        self,
        prompt: str,
        schema: Type[Any],
        **kwargs,
    ) -> Any:
        """
        Виконує structured completion з автоматичним retry.

        Args:
            prompt: Текст промпту
            schema: Pydantic схема для відповіді
            **kwargs: Додаткові параметри для моделі

        Returns:
            Структурована відповідь згідно схеми
        """
        last_error: Optional[Exception] = None

        for attempt in range(self._max_retries + 1):
            try:
                result = await self._model.complete_structured(prompt, schema, **kwargs)

                if attempt > 0:
                    self._successful_retries += 1
                    logger.info("Structured request succeeded after %s retries", attempt)

                return result

            except Exception as e:
                last_error = e

                if not self._should_retry(e):
                    raise

                if attempt == self._max_retries:
                    logger.error("All %s retries exhausted", self._max_retries)
                    raise

                delay = self._calculate_delay(attempt)
                self._total_retries += 1

                logger.warning(
                    f"Rate limit hit (structured), retry {attempt + 1}/{self._max_retries} "
                    f"after {delay:.1f}s delay"
                )

                await asyncio.sleep(delay)

        raise last_error  # type: ignore

    @property
    def model_name(self) -> str:
        """Повертає назву обгорнутої моделі."""
        return self._model.model_name

    @property
    def stats(self) -> dict:
        """Статистика retry."""
        return {
            "total_retries": self._total_retries,
            "successful_retries": self._successful_retries,
            "max_retries_setting": self._max_retries,
        }

    def reset_stats(self) -> None:
        """Скидає статистику."""
        self._total_retries = 0
        self._successful_retries = 0

    def __repr__(self) -> str:
        return f"RetryLLMWrapper(model={self._model.model_name}, max_retries={self._max_retries})"
