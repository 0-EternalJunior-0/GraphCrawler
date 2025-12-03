"""Базові класи для content extraction."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ExtractedArticle(BaseModel):
    """
    Pydantic модель для витягнутої статті.

    Attributes:
        title: Заголовок статті
        text: Основний текст статті
        summary: Короткий опис/саммарі
        authors: Список авторів
        publish_date: Дата публікації
        keywords: Ключові слова
        top_image: Головне зображення
        images: Список всіх зображень
        videos: Список відео
        extractor_name: Назва екстрактора який використовувався
    """

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat() if v else None}
    )

    title: Optional[str] = None
    text: Optional[str] = None
    summary: Optional[str] = None
    authors: List[str] = Field(default_factory=list)
    publish_date: Optional[datetime] = None
    keywords: List[str] = Field(default_factory=list)
    top_image: Optional[str] = None
    images: List[str] = Field(default_factory=list)
    videos: List[str] = Field(default_factory=list)
    extractor_name: str


class BaseContentExtractor(ABC):
    """
    Базовий абстрактний клас для content extractors.

    Content extractors витягують структуровану інформацію про статті
    з HTML сторінок використовуючи спеціалізовані бібліотеки.

    Example:
        class MyExtractor(BaseContentExtractor):
            @property
            def extractor_name(self) -> str:
                return "my_extractor"

            def extract(self, html: str, url: str) -> Optional[ExtractedArticle]:
                # Ваша логіка екстракції
                return ExtractedArticle(
                    title="...",
                    text="...",
                    extractor_name=self.extractor_name
                )
    """

    @property
    @abstractmethod
    def extractor_name(self) -> str:
        """Повертає назву екстрактора."""
        pass

    @abstractmethod
    def extract(self, html: str, url: str) -> Optional[ExtractedArticle]:
        """
        Витягує статтю з HTML.

        Args:
            html: HTML контент сторінки
            url: URL сторінки

        Returns:
            ExtractedArticle або None якщо екстракція не вдалася
        """
        pass
