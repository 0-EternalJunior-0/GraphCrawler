"""Markdown Generation Result.

Pydantic модель для результату генерації Markdown.
Консистентно з іншими моделями проекту (ExtractedArticle).
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MarkdownResult(BaseModel):
    """
    Результат генерації Markdown.
    
    Містить різні варіанти тексту для різних use cases:
    - text: Чистий текст (для пошуку, word count)
    - raw_markdown: Повний MD з усім контентом
    - fit_markdown: Очищений MD (без nav, footer, ads) - ОСНОВНИЙ
    - markdown_with_citations: MD з посиланнями [1], [2]
    
    Приклад:
        >>> result = md_generator.generate(html)
        >>> print(result.text)           # Чистий текст
        >>> print(result.fit_markdown)   # Очищений Markdown
        >>> print(result.word_count)     # Кількість слів
    """
    
    model_config = ConfigDict(
        frozen=False,  # Дозволяємо модифікацію після створення
        validate_assignment=True,
    )
    
    # Основні варіанти тексту
    text: str = Field(default="", description="Чистий текст без форматування")
    raw_markdown: str = Field(default="", description="Повний MD з усім контентом")
    fit_markdown: str = Field(default="", description="Очищений MD (основний output)")
    
    # Citations (опціонально)
    markdown_with_citations: str = Field(default="", description="MD з [1], [2] посиланнями")
    references: List[Dict[str, Any]] = Field(default_factory=list, description="Список посилань")
    
    # Метадані
    title: str = Field(default="", description="Title сторінки")
    h1: str = Field(default="", description="Перший H1 заголовок")
    description: str = Field(default="", description="Meta description")
    
    # Статистика
    word_count: int = Field(default=0, ge=0, description="Кількість слів")
    char_count: int = Field(default=0, ge=0, description="Кількість символів")
    heading_count: int = Field(default=0, ge=0, description="Кількість заголовків")
    link_count: int = Field(default=0, ge=0, description="Кількість посилань")
    image_count: int = Field(default=0, ge=0, description="Кількість зображень")
    
    # Флаги
    is_truncated: bool = Field(default=False, description="Чи був обрізаний текст")
    
    def model_post_init(self, __context) -> None:
        """Обчислює статистику після створення."""
        if self.text and not self.word_count:
            object.__setattr__(self, 'word_count', len(self.text.split()))
        if self.text and not self.char_count:
            object.__setattr__(self, 'char_count', len(self.text))
    
    def to_dict(self) -> Dict:
        """Конвертує в dictionary (alias для model_dump)."""
        return self.model_dump()
    
    @classmethod
    def empty(cls) -> "MarkdownResult":
        """Повертає порожній результат."""
        return cls()
    
    def __bool__(self) -> bool:
        """Перевірка чи є контент."""
        return bool(self.text or self.fit_markdown)
    
    def __repr__(self) -> str:
        return f"MarkdownResult(words={self.word_count}, chars={self.char_count}, truncated={self.is_truncated})"
