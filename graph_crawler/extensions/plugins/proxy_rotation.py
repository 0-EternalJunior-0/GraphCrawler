"""Плагін для ротації проксі."""

import random
from typing import Any, Dict, List

from graph_crawler.extensions.plugins.base import BasePlugin, PluginContext, PluginType


class ProxyRotationPlugin(BasePlugin):
    """
    Плагін для автоматичної ротації проксі-серверів.

    Змінює проксі перед кожним запитом.

    Конфіг:
        proxy_list: List[str] - список проксі
        strategy: str - 'random' або 'round_robin'
    """

    def __init__(self, config: Dict[str, Any] = None):
        """Ініціалізує ProxyRotationPlugin."""
        super().__init__(config)
        self.proxy_list: List[str] = config.get("proxy_list", [])
        self.strategy = config.get("strategy", "random")
        self.current_index = 0

    @property
    def plugin_type(self) -> PluginType:
        return PluginType.PRE_REQUEST

    @property
    def name(self) -> str:
        return "proxy_rotation"

    def execute(self, context: PluginContext) -> PluginContext:
        """
        Вибирає та встановлює проксі.

        docs: Реалізувати:
        - Вибір проксі за стратегією
        - Встановлення в driver конфіг
        - Перевірка роботоздатності проксі
        """
        if not self.proxy_list:
            return context

        # Вибір проксі
        if self.strategy == "random":
            proxy = random.choice(self.proxy_list)
        else:  # round_robin
            proxy = self.proxy_list[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.proxy_list)

        # Зберігаємо в context
        context.plugin_data["current_proxy"] = proxy

        return context
