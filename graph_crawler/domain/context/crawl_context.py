"""CrawlContext - глобальний shared state для краулінгу.

Phase 1: AI Agent Integration
"""

import threading
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class CrawlContext:
    """
    Глобальний контекст краулінгу.

    Доступний для:
    - Spider
    - Scheduler
    - Plugins
    - External code (AI Agent)

    Thread-safe, observable.

    Attributes:
        result_schema: Pydantic схема для агрегації результатів
        created_at: Час створення контексту
    """

    def __init__(self, result_schema: Optional[type[BaseModel]] = None):
        """
        Ініціалізує CrawlContext.

        Args:
            result_schema: Опціональна Pydantic схема для валідації результату
        """
        self._state: Dict[str, Any] = {}
        self._observers: List[Callable[[str, Any, Any], None]] = []
        self._lock = threading.RLock()
        self._created_at = datetime.now(timezone.utc)

        # Result aggregation
        self._result_schema = result_schema
        self._aggregator: Optional["PydanticResultAggregator"] = None
        if result_schema:
            self._aggregator = PydanticResultAggregator(result_schema)

        # Initialize common keys
        self._state["pages_visited"] = 0
        self._state["extracted_data"] = {}
        self._state["target_found"] = False
        self._state["errors"] = []
        self._state["navigation_history"] = []

    def get(self, key: str, default: Any = None) -> Any:
        """
        Отримати значення зі state.

        Args:
            key: Ключ для пошуку
            default: Значення за замовчуванням

        Returns:
            Значення або default
        """
        with self._lock:
            return self._state.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """
        Встановити значення та сповістити observers.

        Args:
            key: Ключ
            value: Значення
        """
        with self._lock:
            old_value = self._state.get(key)
            self._state[key] = value
            self._notify_observers(key, old_value, value)

    def update(self, key: str, updater: Callable[[Any], Any]) -> Any:
        """
        Атомарне оновлення значення.

        Args:
            key: Ключ
            updater: Функція для оновлення (old_value) -> new_value

        Returns:
            Нове значення
        """
        with self._lock:
            old_value = self._state.get(key)
            new_value = updater(old_value)
            self._state[key] = new_value
            self._notify_observers(key, old_value, new_value)
            return new_value

    def delete(self, key: str) -> Optional[Any]:
        """
        Видалити ключ зі state.

        Args:
            key: Ключ для видалення

        Returns:
            Видалене значення або None
        """
        with self._lock:
            if key in self._state:
                old_value = self._state.pop(key)
                self._notify_observers(key, old_value, None)
                return old_value
            return None

    def has(self, key: str) -> bool:
        """
        Перевірити наявність ключа.

        Args:
            key: Ключ для перевірки

        Returns:
            True якщо ключ існує
        """
        with self._lock:
            return key in self._state

    def keys(self) -> List[str]:
        """Повернути всі ключі."""
        with self._lock:
            return list(self._state.keys())

    def append_to_list(self, key: str, value: Any) -> None:
        """
        Додати елемент до списку.

        Args:
            key: Ключ списку
            value: Елемент для додавання
        """
        self.update(key, lambda lst: (lst or []) + [value])

    def increment(self, key: str, delta: int = 1) -> int:
        """
        Інкрементувати числове значення.

        Args:
            key: Ключ
            delta: Значення для додавання

        Returns:
            Нове значення
        """
        return self.update(key, lambda x: (x or 0) + delta)

    def merge_dict(self, key: str, data: Dict[str, Any]) -> None:
        """
        Merge словник з існуючим.

        Args:
            key: Ключ словника
            data: Дані для merge
        """
        self.update(key, lambda d: {**(d or {}), **data})

    def observe(self, callback: Callable[[str, Any, Any], None]) -> Callable[[], None]:
        """
        Підписатись на зміни state.

        Args:
            callback: Функція (key, old_value, new_value) -> None

        Returns:
            Функція для відписки
        """
        with self._lock:
            self._observers.append(callback)

        def unsubscribe():
            with self._lock:
                if callback in self._observers:
                    self._observers.remove(callback)

        return unsubscribe

    def _notify_observers(self, key: str, old: Any, new: Any) -> None:
        """Сповістити всіх observers про зміну."""
        for observer in self._observers:
            try:
                observer(key, old, new)
            except Exception:
                pass  # Log but don't fail

    @property
    def pages_visited(self) -> int:
        """Кількість відвіданих сторінок."""
        return self.get("pages_visited", 0)

    @pages_visited.setter
    def pages_visited(self, value: int) -> None:
        self.set("pages_visited", value)

    def increment_pages_visited(self) -> int:
        """Інкрементувати лічильник сторінок."""
        return self.increment("pages_visited")

    @property
    def extracted_data(self) -> Dict[str, Any]:
        """Витягнуті дані."""
        return self.get("extracted_data", {})

    @property
    def target_found(self) -> bool:
        """Чи знайдено target."""
        return self.get("target_found", False)

    @target_found.setter
    def target_found(self, value: bool) -> None:
        self.set("target_found", value)

    @property
    def errors(self) -> List[Dict[str, Any]]:
        """Список помилок."""
        return self.get("errors", [])

    def add_error(self, error: str, url: Optional[str] = None, **kwargs) -> None:
        """Додати помилку."""
        error_entry = {
            "error": error,
            "url": url,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **kwargs,
        }
        self.append_to_list("errors", error_entry)

    @property
    def navigation_history(self) -> List[str]:
        """Історія навігації (URLs)."""
        return self.get("navigation_history", [])

    def add_to_navigation_history(self, url: str) -> None:
        """Додати URL до історії навігації."""
        self.append_to_list("navigation_history", url)

    def add_extracted_data(self, data: Dict[str, Any], source_url: str) -> None:
        """
        Додати витягнуті дані та агрегувати.

        Args:
            data: Словник з даними
            source_url: URL джерела
        """
        # Зберігаємо в extracted_data
        self.merge_dict("extracted_data", data)

        # Агрегуємо якщо є schema
        if self._aggregator:
            self._aggregator.add(data, source_url)

    @property
    def result(self) -> Optional[BaseModel]:
        """
        Отримати агрегований результат.

        Returns:
            Pydantic model або None
        """
        if self._aggregator:
            return self._aggregator.get_result()
        return None

    @property
    def result_complete(self) -> bool:
        """
        Чи результат повний (всі required поля заповнені).

        Returns:
            True якщо повний
        """
        if self._aggregator:
            return self._aggregator.is_complete()
        return False

    @property
    def result_completeness(self) -> float:
        """
        Відсоток заповненості результату (0.0 - 1.0).

        Returns:
            Float від 0.0 до 1.0
        """
        if self._aggregator:
            return self._aggregator.get_completeness()
        return 0.0

    def get_missing_fields(self) -> List[str]:
        """
        Отримати список незаповнених полів.

        Returns:
            Список назв полів
        """
        if self._aggregator:
            return self._aggregator.get_missing_fields()
        return []

    @property
    def created_at(self) -> datetime:
        """Час створення контексту."""
        return self._created_at

    @property
    def result_schema(self) -> Optional[type[BaseModel]]:
        """Pydantic схема результату."""
        return self._result_schema

    def to_dict(self) -> Dict[str, Any]:
        """
        Серіалізувати state в словник.

        Returns:
            Копія state
        """
        with self._lock:
            return dict(self._state)

    def __repr__(self) -> str:
        return (
            f"CrawlContext("
            f"pages_visited={self.pages_visited}, "
            f"target_found={self.target_found}, "
            f"keys={len(self._state)})"
        )


class PydanticResultAggregator(Generic[T]):
    """
    Агрегатор результатів на основі Pydantic схеми.

    Автоматично:
    - Визначає які поля заповнені
    - Об'єднує дані з різних джерел
    - Перевіряє повноту

    Attributes:
        schema: Pydantic модель для валідації
    """

    def __init__(self, schema: type[T]):
        """
        Ініціалізує агрегатор.

        Args:
            schema: Pydantic модель
        """
        self.schema = schema
        self._data: Dict[str, Any] = {}
        self._sources: Dict[str, str] = {}  # field -> source_url
        self._lock = threading.RLock()

    def add(self, partial: Dict[str, Any], source_url: str) -> None:
        """
        Додати дані (не перезаписує існуючі).

        Args:
            partial: Часткові дані
            source_url: URL джерела
        """
        with self._lock:
            for key, value in partial.items():
                if value is not None and key not in self._data:
                    self._data[key] = value
                    self._sources[key] = source_url

    def get_result(self) -> Optional[T]:
        """
        Повернути результат якщо валідний.

        Returns:
            Pydantic model або None
        """
        with self._lock:
            try:
                return self.schema.model_validate(self._data)
            except ValidationError:
                return None

    def is_complete(self) -> bool:
        """
        Перевірити чи всі required поля заповнені.

        Returns:
            True якщо повний
        """
        with self._lock:
            required_fields = [
                name for name, field in self.schema.model_fields.items() if field.is_required()
            ]
            return all(f in self._data for f in required_fields)

    def get_completeness(self) -> float:
        """
        Відсоток заповненості.

        Returns:
            Float від 0.0 до 1.0
        """
        with self._lock:
            all_fields = list(self.schema.model_fields.keys())
            if not all_fields:
                return 1.0
            filled = sum(1 for f in all_fields if f in self._data)
            return filled / len(all_fields)

    def get_missing_fields(self) -> List[str]:
        """
        Список незаповнених полів.

        Returns:
            Список назв полів
        """
        with self._lock:
            return [name for name in self.schema.model_fields if name not in self._data]

    def get_sources(self) -> Dict[str, str]:
        """
        Отримати джерела для кожного поля.

        Returns:
            Словник field -> source_url
        """
        with self._lock:
            return dict(self._sources)

    def clear(self) -> None:
        """Очистити всі дані."""
        with self._lock:
            self._data.clear()
            self._sources.clear()

    def __repr__(self) -> str:
        return (
            f"PydanticResultAggregator("
            f"schema={self.schema.__name__}, "
            f"completeness={self.get_completeness():.1%})"
        )
