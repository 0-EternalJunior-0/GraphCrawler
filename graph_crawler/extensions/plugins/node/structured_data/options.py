"""Налаштування для StructuredData плагіна."""

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class StructuredDataOptions(BaseModel):
    """
    Налаштування витягування мікророзмітки.

    Pydantic BaseModel для консистентності з NodePluginContext.
    Включає валідацію через validators.

    Example:
        >>> options = StructuredDataOptions(
        ...     parse_rdfa=True,
        ...     allowed_types=['Product', 'Article']
        ... )
    """

    # Які формати парсити
    parse_jsonld: bool = True
    parse_microdata: bool = True
    parse_opengraph: bool = True
    parse_twitter: bool = True
    parse_rdfa: bool = False  # Вимкнено за замовчуванням

    # Фільтрація типів (None = всі)
    allowed_types: Optional[List[str]] = None

    # Ліміти безпеки
    max_jsonld_blocks: int = Field(default=10, ge=1, le=100)
    max_jsonld_size: int = Field(default=100_000, ge=1000, le=10_000_000)
    max_microdata_items: int = Field(default=50, ge=1, le=500)
    max_nesting_depth: int = Field(default=5, ge=1, le=20)

    # Таймаути
    timeout_per_parser: float = Field(default=2.0, gt=0, le=30.0)

    # Обробка помилок
    fail_silently: bool = True

    # Опції парсингу
    include_nested: bool = True
    normalize_types: bool = True  # "schema.org/Product" -> "Product"

    @field_validator("allowed_types")
    @classmethod
    def validate_allowed_types(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Валідація allowed_types."""
        if v is not None:
            # Видаляємо дублікати, зберігаємо порядок
            seen = set()
            result = []
            for t in v:
                if t not in seen:
                    seen.add(t)
                    result.append(t)
            return result
        return v
