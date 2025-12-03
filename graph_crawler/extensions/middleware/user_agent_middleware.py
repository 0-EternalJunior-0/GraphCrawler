"""User-Agent Rotation Middleware - ротація User-Agent для імітації різних браузерів.

Містить базу 50+ реальних User-Agent рядків з різних браузерів та платформ.
"""

import logging
import random
from typing import List, Optional

from graph_crawler.extensions.middleware.base import (
    BaseMiddleware,
    MiddlewareContext,
    MiddlewareType,
)

logger = logging.getLogger(__name__)

# База реальних User-Agent рядків (50+ варіантів)
USER_AGENTS_DATABASE = [
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # Chrome on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # Chrome on Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:119.0) Gecko/20100101 Firefox/119.0",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    # Firefox on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13.5; rv:121.0) Gecko/20100101 Firefox/121.0",
    # Firefox on Linux
    "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
    # Safari on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    # Safari on iOS
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    # Edge on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    # Opera on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 OPR/105.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 OPR/104.0.0.0",
    # Opera on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 OPR/105.0.0.0",
    # Chrome on Android
    "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.144 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.144 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.144 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36",
    # Firefox on Android
    "Mozilla/5.0 (Android 14; Mobile; rv:121.0) Gecko/121.0 Firefox/121.0",
    "Mozilla/5.0 (Android 13; Mobile; rv:120.0) Gecko/120.0 Firefox/120.0",
    # Samsung Internet
    "Mozilla/5.0 (Linux; Android 14; SAMSUNG SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/23.0 Chrome/115.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SAMSUNG SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/22.0 Chrome/111.0.0.0 Mobile Safari/537.36",
    # Brave on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Brave/120.0.0.0",
    # Vivaldi on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Vivaldi/6.5.3206.55",
    # Chrome on ChromeOS
    "Mozilla/5.0 (X11; CrOS x86_64 15359.58.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # Yandex Browser
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 YaBrowser/24.1.0.0 Safari/537.36",
    # UC Browser
    "Mozilla/5.0 (Linux; U; Android 13; en-US; SM-G991B Build/TP1A.220624.014) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/100.0.4896.127 UCBrowser/13.4.0.1306 Mobile Safari/537.36",
    # Older but still common versions
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:115.0) Gecko/20100101 Firefox/115.0",
]


class UserAgentMiddleware(BaseMiddleware):
    """
    Middleware для ротації User-Agent.

    Імітує різні браузери та платформи для обходу простих систем детекції ботів.
    Містить базу 50+ реальних User-Agent рядків.

    Конфігурація:
        strategy: Стратегія вибору UA (default: "random")
            - "random": Випадковий вибір при кожному запиті
            - "round_robin": По черзі
            - "sequential": Послідовний (для тестування)
            - "sticky": Один UA для всіх запитів (вибирається випадково при ініціалізації)

        user_agents: Власний список User-Agent (опціонально)
            Якщо не вказано - використовується вбудована база

        weights: Ваги для різних категорій браузерів (опціонально)
            Дозволяє налаштувати розподіл UA за типами браузерів

    Приклади конфігурації:

    1. Базове використання (випадкова ротація):
        config = {
            "strategy": "random"
        }

    2. З власними User-Agents:
        config = {
            "strategy": "random",
            "user_agents": [
                "Mozilla/5.0...",
                "Mozilla/5.0...",
            ]
        }

    3. Sticky mode (один UA для всієї сесії):
        config = {
            "strategy": "sticky"
        }

    4. Round-robin (по черзі):
        config = {
            "strategy": "round_robin"
        }
    """

    def __init__(self, config: dict = None):
        super().__init__(config)
        self.user_agents: List[str] = []
        self.strategy = "random"
        self.current_index = 0
        self.sticky_ua: Optional[str] = None
        self.usage_stats = {}  # Статистика використання UA

    @property
    def middleware_type(self) -> MiddlewareType:
        return MiddlewareType.PRE_REQUEST

    @property
    def name(self) -> str:
        return "user_agent"

    def setup(self):
        """Ініціалізує список User-Agents та стратегію."""
        # Отримуємо список UA (власний або дефолтний)
        custom_user_agents = self.config.get("user_agents")
        if custom_user_agents:
            self.user_agents = custom_user_agents
            logger.info(f"Using {len(self.user_agents)} custom User-Agents")
        else:
            self.user_agents = USER_AGENTS_DATABASE.copy()
            logger.info(f"Using {len(self.user_agents)} built-in User-Agents")

        # Перевіряємо що список не пустий
        if not self.user_agents:
            raise ValueError("User-Agent list is empty")

        # Отримуємо стратегію
        self.strategy = self.config.get("strategy", "random")

        # Для sticky mode - вибираємо один UA при ініціалізації
        if self.strategy == "sticky":
            self.sticky_ua = random.choice(self.user_agents)
            logger.info(f"Sticky mode: using fixed User-Agent")

        logger.info(f"User-Agent rotation initialized: strategy={self.strategy}")

    def _get_next_user_agent(self) -> str:
        """
        Вибирає наступний User-Agent згідно стратегії.

        Returns:
            User-Agent рядок
        """
        if self.strategy == "sticky":
            # Sticky mode - завжди той самий UA
            return self.sticky_ua

        elif self.strategy == "round_robin":
            # Round-robin - по черзі
            ua = self.user_agents[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.user_agents)
            return ua

        elif self.strategy == "sequential":
            # Sequential - послідовно (не loop)
            if self.current_index < len(self.user_agents):
                ua = self.user_agents[self.current_index]
                self.current_index += 1
                return ua
            else:
                # Якщо закінчились - повертаємось до початку
                self.current_index = 0
                return self.user_agents[0]

        else:  # default: "random"
            # Random - випадковий вибір
            return random.choice(self.user_agents)

    def process(self, context: MiddlewareContext) -> MiddlewareContext:
        """
        Встановлює User-Agent для запиту.

        Args:
            context: Контекст запиту

        Returns:
            Оновлений контекст з новим User-Agent
        """
        # Отримуємо старий UA (якщо був)
        old_user_agent = context.headers.get("User-Agent")

        # Вибираємо новий User-Agent
        user_agent = self._get_next_user_agent()

        # Встановлюємо в headers
        context.headers["User-Agent"] = user_agent

        # Оновлюємо статистику
        if user_agent not in self.usage_stats:
            self.usage_stats[user_agent] = 0
        self.usage_stats[user_agent] += 1

        # Додаємо метадані
        context.metadata["user_agent"] = {
            "value": user_agent,
            "strategy": self.strategy,
            "usage_count": self.usage_stats[user_agent],
        }

        # Публікуємо подію про ротацію UA (якщо є event_bus)
        if self.event_bus:
            from graph_crawler.domain.events.events import CrawlerEvent, EventType

            self.event_bus.publish(
                CrawlerEvent.create(
                    EventType.USER_AGENT_ROTATED,
                    data={
                        "url": context.url,
                        "old_user_agent": old_user_agent,
                        "new_user_agent": user_agent,
                        "strategy": self.strategy,
                        "usage_count": self.usage_stats[user_agent],
                        "total_user_agents": len(self.user_agents),
                    },
                )
            )

        from graph_crawler.shared.constants import UA_DISPLAY_LENGTH

        logger.debug(f"Set User-Agent: {user_agent[:UA_DISPLAY_LENGTH]}...")

        return context

    def get_stats(self) -> dict:
        """
        Повертає статистику використання User-Agents.

        Returns:
            Словник зі статистикою
        """
        total_requests = sum(self.usage_stats.values())

        # Топ найбільш використаних UA
        from graph_crawler.shared.constants import UA_DISPLAY_LENGTH, UA_TOP_COUNT

        top_user_agents = sorted(
            self.usage_stats.items(), key=lambda x: x[1], reverse=True
        )[:UA_TOP_COUNT]

        return {
            "total_user_agents": len(self.user_agents),
            "strategy": self.strategy,
            "total_requests": total_requests,
            "unique_used": len(self.usage_stats),
            "top_user_agents": [
                {"ua": ua[:UA_DISPLAY_LENGTH] + "...", "count": count}
                for ua, count in top_user_agents
            ],
        }

    def reset_stats(self):
        """Скидає статистику використання."""
        self.usage_stats.clear()
        self.current_index = 0
        if self.strategy == "sticky":
            # Вибираємо новий sticky UA
            self.sticky_ua = random.choice(self.user_agents)
