"""Strategy Pattern для URL фільтрів."""

from abc import ABC, abstractmethod
from typing import Any, Dict

from graph_crawler.domain.interfaces.filter import IDomainFilter, IPathFilter


class BaseURLFilter(ABC):
    """
    Базова стратегія для URL фільтрації.

    Strategy Pattern дозволяє легко змінювати алгоритм фільтрації.

    Приклади стратегій:
    - DomainFilter - фільтр за доменом
    - PathFilter - фільтр за шляхом (regex)
    - RobotsTxtFilter - фільтр згідно robots.txt
    - CustomFilter - кастомна логіка
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.enabled = True
        self.event_bus = None  # For event publishing (Alpha 2.0)

    @property
    @abstractmethod
    def name(self) -> str:
        """Назва фільтра."""
        pass

    @abstractmethod
    def is_allowed(self, url: str, source_url: str = None) -> bool:
        """
        Перевіряє чи дозволений URL.

        Args:
            url: URL для перевірки
            source_url: URL джерела (опціонально)

        Returns:
            True якщо дозволено
        """
        pass

    def _publish_filtered_event(
        self, url: str, filter_type: str, reason: str, pattern: str = None
    ):
        """
        Публікує подію про фільтрацію URL (Alpha 2.0).

        FIXED: Extracted to base class to avoid code duplication.

        Args:
            url: URL що відфільтровано
            filter_type: Тип фільтра ('domain' або 'path')
            reason: Причина фільтрації
            pattern: Regex pattern що зматчився (опціонально для PathFilter)
        """
        if not self.event_bus:
            return

        from graph_crawler.domain.events import CrawlerEvent, EventType

        data = {"url": url, "filter_type": filter_type, "reason": reason}

        if pattern:
            data["pattern"] = pattern

        self.event_bus.publish(
            CrawlerEvent.create(EventType.URL_FILTERED_OUT, data=data)
        )

    def __repr__(self):
        return f"{self.__class__.__name__}(enabled={self.enabled})"
