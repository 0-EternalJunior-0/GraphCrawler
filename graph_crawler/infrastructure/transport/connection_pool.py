"""
Connection Pool Manager для HTTP з'єднань.

Features:
- Використовує aiohttp для async операцій
- aiohttp.TCPConnector для connection pooling
- Всі методи async
- Async context manager support
- Оптимізований менеджер connection pool для прискорення краулінгу
- Переіспользування з'єднань замість створення нових на кожен запит
- Підтримка до 100 одночасних з'єднань
- Retry стратегія з exponential backoff
- Моніторинг статистики pool
"""

import asyncio
import logging
import time
from typing import Any, Dict, Optional

import aiohttp

from graph_crawler.shared.constants import (
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_USER_AGENT,
    HTTP_RETRYABLE_STATUS_CODES,
)

logger = logging.getLogger(__name__)


class ConnectionPoolManager:
    """
    Async менеджер connection pool для оптимізації HTTP запитів .

    Використовує aiohttp.TCPConnector для async connection pooling.

    Переваги:
    -  Швидкість: Async I/O без блокування
    -  Retry: Автоматичні повтори з asyncio.sleep()
    -  Моніторинг: Статистика використання pool
    -  Масштабування: До 100 одночасних з'єднань

    Приклад:
        >>> async with ConnectionPoolManager(pool_size=100) as manager:
        ...     response = await manager.get("https://example.com")
        ...     stats = manager.get_statistics()
        ...     print(f"Total requests: {stats['total_requests']}")
    """

    def __init__(
        self,
        pool_size: int = 100,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
        timeout: int = DEFAULT_REQUEST_TIMEOUT,
        user_agent: str = DEFAULT_USER_AGENT,
        **kwargs,
    ):
        """
        Ініціалізує Connection Pool Manager.

        Args:
            pool_size: Розмір connection pool (default: 100)
            max_retries: Максимальна кількість повторів (default: 3)
            backoff_factor: Множник для exponential backoff (default: 0.5)
            timeout: Timeout для запитів в секундах (default: 30)
            user_agent: User-Agent header (default: з constants)
            **kwargs: Додаткові параметри
        """
        self.pool_size = pool_size
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.timeout = timeout
        self.user_agent = user_agent

        # Статистика
        self._lock = asyncio.Lock()
        self._stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "retry_attempts": 0,
            "active_connections": 0,
            "pool_size": pool_size,
            "created_at": time.time(),
        }

        # aiohttp components (створюються в init())
        self._connector: Optional[aiohttp.TCPConnector] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._initialized = False

        logger.info(
            f"ConnectionPoolManager initialized (async): "
            f"pool_size={pool_size}, max_retries={max_retries}, "
            f"timeout={timeout}s"
        )

    async def init(self) -> None:
        """
        Async ініціалізація session та connector.

        Викликати перед використанням:
            manager = ConnectionPoolManager()
            await manager.init()
        """
        if self._initialized:
            return

        # TCP Connector з connection pooling
        self._connector = aiohttp.TCPConnector(
            limit=self.pool_size,
            limit_per_host=self.pool_size // 2,
            ttl_dns_cache=300,
            enable_cleanup_closed=True,
        )

        # Default headers
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
        }

        # Client session з timeout
        timeout_config = aiohttp.ClientTimeout(total=self.timeout)
        self._session = aiohttp.ClientSession(
            connector=self._connector,
            headers=headers,
            timeout=timeout_config,
        )

        self._initialized = True
        logger.debug("ConnectionPoolManager session created (async)")

    async def request(
        self, method: str, url: str, timeout: Optional[int] = None, **kwargs
    ) -> aiohttp.ClientResponse:
        """
        Async виконує HTTP запит через connection pool.

        Args:
            method: HTTP метод (GET, POST, etc.)
            url: URL для запиту
            timeout: Timeout в секундах (default: з конфігурації)
            **kwargs: Додаткові параметри для request

        Returns:
            aiohttp.ClientResponse об'єкт

        Raises:
            aiohttp.ClientError: При помилках запиту
        """
        if not self._initialized:
            await self.init()

        request_timeout = aiohttp.ClientTimeout(total=timeout or self.timeout)

        # Оновлення статистики
        async with self._lock:
            self._stats["total_requests"] += 1
            self._stats["active_connections"] += 1

        last_exception = None
        current_delay = self.backoff_factor

        for attempt in range(1, self.max_retries + 1):
            try:
                response = await self._session.request(
                    method=method, url=url, timeout=request_timeout, **kwargs
                )

                # Перевіряємо статус для retry
                if (
                    response.status in HTTP_RETRYABLE_STATUS_CODES
                    and attempt < self.max_retries
                ):
                    async with self._lock:
                        self._stats["retry_attempts"] += 1
                    logger.warning(
                        f"Status {response.status} for {url}, retrying ({attempt}/{self.max_retries})"
                    )
                    await asyncio.sleep(current_delay)
                    current_delay *= 2
                    continue

                # Успішний запит
                async with self._lock:
                    self._stats["successful_requests"] += 1
                    self._stats["active_connections"] -= 1

                return response

            except aiohttp.ClientError as e:
                last_exception = e

                if attempt < self.max_retries:
                    async with self._lock:
                        self._stats["retry_attempts"] += 1
                    logger.warning(
                        f"Request failed ({attempt}/{self.max_retries}): {url}, error: {e}"
                    )
                    await asyncio.sleep(current_delay)
                    current_delay *= 2
                else:
                    # Всі спроби вичерпано
                    async with self._lock:
                        self._stats["failed_requests"] += 1
                        self._stats["active_connections"] -= 1

                    logger.error(
                        f" Request failed after {self.max_retries} attempts: {url}"
                    )
                    raise

        # Якщо дійшли сюди - піднімаємо останній exception
        if last_exception:
            async with self._lock:
                self._stats["failed_requests"] += 1
                self._stats["active_connections"] -= 1
            raise last_exception

    async def get(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """Async виконує GET запит."""
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """Async виконує POST запит."""
        return await self.request("POST", url, **kwargs)

    async def fetch_text(self, url: str, **kwargs) -> str:
        """
        Async завантажує текст зі сторінки.

        Args:
            url: URL для завантаження
            **kwargs: Додаткові параметри

        Returns:
            Текст відповіді
        """
        response = await self.get(url, **kwargs)
        return await response.text()

    async def fetch_json(self, url: str, **kwargs) -> Any:
        """
        Async завантажує JSON зі сторінки.

        Args:
            url: URL для завантаження
            **kwargs: Додаткові параметри

        Returns:
            Розпарсений JSON
        """
        response = await self.get(url, **kwargs)
        return await response.json()

    def get_statistics(self) -> Dict[str, Any]:
        """
        Повертає статистику використання connection pool.

        Returns:
            Словник з метриками
        """
        stats = self._stats.copy()

        # Додаткові розрахунки
        total = stats["total_requests"]
        if total > 0:
            stats["success_rate"] = (stats["successful_requests"] / total) * 100
        else:
            stats["success_rate"] = 0.0

        stats["uptime"] = time.time() - stats["created_at"]

        return stats

    def reset_statistics(self):
        """Скидає статистику."""
        created_at = self._stats["created_at"]
        pool_size = self._stats["pool_size"]

        self._stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "retry_attempts": 0,
            "active_connections": 0,
            "pool_size": pool_size,
            "created_at": created_at,
        }

        logger.info(" Statistics reset")

    def get_summary(self) -> str:
        """
        Повертає текстовий summary статистики.

        Returns:
            Форматований текст з статистикою
        """
        stats = self.get_statistics()

        summary = f"""

   Async Connection Pool Statistics

 Pool Size:          {stats['pool_size']:>6}
 Total Requests:     {stats['total_requests']:>6}
 Successful:         {stats['successful_requests']:>6} ({stats['success_rate']:>5.1f}%)
 Failed:             {stats['failed_requests']:>6}
 Retry Attempts:     {stats['retry_attempts']:>6}
 Active Connections: {stats['active_connections']:>6}
 Uptime:             {stats['uptime']:>6.1f}s

        """.strip()

        return summary

    async def close(self) -> None:
        """Async закриває session та звільняє ресурси."""
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None
        if self._connector and not self._connector.closed:
            await self._connector.close()
        self._connector = None
        # Даємо час на закриття з'єднань
        await asyncio.sleep(0.25)
        self._initialized = False
        logger.debug("ConnectionPoolManager closed (async)")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.init()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
        return False

    def __repr__(self) -> str:
        return (
            f"ConnectionPoolManager(pool_size={self.pool_size}, "
            f"max_retries={self.max_retries}, timeout={self.timeout}s, async=True)"
        )
