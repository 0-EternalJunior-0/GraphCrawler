"""Cache Middleware - кешування відповідей . Використовує aiofiles для async file I/O."""

import asyncio
import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Optional

from graph_crawler.extensions.middleware.base import (
    BaseMiddleware,
    MiddlewareContext,
    MiddlewareType,
)
from graph_crawler.shared.constants import DEFAULT_CACHE_TTL, HTTP_OK

try:
    import aiofiles
    import aiofiles.os

    AIOFILES_AVAILABLE = True
except ImportError:
    AIOFILES_AVAILABLE = False

logger = logging.getLogger(__name__)


class CacheMiddleware(BaseMiddleware):
    """
    Middleware для кешування HTTP відповідей у файлову систему.

    Конфіг:
        ttl: Time-to-live для кешу в секундах (default: 3600 = 1 година)
        cache_dir: Директорія для збереження кешу (default: /tmp/graph_crawler_cache)
        enabled: Увімкнути кеш (default: True)
    """

    def __init__(self, config: dict = None):
        super().__init__(config)
        self.cache_dir = Path(self.config.get("cache_dir", "/tmp/graph_crawler_cache"))
        self.ttl = self.config.get("ttl", DEFAULT_CACHE_TTL)
        self.enabled = self.config.get("enabled", True)
        self.setup()

    @property
    def middleware_type(self) -> MiddlewareType:
        return MiddlewareType.PRE_REQUEST

    @property
    def name(self) -> str:
        return "cache"

    def setup(self):
        """Створює директорію для кешу."""
        if self.enabled:
            try:
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                logger.debug(f"Cache directory created: {self.cache_dir}")
            except Exception as e:
                logger.error(f"Failed to create cache directory: {e}")
                self.enabled = False

    def _get_cache_path(self, url: str) -> Path:
        """Генерує шлях до файлу кешу на основі URL."""
        # Хешуємо URL для використання як ім'я файлу
        url_hash = hashlib.md5(url.encode()).hexdigest()
        return self.cache_dir / f"{url_hash}.json"

    def _is_cache_valid(self, cache_path: Path) -> bool:
        """Перевіряє чи кеш ще валідний (не застарів)."""
        if not cache_path.exists():
            return False

        # Перевіряємо час модифікації
        mtime = cache_path.stat().st_mtime
        age = time.time() - mtime

        return age < self.ttl

    async def _load_from_cache_async(self, url: str) -> Optional[dict]:
        """Async завантажує відповідь з кешу ."""
        cache_path = self._get_cache_path(url)

        if not self._is_cache_valid(cache_path):
            return None

        try:
            if AIOFILES_AVAILABLE:
                async with aiofiles.open(cache_path, "r", encoding="utf-8") as f:
                    content = await f.read()
                data = json.loads(content)
            else:
                # Fallback до sync
                with open(cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            logger.debug(f"Cache HIT: {url}")
            return data
        except Exception as e:
            logger.warning(f"Failed to load cache for {url}: {e}")
            return None

    async def _save_to_cache_async(self, url: str, response: dict):
        """Async зберігає відповідь у кеш ."""
        cache_path = self._get_cache_path(url)

        try:
            if AIOFILES_AVAILABLE:
                async with aiofiles.open(cache_path, "w", encoding="utf-8") as f:
                    await f.write(json.dumps(response, ensure_ascii=False))
            else:
                # Fallback до sync
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(response, f, ensure_ascii=False)
            logger.debug(f"Cached: {url}")
        except Exception as e:
            logger.warning(f"Failed to save cache for {url}: {e}")

    def _load_from_cache(self, url: str) -> Optional[dict]:
        """Sync завантажує відповідь з кешу (legacy)."""
        cache_path = self._get_cache_path(url)

        if not self._is_cache_valid(cache_path):
            return None

        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            logger.debug(f"Cache HIT: {url}")
            return data
        except Exception as e:
            logger.warning(f"Failed to load cache for {url}: {e}")
            return None

    def _save_to_cache(self, url: str, response: dict):
        """Sync зберігає відповідь у кеш (legacy)."""
        cache_path = self._get_cache_path(url)

        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(response, f, ensure_ascii=False)
            logger.debug(f"Cached: {url}")
        except Exception as e:
            logger.warning(f"Failed to save cache for {url}: {e}")

    async def process(self, context: MiddlewareContext) -> MiddlewareContext:
        """
        Async перевіряє кеш перед запитом .

        Якщо є валідний кеш - встановлює skip_request і додає відповідь.
        Використовує aiofiles для async file I/O якщо доступний.

        Args:
            context: Контекст запиту

        Returns:
            Оновлений контекст
        """
        if not self.enabled:
            return context

        url = context.url

        # Async перевіряємо кеш
        cached_response = await self._load_from_cache_async(url)

        if cached_response:
            # Кеш знайдено - пропускаємо запит
            context.skip_request = True
            context.response = cached_response
            context.middleware_data["cache"] = {"hit": True}
        else:
            # Кеш не знайдено
            context.middleware_data["cache"] = {"hit": False}

        return context

    async def process_response_async(self, response: dict, **kwargs) -> dict:
        """
        Async зберігає відповідь у кеш після запиту .

        Args:
            response: Відповідь від драйвера
            **kwargs: Додаткові параметри

        Returns:
            Відповідь без змін
        """
        if not self.enabled:
            return response

        url = response.get("url")

        # Зберігаємо тільки успішні відповіді
        if url and response.get("status_code") == HTTP_OK and not response.get("error"):
            await self._save_to_cache_async(url, response)

        return response
