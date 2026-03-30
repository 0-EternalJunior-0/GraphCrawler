"""Базові класи для Crawl Engine плагінів.

Engine плагіни працюють на рівні package_crawler engine і впливають на процес краулінгу:
- Приоритизація URL
- Рішення про сканування
- ML-керований обхід
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class EnginePluginType(str, Enum):
    """Типи Engine плагінів."""

    # Викликається ПЕРЕД додаванням URL в Scheduler
    BEFORE_URL_ADDED = "before_url_added"

    # Викликається коли потрібно обчислити пріоритети для списку URL
    # Використовується для batch пріоритизації
    CALCULATE_PRIORITIES = "calculate_priorities"

    # Викликається ПІСЛЯ сканування для аналізу результатів
    # Може впливати на наступні URL
    AFTER_SCAN_ANALYSIS = "after_scan_analysis"


@dataclass
class EnginePluginContext:
    """Контекст для Engine плагінів.

    Передає дані між плагіном та Scheduler через абстракцію.
    """

    url: str
    url_text: Optional[str] = None
    depth: int = 0
    parent_url: Optional[str] = None
    parent_score: Optional[float] = None

    # Batch обробка
    urls_batch: List[str] = field(default_factory=list)

    # Parent context
    parent_context: Dict[str, Any] = field(default_factory=dict)

    # Результати сканування
    scanned_html: Optional[str] = None
    scanned_text: Optional[str] = None
    scanned_metadata: Dict[str, Any] = field(default_factory=dict)
    extracted_links: List[str] = field(default_factory=list)

    # User data
    user_data: Dict[str, Any] = field(default_factory=dict)


class BaseEnginePlugin(ABC):
    """Базовий клас для Crawl Engine плагінів.

    Engine плагіни працюють на вищому рівні ніж Node плагіни:
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Ініціалізує Engine плагін.

        Args:
            config: Словник з конфігурацією
        """
        self.config = config or {}
        self.enabled = self.config.get("enabled", True)

        logger.debug("%s initialized with config: %s", self.name, self.config)

    @property
    @abstractmethod
    def plugin_type(self) -> EnginePluginType:
        """Тип плагіну."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Назва плагіну."""
        pass

    @abstractmethod
    def calculate_url_priority(self, context: EnginePluginContext) -> Optional[int]:
        """Обчислює пріоритет для URL.

        Викликається коли потрібно визначити пріоритет URL перед додаванням в чергу.

        Args:
            context: Контекст з інформацією про URL

        Returns:
            int: Пріоритет 1-15 (15 = найвищий)
            None: Якщо плагін не може визначити пріоритет для цього URL

        Note:
            Повернення None означає "skip" - інші плагіни або дефолтні правила
            визначать пріоритет.
        """
        pass

    def calculate_batch_priorities(self, contexts: List[EnginePluginContext]) -> Dict[str, int]:
        """Обчислює пріоритети для batch URL (опціонально).

        Деякі ML моделі ефективніші при batch обробці.
        За замовчуванням викликає calculate_url_priority для кожного URL.

        Args:
            contexts: Список контекстів для обробки

        Returns:
            Dict[url, priority]: Мапа URL -> пріоритет
        """
        result = {}
        for ctx in contexts:
            priority = self.calculate_url_priority(ctx)
            if priority is not None:
                result[ctx.url] = priority
        return result

    def should_scan_url(self, context: EnginePluginContext) -> Optional[bool]:
        """Визначає чи потрібно сканувати URL (опціонально).

        Дозволяє плагіну явно блокувати або дозволяти сканування URL.

        Args:
            context: Контекст з інформацією про URL

        Returns:
            True: Точно сканувати цей URL (високий пріоритет)
            False: Точно НЕ сканувати цей URL (блокувати)
            None: Немає явного рішення, використати дефолтні правила
        """
        return None

    def analyze_scan_result(self, context: EnginePluginContext) -> Tuple[float, Dict[str, Any]]:
        """Аналізує результати сканування (опціонально).

        Викликається ПІСЛЯ сканування для аналізу контенту.
        Може впливати на пріоритизацію наступних URL.

        Args:
            context: Контекст з результатами сканування

        Returns:
            Tuple[score, metadata]:
                score: Relevance score сторінки 0.0-1.0
                metadata: Додаткові дані про сторінку
        """
        return 0.0, {}

    def setup(self):
        """Ініціалізація плагіну (опціонально)."""
        pass

    def teardown(self):
        """Очищення ресурсів плагіну (опціонально)."""
        pass

    def __repr__(self):
        return f"{self.__class__.__name__}(enabled={self.enabled}, type={self.plugin_type.value})"
