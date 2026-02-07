"""DNS Cache для оптимізації швидкості запитів.

DNS lookup на кожному запиті займає 50-100ms. Цей модуль кешує DNS відповіді
щоб економити час на повторних запитах до того самого домену.

Архітектура:
- Використовує monkey patching socket.getaddrinfo
- Працює з будь-якою HTTP бібліотекою (requests, aiohttp, httpx, urllib)
- Не залежить від конкретних драйверів
- Thread-safe через threading.Lock
- TTL для автоматичного оновлення кешу

Приклад використання:
    >>> from graph_crawler.shared.utils.dns_cache import DNSCache
    >>> from graph_crawler import crawl
    >>>
    >>> # Активувати DNS cache для краулінгу
    >>> with DNSCache(ttl=3600, max_cache_size=1000) as dns_cache:
    ...     graph = crawl("https://example.com", max_depth=3)
    ...     stats = dns_cache.get_statistics()
    ...     print(f"Cache hit rate: {stats['hit_rate']:.1%}")
    Cache hit rate: 87.3%

Як це працює:
1. Патчить socket.getaddrinfo (низький рівень DNS lookup)
2. Перехоплює всі DNS запити від будь-якої бібліотеки
3. Якщо домен в кеші та не expired - повертає кешовану IP
4. Якщо домену немає або TTL закінчився - робить real DNS lookup та кешує
5. При виході з context manager - відновлює оригінальну функцію

Переваги:
Економія 50-100ms на кожному запиті (крім першого на домен)
Працює з усіма HTTP драйверами автоматично
Не ламається при створенні custom драйверів
Thread-safe для багатопоточного краулінгу
TTL запобігає використанню застарілих IP
Статистика для моніторингу ефективності
"""

import logging
import socket
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class DNSCacheEntry:
    """Запис в DNS кеші.

    Attributes:
        domain: Доменне ім'я
        ip_addresses: Список IP адрес для домену
        cached_at: Час коли запис було додано в кеш
        expires_at: Час коли запис стане недійсним (cached_at + TTL)
        hit_count: Кількість разів коли цей запис використовувався з кешу
        original_result: Оригінальний результат socket.getaddrinfo для відновлення
    """

    domain: str
    ip_addresses: List[str]
    cached_at: float
    expires_at: float
    hit_count: int = 0
    original_result: List[Tuple] = field(default_factory=list)

    def is_expired(self) -> bool:
        """Перевіряє чи запис застарів (TTL закінчився)."""
        return time.time() > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        """Конвертує запис в словник для експорту."""
        return {
            "domain": self.domain,
            "ip_addresses": self.ip_addresses,
            "cached_at": datetime.fromtimestamp(self.cached_at).isoformat(),
            "expires_at": datetime.fromtimestamp(self.expires_at).isoformat(),
            "hit_count": self.hit_count,
            "ttl_remaining_seconds": max(0, int(self.expires_at - time.time())),
        }


class DNSCache:
    """DNS Cache для оптимізації швидкості HTTP запитів.

    Кешує DNS lookup результати щоб уникнути повторних запитів до DNS серверів.
    Економія: 50-100ms на кожному запиті (крім першого на домен).

    Використовує monkey patching socket.getaddrinfo, тому працює з:
    - requests (HTTPDriver)
    - aiohttp (AsyncDriver)
    - httpx
    - urllib
    - будь-якою іншою HTTP бібліотекою

    Thread-safe: Використовує threading.Lock для безпечної роботи в багатопоточному середовищі.

    Приклади:
        >>> # Базове використання
        >>> with DNSCache() as dns_cache:
        ...     # Всі HTTP запити автоматично використовують DNS cache
        ...     driver = HTTPDriver()
        ...     response = driver.fetch("https://example.com")

        >>> # З custom налаштуваннями
        >>> with DNSCache(ttl=7200, max_cache_size=5000) as cache:
        ...     graph = crawl("https://example.com", max_depth=5)
        ...     print(cache.get_summary())

        >>> # Ручне управління (без context manager)
        >>> cache = DNSCache(ttl=1800)
        >>> cache.enable()
        >>> try:
        ...     # Ваш код з HTTP запитами
        ...     pass
        ... finally:
        ...     cache.disable()

    Args:
        ttl: Time To Live в секундах (за замовчуванням 3600 = 1 година)
        max_cache_size: Максимальна кількість записів в кеші (за замовчуванням 10000)
        enabled: Чи активувати кеш відразу (за замовчуванням False, активується через enable())
    """

    def __init__(
        self, ttl: int = 3600, max_cache_size: int = 10000, enabled: bool = False
    ):
        """
        Ініціалізує DNS Cache.

        Args:
            ttl: Час життя записів в секундах (за замовчуванням 3600 = 1 година)
            max_cache_size: Максимальна кількість доменів в кеші (за замовчуванням 10000)
            enabled: Чи активувати кеш одразу (за замовчуванням False)
        """
        self.ttl = ttl
        self.max_cache_size = max_cache_size
        self._cache: Dict[str, DNSCacheEntry] = {}
        self._lock = threading.Lock()
        self._enabled = False
        self._original_getaddrinfo = socket.getaddrinfo

        # Статистика
        self._stats = {
            "total_lookups": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "expired_entries": 0,
            "evictions": 0,
        }

        logger.info(
            f" DNSCache initialized: ttl={ttl}s, max_size={max_cache_size}, enabled={enabled}"
        )

        if enabled:
            self.enable()

    def _patched_getaddrinfo(self, host, port, family=0, type=0, proto=0, flags=0):
        """
        Патчена версія socket.getaddrinfo яка використовує кеш.

        Це внутрішня функція яка замінює socket.getaddrinfo коли кеш активний.
        Перехоплює всі DNS lookup запити та використовує кеш якщо можливо.

        Args:
            host: Доменне ім'я або IP адреса
            port: Порт
            family: Address family (AF_INET, AF_INET6, AF_UNSPEC)
            type: Socket type (SOCK_STREAM, SOCK_DGRAM)
            proto: Protocol (IPPROTO_TCP, IPPROTO_UDP)
            flags: Flags для getaddrinfo

        Returns:
            Список tuples у форматі socket.getaddrinfo
        """
        with self._lock:
            self._stats["total_lookups"] += 1

            # Якщо host це вже IP адреса - пропускаємо кеш
            try:
                socket.inet_aton(host)
                # Це IP адреса, не потрібно кешувати
                return self._original_getaddrinfo(
                    host, port, family, type, proto, flags
                )
            except (socket.error, TypeError):
                # Це доменне ім'я, продовжуємо з кешуванням
                pass

            # Перевіряємо чи є в кеші
            if host in self._cache:
                entry = self._cache[host]

                # Перевіряємо чи не expired
                if not entry.is_expired():
                    # Cache HIT!
                    self._stats["cache_hits"] += 1
                    entry.hit_count += 1
                    logger.debug(f"DNS Cache HIT: {host} -> {entry.ip_addresses[0]}")
                    return entry.original_result
                else:
                    # Expired, видаляємо
                    self._stats["expired_entries"] += 1
                    del self._cache[host]
                    logger.debug(f"⏰ DNS Cache EXPIRED: {host}")

            # Cache MISS - робимо real DNS lookup
            self._stats["cache_misses"] += 1
            logger.debug(f" DNS Cache MISS: {host} - performing real DNS lookup")

            result = self._original_getaddrinfo(host, port, family, type, proto, flags)

            # Зберігаємо в кеш
            if result:
                # Витягуємо IP адреси з результату
                ip_addresses = list(set(addr[4][0] for addr in result))

                # Перевіряємо розмір кешу
                if len(self._cache) >= self.max_cache_size:
                    # Evict найстарішій запис
                    oldest_domain = min(
                        self._cache.keys(), key=lambda k: self._cache[k].cached_at
                    )
                    del self._cache[oldest_domain]
                    self._stats["evictions"] += 1
                    logger.debug(f" DNS Cache EVICTION: {oldest_domain} (cache full)")

                # Додаємо новий запис
                now = time.time()
                entry = DNSCacheEntry(
                    domain=host,
                    ip_addresses=ip_addresses,
                    cached_at=now,
                    expires_at=now + self.ttl,
                    original_result=result,
                )
                self._cache[host] = entry
                logger.debug(
                    f" DNS Cache STORED: {host} -> {ip_addresses[0]} (TTL: {self.ttl}s)"
                )

            return result

    def enable(self):
        """Активує DNS cache (патчить socket.getaddrinfo)."""
        if self._enabled:
            logger.warning(" DNSCache already enabled")
            return

        socket.getaddrinfo = self._patched_getaddrinfo
        self._enabled = True
        logger.info("DNSCache ENABLED - all DNS lookups will be cached")

    def disable(self):
        """Деактивує DNS cache (відновлює оригінальну socket.getaddrinfo)."""
        if not self._enabled:
            logger.warning(" DNSCache already disabled")
            return

        socket.getaddrinfo = self._original_getaddrinfo
        self._enabled = False
        logger.info(" DNSCache DISABLED - using original DNS lookups")

    def clear(self):
        """Очищає весь кеш."""
        with self._lock:
            cleared_count = len(self._cache)
            self._cache.clear()
            logger.info(f" DNSCache cleared: {cleared_count} entries removed")

    def invalidate(self, domain: str):
        """
        Видаляє конкретний домен з кешу.

        Корисно якщо знаєте що IP адреса змінилась.

        Args:
            domain: Доменне ім'я для видалення з кешу
        """
        with self._lock:
            if domain in self._cache:
                del self._cache[domain]
                logger.info(f" DNSCache invalidated: {domain}")
            else:
                logger.debug(f" Domain not in cache: {domain}")

    def get_cached_domains(self) -> List[str]:
        """
        Повертає список всіх доменів в кеші.

        Returns:
            Список доменних імен
        """
        with self._lock:
            return list(self._cache.keys())

    def get_entry(self, domain: str) -> Optional[DNSCacheEntry]:
        """
        Отримує запис з кешу для конкретного домену.

        Args:
            domain: Доменне ім'я

        Returns:
            DNSCacheEntry якщо знайдено, None якщо домену немає в кеші
        """
        with self._lock:
            return self._cache.get(domain)

    def get_statistics(self) -> Dict[str, Any]:
        """
        Повертає детальну статистику роботи кешу.

        Returns:
            Словник зі статистикою:
            - total_lookups: Загальна кількість DNS lookup запитів
            - cache_hits: Кількість знайдених в кеші
            - cache_misses: Кількість не знайдених в кеші (real DNS lookup)
            - hit_rate: Відсоток знайдених в кеші (0.0 - 1.0)
            - expired_entries: Кількість застарілих записів
            - evictions: Кількість видалених записів через переповнення кешу
            - cache_size: Поточна кількість записів в кеші
            - enabled: Чи активний кеш
        """
        with self._lock:
            total = self._stats["total_lookups"]
            hits = self._stats["cache_hits"]
            hit_rate = (hits / total) if total > 0 else 0.0

            return {
                "total_lookups": total,
                "cache_hits": hits,
                "cache_misses": self._stats["cache_misses"],
                "hit_rate": hit_rate,
                "expired_entries": self._stats["expired_entries"],
                "evictions": self._stats["evictions"],
                "cache_size": len(self._cache),
                "max_cache_size": self.max_cache_size,
                "ttl_seconds": self.ttl,
                "enabled": self._enabled,
            }

    def get_summary(self) -> str:
        """
        Генерує текстовий summary статистики кешу.

        Returns:
            Форматований текст зі статистикою
        """
        stats = self.get_statistics()

        summary = [
            "=" * 60,
            " DNS Cache Statistics",
            "=" * 60,
            f"Status: {'ENABLED' if stats['enabled'] else ' DISABLED'}",
            f"TTL: {stats['ttl_seconds']} seconds",
            "",
            " Lookup Statistics:",
            f"  Total lookups: {stats['total_lookups']}",
            f"  Cache hits: {stats['cache_hits']} ",
            f"  Cache misses: {stats['cache_misses']} ",
            f"  Hit rate: {stats['hit_rate']:.1%}",
            "",
            " Cache Statistics:",
            f"  Current size: {stats['cache_size']} / {stats['max_cache_size']}",
            f"  Expired entries: {stats['expired_entries']} ⏰",
            f"  Evictions: {stats['evictions']} ",
            "=" * 60,
        ]

        return "\n".join(summary)

    def export_cache(self) -> List[Dict[str, Any]]:
        """
        Експортує весь кеш у форматі списку словників.

        Корисно для аналізу та debugging.

        Returns:
            Список словників з інформацією про кешовані домени
        """
        with self._lock:
            return [entry.to_dict() for entry in self._cache.values()]

    def cleanup_expired(self) -> int:
        """
        Видаляє всі застарілі записи з кешу.

        Викликається автоматично при lookup, але можна викликати вручну
        для звільнення пам'яті.

        Returns:
            Кількість видалених записів
        """
        with self._lock:
            expired_domains = [
                domain for domain, entry in self._cache.items() if entry.is_expired()
            ]

            for domain in expired_domains:
                del self._cache[domain]

            if expired_domains:
                logger.info(f" Cleaned up {len(expired_domains)} expired DNS entries")

            return len(expired_domains)

    # Context manager support
    def __enter__(self):
        """Context manager entry - активує кеш."""
        self.enable()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - деактивує кеш."""
        self.disable()
        return False

    def __repr__(self) -> str:
        """String representation для debugging."""
        return (
            f"DNSCache(ttl={self.ttl}, max_size={self.max_cache_size}, "
            f"enabled={self._enabled}, cached_domains={len(self._cache)})"
        )
