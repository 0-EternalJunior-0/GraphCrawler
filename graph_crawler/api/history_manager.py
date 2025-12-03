"""
Crawl History Manager

Відповідає за управління історією краулінгу.
"""

import threading
from datetime import datetime
from typing import Any, Dict, List, Optional


class CrawlHistoryManager:
    """
    Управління історією краулінгу.

    Responsibilities:
    - Збереження записів історії
    - Обмеження розміру історії
    - Thread-safe операції з історією
    """

    def __init__(self, max_history_size: int = 1000):
        """
        Initialize history manager.

        Args:
            max_history_size: Максимальний розмір історії
        """
        self.history: List[Dict[str, Any]] = []
        self.max_history_size = max_history_size
        self._lock = threading.Lock()

    def add_entry(self, entry: Dict[str, Any]) -> None:
        """
        Додати запис до історії.

        Args:
            entry: Dict з даними запису (timestamp, total_pages, etc.)
        """
        with self._lock:
            # Додаємо timestamp якщо його немає
            if "timestamp" not in entry:
                entry["timestamp"] = datetime.now().isoformat()

            self.history.append(entry)

            # Обмежити розмір історії
            if len(self.history) > self.max_history_size:
                self.history = self.history[-self.max_history_size :]

    def get_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Отримати історію краулінгу.

        Args:
            limit: Максимальна кількість записів (останні N записів).
                   None = всі записи

        Returns:
            List записів історії
        """
        with self._lock:
            if limit is None:
                return self.history.copy()
            return self.history[-limit:]

    def clear_history(self) -> None:
        """Очистити всю історію."""
        with self._lock:
            self.history = []

    def get_history_size(self) -> int:
        """
        Отримати поточний розмір історії.

        Returns:
            Кількість записів в історії
        """
        with self._lock:
            return len(self.history)
