"""IStopCondition Protocol - динамічні умови зупинки краулінгу.

Phase 0: AI Agent Integration
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Callable, List, Optional, Protocol

from pydantic import BaseModel, ValidationError

if TYPE_CHECKING:
    from graph_crawler.domain.context.crawl_context import CrawlContext


class IStopCondition(Protocol):
    """
    Protocol для динамічних умов зупинки краулінгу.

    Викликається після обробки кожної сторінки для перевірки
    чи потрібно зупинити краулінг.
    """

    def should_stop(self, context: "CrawlContext") -> bool:
        """
        Перевіряє чи потрібно зупинитись.

        Args:
            context: Глобальний контекст краулінгу з accumulated state

        Returns:
            True якщо потрібно зупинитись
        """
        ...

    def get_reason(self) -> str:
        """
        Повертає причину зупинки для логування.

        Returns:
            Текстовий опис причини зупинки
        """
        ...


class BaseStopCondition(ABC):
    """Базовий клас для умов зупинки з загальною логікою."""

    def __init__(self, name: Optional[str] = None):
        self._name = name or self.__class__.__name__
        self._triggered = False
        self._trigger_reason: Optional[str] = None

    @abstractmethod
    def should_stop(self, context: "CrawlContext") -> bool:
        """Імплементація перевірки."""
        ...

    def get_reason(self) -> str:
        """Повертає причину зупинки."""
        return self._trigger_reason or f"{self._name} condition met"

    @property
    def name(self) -> str:
        """Назва умови."""
        return self._name

    @property
    def triggered(self) -> bool:
        """Чи була умова triggered."""
        return self._triggered


class TargetFoundStopCondition(BaseStopCondition):
    """
    Зупинка коли знайдено target.

    Перевіряє наявність ключа 'target_found' в контексті.
    """

    def __init__(self):
        super().__init__("TargetFound")

    def should_stop(self, context: "CrawlContext") -> bool:
        found = context.get("target_found", False)
        if found:
            self._triggered = True
            self._trigger_reason = "Target data found"
        return found


class SchemaCompleteStopCondition(BaseStopCondition):
    """
    Зупинка коли Pydantic схема повністю заповнена.

    Перевіряє чи всі required поля в схемі мають значення.
    """

    def __init__(self, schema: type[BaseModel]):
        super().__init__(f"SchemaComplete:{schema.__name__}")
        self.schema = schema

    def should_stop(self, context: "CrawlContext") -> bool:
        data = context.get("extracted_data", {})
        try:
            # Перевіряємо чи всі required поля заповнені
            self.schema.model_validate(data)
            self._triggered = True
            self._trigger_reason = f"Schema {self.schema.__name__} is complete"
            return True
        except ValidationError:
            return False

    def get_missing_fields(self, context: "CrawlContext") -> List[str]:
        """Повертає список незаповнених полів."""
        data = context.get("extracted_data", {})
        return [
            name
            for name, field in self.schema.model_fields.items()
            if field.is_required() and name not in data
        ]


class MaxPagesStopCondition(BaseStopCondition):
    """
    Зупинка після досягнення максимальної кількості сторінок.

    Корисно як safety limit для AI Agent.
    """

    def __init__(self, max_pages: int):
        super().__init__(f"MaxPages:{max_pages}")
        self.max_pages = max_pages

    def should_stop(self, context: "CrawlContext") -> bool:
        pages = context.get("pages_visited", 0)
        if pages >= self.max_pages:
            self._triggered = True
            self._trigger_reason = f"Reached max pages limit: {self.max_pages}"
            return True
        return False


class CallableStopCondition(BaseStopCondition):
    """
    Зупинка на основі callable функції.

    Дозволяє визначити кастомну логіку через lambda або функцію.
    """

    def __init__(
        self,
        condition: Callable[["CrawlContext"], bool],
        reason: str = "Custom condition met",
        name: str = "Callable",
    ):
        super().__init__(name)
        self._condition = condition
        self._custom_reason = reason

    def should_stop(self, context: "CrawlContext") -> bool:
        result = self._condition(context)
        if result:
            self._triggered = True
            self._trigger_reason = self._custom_reason
        return result


class CompositeStopCondition(BaseStopCondition):
    """
    Комбінація декількох умов (AND/OR логіка).

    mode='any': Зупинка якщо будь-яка умова True (OR)
    mode='all': Зупинка якщо всі умови True (AND)
    """

    def __init__(
        self,
        conditions: List[IStopCondition],
        mode: str = "any",
    ):
        if mode not in ("any", "all"):
            raise ValueError("mode must be 'any' or 'all'")

        super().__init__(f"Composite:{mode}")
        self.conditions = conditions
        self.mode = mode
        self._triggered_conditions: List[IStopCondition] = []

    def should_stop(self, context: "CrawlContext") -> bool:
        results = []
        for condition in self.conditions:
            if condition.should_stop(context):
                self._triggered_conditions.append(condition)
                results.append(True)
            else:
                results.append(False)

        should_stop = any(results) if self.mode == "any" else all(results)

        if should_stop:
            self._triggered = True
            reasons = [c.get_reason() for c in self._triggered_conditions]
            self._trigger_reason = f"Composite ({self.mode}): {'; '.join(reasons)}"

        return should_stop

    @property
    def triggered_conditions(self) -> List[IStopCondition]:
        """Список умов які спрацювали."""
        return self._triggered_conditions
