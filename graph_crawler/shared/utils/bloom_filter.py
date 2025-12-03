"""
Bloom Filter для ефективної перевірки seen URLs.

Bloom Filter - це імовірнісна структура даних що дозволяє перевірити
чи елемент є у множині. Використовує в 10 разів менше пам'яті ніж set,
але може давати false positives (1 на 1000 при налаштуваннях).

Використання:
    >>> bloom = BloomFilter(capacity=10_000_000, error_rate=0.001)
    >>> bloom.add("https://example.com")
    >>> "https://example.com" in bloom
    True
    >>> "https://not-added.com" in bloom
    False

Alpha 2.0: Додано Bloom Filter для економії пам'яті при великих краулінгах
"""

import logging
import sys
from typing import Optional

from pybloom_live import ScalableBloomFilter

logger = logging.getLogger(__name__)


class BloomFilter:
    """
    Bloom Filter для ефективної перевірки seen URLs.

    Використовує pybloom-live для реалізації Scalable Bloom Filter,
    який автоматично розширюється коли досягає capacity.

    Args:
        capacity: Очікувана кількість елементів (default: 10,000,000)
        error_rate: Ймовірність false positive (default: 0.001 = 0.1%)
        mode: Режим роботи (default: ScalableBloomFilter.SMALL_SET_GROWTH)

    Attributes:
        capacity: Поточна capacity
        error_rate: Налаштований error rate
        count: Кількість доданих елементів
        bloom: Внутрішній ScalableBloomFilter

    Example:
        >>> # Створюємо Bloom Filter для 10M URLs з 0.1% false positive rate
        >>> bloom = BloomFilter(capacity=10_000_000, error_rate=0.001)
        >>>
        >>> # Додаємо URLs
        >>> bloom.add("https://example.com")
        >>> bloom.add("https://example.com/page1")
        >>>
        >>> # Перевіряємо наявність
        >>> "https://example.com" in bloom
        True
        >>>
        >>> # Статистика
        >>> stats = bloom.get_statistics()
        >>> print(f"Count: {stats['count']}, Memory: {stats['memory_usage_mb']} MB")
    """

    def __init__(
        self,
        capacity: int = 10_000_000,
        error_rate: float = 0.001,
        mode: int = ScalableBloomFilter.SMALL_SET_GROWTH,
    ):
        """
        Ініціалізує Bloom Filter.

        Args:
            capacity: Початкова capacity (default: 10,000,000)
            error_rate: Ймовірність false positive від 0 до 1 (default: 0.001 = 0.1%)
            mode: Режим growth (SMALL_SET_GROWTH або LARGE_SET_GROWTH)

        Raises:
            ValueError: Якщо error_rate не в межах (0, 1)
        """
        if not 0 < error_rate < 1:
            raise ValueError(f"error_rate має бути між 0 та 1, отримано: {error_rate}")

        self.capacity = capacity
        self.error_rate = error_rate
        self.count = 0

        # Створюємо ScalableBloomFilter що автоматично розширюється
        self.bloom = ScalableBloomFilter(
            initial_capacity=capacity, error_rate=error_rate, mode=mode
        )

        logger.info(
            f" Bloom Filter initialized: "
            f"capacity={capacity:,}, error_rate={error_rate*100}%, "
            f"mode={mode}"
        )

    def add(self, url: str) -> None:
        """
        Додає URL до Bloom Filter.

        Args:
            url: URL для додавання

        Example:
            >>> bloom = BloomFilter()
            >>> bloom.add("https://example.com")
            >>> bloom.count
            1
        """
        self.bloom.add(url)
        self.count += 1

        # Логування кожні 10,000 URLs
        if self.count % 10_000 == 0:
            stats = self.get_statistics()
            logger.debug(
                f" Bloom Filter: {self.count:,} URLs added, "
                f"{stats['memory_usage_mb']:.2f} MB used, "
                f"fill ratio: {stats['fill_ratio']:.2%}"
            )

    def __contains__(self, url: str) -> bool:
        """
        Перевіряє чи URL є в Bloom Filter.

        Args:
            url: URL для перевірки

        Returns:
            True якщо URL можливо є (або false positive),
            False якщо URL точно немає

        Example:
            >>> bloom = BloomFilter()
            >>> bloom.add("https://example.com")
            >>> "https://example.com" in bloom
            True
            >>> "https://not-added.com" in bloom
            False
        """
        return url in self.bloom

    def get_statistics(self) -> dict:
        """
        Повертає статистику Bloom Filter.

        Returns:
            dict з полями:
                - count: кількість доданих елементів
                - capacity: поточна capacity
                - error_rate: налаштований error rate
                - memory_usage_bytes: використання пам'яті в байтах
                - memory_usage_mb: використання пам'яті в MB
                - fill_ratio: коефіцієнт заповнення (0.0 - 1.0)
                - estimated_false_positive_rate: поточний FP rate

        Example:
            >>> bloom = BloomFilter(capacity=1_000_000)
            >>> for i in range(500_000):
            ...     bloom.add(f"https://example.com/page{i}")
            >>> stats = bloom.get_statistics()
            >>> print(f"Memory: {stats['memory_usage_mb']:.2f} MB")
            >>> print(f"Fill ratio: {stats['fill_ratio']:.2%}")
        """
        # Розраховуємо використання пам'яті
        memory_bytes = sys.getsizeof(self.bloom)
        memory_mb = memory_bytes / (1024 * 1024)

        # Fill ratio (наскільки заповнений фільтр)
        fill_ratio = self.count / self.capacity if self.capacity > 0 else 0.0

        # Estimated false positive rate зростає з fill ratio
        # Використовуємо апроксимацію: FP ≈ (1 - e^(-k*n/m))^k
        # Для спрощення використовуємо базовий error_rate * (fill_ratio + 1)
        estimated_fp_rate = min(self.error_rate * (fill_ratio + 1), 1.0)

        return {
            "count": self.count,
            "capacity": self.capacity,
            "error_rate": self.error_rate,
            "memory_usage_bytes": memory_bytes,
            "memory_usage_mb": memory_mb,
            "fill_ratio": fill_ratio,
            "estimated_false_positive_rate": estimated_fp_rate,
        }

    def get_summary(self) -> str:
        """
        Повертає текстовий summary статистики.

        Returns:
            Форматований рядок зі статистикою

        Example:
            >>> bloom = BloomFilter()
            >>> bloom.add("https://example.com")
            >>> print(bloom.get_summary())
             Bloom Filter Statistics

            URLs Added:         1
            Capacity:           10,000,000
            Error Rate:         0.10%
            Memory Usage:       0.05 MB
            Fill Ratio:         0.00%
            Estimated FP Rate:  0.10%
        """
        stats = self.get_statistics()

        summary = [
            " Bloom Filter Statistics",
            "" * 42,
            f"URLs Added:         {stats['count']:,}",
            f"Capacity:           {stats['capacity']:,}",
            f"Error Rate:         {stats['error_rate']*100:.2f}%",
            f"Memory Usage:       {stats['memory_usage_mb']:.2f} MB",
            f"Fill Ratio:         {stats['fill_ratio']*100:.2f}%",
            f"Estimated FP Rate:  {stats['estimated_false_positive_rate']*100:.2f}%",
        ]

        # Додаємо warning якщо fill ratio високий
        if stats["fill_ratio"] > 0.8:
            summary.append("")
            summary.append("  WARNING: Fill ratio > 80%, consider increasing capacity")

        return "\n".join(summary)

    def clear(self) -> None:
        """
        Очищує Bloom Filter (створює новий фільтр).

        Example:
            >>> bloom = BloomFilter()
            >>> bloom.add("https://example.com")
            >>> bloom.count
            1
            >>> bloom.clear()
            >>> bloom.count
            0
        """
        self.bloom = ScalableBloomFilter(
            initial_capacity=self.capacity,
            error_rate=self.error_rate,
            mode=ScalableBloomFilter.SMALL_SET_GROWTH,
        )
        self.count = 0
        logger.info(" Bloom Filter cleared")

    def compare_with_set(self, set_memory_bytes: int) -> dict:
        """
        Порівнює використання пам'яті з set.

        Args:
            set_memory_bytes: Розмір set з такою ж кількістю елементів

        Returns:
            dict з порівнянням:
                - bloom_memory_mb: пам'ять Bloom Filter
                - set_memory_mb: пам'ять set
                - memory_saving_mb: економія пам'яті
                - memory_saving_ratio: коефіцієнт економії (скільки разів менше)

        Example:
            >>> import sys
            >>> urls = [f"https://example.com/page{i}" for i in range(100_000)]
            >>> url_set = set(urls)
            >>> set_memory = sys.getsizeof(url_set)
            >>>
            >>> bloom = BloomFilter()
            >>> for url in urls:
            ...     bloom.add(url)
            >>>
            >>> comparison = bloom.compare_with_set(set_memory)
            >>> print(f"Memory saving: {comparison['memory_saving_ratio']:.1f}x")
        """
        stats = self.get_statistics()
        bloom_memory_mb = stats["memory_usage_mb"]
        set_memory_mb = set_memory_bytes / (1024 * 1024)

        memory_saving_mb = set_memory_mb - bloom_memory_mb
        memory_saving_ratio = (
            set_memory_mb / bloom_memory_mb if bloom_memory_mb > 0 else 0
        )

        return {
            "bloom_memory_mb": bloom_memory_mb,
            "set_memory_mb": set_memory_mb,
            "memory_saving_mb": memory_saving_mb,
            "memory_saving_ratio": memory_saving_ratio,
        }


# Зручна функція для створення Bloom Filter з preset конфігураціями
def create_bloom_filter(size: str = "medium", error_rate: float = 0.001) -> BloomFilter:
    """
    Створює Bloom Filter з preset розмірами.

    Args:
        size: Розмір фільтра:
            - "small": 100,000 URLs (для невеликих сайтів)
            - "medium": 1,000,000 URLs (для середніх сайтів)
            - "large": 10,000,000 URLs (для великих сайтів)
            - "xlarge": 100,000,000 URLs (для масивних краулінгів)
        error_rate: Ймовірність false positive (default: 0.001 = 0.1%)

    Returns:
        Налаштований BloomFilter

    Example:
        >>> bloom = create_bloom_filter("large")  # 10M URLs capacity
        >>> bloom.capacity
        10000000
    """
    sizes = {
        "small": 100_000,
        "medium": 1_000_000,
        "large": 10_000_000,
        "xlarge": 100_000_000,
    }

    capacity = sizes.get(size.lower(), 1_000_000)

    logger.info(f"Creating Bloom Filter with preset '{size}': {capacity:,} URLs")

    return BloomFilter(capacity=capacity, error_rate=error_rate)
