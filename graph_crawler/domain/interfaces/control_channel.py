"""IControlChannel Protocol - двосторонній канал керування краулінгом.

Phase 2: AI Agent Integration
"""

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Protocol

logger = logging.getLogger(__name__)


class CrawlCommand(str, Enum):
    """Команди для керування краулінгом."""

    # Базові команди
    STOP = "stop"  # Зупинити краулінг
    PAUSE = "pause"  # Призупинити краулінг
    RESUME = "resume"  # Продовжити краулінг

    # Команди пріоритизації
    REPRIORITIZE = "reprioritize"  # Змінити пріоритет URL
    SKIP_URL = "skip_url"  # Пропустити URL
    FORCE_VISIT = "force_visit"  # Примусово відвідати URL

    # Команди стратегії
    CHANGE_STRATEGY = "change_strategy"  # Змінити стратегію навігації
    SET_DEPTH_LIMIT = "set_depth_limit"  # Встановити ліміт глибини

    # Команди даних
    REQUEST_STATE = "request_state"  # Запросити поточний стан
    UPDATE_GOAL = "update_goal"  # Оновити мету краулінгу


@dataclass
class ControlMessage:
    """
    Повідомлення для керування краулінгом.

    Attributes:
        command: Тип команди
        data: Додаткові дані для команди
        sender: Ідентифікатор відправника (плагін, AI Agent, тощо)
        priority: Пріоритет повідомлення (вищий = обробляється першим)
        timestamp: Час створення повідомлення
    """

    command: CrawlCommand
    data: Dict[str, Any] = field(default_factory=dict)
    sender: str = "unknown"
    priority: int = 0
    timestamp: Optional[float] = None

    def __post_init__(self):
        if self.timestamp is None:
            import time

            self.timestamp = time.time()


class IControlChannel(Protocol):
    """
    Protocol для двостороннього каналу керування.

    Дозволяє:
    - Плагінам відправляти команди Spider
    - Зовнішньому коду керувати краулінгом
    - Підписуватись на команди
    """

    def send(self, message: ControlMessage) -> None:
        """
        Відправити команду в канал.

        Args:
            message: Повідомлення з командою
        """
        ...

    def receive(self) -> Optional[ControlMessage]:
        """
        Отримати команду з каналу (non-blocking).

        Returns:
            ControlMessage або None якщо черга порожня
        """
        ...

    async def receive_async(self, timeout: Optional[float] = None) -> Optional[ControlMessage]:
        """
        Async отримати команду з каналу.

        Args:
            timeout: Таймаут очікування в секундах (None = очікувати безкінечно)

        Returns:
            ControlMessage або None при timeout
        """
        ...

    def has_pending(self) -> bool:
        """
        Перевірити чи є команди в черзі.

        Returns:
            True якщо є непрочитані команди
        """
        ...

    def subscribe(self, command: CrawlCommand, callback: Callable[[ControlMessage], None]) -> None:
        """
        Підписатись на певний тип команд.

        Args:
            command: Тип команди
            callback: Функція для виклику при отриманні команди
        """
        ...


class AsyncQueueControlChannel:
    """
    Реалізація IControlChannel через asyncio.Queue.

    """

    def __init__(self, max_size: int = 100):
        """
        Ініціалізує канал.

        Args:
            max_size: Максимальний розмір черги
        """
        self._queue: asyncio.Queue[ControlMessage] = asyncio.Queue(maxsize=max_size)
        self._priority_queue: List[ControlMessage] = []  # Для пріоритетних повідомлень
        self._subscribers: Dict[CrawlCommand, List[Callable[[ControlMessage], None]]] = {}
        self._lock = asyncio.Lock()

    def send(self, message: ControlMessage) -> None:
        """
        Відправити команду в канал.

        Args:
            message: Повідомлення з командою
        """
        try:
            # Спочатку сповіщаємо підписників
            self._notify_subscribers(message)

            # Потім додаємо в чергу
            self._queue.put_nowait(message)
            logger.debug("Control message sent: %s from %s", message.command.value, message.sender)

        except asyncio.QueueFull:
            logger.warning("Control channel queue full, dropping message: %s", message.command.value)

    def receive(self) -> Optional[ControlMessage]:
        """
        Отримати команду з каналу (non-blocking).

        Returns:
            ControlMessage або None якщо черга порожня
        """
        try:
            return self._queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    async def receive_async(self, timeout: Optional[float] = None) -> Optional[ControlMessage]:
        """
        Async отримати команду з каналу.

        Args:
            timeout: Таймаут очікування в секундах

        Returns:
            ControlMessage або None при timeout
        """
        try:
            if timeout is not None:
                return await asyncio.wait_for(self._queue.get(), timeout=timeout)
            else:
                return await self._queue.get()
        except asyncio.TimeoutError:
            return None
        except asyncio.QueueEmpty:
            return None

    def has_pending(self) -> bool:
        """
        Перевірити чи є команди в черзі.

        Returns:
            True якщо є непрочитані команди
        """
        return not self._queue.empty()

    def subscribe(self, command: CrawlCommand, callback: Callable[[ControlMessage], None]) -> None:
        """
        Підписатись на певний тип команд.

        Args:
            command: Тип команди
            callback: Функція для виклику при отриманні команди
        """
        if command not in self._subscribers:
            self._subscribers[command] = []
        self._subscribers[command].append(callback)
        logger.debug("Subscribed to command: %s", command.value)

    def unsubscribe(
        self, command: CrawlCommand, callback: Callable[[ControlMessage], None]
    ) -> None:
        """
        Відписатись від типу команд.

        Args:
            command: Тип команди
            callback: Функція для видалення
        """
        if command in self._subscribers and callback in self._subscribers[command]:
            self._subscribers[command].remove(callback)

    def _notify_subscribers(self, message: ControlMessage) -> None:
        """Сповістити підписників про команду."""
        callbacks = self._subscribers.get(message.command, [])
        for callback in callbacks:
            try:
                callback(message)
            except Exception as e:
                logger.error("Subscriber callback error: %s", e)

    def clear(self) -> None:
        """Очистити чергу команд."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    @property
    def pending_count(self) -> int:
        """Кількість команд в черзі."""
        return self._queue.qsize()

    def __repr__(self) -> str:
        return f"AsyncQueueControlChannel(pending={self.pending_count})"


class SyncControlChannel:
    """
    Синхронна реалізація IControlChannel через threading.Queue.

    Для використання в sync контексті (наприклад, в sync плагінах).
    """

    def __init__(self, max_size: int = 100):
        """
        Ініціалізує канал.

        Args:
            max_size: Максимальний розмір черги
        """
        import queue
        import threading

        self._queue: queue.Queue[ControlMessage] = queue.Queue(maxsize=max_size)
        self._subscribers: Dict[CrawlCommand, List[Callable[[ControlMessage], None]]] = {}
        self._lock = threading.RLock()

    def send(self, message: ControlMessage) -> None:
        """Відправити команду в канал."""
        import queue

        try:
            # Сповіщаємо підписників
            self._notify_subscribers(message)

            # Додаємо в чергу
            self._queue.put_nowait(message)
            logger.debug("Control message sent (sync): %s", message.command.value)

        except queue.Full:
            logger.warning("Control channel queue full")

    def receive(self) -> Optional[ControlMessage]:
        """Отримати команду з каналу (non-blocking)."""
        import queue

        try:
            return self._queue.get_nowait()
        except queue.Empty:
            return None

    async def receive_async(self, timeout: Optional[float] = None) -> Optional[ControlMessage]:
        """Async wrapper для sync receive."""
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.receive)

    def has_pending(self) -> bool:
        """Перевірити чи є команди в черзі."""
        return not self._queue.empty()

    def subscribe(self, command: CrawlCommand, callback: Callable[[ControlMessage], None]) -> None:
        """Підписатись на певний тип команд."""
        with self._lock:
            if command not in self._subscribers:
                self._subscribers[command] = []
            self._subscribers[command].append(callback)

    def _notify_subscribers(self, message: ControlMessage) -> None:
        """Сповістити підписників."""
        with self._lock:
            callbacks = self._subscribers.get(message.command, [])

        for callback in callbacks:
            try:
                callback(message)
            except Exception as e:
                logger.error("Subscriber error: %s", e)

    @property
    def pending_count(self) -> int:
        """Кількість команд в черзі."""
        return self._queue.qsize()


# Convenience функції для створення команд


def stop_command(reason: str = "Stop requested", sender: str = "unknown") -> ControlMessage:
    """Створити команду зупинки."""
    return ControlMessage(
        command=CrawlCommand.STOP,
        data={"reason": reason},
        sender=sender,
        priority=10,  # Висока пріоритетність
    )


def pause_command(sender: str = "unknown") -> ControlMessage:
    """Створити команду паузи."""
    return ControlMessage(command=CrawlCommand.PAUSE, sender=sender, priority=5)


def resume_command(sender: str = "unknown") -> ControlMessage:
    """Створити команду продовження."""
    return ControlMessage(command=CrawlCommand.RESUME, sender=sender, priority=5)


def reprioritize_command(url: str, new_priority: int, sender: str = "unknown") -> ControlMessage:
    """Створити команду зміни пріоритету URL."""
    return ControlMessage(
        command=CrawlCommand.REPRIORITIZE,
        data={"url": url, "priority": new_priority},
        sender=sender,
    )


def force_visit_command(url: str, sender: str = "unknown") -> ControlMessage:
    """Створити команду примусового відвідування."""
    return ControlMessage(
        command=CrawlCommand.FORCE_VISIT, data={"url": url}, sender=sender, priority=8
    )
