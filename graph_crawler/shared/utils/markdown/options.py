"""Markdown Generator Options.

Pydantic модель для налаштувань генерації Markdown.
Консистентно з архітектурою проекту.
"""

from typing import FrozenSet

from pydantic import BaseModel, ConfigDict, Field


class MarkdownOptions(BaseModel):
    """
    Опції для MarkdownGenerator.

    Дозволяє налаштувати:
    - Які елементи видаляти (noise)
    - Чи включати посилання/зображення
    - Максимальна довжина тексту

    Приклад:
        >>> options = MarkdownOptions(
        ...     remove_nav=True,
        ...     remove_footer=True,
        ...     include_links=False,
        ...     max_length=50000,
        ... )
    """

    model_config = ConfigDict(
        frozen=False,
        validate_assignment=True,
    )

    # Видалення noise елементів
    remove_nav: bool = Field(default=True, description="Видаляти nav елементи")
    remove_header: bool = Field(default=True, description="Видаляти header елементи")
    remove_footer: bool = Field(default=True, description="Видаляти footer елементи")
    remove_aside: bool = Field(default=True, description="Видаляти aside елементи")
    remove_ads: bool = Field(default=True, description="Видаляти рекламу за класами/id")
    remove_scripts: bool = Field(default=True, description="Видаляти script, style, noscript")
    remove_buttons: bool = Field(default=True, description="Видаляти button елементи")
    remove_forms: bool = Field(default=False, description="Видаляти form елементи")

    # Теги для видалення (immutable для thread-safety)
    noise_tags: FrozenSet[str] = Field(
        default_factory=lambda: frozenset(
            {
                "script",
                "style",
                "noscript",
                "template",
                "svg",
                "canvas",
                "iframe",
                "embed",
                "object",
                "video",
                "audio",
            }
        ),
        description="Теги для автоматичного видалення",
    )

    # Класи для видалення (реклама, попапи)
    noise_classes: FrozenSet[str] = Field(
        default_factory=lambda: frozenset(
            {
                "ad",
                "ads",
                "advertisement",
                "advert",
                "banner",
                "sidebar",
                "cookie",
                "popup",
                "modal",
                "overlay",
                "newsletter",
                "subscribe",
                "social",
                "share",
                "comment",
                "comments",
                "related",
                "recommended",
            }
        ),
        description="CSS класи для видалення",
    )

    # ID для видалення
    noise_ids: FrozenSet[str] = Field(
        default_factory=lambda: frozenset(
            {
                "cookie",
                "popup",
                "modal",
                "overlay",
                "ad",
                "ads",
                "sidebar",
                "newsletter",
                "comments",
            }
        ),
        description="HTML ID для видалення",
    )

    # Включення контенту
    include_links: bool = Field(default=True, description="Включати посилання в MD")
    include_images: bool = Field(default=False, description="Включати зображення в MD")
    include_tables: bool = Field(default=True, description="Включати таблиці в MD")
    include_code_blocks: bool = Field(default=True, description="Включати код в MD")
    include_lists: bool = Field(default=True, description="Включати списки в MD")
    include_blockquotes: bool = Field(default=True, description="Включати цитати в MD")

    # Обмеження
    max_length: int = Field(default=100000, ge=0, description="Максимальна довжина тексту")
    min_paragraph_length: int = Field(default=10, ge=0, description="Мінімальна довжина параграфа")
    min_heading_length: int = Field(default=2, ge=0, description="Мінімальна довжина заголовка")

    # Форматування
    preserve_whitespace: bool = Field(default=False, description="Зберігати whitespace")
    normalize_whitespace: bool = Field(default=True, description="Нормалізувати пробіли")

    # Citations
    generate_citations: bool = Field(default=False, description="Генерувати [1], [2] посилання")

    def should_remove_tag(self, tag_name: str) -> bool:
        """Перевіряє чи потрібно видалити тег."""
        tag_lower = tag_name.lower()

        # Завжди видаляємо noise теги
        if tag_lower in self.noise_tags:
            return True

        # Перевіряємо опціональні теги
        if self.remove_nav and tag_lower == "nav":
            return True
        if self.remove_header and tag_lower == "header":
            return True
        if self.remove_footer and tag_lower == "footer":
            return True
        if self.remove_aside and tag_lower == "aside":
            return True
        if self.remove_buttons and tag_lower == "button":
            return True
        if self.remove_forms and tag_lower == "form":
            return True

        return False

    def should_remove_by_class(self, class_str: str) -> bool:
        """Перевіряє чи потрібно видалити елемент за класом."""
        if not class_str or not self.remove_ads:
            return False

        # Розбиваємо на окремі класи та перевіряємо як повні слова
        class_set = set(class_str.lower().split())
        return bool(class_set & self.noise_classes)

    def should_remove_by_id(self, id_str: str) -> bool:
        """Перевіряє чи потрібно видалити елемент за ID."""
        if not id_str or not self.remove_ads:
            return False

        id_lower = id_str.lower()
        return any(ni in id_lower for ni in self.noise_ids)

    def with_overrides(self, **kwargs) -> "MarkdownOptions":
        """
        Створює нову копію з переписаними значеннями.

        Immutable pattern для thread-safety.

        Args:
            **kwargs: Значення для перепису

        Returns:
            Новий MarkdownOptions instance
        """
        data = self.model_dump()
        data.update(kwargs)
        return MarkdownOptions(**data)
