"""
Proxy Pool Manager для GraphCrawler.

Цей модуль надає функціонал для управління пулом proxy серверів,
включаючи ротацію, health check та автоматичне видалення неробочих proxy.
"""

import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class ProxyType(str, Enum):
    """Типи proxy серверів."""

    HTTP = "http"
    HTTPS = "https"
    SOCKS5 = "socks5"


class RotationStrategy(str, Enum):
    """Стратегії ротації proxy."""

    ROUND_ROBIN = "round_robin"  # По черзі
    RANDOM = "random"  # Випадковий вибір
    LEAST_USED = "least_used"  # Найменше використовуваний
    BEST_PERFORMING = "best_performing"  # З найкращою швидкістю


@dataclass
class ProxyStats:
    """Статистика використання proxy."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_response_time: float = 0.0  # В секундах
    last_used: Optional[datetime] = None
    last_check: Optional[datetime] = None
    is_healthy: bool = True
    consecutive_failures: int = 0

    @property
    def success_rate(self) -> float:
        """Відсоток успішних запитів."""
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100

    @property
    def average_response_time(self) -> float:
        """Середній час відповіді в мілісекундах."""
        if self.successful_requests == 0:
            return 0.0
        return (self.total_response_time / self.successful_requests) * 1000


@dataclass
class Proxy:
    """
    Представлення proxy сервера.

    Args:
        url: URL proxy сервера (наприклад, "http://proxy.example.com:8080")
        proxy_type: Тип proxy (HTTP, HTTPS, SOCKS5)
        username: Опціональне ім'я користувача для автентифікації
        password: Опціональний пароль
        stats: Статистика використання

    Example:
        >>> proxy = Proxy(
        ...     url="http://proxy.example.com:8080",
        ...     proxy_type=ProxyType.HTTP
        ... )
        >>> proxy.get_formatted_url()
        'http://proxy.example.com:8080'
    """

    url: str
    proxy_type: ProxyType = ProxyType.HTTP
    username: Optional[str] = None
    password: Optional[str] = None
    stats: ProxyStats = field(default_factory=ProxyStats)

    def get_formatted_url(self) -> str:
        """
        Повертає відформатований URL для використання з requests.

        Returns:
            Відформатований URL з автентифікацією якщо потрібно
        """
        if self.username and self.password:
            # Додаємо credentials в URL
            if "://" in self.url:
                protocol, rest = self.url.split("://", 1)
                return f"{protocol}://{self.username}:{self.password}@{rest}"
            else:
                return f"http://{self.username}:{self.password}@{self.url}"
        return self.url

    def get_proxy_dict(self) -> Dict[str, str]:
        """
        Повертає словник для використання з requests.

        Returns:
            Dict з ключами 'http' та 'https'
        """
        formatted_url = self.get_formatted_url()
        return {"http": formatted_url, "https": formatted_url}

    def to_dict(self) -> Dict[str, Any]:
        """Конвертує proxy в словник."""
        result = {
            "url": self.url,
            "proxy_type": self.proxy_type.value,
            "username": self.username,
            "password": "***" if self.password else None,  # Не показуємо пароль
            "stats": {
                "total_requests": self.stats.total_requests,
                "successful_requests": self.stats.successful_requests,
                "failed_requests": self.stats.failed_requests,
                "success_rate": self.stats.success_rate,
                "average_response_time_ms": self.stats.average_response_time,
                "is_healthy": self.stats.is_healthy,
                "consecutive_failures": self.stats.consecutive_failures,
                "last_used": (
                    self.stats.last_used.isoformat() if self.stats.last_used else None
                ),
                "last_check": (
                    self.stats.last_check.isoformat() if self.stats.last_check else None
                ),
            },
        }
        return result


class ProxyPoolManager:
    """
    Менеджер пулу proxy серверів з автоматичною ротацією та health check.

    Args:
        proxies: Початковий список proxy серверів
        rotation_strategy: Стратегія ротації (round_robin, random, least_used, best_performing)
        health_check_url: URL для перевірки здоров'я proxy (за замовчуванням http://httpbin.org/ip)
        health_check_timeout: Timeout для health check в секундах
        health_check_interval: Інтервал між автоматичними перевірками в секундах (0 = вимкнено)
        max_consecutive_failures: Максимальна кількість послідовних помилок перед видаленням proxy
        auto_remove_failed: Автоматично видаляти неробочі proxy

    Example:
        >>> manager = ProxyPoolManager(
        ...     proxies=[
        ...         Proxy(url="http://proxy1.example.com:8080", proxy_type=ProxyType.HTTP),
        ...         Proxy(url="http://proxy2.example.com:8080", proxy_type=ProxyType.HTTP),
        ...     ],
        ...     rotation_strategy=RotationStrategy.ROUND_ROBIN
        ... )
        >>> proxy = manager.get_next_proxy()
        >>> print(proxy.url)
        'http://proxy1.example.com:8080'
    """

    def __init__(
        self,
        proxies: Optional[List[Proxy]] = None,
        rotation_strategy: RotationStrategy = RotationStrategy.ROUND_ROBIN,
        health_check_url: str = "http://httpbin.org/ip",
        health_check_timeout: int = 10,
        health_check_interval: int = 0,  # 0 = вимкнено
        max_consecutive_failures: int = 3,
        auto_remove_failed: bool = True,
    ):
        self._proxies: List[Proxy] = proxies or []
        self._rotation_strategy = rotation_strategy
        self._health_check_url = health_check_url
        self._health_check_timeout = health_check_timeout
        self._health_check_interval = health_check_interval
        self._max_consecutive_failures = max_consecutive_failures
        self._auto_remove_failed = auto_remove_failed

        self._lock = threading.Lock()
        self._current_index = 0
        self._start_time = datetime.now()

        logger.info(
            f" ProxyPoolManager ініціалізовано з {len(self._proxies)} proxy, "
            f"стратегія: {rotation_strategy.value}"
        )

    def add_proxy(
        self,
        url: str,
        proxy_type: ProxyType = ProxyType.HTTP,
        username: Optional[str] = None,
        password: Optional[str] = None,
        check_health: bool = True,
    ) -> bool:
        """
        Додає новий proxy до пулу.

        Args:
            url: URL proxy сервера
            proxy_type: Тип proxy
            username: Опціональне ім'я користувача
            password: Опціональний пароль
            check_health: Чи перевіряти здоров'я перед додаванням

        Returns:
            True якщо успішно додано, False якщо health check провалився
        """
        proxy = Proxy(
            url=url, proxy_type=proxy_type, username=username, password=password
        )

        if check_health:
            if not self.check_proxy_health(proxy):
                logger.warning(f" Proxy {url} не пройшов health check, не додано")
                return False

        with self._lock:
            self._proxies.append(proxy)
            logger.info(
                f"Додано proxy: {url}, загальна кількість: {len(self._proxies)}"
            )
        return True

    def remove_proxy(self, url: str) -> bool:
        """
        Видаляє proxy з пулу.

        Args:
            url: URL proxy для видалення

        Returns:
            True якщо видалено, False якщо не знайдено
        """
        with self._lock:
            for i, proxy in enumerate(self._proxies):
                if proxy.url == url:
                    self._proxies.pop(i)
                    logger.info(
                        f" Видалено proxy: {url}, залишилось: {len(self._proxies)}"
                    )
                    return True
        logger.warning(f" Proxy {url} не знайдено")
        return False

    def get_next_proxy(self) -> Optional[Proxy]:
        """
        Отримує наступний proxy згідно стратегії ротації.

        Returns:
            Proxy об'єкт або None якщо пул порожній
        """
        with self._lock:
            if not self._proxies:
                logger.warning(" Пул proxy порожній")
                return None

            if self._rotation_strategy == RotationStrategy.ROUND_ROBIN:
                proxy = self._proxies[self._current_index]
                self._current_index = (self._current_index + 1) % len(self._proxies)

            elif self._rotation_strategy == RotationStrategy.RANDOM:
                import random

                proxy = random.choice(self._proxies)

            elif self._rotation_strategy == RotationStrategy.LEAST_USED:
                proxy = min(self._proxies, key=lambda p: p.stats.total_requests)

            elif self._rotation_strategy == RotationStrategy.BEST_PERFORMING:
                # Вибираємо з найкращим success rate і швидкістю
                healthy_proxies = [p for p in self._proxies if p.stats.is_healthy]
                if not healthy_proxies:
                    healthy_proxies = self._proxies

                proxy = max(
                    healthy_proxies,
                    key=lambda p: (
                        p.stats.success_rate if p.stats.total_requests > 0 else 0,
                        (
                            -p.stats.average_response_time
                            if p.stats.successful_requests > 0
                            else 0
                        ),
                    ),
                )
            else:
                proxy = self._proxies[0]

            proxy.stats.last_used = datetime.now()
            return proxy

    def check_proxy_health(self, proxy: Proxy) -> bool:
        """
        Перевіряє здоров'я proxy сервера.

        Args:
            proxy: Proxy для перевірки

        Returns:
            True якщо proxy працює, False якщо ні
        """
        try:
            start_time = time.time()
            response = requests.get(
                self._health_check_url,
                proxies=proxy.get_proxy_dict(),
                timeout=self._health_check_timeout,
            )
            response_time = time.time() - start_time

            if response.status_code == 200:
                proxy.stats.is_healthy = True
                proxy.stats.consecutive_failures = 0
                proxy.stats.last_check = datetime.now()
                logger.debug(
                    f"Proxy {proxy.url} здоровий, час відповіді: {response_time:.2f}s"
                )
                return True
            else:
                logger.warning(
                    f" Proxy {proxy.url} повернув статус {response.status_code}"
                )
                return False

        except Exception as e:
            proxy.stats.is_healthy = False
            proxy.stats.consecutive_failures += 1
            proxy.stats.last_check = datetime.now()
            logger.warning(f" Health check failed for {proxy.url}: {str(e)}")

            if (
                self._auto_remove_failed
                and proxy.stats.consecutive_failures >= self._max_consecutive_failures
            ):
                logger.error(
                    f" Видалення proxy {proxy.url} після "
                    f"{proxy.stats.consecutive_failures} невдалих спроб"
                )
                self.remove_proxy(proxy.url)

            return False

    def check_all_proxies_health(self) -> Dict[str, bool]:
        """
        Перевіряє здоров'я всіх proxy в пулі.

        Returns:
            Словник {url: is_healthy}
        """
        results = {}
        with self._lock:
            proxies_to_check = self._proxies.copy()

        for proxy in proxies_to_check:
            is_healthy = self.check_proxy_health(proxy)
            results[proxy.url] = is_healthy

        healthy_count = sum(1 for v in results.values() if v)
        logger.info(
            f" Health check завершено: {healthy_count}/{len(results)} proxy здорові"
        )
        return results

    def record_request_result(
        self, proxy: Proxy, success: bool, response_time: Optional[float] = None
    ):
        """
        Записує результат використання proxy.

        Args:
            proxy: Використаний proxy
            success: Чи був запит успішним
            response_time: Час відповіді в секундах
        """
        with self._lock:
            proxy.stats.total_requests += 1
            if success:
                proxy.stats.successful_requests += 1
                proxy.stats.consecutive_failures = 0
                if response_time is not None:
                    proxy.stats.total_response_time += response_time
            else:
                proxy.stats.failed_requests += 1
                proxy.stats.consecutive_failures += 1

                if (
                    self._auto_remove_failed
                    and proxy.stats.consecutive_failures
                    >= self._max_consecutive_failures
                ):
                    logger.error(
                        f" Видалення proxy {proxy.url} після "
                        f"{proxy.stats.consecutive_failures} невдалих запитів"
                    )
                    self.remove_proxy(proxy.url)

    def get_statistics(self) -> Dict[str, Any]:
        """
        Повертає детальну статистику пулу proxy.

        Returns:
            Словник з статистикою
        """
        with self._lock:
            if not self._proxies:
                return {
                    "total_proxies": 0,
                    "healthy_proxies": 0,
                    "unhealthy_proxies": 0,
                    "proxies": [],
                }

            healthy = sum(1 for p in self._proxies if p.stats.is_healthy)
            total_requests = sum(p.stats.total_requests for p in self._proxies)
            successful_requests = sum(
                p.stats.successful_requests for p in self._proxies
            )

            return {
                "total_proxies": len(self._proxies),
                "healthy_proxies": healthy,
                "unhealthy_proxies": len(self._proxies) - healthy,
                "total_requests": total_requests,
                "successful_requests": successful_requests,
                "failed_requests": total_requests - successful_requests,
                "overall_success_rate": (
                    (successful_requests / total_requests * 100)
                    if total_requests > 0
                    else 0.0
                ),
                "rotation_strategy": self._rotation_strategy.value,
                "uptime_seconds": (datetime.now() - self._start_time).total_seconds(),
                "proxies": [p.to_dict() for p in self._proxies],
            }

    def get_summary(self) -> str:
        """
        Повертає текстовий summary статистики.

        Returns:
            Відформатований текстовий звіт
        """
        stats = self.get_statistics()

        summary = f"""
 Proxy Pool Manager Summary

Proxies: {stats['total_proxies']} total
   Healthy: {stats['healthy_proxies']}
   Unhealthy: {stats['unhealthy_proxies']}

Requests: {stats['total_requests']} total
   Successful: {stats['successful_requests']}
   Failed: {stats['failed_requests']}
   Success Rate: {stats['overall_success_rate']:.1f}%

Rotation Strategy: {stats['rotation_strategy']}
Uptime: {stats['uptime_seconds']:.0f}s

Proxy Details:
"""
        for i, proxy_dict in enumerate(stats["proxies"], 1):
            proxy_stats = proxy_dict["stats"]
            summary += f"""
  {i}. {proxy_dict['url']}
     Type: {proxy_dict['proxy_type']}
     Status: {'Healthy' if proxy_stats['is_healthy'] else ' Unhealthy'}
     Requests: {proxy_stats['total_requests']} (Success: {proxy_stats['successful_requests']}, Failed: {proxy_stats['failed_requests']})
     Success Rate: {proxy_stats['success_rate']:.1f}%
     Avg Response Time: {proxy_stats['average_response_time_ms']:.0f}ms
     Consecutive Failures: {proxy_stats['consecutive_failures']}
"""

        return summary

    def __len__(self) -> int:
        """Повертає кількість proxy в пулі."""
        return len(self._proxies)

    def __repr__(self) -> str:
        return (
            f"ProxyPoolManager(proxies={len(self._proxies)}, "
            f"strategy={self._rotation_strategy.value})"
        )


def create_proxy_manager(
    proxy_urls: List[str],
    rotation_strategy: RotationStrategy = RotationStrategy.ROUND_ROBIN,
    check_health: bool = True,
) -> ProxyPoolManager:
    """
    Factory функція для швидкого створення ProxyPoolManager.

    Args:
        proxy_urls: Список URL proxy серверів
        rotation_strategy: Стратегія ротації
        check_health: Чи перевіряти здоров'я при додаванні

    Returns:
        ProxyPoolManager з додан proxy

    Example:
        >>> manager = create_proxy_manager(
        ...     proxy_urls=[
        ...         "http://proxy1.example.com:8080",
        ...         "http://proxy2.example.com:8080"
        ...     ],
        ...     rotation_strategy=RotationStrategy.RANDOM
        ... )
    """
    manager = ProxyPoolManager(rotation_strategy=rotation_strategy)

    for url in proxy_urls:
        manager.add_proxy(url, check_health=check_health)

    return manager
