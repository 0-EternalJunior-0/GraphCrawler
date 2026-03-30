"""
HTTP Cache плагін для Async HTTP драйвера.

Реалізує кешування на рівні HTTP з підтримкою:
- ETag / If-None-Match
- Last-Modified / If-Modified-Since
- 304 Not Modified response handling

Мета: Зменшення трафіку при масштабному краулінгу (100k+ сторінок).
При 304 Not Modified сервер повертає тільки headers (~500 bytes) замість
повного контенту (~100KB), що економить до 99% трафіку для незмінених сторінок.

Приклад використання:
    from graph_crawler.infrastructure.transport.async_http.plugins.http_cache import AsyncHTTPCachePlugin
    
    cache = AsyncHTTPCachePlugin(AsyncHTTPCachePlugin.create_config(
        enabled=True,
        max_cache_size=10000,  # Макс. 10k записів
        respect_cache_headers=True,
    ))
    
    driver = AsyncDriver(plugins=[cache])
"""

import hashlib
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from graph_crawler.infrastructure.transport.async_http.context import AsyncHTTPContext
from graph_crawler.infrastructure.transport.async_http.stages import AsyncHTTPStage
from graph_crawler.infrastructure.transport.base_plugin import BaseDriverPlugin

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Запис кешу для одного URL."""
    
    url: str
    etag: Optional[str] = None
    last_modified: Optional[str] = None
    content_hash: Optional[str] = None
    html: Optional[str] = None  # Кешований контент (опціонально)
    headers: Dict[str, str] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    hits: int = 0
    
    def is_fresh(self, max_age: int) -> bool:
        """Перевіряє чи кеш ще свіжий."""
        return (time.time() - self.created_at) < max_age


class LRUCache:
    """LRU кеш з обмеженням розміру для HTTP cache entries."""
    
    def __init__(self, max_size: int = 10000):
        self._max_size = max_size
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "304_responses": 0,
        }
    
    def get(self, url: str) -> Optional[CacheEntry]:
        """Отримує запис з кешу (LRU: переміщує в кінець)."""
        if url in self._cache:
            self._cache.move_to_end(url)
            self._stats["hits"] += 1
            entry = self._cache[url]
            entry.hits += 1
            return entry
        self._stats["misses"] += 1
        return None
    
    def set(self, url: str, entry: CacheEntry) -> None:
        """Зберігає запис в кеш (з LRU eviction)."""
        if url in self._cache:
            self._cache.move_to_end(url)
        else:
            if len(self._cache) >= self._max_size:
                # LRU eviction - видаляємо найстаріший запис
                self._cache.popitem(last=False)
                self._stats["evictions"] += 1
        self._cache[url] = entry
    
    def record_304(self) -> None:
        """Записує 304 Not Modified response."""
        self._stats["304_responses"] += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Повертає статистику кешу."""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = (self._stats["hits"] / total * 100) if total > 0 else 0
        return {
            **self._stats,
            "size": len(self._cache),
            "max_size": self._max_size,
            "hit_rate_percent": round(hit_rate, 2),
        }
    
    def clear(self) -> None:
        """Очищує кеш."""
        self._cache.clear()


class AsyncHTTPCachePlugin(BaseDriverPlugin):
    """
    Async плагін для HTTP кешування з підтримкою ETag та Last-Modified.
    
    Як це працює:
    1. При ПЕРШОМУ запиті - зберігаємо ETag та Last-Modified з response headers
    2. При ПОВТОРНОМУ запиті - додаємо If-None-Match та If-Modified-Since headers
    3. Якщо сервер повертає 304 - використовуємо кешований контент
    
    Економія трафіку:
    - Звичайна сторінка: ~100KB
    - 304 Not Modified: ~500 bytes
    - Економія: до 99% для незмінених сторінок
    
    Для краулінгу 100k сайтів по 800-4500 сторінок:
    - Без кешу: 100k * 4500 * 100KB = ~42TB
    - З кешем (50% 304): ~21TB економії
    
    Конфігурація:
        enabled: Увімкнути/вимкнути кешування (default: True)
        max_cache_size: Максимальний розмір кешу в записах (default: 10000)
        store_content: Зберігати HTML контент в кеші (default: False, економить RAM)
        max_age_seconds: Максимальний вік кешу в секундах (default: 3600)
        respect_cache_headers: Поважати Cache-Control headers сервера (default: True)
    
    Приклад:
        plugin = AsyncHTTPCachePlugin(AsyncHTTPCachePlugin.create_config(
            enabled=True,
            max_cache_size=50000,  # Для великих краулінгів
            store_content=False,   # Економимо RAM
        ))
    """

    @property
    def name(self) -> str:
        return "async_http_cache"

    def get_hooks(self) -> List[str]:
        return [
            AsyncHTTPStage.PREPARING_REQUEST,
            AsyncHTTPStage.RESPONSE_RECEIVED,
        ]

    @staticmethod
    def create_config(
        enabled: bool = True,
        max_cache_size: int = 10000,
        store_content: bool = False,
        max_age_seconds: int = 3600,
        respect_cache_headers: bool = True,
    ) -> Dict[str, Any]:
        """
        Створює конфігурацію для HTTP Cache плагіна.
        
        Args:
            enabled: Увімкнути кешування
            max_cache_size: Максимальний розмір LRU кешу
            store_content: Чи зберігати HTML контент (RAM intensive)
            max_age_seconds: Максимальний час життя кешу
            respect_cache_headers: Поважати Cache-Control headers
            
        Returns:
            Словник конфігурації
        """
        return {
            "enabled": enabled,
            "max_cache_size": max_cache_size,
            "store_content": store_content,
            "max_age_seconds": max_age_seconds,
            "respect_cache_headers": respect_cache_headers,
        }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Ініціалізує HTTP Cache плагін."""
        super().__init__(config)
        
        self._enabled = self.config.get("enabled", True)
        max_size = self.config.get("max_cache_size", 10000)
        self._cache = LRUCache(max_size=max_size)
        self._store_content = self.config.get("store_content", False)
        self._max_age = self.config.get("max_age_seconds", 3600)
        self._respect_cache_headers = self.config.get("respect_cache_headers", True)
        
        if self._enabled:
            logger.info(
                "HTTP Cache plugin initialized: max_size=%d, store_content=%s, max_age=%ds",
                max_size, self._store_content, self._max_age
            )

    async def on_preparing_request(self, ctx: AsyncHTTPContext) -> AsyncHTTPContext:
        """
        Додає conditional headers (If-None-Match, If-Modified-Since) перед запитом.
        
        Якщо URL вже є в кеші - додаємо headers для conditional request.
        Це дозволяє серверу повернути 304 Not Modified замість повного контенту.
        """
        if not self._enabled:
            return ctx
            
        cache_entry = self._cache.get(ctx.url)
        if cache_entry is None:
            return ctx
            
        # Перевіряємо чи кеш ще свіжий
        if not cache_entry.is_fresh(self._max_age):
            return ctx
        
        # Додаємо conditional headers
        if cache_entry.etag:
            ctx.headers["If-None-Match"] = cache_entry.etag
            logger.debug("Added If-None-Match: %s for %s", cache_entry.etag[:20], ctx.url)
            
        if cache_entry.last_modified:
            ctx.headers["If-Modified-Since"] = cache_entry.last_modified
            logger.debug("Added If-Modified-Since: %s for %s", cache_entry.last_modified, ctx.url)
        
        # Зберігаємо cache entry в контексті для використання в response handler
        ctx.data["_cache_entry"] = cache_entry
        
        return ctx

    async def on_response_received(self, ctx: AsyncHTTPContext) -> AsyncHTTPContext:
        """
        Обробляє відповідь сервера - кешує або використовує кешовані дані.
        
        При 304 Not Modified:
        - Використовуємо кешований контент (якщо store_content=True)
        - Оновлюємо статистику
        - Встановлюємо ctx.data["cache_hit"] = True
        
        При 200 OK:
        - Зберігаємо ETag та Last-Modified в кеш
        - Оновлюємо кешований контент (якщо store_content=True)
        """
        if not self._enabled:
            return ctx
            
        # Обробка 304 Not Modified
        if ctx.status_code == 304:
            self._cache.record_304()
            ctx.data["cache_hit"] = True
            ctx.data["cache_304"] = True
            
            cache_entry = ctx.data.get("_cache_entry")
            if cache_entry and self._store_content and cache_entry.html:
                # Використовуємо кешований контент
                ctx.html = cache_entry.html
                logger.debug("304 Not Modified - using cached content for %s", ctx.url)
            else:
                logger.debug("304 Not Modified for %s (no cached content)", ctx.url)
            
            return ctx
        
        # Кешуємо нову відповідь при 200 OK
        if ctx.status_code == 200:
            etag = ctx.response_headers.get("ETag") or ctx.response_headers.get("etag")
            last_modified = (
                ctx.response_headers.get("Last-Modified") 
                or ctx.response_headers.get("last-modified")
            )
            
            # Зберігаємо в кеш тільки якщо є ETag або Last-Modified
            if etag or last_modified:
                # Обчислюємо hash контенту для додаткової перевірки
                content_hash = None
                if ctx.html:
                    content_hash = hashlib.md5(ctx.html.encode()).hexdigest()
                
                entry = CacheEntry(
                    url=ctx.url,
                    etag=etag,
                    last_modified=last_modified,
                    content_hash=content_hash,
                    html=ctx.html if self._store_content else None,
                    headers=dict(ctx.response_headers),
                )
                
                self._cache.set(ctx.url, entry)
                ctx.data["cache_stored"] = True
                
                logger.debug(
                    "Cached response for %s: etag=%s, last_modified=%s",
                    ctx.url,
                    etag[:20] if etag else None,
                    last_modified
                )
        
        return ctx

    def get_stats(self) -> Dict[str, Any]:
        """Повертає статистику кешу."""
        return self._cache.get_stats()
    
    def clear_cache(self) -> None:
        """Очищує кеш."""
        self._cache.clear()
        logger.info("HTTP cache cleared")

    async def teardown(self) -> None:
        """Cleanup при закритті драйвера."""
        stats = self.get_stats()
        logger.info(
            "HTTP Cache stats: hits=%d, misses=%d, 304_responses=%d, hit_rate=%.1f%%",
            stats["hits"], stats["misses"], stats["304_responses"], stats["hit_rate_percent"]
        )
