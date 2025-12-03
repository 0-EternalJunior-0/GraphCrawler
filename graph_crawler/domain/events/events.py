"""Event типи та моделі."""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Типи подій в системі."""

    # Node події
    NODE_CREATED = "node_created"
    NODE_SCAN_STARTED = (
        "node_scan_started"  # Додано Alpha 2.0 - перед початком скану ноди
    )
    NODE_SCANNED = "node_scanned"
    NODE_FAILED = "node_failed"
    NODE_SKIPPED_UNCHANGED = (
        "node_skipped_unchanged"  # Додано Alpha 2.0 - incremental skip
    )
    NODE_DETECTED_CHANGED = (
        "node_detected_changed"  # Додано Alpha 2.0 - incremental changed
    )

    # Edge події
    EDGE_CREATED = "edge_created"

    # Crawler події
    CRAWL_STARTED = "crawl_started"
    CRAWL_COMPLETED = "crawl_completed"
    CRAWL_PAUSED = "crawl_paused"
    CRAWL_RESUMED = "crawl_resumed"
    BATCH_COMPLETED = "batch_completed"  # Додано Alpha 2.0 - після обробки batch

    # Scheduler події (Додано Alpha 2.0)
    URL_ADDED_TO_QUEUE = "url_added_to_queue"  # URL додано в чергу
    URL_EXCLUDED = "url_excluded"  # URL виключено через action='exclude'
    URL_PRIORITIZED = "url_prioritized"  # URL отримав пріоритет
    URL_FILTERED_OUT = "url_filtered_out"  # URL відфільтровано (domain/path filter)

    # Error події
    ERROR_OCCURRED = "error_occurred"
    RETRY_ATTEMPTED = "retry_attempted"

    # Storage події (Додано Alpha 2.0)
    GRAPH_SAVED = "graph_saved"
    GRAPH_LOADED = "graph_loaded"
    STORAGE_UPGRADED = "storage_upgraded"  # Memory → JSON → SQLite перехід

    # Plugin події (Додано Alpha 2.0)
    PLUGIN_STARTED = "plugin_started"  # Плагін почав виконання
    PLUGIN_COMPLETED = "plugin_completed"  # Плагін завершив виконання
    PLUGIN_FAILED = "plugin_failed"  # Плагін завершився з помилкою

    # Progress та Performance події (Alpha 2.0 - для Dashboard)
    PROGRESS_UPDATE = "progress_update"  # Оновлення прогресу
    PAGE_FETCH_TIME = "page_fetch_time"  # Час завантаження сторінки

    # Middleware події (Alpha 2.0 - Категорія 7.1)
    # Rate Limiting
    RATE_LIMIT_WAIT = "rate_limit_wait"  # Очікування на токен
    RATE_LIMIT_TOKEN_CONSUMED = "rate_limit_token_consumed"  # Токен спожито
    # Proxy Rotation
    PROXY_SELECTED = "proxy_selected"  # Proxy обрано для запиту
    PROXY_FAILED = "proxy_failed"  # Proxy не працює
    PROXY_HEALTH_CHECK = "proxy_health_check"  # Перевірка здоров'я proxy
    PROXY_DISABLED = "proxy_disabled"  # Proxy автоматично вимкнено
    PROXY_RECHECK = "proxy_recheck"  # Повторна перевірка мертвих proxy
    # User Agent Rotation
    USER_AGENT_ROTATED = "user_agent_rotated"  # User agent змінено
    # Retry Middleware
    RETRY_STARTED = "retry_started"  # Початок retry спроби
    RETRY_SUCCESS = "retry_success"  # Успішний retry після помилки
    RETRY_EXHAUSTED = "retry_exhausted"  # Вичерпано всі retry спроби
    # Error Recovery Middleware
    ERROR_DETECTED = "error_detected"  # Виявлено помилку
    ERROR_RECOVERY_STARTED = "error_recovery_started"  # Почато recovery
    ERROR_RECOVERY_SUCCESS = "error_recovery_success"  # Recovery успішний
    ERROR_RECOVERY_FAILED = "error_recovery_failed"  # Recovery не вдався
    ERROR_THRESHOLD_REACHED = "error_threshold_reached"  # Досягнуто ліміт помилок

    # Sitemap події (Alpha 2.0 - для sitemap crawling)
    SITEMAP_CRAWL_STARTED = "sitemap_crawl_started"  # Початок sitemap краулінгу
    ROBOTS_TXT_PARSED = "robots_txt_parsed"  # robots.txt спарсено
    SITEMAP_INDEX_FOUND = "sitemap_index_found"  # Знайдено sitemap index
    SITEMAP_PARSED = "sitemap_parsed"  # Sitemap спарсено
    URL_EXTRACTED = "url_extracted"  # URL витягнуто зі sitemap
    SITEMAP_ERROR = "sitemap_error"  # Помилка при обробці sitemap (404, parse error)
    SITEMAP_CRAWL_COMPLETED = "sitemap_crawl_completed"  # Завершення sitemap краулінгу

    # Driver fetch події (Alpha 2.0 - Категорія 7.2)
    FETCH_STARTED = "fetch_started"  # Початок fetch запиту
    FETCH_SUCCESS = "fetch_success"  # Успішний fetch
    FETCH_ERROR = "fetch_error"  # Помилка fetch
    FETCH_RETRY = "fetch_retry"  # Повторна спроба fetch

    # Storage події (Alpha 2.0 - Категорія 7.3)
    STORAGE_SAVE_STARTED = "storage_save_started"  # Початок збереження
    STORAGE_SAVE_SUCCESS = "storage_save_success"  # Успішне збереження
    STORAGE_SAVE_ERROR = "storage_save_error"  # Помилка збереження
    STORAGE_LOAD_STARTED = "storage_load_started"  # Початок завантаження
    STORAGE_LOAD_SUCCESS = "storage_load_success"  # Успішне завантаження
    STORAGE_LOAD_ERROR = "storage_load_error"  # Помилка завантаження

    # Exporter події (Alpha 2.0 - Категорія 7.4)
    EXPORT_STARTED = "export_started"  # Початок експорту
    EXPORT_PROGRESS = "export_progress"  # Прогрес експорту
    EXPORT_SUCCESS = "export_success"  # Успішний експорт
    EXPORT_ERROR = "export_error"  # Помилка експорту


@dataclass
class CrawlerEvent:
    """
    Базова модель події.

    Атрибути:
        event_type: Тип події
        timestamp: Час події
        data: Дані події
        metadata: Додаткові метадані
    """

    event_type: EventType
    timestamp: datetime
    data: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None

    @classmethod
    def create(
        cls,
        event_type: EventType,
        data: Dict[str, Any] = None,
        metadata: Dict[str, Any] = None,
    ) -> "CrawlerEvent":
        """Створює нову подію."""
        return cls(
            event_type=event_type,
            timestamp=datetime.now(),
            data=data or {},
            metadata=metadata or {},
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Серіалізує подію з перевіркою JSON compatibility.

         ВАЖЛИВО: data має містити тільки JSON-serializable типи.
        Якщо data містить несеріалізовані об'єкти (Node, Graph тощо),
        вони будуть конвертовані в строкове представлення.

        Returns:
            Словник з серіалізованою подією
        """
        # Перевіряємо чи data JSON-serializable
        safe_data = self._ensure_json_serializable(self.data)
        safe_metadata = self._ensure_json_serializable(self.metadata or {})

        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "data": safe_data,
            "metadata": safe_metadata,
        }

    def _ensure_json_serializable(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Переконується що дані JSON-serializable.

        Args:
            data: Дані для перевірки

        Returns:
            Безпечні дані (JSON-serializable)
        """
        try:
            # Спроба серіалізації
            json.dumps(data)
            return data
        except (TypeError, ValueError) as e:
            # Є несеріалізовані об'єкти - конвертуємо їх
            logger.warning(f"Event data contains non-serializable objects: {e}")
            safe_data = {}
            for key, value in data.items():
                if isinstance(value, (int, float, str, bool, type(None))):
                    # Прості типи - залишаємо як є
                    safe_data[key] = value
                elif isinstance(value, (list, tuple)):
                    # Списки - конвертуємо елементи
                    safe_data[key] = [
                        (
                            str(v)
                            if not isinstance(v, (int, float, str, bool, type(None)))
                            else v
                        )
                        for v in value
                    ]
                elif isinstance(value, dict):
                    # Словники - рекурсивно обробляємо
                    safe_data[key] = self._ensure_json_serializable(value)
                else:
                    # Складні об'єкти - конвертуємо в строку
                    safe_data[key] = str(value)
            return safe_data
