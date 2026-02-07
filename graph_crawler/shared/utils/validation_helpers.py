"""Validation Helpers - Універсальні функції для валідації полів у конфігураціях."""

from typing import Any, Callable, List, Optional, Union

from pydantic import field_validator


def create_enum_validator(
    field_name: str,
    allowed_values: Union[List[str], Callable[[], List[str]]],
    case_sensitive: bool = True,
    normalize: bool = False,
) -> Callable:
    """
    Фабрика для створення enum валідаторів.

    Використання:
        class MyConfig(BaseModel):
            mode: str = "sequential"

            # Статичний список
            _validate_mode = field_validator("mode")(
                create_enum_validator("mode", ["sequential", "multiprocessing", "celery"])
            )

            # Динамічний список (з Registry)
            _validate_mode = field_validator("mode")(
                create_enum_validator("mode", lambda: CrawlModeRegistry.get_all_names())
            )

    Args:
        field_name: Назва поля для валідації
        allowed_values: Список дозволених значень або функція яка повертає список
        case_sensitive: Чи враховувати регістр (default: True)
        normalize: Чи нормалізувати значення (наприклад, до lower case)

    Returns:
        Функція валідатор для використання з @field_validator
    """

    def validator(cls, v: Any) -> Any:
        # Отримуємо список дозволених значень
        if callable(allowed_values):
            allowed = allowed_values()
        else:
            allowed = allowed_values

        # Перевіряємо значення
        if case_sensitive:
            is_valid = v in allowed
        else:
            is_valid = v.lower() in [a.lower() for a in allowed]

        if not is_valid:
            raise ValueError(f"Invalid {field_name}: {v}. Allowed: {allowed}")

        # Нормалізація
        if normalize and not case_sensitive:
            return v.lower()

        return v

    # Додаємо classmethod декоратор
    return classmethod(validator)


def validate_enum_field(
    field_name: str, value: str, allowed_values: List[str], case_sensitive: bool = True
) -> str:
    """
    Простий helper для валідації enum полів.

    Використання:
        @field_validator("mode")
        @classmethod
        def validate_mode(cls, v: str) -> str:
            return validate_enum_field(
                "mode",
                v,
                ["sequential", "multiprocessing", "celery"]
            )

    Args:
        field_name: Назва поля
        value: Значення для валідації
        allowed_values: Список дозволених значень
        case_sensitive: Чи враховувати регістр

    Returns:
        Валідоване значення

    Raises:
        ValueError: Якщо значення недозволене
    """
    if case_sensitive:
        is_valid = value in allowed_values
    else:
        is_valid = value.upper() in [v.upper() for v in allowed_values]

    if not is_valid:
        raise ValueError(f"Invalid {field_name}: {value}. Allowed: {allowed_values}")

    return value


def validate_positive_number(
    field_name: str,
    value: Union[int, float],
    min_value: Optional[Union[int, float]] = None,
    max_value: Optional[Union[int, float]] = None,
    allow_zero: bool = False,
) -> Union[int, float]:
    """
    Валідація позитивних чисел з опціональними мінімумом та максимумом.

    Args:
        field_name: Назва поля
        value: Значення для валідації
        min_value: Мінімальне дозволене значення (опціонально)
        max_value: Максимальне дозволене значення (опціонально)
        allow_zero: Чи дозволяти нуль (default: False)

    Returns:
        Валідоване значення

    Raises:
        ValueError: Якщо значення не валідне
    """
    if not allow_zero and value <= 0:
        raise ValueError(f"{field_name} must be positive, got {value}")

    if allow_zero and value < 0:
        raise ValueError(f"{field_name} must be non-negative, got {value}")

    if min_value is not None and value < min_value:
        raise ValueError(f"{field_name} must be >= {min_value}, got {value}")

    if max_value is not None and value > max_value:
        raise ValueError(f"{field_name} must be <= {max_value}, got {value}")

    return value


def validate_string_length(
    field_name: str,
    value: str,
    min_length: Optional[int] = None,
    max_length: Optional[int] = None,
    allow_empty: bool = False,
) -> str:
    """
    Валідація довжини строки.

    Args:
        field_name: Назва поля
        value: Значення для валідації
        min_length: Мінімальна довжина (опціонально)
        max_length: Максимальна довжина (опціонально)
        allow_empty: Чи дозволяти пусту строку (default: False)

    Returns:
        Валідоване значення

    Raises:
        ValueError: Якщо довжина не валідна
    """
    length = len(value)

    if not allow_empty and length == 0:
        raise ValueError(f"{field_name} cannot be empty")

    if min_length is not None and length < min_length:
        raise ValueError(
            f"{field_name} must be at least {min_length} characters, got {length}"
        )

    if max_length is not None and length > max_length:
        raise ValueError(
            f"{field_name} must be at most {max_length} characters, got {length}"
        )

    return value


def validate_url(
    field_name: str,
    value: str,
    require_scheme: bool = True,
    allowed_schemes: Optional[List[str]] = None,
) -> str:
    """
    Базова валідація URL.

    Args:
        field_name: Назва поля
        value: URL для валідації
        require_scheme: Чи вимагати scheme (http://, https://)
        allowed_schemes: Список дозволених schemes (опціонально)

    Returns:
        Валідований URL

    Raises:
        ValueError: Якщо URL не валідний
    """
    if not value or not value.strip():
        raise ValueError(f"{field_name} cannot be empty")

    value = value.strip()

    if require_scheme:
        if not value.startswith(("http://", "https://", "ftp://", "ws://", "wss://")):
            raise ValueError(
                f"{field_name} must start with a valid scheme (http://, https://, etc.)"
            )

    if allowed_schemes:
        has_valid_scheme = any(
            value.startswith(f"{scheme}://") for scheme in allowed_schemes
        )
        if not has_valid_scheme:
            raise ValueError(
                f"{field_name} must use one of these schemes: {allowed_schemes}"
            )

    return value


def validate_port(field_name: str, value: int) -> int:
    """
    Валідація порту (1-65535).

    Args:
        field_name: Назва поля
        value: Порт для валідації

    Returns:
        Валідований порт

    Raises:
        ValueError: Якщо порт не валідний
    """
    return validate_positive_number(field_name, value, min_value=1, max_value=65535)


def validate_percentage(field_name: str, value: Union[int, float]) -> Union[int, float]:
    """
    Валідація відсотка (0-100).

    Args:
        field_name: Назва поля
        value: Значення для валідації

    Returns:
        Валідоване значення

    Raises:
        ValueError: Якщо значення не в діапазоні 0-100
    """
    return validate_positive_number(
        field_name, value, min_value=0, max_value=100, allow_zero=True
    )
