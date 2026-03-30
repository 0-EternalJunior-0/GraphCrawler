"""
Стратегії детекції змін для incremental crawling.

Використовуються для визначення чи сторінка змінилася з останнього краулінгу.

Example:
    >>> from graph_crawler.domain.entities.strategies import HashStrategy, MetadataStrategy
    >>>
    >>> # Реєстрація в bootstrap
    >>> from graph_crawler.domain.entities.registries import ChangeDetectionStrategyRegistry
    >>> ChangeDetectionStrategyRegistry.register("hash", HashStrategy)
    >>> ChangeDetectionStrategyRegistry.register("metadata", MetadataStrategy)
"""

import hashlib
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class BaseChangeDetectionStrategy(ABC):
    """
    Базовий клас для стратегій детекції змін.

    Визначає інтерфейс для перевірки чи вміст сторінки змінився.
    """

    @abstractmethod
    def has_changed(self, old_data: Dict[str, Any], new_data: Dict[str, Any]) -> bool:
        """
        Перевіряє чи дані змінилися.

        Args:
            old_data: Попередні дані сторінки
            new_data: Нові дані сторінки

        Returns:
            True якщо дані змінилися, False інакше
        """
        pass

    @abstractmethod
    def compute_signature(self, data: Dict[str, Any]) -> str:
        """
        Обчислює сигнатуру даних для порівняння.

        Args:
            data: Дані для обчислення сигнатури

        Returns:
            Строка-сигнатура даних
        """
        pass


class HashStrategy(BaseChangeDetectionStrategy):
    """
    Стратегія детекції змін на основі хешу контенту.

    Обчислює MD5 хеш вмісту сторінки та порівнює з попереднім.
    Ефективна для виявлення будь-яких змін у контенті.

    Example:
        >>> strategy = HashStrategy()
        >>> old = {"content": "Hello World", "title": "Test"}
        >>> new = {"content": "Hello World!", "title": "Test"}
        >>> strategy.has_changed(old, new)
        True
    """

    def __init__(self, fields: Optional[list] = None):
        """
        Args:
            fields: Список полів для хешування.
                   None = хешувати все (дефолт)
        """
        self.fields = fields or ["content", "html", "title", "text"]

    def compute_signature(self, data: Dict[str, Any]) -> str:
        """
        Обчислює MD5 хеш заданих полів.

        Args:
            data: Словник з даними

        Returns:
            MD5 хеш у вигляді hex-строки
        """
        content_parts = []
        for field in self.fields:
            value = data.get(field, "")
            if value:
                if isinstance(value, str):
                    content_parts.append(value)
                else:
                    content_parts.append(str(value))

        combined = "||".join(content_parts)
        # usedforsecurity=False - MD5 використовується для content fingerprinting, не для безпеки
        return hashlib.md5(combined.encode("utf-8"), usedforsecurity=False).hexdigest()

    def has_changed(self, old_data: Dict[str, Any], new_data: Dict[str, Any]) -> bool:
        """
        Порівнює хеші старих та нових даних.

        Args:
            old_data: Попередні дані
            new_data: Нові дані

        Returns:
            True якщо хеші різні (контент змінився)
        """
        old_hash = self.compute_signature(old_data)
        new_hash = self.compute_signature(new_data)

        changed = old_hash != new_hash
        if changed:
            logger.debug("Content changed: %s... -> %s...", old_hash, new_hash)

        return changed


class MetadataStrategy(BaseChangeDetectionStrategy):
    """
    Стратегія детекції змін на основі метаданих.

    Example:
        >>> strategy = MetadataStrategy()
        >>> old = {"last_modified": "2024-01-01", "etag": "abc123"}
        >>> new = {"last_modified": "2024-01-02", "etag": "def456"}
        >>> strategy.has_changed(old, new)
        True
    """

    def __init__(self, check_fields: Optional[list] = None):
        """
        Args:
            check_fields: Поля метаданих для перевірки.
                         Дефолт: ['last_modified', 'etag', 'content_length']
        """
        self.check_fields = check_fields or [
            "last_modified",
            "etag",
            "content_length",
            "content_type",
        ]

    def compute_signature(self, data: Dict[str, Any]) -> str:
        """
        Створює сигнатуру з метаданих.

        Args:
            data: Словник з метаданими

        Returns:
            Комбінована строка метаданих
        """
        parts = []
        for field in self.check_fields:
            value = data.get(field, "")
            if value:
                parts.append(f"{field}={value}")

        return "|".join(sorted(parts))

    def has_changed(self, old_data: Dict[str, Any], new_data: Dict[str, Any]) -> bool:
        """
        Порівнює метадані старих та нових даних.

        Args:
            old_data: Попередні метадані
            new_data: Нові метадані

        Returns:
            True якщо метадані змінились
        """
        # Перевіряємо кожне поле окремо
        for field in self.check_fields:
            old_value = old_data.get(field)
            new_value = new_data.get(field)

            # Якщо обидва значення існують і відрізняються
            if old_value and new_value and old_value != new_value:
                logger.debug("Metadata changed: %s = %s -> %s", field, old_value, new_value)
                return True

        # Якщо немає метаданих для порівняння, вважаємо що змінилось
        old_sig = self.compute_signature(old_data)
        new_sig = self.compute_signature(new_data)

        if not old_sig and not new_sig:
            logger.debug("No metadata available, assuming changed")
            return True

        return old_sig != new_sig
