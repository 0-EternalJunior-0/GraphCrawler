"""
Simple User-Agent Rotation Module.

Ця версія використовує fake-useragent бібліотеку напряму
без надмірної кастомізації.
"""

import logging
import random
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    from fake_useragent import UserAgent
except ImportError:
    raise ImportError(
        "fake-useragent is required for UserAgentRotator. "
        "Install it with: pip install fake-useragent>=2.2.0"
    )

logger = logging.getLogger(__name__)


@dataclass
class UserAgentStats:
    """Статистика використання User-Agent"""

    total_requests: int = 0
    unique_user_agents: set = field(default_factory=set)
    last_used: Optional[str] = None
    started_at: datetime = field(default_factory=datetime.now)


class UserAgentRotator:
    """
    User-Agent Rotator використовуючи fake-useragent.

    Спрощена версія. Економія ~250 рядків коду порівняно з повною версією.
    Використовує fake-useragent API напряму для максимальної простоти.

    Args:
        browsers: Список браузерів для ротації (опціонально)
        rotation_strategy: Стратегія ("random", "round_robin", "weighted")
        fallback: Fallback User-Agent якщо бібліотека не працює

    Example:
        >>> rotator = UserAgentRotator()
        >>> ua = rotator.get_random()
        >>>
        >>> # З конкретним браузером
        >>> ua = rotator.get_chrome()
        >>>
        >>> # Round-robin
        >>> rotator = UserAgentRotator(rotation_strategy="round_robin")
        >>> ua = rotator.get_next()  # Чергує браузери
    """

    def __init__(
        self,
        browsers: Optional[List[str]] = None,
        rotation_strategy: str = "random",
        fallback: Optional[str] = None,
    ):
        """Ініціалізує UserAgentRotator"""
        self.browsers = browsers or ["chrome", "firefox", "safari", "edge"]
        self.rotation_strategy = rotation_strategy

        # Fallback User-Agent
        self.fallback = fallback or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        # Ініціалізація fake-useragent
        try:
            self.ua = UserAgent(fallback=self.fallback)
            logger.info(" UserAgentRotator ініціалізовано")
        except Exception as e:
            logger.warning(f" Помилка fake-useragent: {e}. Використовую fallback.")
            self.ua = None

        # Статистика
        self.stats = UserAgentStats()

        # Round-robin state
        self._round_robin_index = 0
        self._lock = threading.Lock()

    def get_random(self) -> str:
        """
        Отримати випадковий User-Agent.

        Returns:
            str: Випадковий User-Agent
        """
        try:
            if self.ua is None:
                ua_string = self.fallback
            else:
                ua_string = self.ua.random

            self._update_stats(ua_string)
            return ua_string

        except Exception as e:
            logger.warning(f" Помилка: {e}. Використовую fallback.")
            self._update_stats(self.fallback)
            return self.fallback

    def get_chrome(self) -> str:
        """Отримати Chrome User-Agent"""
        return self._get_browser_ua("chrome")

    def get_firefox(self) -> str:
        """Отримати Firefox User-Agent"""
        return self._get_browser_ua("firefox")

    def get_safari(self) -> str:
        """Отримати Safari User-Agent"""
        return self._get_browser_ua("safari")

    def get_edge(self) -> str:
        """Отримати Edge User-Agent"""
        return self._get_browser_ua("edge")

    def _get_browser_ua(self, browser: str) -> str:
        """Внутрішній метод для отримання UA конкретного браузера"""
        try:
            if self.ua is None:
                return self.fallback

            if hasattr(self.ua, browser):
                ua_string = getattr(self.ua, browser)
            else:
                ua_string = self.ua.random

            self._update_stats(ua_string)
            return ua_string

        except Exception as e:
            logger.warning(f" Помилка браузера {browser}: {e}")
            self._update_stats(self.fallback)
            return self.fallback

    def get_next(self) -> str:
        """
        Отримати наступний User-Agent згідно стратегії.

        Returns:
            str: User-Agent рядок
        """
        if self.rotation_strategy == "random":
            return self.get_random()

        elif self.rotation_strategy == "round_robin":
            return self._get_round_robin()

        elif self.rotation_strategy == "weighted":
            return self._get_weighted()

        else:
            return self.get_random()

    def _get_round_robin(self) -> str:
        """Round-robin вибір User-Agent"""
        with self._lock:
            browser = self.browsers[self._round_robin_index]
            self._round_robin_index = (self._round_robin_index + 1) % len(self.browsers)

        return self._get_browser_ua(browser)

    def _get_weighted(self) -> str:
        """Weighted вибір на основі популярності браузерів (2024)"""
        weights = {
            "chrome": 65,  # Chrome найпопулярніший
            "safari": 20,  # Safari другий
            "edge": 8,  # Edge третій
            "firefox": 5,  # Firefox четвертий
            "opera": 2,  # Opera п'ятий
        }

        available_browsers = [b for b in self.browsers if b in weights]
        browser_weights = [weights.get(b, 1) for b in available_browsers]

        browser = random.choices(available_browsers, weights=browser_weights, k=1)[0]
        return self._get_browser_ua(browser)

    def _update_stats(self, ua_string: str):
        """Оновити статистику"""
        with self._lock:
            self.stats.total_requests += 1
            self.stats.unique_user_agents.add(ua_string)
            self.stats.last_used = ua_string

    def get_statistics(self) -> Dict[str, Any]:
        """
        Отримати статистику використання.

        Returns:
            Dict: Словник зі статистикою
        """
        with self._lock:
            uptime = (datetime.now() - self.stats.started_at).total_seconds()

            return {
                "total_requests": self.stats.total_requests,
                "unique_user_agents": len(self.stats.unique_user_agents),
                "last_used": self.stats.last_used,
                "uptime_seconds": uptime,
                "requests_per_second": (
                    self.stats.total_requests / uptime if uptime > 0 else 0
                ),
            }

    def get_summary(self) -> str:
        """Текстовий summary статистики"""
        stats = self.get_statistics()

        return f"""
 User-Agent Rotator Summary
{'=' * 50}

 Statistics:
  - Total requests: {stats['total_requests']}
  - Unique UAs: {stats['unique_user_agents']}
  - Rate: {stats['requests_per_second']:.2f} req/sec
  - Uptime: {stats['uptime_seconds']:.1f}s

 Last Used:
  {stats['last_used'][:80] if stats['last_used'] else 'None'}...

 Configuration:
  - Strategy: {self.rotation_strategy}
  - Browsers: {', '.join(self.browsers)}
"""

    def reset_statistics(self):
        """Скинути статистику"""
        with self._lock:
            self.stats = UserAgentStats()
            logger.info(" Статистика скинута")


def create_rotator(
    browsers: Optional[List[str]] = None, strategy: str = "random"
) -> UserAgentRotator:
    """
    Factory функція для швидкого створення rotator.

    Args:
        browsers: Список браузерів
        strategy: Стратегія ротації

    Returns:
        UserAgentRotator

    Example:
        >>> rotator = create_rotator(browsers=["chrome", "firefox"])
        >>> ua = rotator.get_random()
    """
    return UserAgentRotator(browsers=browsers, rotation_strategy=strategy)
