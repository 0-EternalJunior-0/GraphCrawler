"""Base classes for CAPTCHA bypass."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class BypassStrategy(str, Enum):
    """Стратегії обходу CAPTCHA."""

    COOKIE_PERSISTENCE = "cookie_persistence"  # Зберігання cookies
    SESSION_REUSE = "session_reuse"  # Переіспользування сесій
    DELAY_STRATEGY = "delay_strategy"  # Очікування
    ALTERNATIVE_ENDPOINTS = "alternative_endpoints"  # Альтернативні endpoints
    ROTATING = "rotating"  # Ротація різних стратегій


class BypassResult(str, Enum):
    """Результати спроби обходу."""

    SUCCESS = "success"  # Успішно обійшли
    FAILED = "failed"  # Не вдалося обійти
    CAPTCHA_STILL_PRESENT = "captcha_still_present"  # CAPTCHA все ще є
    RETRY_NEEDED = "retry_needed"  # Потрібна повторна спроба


@dataclass
class BypassAttempt:
    """Результат спроби обходу CAPTCHA."""

    strategy: BypassStrategy
    result: BypassResult
    timestamp: datetime = field(default_factory=datetime.now)
    response_status: Optional[int] = None
    response_time: Optional[float] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionInfo:
    """Інформація про збережену сесію."""

    url: str
    cookies: Dict[str, str]
    headers: Dict[str, str]
    created_at: datetime
    last_used: datetime
    success_count: int = 0
    failure_count: int = 0

    def is_expired(self, max_age_hours: int = 24) -> bool:
        """Перевірка чи сесія прострочена."""
        age = datetime.now() - self.created_at
        return age > timedelta(hours=max_age_hours)

    @property
    def success_rate(self) -> float:
        """Відсоток успішних запитів."""
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.0
        return (self.success_count / total) * 100

    def to_dict(self) -> Dict[str, Any]:
        """Серіалізація в dict для JSON (безпечна альтернатива pickle)."""
        return {
            "url": self.url,
            "cookies": self.cookies,
            "headers": self.headers,
            "created_at": self.created_at.isoformat(),
            "last_used": self.last_used.isoformat(),
            "success_count": self.success_count,
            "failure_count": self.failure_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionInfo":
        """Десеріалізація з dict (безпечна альтернатива pickle)."""
        return cls(
            url=data["url"],
            cookies=data["cookies"],
            headers=data["headers"],
            created_at=datetime.fromisoformat(data["created_at"]),
            last_used=datetime.fromisoformat(data["last_used"]),
            success_count=data.get("success_count", 0),
            failure_count=data.get("failure_count", 0),
        )
