# graph_crawler/infrastructure/transport/async_http/plugins/autothrottle.py
"""
Async AutoThrottle Plugin — адаптивне обмеження швидкості на основі затримки відповіді.

Реалізує Scrapy-сумісний алгоритм throttling для async HTTP транспорту.

Architecture Decision: ADR-2026-001
Technical Design: TDD-2026-001
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from graph_crawler.infrastructure.transport.async_http.context import AsyncHTTPContext
from graph_crawler.infrastructure.transport.async_http.stages import AsyncHTTPStage
from graph_crawler.infrastructure.transport.base_plugin import BaseDriverPlugin
from graph_crawler.infrastructure.transport.context import EventPriority

logger = logging.getLogger(__name__)

__all__ = ["AsyncAutoThrottlePlugin", "DomainSlot", "AutoThrottleConfig"]


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass(frozen=True)
class AutoThrottleConfig:
    """
    Незмінна конфігурація для AutoThrottle плагіна.
    
    Attributes:
        start_delay: Початкова затримка для нових доменів (секунди)
        max_delay: Верхня межа для затримки
        min_delay: Нижня межа (floor) для затримки
        target_concurrency: Цільова кількість паралельних запитів на домен
        debug: Детальне логування кожного запиту
        error_backoff_factor: Множник для затримки при помилках
    """
    start_delay: float = 5.0
    max_delay: float = 60.0
    min_delay: float = 0.0
    target_concurrency: float = 1.0
    debug: bool = False
    error_backoff_factor: float = 1.5
    
    def __post_init__(self):
        if self.target_concurrency <= 0:
            raise ValueError(f"target_concurrency must be > 0, got {self.target_concurrency}")
        if self.min_delay > self.max_delay:
            raise ValueError(f"min_delay ({self.min_delay}) > max_delay ({self.max_delay})")
        if self.start_delay < self.min_delay or self.start_delay > self.max_delay:
            raise ValueError(
                f"start_delay ({self.start_delay}) must be in "
                f"[{self.min_delay}, {self.max_delay}]"
            )
    
    @classmethod
    def conservative(cls) -> "AutoThrottleConfig":
        """Профіль для чутливих цілей."""
        return cls(
            start_delay=10.0,
            max_delay=120.0,
            min_delay=5.0,
            target_concurrency=0.5
        )
    
    @classmethod
    def balanced(cls) -> "AutoThrottleConfig":
        """Профіль для загального краулінгу."""
        return cls(
            start_delay=5.0,
            max_delay=60.0,
            min_delay=0.5,
            target_concurrency=1.0
        )
    
    @classmethod
    def aggressive(cls) -> "AutoThrottleConfig":
        """Профіль для високопродуктивних серверів."""
        return cls(
            start_delay=1.0,
            max_delay=30.0,
            min_delay=0.0,
            target_concurrency=4.0
        )


# =============================================================================
# DOMAIN SLOT
# =============================================================================

@dataclass
class DomainSlot:
    """
    Контейнер стану для per-domain throttling.
    
    Кожен домен має ізольований слот з незалежним відстеженням затримки.
    Thread-safe доступ керується lock-ом батьківського плагіна.
    """
    domain: str
    delay: float = 5.0
    last_request_time: float = field(default_factory=time.time)
    
    # Метрики
    active_requests: int = 0
    total_requests: int = 0
    total_latency: float = 0.0
    error_count: int = 0
    success_count: int = 0
    throttle_adjustments: int = 0
    
    # Відстеження
    min_latency_observed: float = float("inf")
    max_latency_observed: float = 0.0
    
    @property
    def avg_latency(self) -> float:
        """Середня затримка відповіді."""
        return self.total_latency / self.total_requests if self.total_requests > 0 else 0.0
    
    @property
    def error_rate(self) -> float:
        """Співвідношення помилок до загальної кількості запитів."""
        return self.error_count / self.total_requests if self.total_requests > 0 else 0.0
    
    @property
    def effective_throughput(self) -> float:
        """Оцінка запитів за секунду на основі поточної затримки."""
        return 1.0 / self.delay if self.delay > 0 else float("inf")
    
    def to_dict(self) -> Dict[str, Any]:
        """Експорт метрик як словник."""
        return {
            "domain": self.domain,
            "delay_ms": round(self.delay * 1000, 2),
            "active_requests": self.active_requests,
            "total_requests": self.total_requests,
            "avg_latency_ms": round(self.avg_latency * 1000, 2),
            "min_latency_ms": round(self.min_latency_observed * 1000, 2) 
                if self.min_latency_observed != float("inf") else None,
            "max_latency_ms": round(self.max_latency_observed * 1000, 2),
            "error_count": self.error_count,
            "error_rate": round(self.error_rate * 100, 2),
            "throttle_adjustments": self.throttle_adjustments,
            "effective_rps": round(self.effective_throughput, 3)
        }


# =============================================================================
# MAIN PLUGIN
# =============================================================================

class AsyncAutoThrottlePlugin(BaseDriverPlugin):
    """
    Плагін адаптивного обмеження швидкості на основі затримки відповіді.
    
    Реалізує алгоритм Scrapy AutoThrottle для async HTTP запитів:
    1. Вимірює затримку відповіді для кожного запиту
    2. Обчислює цільову затримку: latency / target_concurrency
    3. Застосовує експоненційне згладжування з поточною затримкою
    4. Забезпечує обмеження та захист від помилок
    
    Приклади:
        >>> plugin = AsyncAutoThrottlePlugin(AutoThrottleConfig.balanced())
        >>> async with AsyncDriver(plugins=[plugin]) as driver:
        ...     await driver.fetch_many(urls)
        ...     print(plugin.get_stats())
    
    Профілі конфігурації:
        - AutoThrottleConfig.conservative(): Для чутливих цілей
        - AutoThrottleConfig.balanced(): Загальне використання
        - AutoThrottleConfig.aggressive(): Високопродуктивні сервери
    
    Lifecycle Hooks:
        - PREPARING_REQUEST: Застосовує затримку перед запитом
        - RESPONSE_RECEIVED: Коригує затримку на основі latency
        - REQUEST_FAILED: Збільшує затримку при помилках
    
    Thread Safety:
        Всі операції зі слотами захищені asyncio.Lock.
        Безпечно для паралельного використання з fetch_many().
    """
    
    # Ключі контексту для метаданих запиту
    CTX_START_TIME = "autothrottle_start_time"
    CTX_DOMAIN = "autothrottle_domain"
    CTX_SKIP_ADJUST = "autothrottle_dont_adjust_delay"
    
    def __init__(
        self,
        config: Optional[AutoThrottleConfig | Dict[str, Any]] = None,
        priority: int = EventPriority.HIGH,
    ):
        """
        Ініціалізація AutoThrottle плагіна.
        
        Args:
            config: AutoThrottleConfig або dict з параметрами
            priority: Пріоритет виконання плагіна (рекомендовано HIGH)
        """
        # Обробка dict та dataclass конфігурації
        if config is None:
            throttle_config = AutoThrottleConfig()
        elif isinstance(config, AutoThrottleConfig):
            throttle_config = config
        else:
            throttle_config = AutoThrottleConfig(**config)
        
        # Конвертація dataclass у dict для батьківського класу
        config_dict = asdict(throttle_config)
        
        super().__init__(config=config_dict, priority=priority)
        
        # Зберігаємо типізовану конфігурацію окремо
        self._throttle_config = throttle_config
        
        # Стан
        self._slots: Dict[str, DomainSlot] = {}
        self._lock = asyncio.Lock()
        self._initialized = True
        
        logger.info(
            "AsyncAutoThrottlePlugin initialized: start_delay=%ss, "
            "target_concurrency=%s, bounds=[%ss, %ss]",
            self._throttle_config.start_delay,
            self._throttle_config.target_concurrency,
            self._throttle_config.min_delay,
            self._throttle_config.max_delay,
        )
    
    @property
    def name(self) -> str:
        return "async_autothrottle"
    
    def get_hooks(self) -> List[str]:
        return [
            AsyncHTTPStage.PREPARING_REQUEST,
            AsyncHTTPStage.RESPONSE_RECEIVED,
            AsyncHTTPStage.REQUEST_FAILED,
        ]
    
    # -------------------------------------------------------------------------
    # КЕРУВАННЯ ДОМЕНАМИ ТА СЛОТАМИ
    # -------------------------------------------------------------------------
    
    @staticmethod
    def _extract_domain(url: str) -> str:
        """Витягує домен з URL для пошуку слота."""
        parsed = urlparse(url)
        return parsed.netloc or parsed.path.split("/")[0] or url
    
    async def _get_or_create_slot(self, domain: str) -> DomainSlot:
        """Отримує існуючий слот або створює новий (thread-safe)."""
        async with self._lock:
            if domain not in self._slots:
                self._slots[domain] = DomainSlot(
                    domain=domain,
                    delay=self._throttle_config.start_delay,
                )
                logger.debug("[AutoThrottle] Created slot for domain: %s", domain)
            return self._slots[domain]
    
    # -------------------------------------------------------------------------
    # ОСНОВНИЙ АЛГОРИТМ
    # -------------------------------------------------------------------------
    
    def _calculate_new_delay(
        self,
        slot: DomainSlot,
        latency: float,
        status_code: int,
    ) -> Tuple[float, bool]:
        """
        Обчислює нове значення затримки.
        
        Returns:
            Tuple з (нова_затримка, чи_оновлювати)
        """
        # Цільова затримка на основі latency та concurrency
        target_delay = latency / self._throttle_config.target_concurrency
        
        # Експоненційне згладжування
        smoothed_delay = (slot.delay + target_delay) / 2.0
        
        # Асиметрична відповідь: швидке сповільнення, поступове прискорення
        new_delay = max(target_delay, smoothed_delay)
        
        # Застосування меж
        new_delay = max(
            self._throttle_config.min_delay,
            min(new_delay, self._throttle_config.max_delay),
        )
        
        # Захист від помилок: не зменшувати затримку при non-2xx
        is_success = 200 <= status_code < 300
        if not is_success and new_delay < slot.delay:
            return (slot.delay, False)
        
        return (new_delay, True)
    
    # -------------------------------------------------------------------------
    # LIFECYCLE HOOKS
    # -------------------------------------------------------------------------
    
    async def on_preparing_request(self, ctx: AsyncHTTPContext) -> AsyncHTTPContext:
        """
        Застосовує throttling затримку перед відправкою запиту.
        
        Цей hook:
        1. Знаходить слот домену
        2. Обчислює необхідний час очікування
        3. Резервує слот (оновлює last_request_time) ДО sleep
        4. Засипає якщо потрібно
        5. Записує метадані запиту
        
        ВАЖЛИВО: last_request_time оновлюється ДО sleep, щоб наступні
        coroutines бачили правильний час і чекали свою чергу.
        """
        domain = self._extract_domain(ctx.url)
        slot = await self._get_or_create_slot(domain)
        
        # Обчислюємо час очікування та РЕЗЕРВУЄМО слот атомарно
        wait_time = 0.0
        
        async with self._lock:
            now = time.time()
            time_since_last = now - slot.last_request_time
            wait_time = slot.delay - time_since_last
            
            # КРИТИЧНО: Оновлюємо last_request_time ЗАРАЗ, щоб наступні
            # coroutines бачили що цей слот зайнятий і чекали свою чергу
            if wait_time > 0:
                # Резервуємо час коли цей запит БУДЕ виконаний
                slot.last_request_time = now + wait_time
            else:
                # Запит йде одразу
                slot.last_request_time = now
            
            slot.active_requests += 1
        
        # Sleep ПОЗА lock щоб дозволити іншим coroutine обчислювати свій wait_time
        if wait_time > 0:
            if self._throttle_config.debug:
                logger.debug(
                    "[AutoThrottle][%s] Waiting %.3fs (delay=%.3fs)",
                    domain,
                    wait_time,
                    slot.delay,
                )
            await asyncio.sleep(wait_time)
        
        # Зберігаємо метадані для обробки відповіді
        ctx.data[self.CTX_START_TIME] = time.time()
        ctx.data[self.CTX_DOMAIN] = domain
        
        return ctx
    
    async def on_response_received(self, ctx: AsyncHTTPContext) -> AsyncHTTPContext:
        """
        Коригує затримку на основі latency відповіді.
        
        Цей hook:
        1. Обчислює фактичну latency
        2. Застосовує алгоритм throttling
        3. Оновлює затримку слота
        4. Записує метрики
        """
        domain = ctx.data.get(self.CTX_DOMAIN)
        start_time = ctx.data.get(self.CTX_START_TIME)
        
        if not domain or start_time is None:
            return ctx
        
        latency = time.time() - start_time
        status_code = ctx.status_code or 0
        
        slot = await self._get_or_create_slot(domain)
        
        async with self._lock:
            # Оновлюємо лічильники
            slot.active_requests = max(0, slot.active_requests - 1)
            slot.total_requests += 1
            slot.total_latency += latency
            slot.min_latency_observed = min(slot.min_latency_observed, latency)
            slot.max_latency_observed = max(slot.max_latency_observed, latency)
            
            if 200 <= status_code < 300:
                slot.success_count += 1
            
            # Перевірка opt-out
            if ctx.data.get(self.CTX_SKIP_ADJUST, False):
                return ctx
            
            # Обчислюємо та застосовуємо нову затримку
            old_delay = slot.delay
            new_delay, should_update = self._calculate_new_delay(
                slot, latency, status_code,
            )
            
            if should_update:
                slot.delay = new_delay
                slot.throttle_adjustments += 1
                
                if self._throttle_config.debug:
                    delta = new_delay - old_delay
                    logger.info(
                        "[AutoThrottle][%s] delay: %.0fms (%+.0f) | "
                        "latency: %.0fms | active: %d | status: %d",
                        domain,
                        new_delay * 1000,
                        delta * 1000,
                        latency * 1000,
                        slot.active_requests,
                        status_code,
                    )
        
        return ctx
    
    async def on_request_failed(self, ctx: AsyncHTTPContext) -> AsyncHTTPContext:
        """
        Обробляє невдалі запити збільшенням затримки.
        
        Застосовує backoff factor до поточної затримки при помилках.
        """
        domain = ctx.data.get(self.CTX_DOMAIN)
        
        if not domain:
            return ctx
        
        slot = await self._get_or_create_slot(domain)
        
        async with self._lock:
            slot.active_requests = max(0, slot.active_requests - 1)
            slot.error_count += 1
            slot.total_requests += 1
            
            old_delay = slot.delay
            new_delay = min(
                slot.delay * self._throttle_config.error_backoff_factor,
                self._throttle_config.max_delay,
            )
            slot.delay = new_delay
            slot.throttle_adjustments += 1
            
            if self._throttle_config.debug:
                logger.warning(
                    "[AutoThrottle][%s] Request failed, delay: %.0fms -> %.0fms "
                    "(error #%d)",
                    domain,
                    old_delay * 1000,
                    new_delay * 1000,
                    slot.error_count,
                )
        
        return ctx
    
    # -------------------------------------------------------------------------
    # ПУБЛІЧНИЙ API
    # -------------------------------------------------------------------------
    
    def get_stats(self) -> Dict[str, Dict[str, Any]]:
        """Отримати статистику для всіх доменів."""
        return {
            domain: slot.to_dict()
            for domain, slot in self._slots.items()
        }
    
    def get_slot_delay(self, domain: str) -> Optional[float]:
        """Отримати поточну затримку для конкретного домену."""
        slot = self._slots.get(domain)
        return slot.delay if slot else None
    
    async def reset(self, domain: Optional[str] = None) -> None:
        """Скинути стан throttle для домену(ів)."""
        async with self._lock:
            if domain:
                if domain in self._slots:
                    self._slots[domain] = DomainSlot(
                        domain=domain,
                        delay=self._throttle_config.start_delay,
                    )
                    logger.info("[AutoThrottle] Reset slot: %s", domain)
            else:
                self._slots.clear()
                logger.info("[AutoThrottle] Reset all slots")
    
    def __repr__(self) -> str:
        return (
            f"AsyncAutoThrottlePlugin("
            f"start_delay={self._throttle_config.start_delay}, "
            f"target_concurrency={self._throttle_config.target_concurrency}, "
            f"domains={len(self._slots)})"
        )
