"""Результат витягування мікророзмітки."""

from enum import Enum
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, ConfigDict, Field, computed_field


class SchemaType(str, Enum):
    """Популярні schema.org типи."""

    ARTICLE = "Article"
    NEWS_ARTICLE = "NewsArticle"
    BLOG_POSTING = "BlogPosting"
    PRODUCT = "Product"
    OFFER = "Offer"
    JOB_POSTING = "JobPosting"
    RECIPE = "Recipe"
    EVENT = "Event"
    ORGANIZATION = "Organization"
    LOCAL_BUSINESS = "LocalBusiness"
    PERSON = "Person"
    FAQ_PAGE = "FAQPage"
    HOW_TO = "HowTo"
    VIDEO_OBJECT = "VideoObject"
    BREADCRUMB_LIST = "BreadcrumbList"
    REVIEW = "Review"
    AGGREGATE_RATING = "AggregateRating"


class StructuredDataResult(BaseModel):
    """
    Результат витягування мікророзмітки.

    Pydantic BaseModel для:
    - Автоматичної валідації
    - Серіалізації через model_dump()
    - Консистентності з NodePluginContext

    Law of Demeter: Методи для доступу до даних замість прямого звернення.
    """

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        frozen=False,  # Дозволяємо мутацію під час парсингу
    )

    # Основний тип контенту
    primary_type: Optional[str] = None

    # Дані по форматах
    jsonld: List[Dict[str, Any]] = Field(default_factory=list)
    microdata: List[Dict[str, Any]] = Field(default_factory=list)
    opengraph: Dict[str, str] = Field(default_factory=dict)
    twitter: Dict[str, str] = Field(default_factory=dict)
    rdfa: List[Dict[str, Any]] = Field(default_factory=list)

    # Метадані
    all_types: Set[str] = Field(default_factory=set)
    errors: List[str] = Field(default_factory=list)

    # Статистика парсингу
    parse_time_ms: float = 0.0

    @computed_field
    @property
    def has_data(self) -> bool:
        """Чи знайдено хоч якісь дані."""
        return bool(self.jsonld or self.microdata or self.opengraph or self.twitter)

    @computed_field
    @property
    def jsonld_count(self) -> int:
        """Кількість JSON-LD блоків."""
        return len(self.jsonld)

    @computed_field
    @property
    def microdata_count(self) -> int:
        """Кількість Microdata елементів."""
        return len(self.microdata)

    @classmethod
    def empty(cls) -> "StructuredDataResult":
        """Створює порожній результат."""
        return cls()

    @classmethod
    def with_error(cls, error: str) -> "StructuredDataResult":
        """Створює результат з помилкою."""
        return cls(errors=[error])

    def get_type(self) -> Optional[str]:
        """
        Повертає основний тип контенту.

        Пріоритет: primary_type > перший з all_types
        """
        if self.primary_type:
            return self.primary_type
        if self.all_types:
            return next(iter(self.all_types))
        return None

    def get_property(self, prop: str, default: Any = None) -> Any:
        """
        Шукає властивість у всіх джерелах.

        Порядок пошуку (за точністю даних):
        1. JSON-LD (найточніші)
        2. Microdata
        3. Open Graph (базові)
        4. Twitter Cards (базові)

        Args:
            prop: Назва властивості
            default: Значення за замовчуванням

        Returns:
            Знайдене значення або default
        """
        # JSON-LD
        for item in self.jsonld:
            if prop in item:
                return item[prop]
            # Підтримка вкладених об'єктів
            if "@graph" in item:
                for graph_item in item["@graph"]:
                    if isinstance(graph_item, dict) and prop in graph_item:
                        return graph_item[prop]

        # Microdata
        for item in self.microdata:
            if prop in item:
                return item[prop]

        # Open Graph
        og_mapping = {
            "title": "title",
            "description": "description",
            "image": "image",
            "url": "url",
            "type": "type",
            "site_name": "site_name",
        }
        if prop in og_mapping and og_mapping[prop] in self.opengraph:
            return self.opengraph[og_mapping[prop]]

        # Twitter
        twitter_mapping = {
            "title": "title",
            "description": "description",
            "image": "image",
            "card": "card",
        }
        if prop in twitter_mapping and twitter_mapping[prop] in self.twitter:
            return self.twitter[twitter_mapping[prop]]

        return default

    def get_all_of_type(self, schema_type: str) -> List[Dict[str, Any]]:
        """
        Повертає всі об'єкти заданого типу.

        Шукає в JSON-LD та Microdata.
        """
        results = []

        for item in self.jsonld:
            if self._matches_type(item, schema_type):
                results.append(item)
            # Перевіряємо @graph
            if "@graph" in item:
                for graph_item in item["@graph"]:
                    if isinstance(graph_item, dict) and self._matches_type(graph_item, schema_type):
                        results.append(graph_item)

        for item in self.microdata:
            if self._matches_type(item, schema_type):
                results.append(item)

        return results

    def has_type(self, schema_type: str) -> bool:
        """Перевіряє наявність типу."""
        return schema_type in self.all_types

    def _matches_type(self, item: Dict, schema_type: str) -> bool:
        """Перевіряє чи item відповідає типу."""
        item_type = item.get("@type") or item.get("type")
        if isinstance(item_type, list):
            return schema_type in item_type
        return item_type == schema_type
