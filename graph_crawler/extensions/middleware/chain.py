"""Middleware Chain - ланцюжок обробки ."""

import asyncio
import inspect
from typing import Dict, List

from graph_crawler.extensions.middleware.base import (
    BaseMiddleware,
    MiddlewareContext,
    MiddlewareType,
)


class MiddlewareChain:
    """
    Ланцюжок обробки middleware .

    Виконує middleware послідовно, кожен отримує context від попереднього.
    Підтримує як sync, так і async middleware.

    Переваги:
    - Гнучка обробка request/response
    - Легко додавати/видаляти middleware
    - Композиція функціональності
    - Логування, Retry, Cache як middleware
    - Async-first з fallback на sync

    Приклад:
        chain = MiddlewareChain()
        chain.add(LoggingMiddleware())
        chain.add(RetryMiddleware())
        chain.add(CacheMiddleware())

        context = MiddlewareContext(url="https://example.com")
        result = await chain.execute(MiddlewareType.PRE_REQUEST, context)
    """

    def __init__(self):
        self.middlewares: Dict[MiddlewareType, List[BaseMiddleware]] = {
            middleware_type: [] for middleware_type in MiddlewareType
        }

    def add(self, middleware: BaseMiddleware):
        """
        Додає middleware до ланцюжка.

        Args:
            middleware: Екземпляр middleware
        """
        if middleware.enabled:
            self.middlewares[middleware.middleware_type].append(middleware)
            # setup() може бути async або sync
            setup_result = middleware.setup()
            if asyncio.iscoroutine(setup_result):
                # Створюємо task для async setup (буде виконано пізніше)
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.create_task(setup_result)
                    else:
                        loop.run_until_complete(setup_result)
                except RuntimeError:
                    # Якщо немає event loop - просто пропускаємо
                    pass

    def remove(self, middleware_name: str):
        """
        Видаляє middleware за назвою.

        Args:
            middleware_name: Назва middleware
        """
        for middleware_type, middlewares_list in self.middlewares.items():
            self.middlewares[middleware_type] = [
                m for m in middlewares_list if m.name != middleware_name
            ]

    async def execute(
        self, middleware_type: MiddlewareType, context: MiddlewareContext
    ) -> MiddlewareContext:
        """
        Async виконує всі middleware вказаного типу .

        Middleware виконуються послідовно, кожен отримує context від попереднього.
        Підтримує як async, так і sync middleware.process().

        Args:
            middleware_type: Тип middleware для виконання
            context: Контекст з даними

        Returns:
            Оновлений контекст
        """
        for middleware in self.middlewares.get(middleware_type, []):
            if middleware.enabled:
                try:
                    # Підтримка як async, так і sync middleware
                    result = middleware.process(context)
                    if asyncio.iscoroutine(result):
                        context = await result
                    else:
                        context = result

                    # Переривання ланцюжка (наприклад, cache hit)
                    if context.skip_request:
                        break

                except Exception as e:
                    context.error = e
                    print(f"Middleware {middleware.name} error: {e}")

        return context

    def teardown_all(self):
        """Закриває всі middleware."""
        for middlewares_list in self.middlewares.values():
            for middleware in middlewares_list:
                middleware.teardown()

    def get_middleware_by_name(self, name: str) -> BaseMiddleware:
        """Знаходить middleware за назвою."""
        for middlewares_list in self.middlewares.values():
            for middleware in middlewares_list:
                if middleware.name == name:
                    return middleware
        return None

    def get_stats(self) -> dict:
        """Повертає статистику middleware."""
        stats = {}
        for middleware_type, middlewares_list in self.middlewares.items():
            stats[middleware_type.value] = [
                middleware.name for middleware in middlewares_list
            ]
        return stats
