"""Path Filter Strategy (regex)."""

import logging
import re
from typing import List
from urllib.parse import urlparse

from graph_crawler.application.use_cases.crawling.filters.base import BaseURLFilter
from graph_crawler.domain.value_objects.models import PathFilterConfig

logger = logging.getLogger(__name__)


class PathFilter(BaseURLFilter):
    """
    Фільтр за шляхом (regex patterns).

    Конфіг:
        excluded_patterns: list - regex для виключення
        included_patterns: list - regex для включення

    Приклад:
        excluded_patterns: ['/blog/', '.*\\/archive\\/.*']
        included_patterns: ['/products/.*']
    """

    @property
    def name(self) -> str:
        return "path"

    def __init__(self, config: PathFilterConfig, event_bus=None):
        """
        Ініціалізує фільтр.

        Args:
            config: PathFilterConfig (Pydantic модель)
            event_bus: EventBus для публікації подій (опціонально)
        """
        self.pydantic_config = config
        super().__init__(config.model_dump())

        self.excluded_patterns = self._compile_patterns(config.excluded_patterns)
        self.included_patterns = self._compile_patterns(config.included_patterns)

        # EventBus для подій
        self.event_bus = event_bus

    def _compile_patterns(self, patterns: List[str]) -> List[re.Pattern]:
        """Компілює regex patterns."""
        compiled = []
        for pattern in patterns:
            try:
                compiled.append(re.compile(pattern))
            except re.error as e:
                logger.error(f"Invalid regex pattern '{pattern}': {e}")
        return compiled

    def is_allowed(self, url: str, source_url: str = None) -> bool:
        """
        Перевіряє чи дозволений шлях.

        Args:
            url: URL для перевірки
            source_url: URL джерела (не використовується)

        Returns:
            True якщо шлях дозволений
        """
        if not self.enabled:
            return True

        # Витягуємо шлях з URL
        parsed = urlparse(url)
        path = parsed.path

        # Перевірка excluded_patterns - якщо збігається, то блокуємо
        for pattern in self.excluded_patterns:
            if pattern.search(path):
                logger.debug(f"Path excluded by pattern {pattern.pattern}: {path}")
                self._publish_filtered_event(
                    url, "path", "excluded_pattern", pattern.pattern
                )
                return False

        # Перевірка included_patterns - якщо задані, то дозволяємо тільки їх
        if self.included_patterns:
            for pattern in self.included_patterns:
                if pattern.search(path):
                    return True
            logger.debug(f"Path not in included patterns: {path}")
            self._publish_filtered_event(url, "path", "not_included", None)
            return False

        return True

    # FIXED: Method moved to BaseURLFilter to avoid duplication
    # Now using super()._publish_filtered_event() instead
