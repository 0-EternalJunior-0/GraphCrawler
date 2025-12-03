"""Node Data Transfer Objects.

DTO для передачі даних про Node між шарами.
НЕ містить бізнес-логіки - тільки дані.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator


class NodeDTO(BaseModel):
    """
    Data Transfer Object для Node.

    Використовується для передачі даних про Node між шарами.
    НЕ містить бізнес-логіки (process_html, plugins) - тільки дані.

    Attributes:
        node_id: Унікальний ID ноди
        url: URL сторінки
        depth: Глибина від кореневої ноди
        should_scan: Чи треба сканувати цю ноду
        can_create_edges: Чи може нода створювати edges
        scanned: Чи була нода просканована
        response_status: HTTP статус код
        metadata: Метадані сторінки (title, description, etc.)
        user_data: Додаткові дані від плагінів
        content_hash: Hash контенту для incremental crawling
        priority: Пріоритет сканування (1-10)
        created_at: Час створення ноди
        lifecycle_stage: Етап життєвого циклу ("url_stage" або "html_stage")

    Example:
        >>> node_dto = NodeDTO(
        ...     node_id="123",
        ...     url="https://example.com",
        ...     depth=0,
        ...     should_scan=True,
        ...     can_create_edges=True,
        ...     scanned=False,
        ...     metadata={"title": "Example"},
        ...     created_at=datetime.now(),
        ...     lifecycle_stage="url_stage"
        ... )
    """

    node_id: str
    url: str
    depth: int = Field(ge=0, description="Глибина від кореневої ноди")
    should_scan: bool = Field(default=True, description="Чи треба сканувати")
    can_create_edges: bool = Field(
        default=True, description="Чи може створювати edges"
    )
    scanned: bool = Field(default=False, description="Чи була просканована")
    response_status: Optional[int] = Field(
        default=None, description="HTTP статус код"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Метадані сторінки"
    )
    user_data: Dict[str, Any] = Field(
        default_factory=dict, description="Дані від плагінів"
    )
    content_hash: Optional[str] = Field(
        default=None, description="Hash контенту для change detection"
    )
    priority: Optional[int] = Field(
        default=None, ge=1, le=10, description="Пріоритет (1-10)"
    )
    created_at: datetime = Field(description="Час створення")
    lifecycle_stage: str = Field(
        default="url_stage", description='Етап: "url_stage" або "html_stage"'
    )

    @field_validator("lifecycle_stage")
    @classmethod
    def validate_lifecycle_stage(cls, v: str) -> str:
        """Валідація lifecycle_stage."""
        allowed_stages = ["url_stage", "html_stage"]
        if v not in allowed_stages:
            raise ValueError(
                f"lifecycle_stage must be one of {allowed_stages}, got: {v}"
            )
        return v

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Валідація URL."""
        if not v:
            raise ValueError("URL cannot be empty")
        if not v.startswith(("http://", "https://")):
            raise ValueError(f"URL must start with http:// or https://, got: {v}")
        return v

    class Config:
        """Pydantic конфігурація."""

        json_schema_extra = {
            "example": {
                "node_id": "550e8400-e29b-41d4-a716-446655440000",
                "url": "https://example.com/page",
                "depth": 1,
                "should_scan": True,
                "can_create_edges": True,
                "scanned": False,
                "response_status": 200,
                "metadata": {
                    "title": "Example Page",
                    "description": "An example page",
                },
                "user_data": {},
                "content_hash": "a7b3c9d2e1f4567890abcdef12345678",
                "priority": 5,
                "created_at": "2024-12-03T10:30:00",
                "lifecycle_stage": "html_stage",
            }
        }


class CreateNodeDTO(BaseModel):
    """
    DTO для створення нової Node.

    Містить мінімальний набір полів для створення ноди.
    Інші поля встановлюються автоматично.

    Attributes:
        url: URL сторінки (обов'язково)
        depth: Глибина від кореневої ноди (default: 0)
        should_scan: Чи треба сканувати (default: True)
        can_create_edges: Чи може створювати edges (default: True)
        priority: Пріоритет сканування (optional)

    Example:
        >>> create_dto = CreateNodeDTO(
        ...     url="https://example.com",
        ...     depth=0,
        ...     should_scan=True,
        ... )
    """

    url: str
    depth: int = Field(default=0, ge=0)
    should_scan: bool = True
    can_create_edges: bool = True
    priority: Optional[int] = Field(default=None, ge=1, le=10)

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Валідація URL."""
        if not v:
            raise ValueError("URL cannot be empty")
        if not v.startswith(("http://", "https://")):
            raise ValueError(f"URL must start with http:// or https://, got: {v}")
        return v

    class Config:
        """Pydantic конфігурація."""

        json_schema_extra = {
            "example": {
                "url": "https://example.com",
                "depth": 0,
                "should_scan": True,
                "can_create_edges": True,
                "priority": 5,
            }
        }


class NodeMetadataDTO(BaseModel):
    """
    DTO для метаданих Node (спрощена версія для API responses).

    Містить тільки найважливіші поля для відображення.
    Використовується коли потрібна легка версія NodeDTO.

    Attributes:
        node_id: Унікальний ID
        url: URL сторінки
        title: Title сторінки (з metadata)
        description: Description (з metadata)
        h1: H1 заголовок (з metadata)
        keywords: Keywords (з metadata)
        canonical_url: Canonical URL (з metadata)
        language: Мова сторінки (з metadata)

    Example:
        >>> metadata_dto = NodeMetadataDTO(
        ...     node_id="123",
        ...     url="https://example.com",
        ...     title="Example",
        ...     description="An example page"
        ... )
    """

    node_id: str
    url: str
    title: Optional[str] = None
    description: Optional[str] = None
    h1: Optional[str] = None
    keywords: Optional[str] = None
    canonical_url: Optional[str] = None
    language: Optional[str] = None

    class Config:
        """Pydantic конфігурація."""

        json_schema_extra = {
            "example": {
                "node_id": "550e8400-e29b-41d4-a716-446655440000",
                "url": "https://example.com",
                "title": "Example Domain",
                "description": "Example Domain for documentation",
                "h1": "Example Domain",
                "keywords": "example, domain, documentation",
                "canonical_url": "https://example.com",
                "language": "en",
            }
        }
