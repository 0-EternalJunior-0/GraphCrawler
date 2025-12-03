"""Менеджер плагінів для драйверів.

Відповідає за:
- Реєстрацію плагінів
- Виклик хуків на етапах драйвера
- Підписку плагінів на події інших плагінів
- Обробку помилок плагінів
- Пріоритизацію виконання
"""

import asyncio
import logging
import time
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional

from graph_crawler.infrastructure.transport.base_plugin import BaseDriverPlugin
from graph_crawler.infrastructure.transport.context import DriverContext

logger = logging.getLogger(__name__)


class DriverPluginManager:
    """
    Менеджер плагінів для драйвера.

    Координує виконання плагінів на різних етапах роботи драйвера.

    Приклад:
        manager = DriverPluginManager(is_async=True)
        manager.register(StealthPlugin())
        manager.register(CaptchaSolverPlugin())

        # Виконання хуків
        ctx = await manager.execute_hook('navigation_completed', ctx)
    """

    def __init__(self, is_async: bool = False):
        """
        Ініціалізація менеджера.

        Args:
            is_async: Чи плагіни асинхронні (залежить від драйвера)
        """
        self.is_async = is_async
        self.plugins: List[BaseDriverPlugin] = []

        # Індексація плагінів по хукам для швидкого доступу
        self.hook_plugins: Dict[str, List[BaseDriverPlugin]] = defaultdict(list)

        # Індексація плагінів по подіям
        self.event_plugins: Dict[str, List[BaseDriverPlugin]] = defaultdict(list)

        logger.info(f"DriverPluginManager initialized (async={is_async})")

    def register(self, plugin: BaseDriverPlugin):
        """
        Реєструє плагін у менеджері.

        Args:
            plugin: Екземпляр плагіна для реєстрації
        """
        if not plugin.enabled:
            logger.debug(f"Plugin '{plugin.name}' is disabled, skipping registration")
            return

        # Додаємо в загальний список
        self.plugins.append(plugin)

        # Індексуємо по хукам - отримуємо value якщо це Enum
        for hook in plugin.get_hooks():
            hook_name = hook.value if hasattr(hook, "value") else str(hook)
            self.hook_plugins[hook_name].append(plugin)

        # Індексуємо по подіях
        for event in plugin.get_events():
            event_name = event.value if hasattr(event, "value") else str(event)
            self.event_plugins[event_name].append(plugin)

        # Сортуємо плагіни по пріоритету (менше число = вищий пріоритет)
        for hook_name in self.hook_plugins:
            self.hook_plugins[hook_name].sort(key=lambda p: p.priority)

        for event_name in self.event_plugins:
            self.event_plugins[event_name].sort(key=lambda p: p.priority)

        # Виконуємо setup
        try:
            plugin.setup()
            logger.info(f"Plugin '{plugin.name}' registered successfully")
        except Exception as e:
            logger.error(f"Error in plugin '{plugin.name}' setup: {e}")
            plugin.enabled = False

    def setup_event_subscriptions(self, context: DriverContext):
        """
        Налаштовує підписки плагінів на події через контекст.

        Викликається перед виконанням запиту.

        Args:
            context: Контекст драйвера
        """
        for event_name, plugins in self.event_plugins.items():
            for plugin in plugins:
                if not plugin.enabled:
                    continue

                # Створюємо handler для події
                handler_name = f"on_{event_name}"
                if hasattr(plugin, handler_name):
                    handler = getattr(plugin, handler_name)
                    context.subscribe(event_name, handler)
                    logger.debug(
                        f"Plugin '{plugin.name}' subscribed to event '{event_name}'"
                    )

    def execute_hook(self, hook_name: str, context: DriverContext) -> DriverContext:
        """
        Виконує всі плагіни для вказаного хуку (синхронна версія).

        Args:
            hook_name: Назва хуку (етапу) - може бути Enum або string
            context: Контекст драйвера

        Returns:
            Оновлений контекст
        """
        # Конвертуємо Enum в string якщо потрібно
        hook_key = hook_name.value if hasattr(hook_name, "value") else str(hook_name)
        plugins = self.hook_plugins.get(hook_key, [])

        if not plugins:
            return context

        logger.debug(f"Executing hook '{hook_key}' with {len(plugins)} plugin(s)")

        for plugin in plugins:
            if not plugin.enabled:
                continue

            if context.cancelled:
                logger.info(
                    f"Execution cancelled, skipping remaining plugins for '{hook_key}'"
                )
                break

            # Перевіряємо наявність handler методу
            handler_name = f"on_{hook_key}"
            if not hasattr(plugin, handler_name):
                logger.warning(
                    f"Plugin '{plugin.name}' has no handler for '{hook_key}'"
                )
                continue

            handler = getattr(plugin, handler_name)

            try:
                start_time = time.time()
                context = handler(context)
                duration = time.time() - start_time

                plugin._record_execution(duration)
                logger.debug(
                    f"Plugin '{plugin.name}' executed '{hook_key}' in {duration:.3f}s"
                )

            except Exception as e:
                logger.error(
                    f"Error in plugin '{plugin.name}' on hook '{hook_key}': {e}",
                    exc_info=True,
                )
                context.errors.append(e)
                plugin._record_execution(0, error=True)

                # Публікуємо подію про помилку
                context.emit(
                    "plugin_error", plugin_name=plugin.name, hook=hook_key, error=str(e)
                )

        return context

    async def execute_hook_async(
        self, hook_name: str, context: DriverContext
    ) -> DriverContext:
        """
        Виконує всі плагіни для вказаного хуку (асинхронна версія).

        Args:
            hook_name: Назва хуку (етапу) - може бути Enum або string
            context: Контекст драйвера

        Returns:
            Оновлений контекст
        """
        # Конвертуємо Enum в string якщо потрібно
        hook_key = hook_name.value if hasattr(hook_name, "value") else str(hook_name)
        plugins = self.hook_plugins.get(hook_key, [])

        if not plugins:
            return context

        logger.debug(f"Executing async hook '{hook_key}' with {len(plugins)} plugin(s)")

        for plugin in plugins:
            if not plugin.enabled:
                continue

            if context.cancelled:
                logger.info(
                    f"Execution cancelled, skipping remaining plugins for '{hook_key}'"
                )
                break

            # Перевіряємо наявність handler методу
            handler_name = f"on_{hook_key}"
            if not hasattr(plugin, handler_name):
                logger.warning(
                    f"Plugin '{plugin.name}' has no handler for '{hook_key}'"
                )
                continue

            handler = getattr(plugin, handler_name)

            try:
                start_time = time.time()

                # Викликаємо async handler
                if asyncio.iscoroutinefunction(handler):
                    context = await handler(context)
                else:
                    # Fallback для sync методів в async контексті
                    context = handler(context)

                duration = time.time() - start_time

                plugin._record_execution(duration)
                logger.debug(
                    f"Plugin '{plugin.name}' executed '{hook_key}' in {duration:.3f}s"
                )

            except Exception as e:
                logger.error(
                    f"Error in plugin '{plugin.name}' on hook '{hook_key}': {e}",
                    exc_info=True,
                )
                context.errors.append(e)
                plugin._record_execution(0, error=True)

                # Публікуємо подію про помилку
                context.emit(
                    "plugin_error", plugin_name=plugin.name, hook=hook_key, error=str(e)
                )

        return context

    def get_plugin_by_name(self, name: str) -> Optional[BaseDriverPlugin]:
        """
        Знаходить плагін за назвою.

        Args:
            name: Назва плагіна

        Returns:
            Екземпляр плагіна або None
        """
        for plugin in self.plugins:
            if plugin.name == name:
                return plugin
        return None

    def get_stats(self) -> Dict[str, Any]:
        """
        Повертає статистику по всіх плагінах.

        Returns:
            Словник зі статистикою
        """
        return {
            "total_plugins": len(self.plugins),
            "enabled_plugins": sum(1 for p in self.plugins if p.enabled),
            "is_async": self.is_async,
            "plugins": [p.get_stats() for p in self.plugins],
        }

    def teardown_all(self):
        """Виконує teardown для всіх плагінів."""
        logger.info("Tearing down all plugins...")

        for plugin in self.plugins:
            try:
                plugin.teardown()
            except Exception as e:
                logger.error(f"Error in plugin '{plugin.name}' teardown: {e}")

        logger.info("All plugins torn down")

    async def teardown_all_async(self):
        """Async виконує teardown для всіх плагінів."""
        logger.info("Tearing down all plugins (async)...")

        for plugin in self.plugins:
            try:
                if hasattr(plugin, "teardown_async") and asyncio.iscoroutinefunction(
                    plugin.teardown_async
                ):
                    await plugin.teardown_async()
                else:
                    plugin.teardown()
            except Exception as e:
                logger.error(f"Error in plugin '{plugin.name}' teardown: {e}")

        logger.info("All plugins torn down")

    def __repr__(self):
        return (
            f"DriverPluginManager(plugins={len(self.plugins)}, async={self.is_async})"
        )
