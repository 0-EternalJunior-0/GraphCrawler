"""RAM-адаптивний плагін для Playwright драйверів.

Моніторить системну RAM через psutil і між батчами адаптує
кількість паралельних fetch-операцій.

Режими вимірювання
------------------
percent_mode=True  (за замовчуванням)
    ratio = psutil.virtual_memory().percent / 100
    Thresholds — це відсотки завантаження всієї системи.
    upper_threshold=0.85 означає "зменшити якщо система вже використовує > 85% RAM".
    Не залежить від обсягу RAM машини → безпечний дефолт для будь-якого сервера.

percent_mode=False
    ratio = used_gb / ram_limit_gb
    Класичний режим: явно задається бюджет у GB.
    УВАГА: ram_limit_gb має бути більший за фонове споживання ОС+процесів.
"""

import asyncio
import logging
from typing import List, Optional

from graph_crawler.infrastructure.transport.base_plugin import BaseDriverPlugin
from graph_crawler.infrastructure.transport.playwright.context import BrowserContext
from graph_crawler.infrastructure.transport.playwright.stages import BrowserStage

logger = logging.getLogger(__name__)


class RamAdaptivePlugin(BaseDriverPlugin):
    """
    Адаптує паралельність fetch-операцій залежно від поточного споживання RAM.

    Підписується на:
    - CONTENT_READY     — вимірює RAM після кожної сторінки
    - BEFORE_FETCH_MANY — аналізує виміри й пише suggested_concurrent в ctx.data

    Працює з PlaywrightDriver і PooledPlaywrightDriver без змін у логіці плагіна.

    Args:
        upper_threshold: Зменшити concurrent якщо тиск перевищує це значення.
                         percent_mode=True → частка 0–1 (напр. 0.85 = 85% RAM зайнято).
                         percent_mode=False → частка від ram_limit_gb.
        lower_threshold: Збільшити concurrent якщо тиск нижче цього значення.
        ram_limit_gb:    Бюджет RAM (тільки при percent_mode=False).
        percent_mode:    True — використовувати % завантаження системи (рекомендовано).
    """

    def __init__(
        self,
        upper_threshold: float = 0.85,
        lower_threshold: float = 0.70,
        min_concurrent: int = 1,
        max_concurrent: int = 32,
        ram_limit_gb: float = 3.0,
        percent_mode: bool = True,
    ):
        super().__init__()
        self._upper = upper_threshold
        self._lower = lower_threshold
        self._min = min_concurrent
        self._max = max_concurrent
        self._current = max_concurrent
        self._ram_limit_gb = ram_limit_gb
        self._percent_mode = percent_mode
        self._samples: list[float] = []
        self._lock: Optional[asyncio.Lock] = None
        self._psutil = None
        self._adaptations = 0
        self._last_ratio = 0.0

    @property
    def name(self) -> str:
        return "ram_adaptive"

    def get_hooks(self) -> List[str]:
        return [BrowserStage.CONTENT_READY, BrowserStage.BEFORE_FETCH_MANY]

    def setup(self):
        try:
            import psutil
            self._psutil = psutil
        except ImportError:
            logger.warning("psutil not found — RamAdaptivePlugin disabled")
            self.enabled = False
            return
        self._lock = asyncio.Lock()
        mode = "percent" if self._percent_mode else f"absolute (limit={self._ram_limit_gb}GB)"
        logger.info("[RamAdaptive] mode=%s upper=%.0f%% lower=%.0f%%",
                    mode, self._upper * 100, self._lower * 100)
        super().setup()

    def _measure_ratio(self) -> float:
        """Повертає поточний рівень тиску RAM як число 0.0–1.0+."""
        if self._percent_mode:
            return self._psutil.virtual_memory().percent / 100.0
        return self._psutil.virtual_memory().used / (1024 ** 3) / self._ram_limit_gb

    def _adapt(self, current: int, ratio: float) -> int:
        if ratio > self._upper:
            return max(self._min, current - 1)
        if ratio < self._lower and current < self._max:
            return min(self._max, current + 1)
        return current

    async def on_content_ready(self, ctx: BrowserContext) -> BrowserContext:
        sample = self._measure_ratio()
        async with self._lock:
            self._samples.append(sample)
        return ctx

    async def on_before_fetch_many(self, ctx: BrowserContext) -> BrowserContext:
        async with self._lock:
            if not self._samples:
                return ctx
            avg_ratio = sum(self._samples) / len(self._samples)
            self._samples.clear()

        self._last_ratio = avg_ratio
        new_concurrent = self._adapt(self._current, avg_ratio)

        if new_concurrent != self._current:
            self._adaptations += 1
            logger.info(
                "[RamAdaptive] pressure=%.0f%% (upper=%.0f%%), concurrent: %d→%d",
                avg_ratio * 100, self._upper * 100, self._current, new_concurrent,
            )
            self._current = new_concurrent

        ctx.data["suggested_concurrent"] = self._current
        ctx.data["ram_pressure"] = (
            "high" if avg_ratio > self._upper else
            "low" if avg_ratio < self._lower else "ok"
        )
        ctx.data["ram_ratio"] = round(avg_ratio, 3)
        return ctx

    def teardown(self):
        self._samples.clear()
        self._psutil = None
        super().teardown()

    def get_stats(self) -> dict:
        base = super().get_stats()
        base.update({
            "current_concurrent": self._current,
            "adaptations": self._adaptations,
            "last_pressure_pct": round(self._last_ratio * 100, 1),
            "percent_mode": self._percent_mode,
            "upper_threshold_pct": self._upper * 100,
            "lower_threshold_pct": self._lower * 100,
        })
        return base
