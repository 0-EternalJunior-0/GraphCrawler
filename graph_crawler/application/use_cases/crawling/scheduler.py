"""Планувальник для управління чергою вузлів.

- Native Cython BloomFilterFast (2.7x швидше за pybloom-live)
- Автоматичний fallback на pybloom-live якщо native не скомпільовано

- Винесено lazy imports на рівень модуля
- Умовний імпорт CrawlerEvent тільки якщо event_bus активний
"""

import asyncio
import heapq
import logging
import re
from typing import Any, List, Optional, Protocol, Set, Union


class BloomFilterProtocol(Protocol):
    """Protocol для BloomFilter для коректної типізації."""

    def add(self, item: str) -> None: ...
    def __contains__(self, item: str) -> bool: ...
    def __len__(self) -> int: ...
    def get_statistics(self) -> dict: ...


from graph_crawler.domain.entities.node import Node
from graph_crawler.shared.constants import (
    DEFAULT_URL_PRIORITY,
)

logger = logging.getLogger(__name__)

#
#
_NATIVE_BLOOM_AVAILABLE = False
_BloomFilterClass = None

try:
    # Централізований імпорт через graph_crawler.native (cross-platform)
    from graph_crawler.native import BloomFilterFast

    if BloomFilterFast is not None:
        _NATIVE_BLOOM_AVAILABLE = True
        _BloomFilterClass = BloomFilterFast
        logger.info(" Native Cython BloomFilterFast loaded (2.7x faster)")
    else:
        raise ImportError("BloomFilterFast is None")
except ImportError:
    # Fallback на pybloom-live
    from graph_crawler.shared.utils.bloom_filter import BloomFilter

    _BloomFilterClass = BloomFilter
    logger.debug("Native BloomFilterFast not available, using pybloom-live")

try:
    from graph_crawler.domain.events import CrawlerEvent, EventType

    _EVENTS_AVAILABLE = True
except ImportError:
    _EVENTS_AVAILABLE = False
    CrawlerEvent = None
    EventType = None


class CrawlScheduler:
    """
    Планувальник для управління чергою вузлів для сканування.

    """

    def __init__(
        self,
        url_rules: Optional[List] = None,
        event_bus=None,
        use_bloom_filter: bool = True,
        bloom_capacity: int = 10_000_000,
        bloom_error_rate: float = 0.001,
        low_memory_mode: bool = False,
        eviction_storage: Optional[Any] = None,
        graph: Optional[Any] = None,
        plugin_manager: Optional[Any] = None,
    ):
        """
        Ініціалізує scheduler.

        """
        # Економія: 1-3 KB на кожен елемент черги
        self.queue: List = []  # heapq priority queue з URLs
        self.counter: int = 0  # Для FIFO при однакових пріоритетах

        self._graph = graph

        self._plugin_manager = plugin_manager

        self._low_memory_mode = low_memory_mode
        self._eviction_storage = eviction_storage

        # Bloom Filter або set для seen URLs
        # Типізація: Union[Set[str], BloomFilterProtocol]
        self.seen_urls: Union[Set[str], Any]  # Any для BloomFilter
        if low_memory_mode:
            self.use_bloom_filter = False
            self.seen_urls = set()  # Мінімальний RAM set
            logger.info(
                "🚀 Scheduler initialized in LOW-MEMORY mode: "
                "Bloom Filter DISABLED, using SQLite for URL uniqueness check"
            )
        elif use_bloom_filter and _BloomFilterClass is not None:
            self.use_bloom_filter = True
            self.seen_urls = _BloomFilterClass(capacity=bloom_capacity, error_rate=bloom_error_rate)
            bloom_type = "Native Cython" if _NATIVE_BLOOM_AVAILABLE else "pybloom-live"
            logger.info(
                f"🚀 Scheduler initialized with {bloom_type} Bloom Filter: "
                f"capacity={bloom_capacity:,}, error_rate={bloom_error_rate * 100}%"
            )
        else:
            self.use_bloom_filter = False
            self.seen_urls = set()
            logger.debug("Scheduler initialized with Python set (not Bloom Filter)")

        # URL Rules для Smart Scheduling
        self.url_rules = url_rules or []

        # EventBus для подій
        self.event_bus = event_bus

        # При async batch mode кілька корутин можуть одночасно додавати URLs
        self._seen_urls_lock = asyncio.Lock()

        # heapq не є thread-safe. При batch mode з asyncio.gather() кілька
        # корутин можуть одночасно модифікувати heap, що призводить до corruption.
        self._queue_lock = asyncio.Lock()

        # Компілюємо regex патерни для швидкості
        self._compiled_rules = []
        for rule in self.url_rules:
            try:
                compiled_pattern = re.compile(rule.pattern)
                self._compiled_rules.append((compiled_pattern, rule))
            except re.error as e:
                logger.warning("Invalid regex pattern '%s': %s", rule.pattern, e)

        logger.debug("Scheduler initialized with %s URL rules", len(self.url_rules))

    def add_node(self, node: Node, priority: Optional[int] = None) -> bool:
        """
        Додає вузол до черги з пріоритетом.
        Економія: 1-3 KB на кожен елемент черги.
        Node об'єкт lazy-load при get_next() через Graph reference.

        1. Фільтрації (action='exclude')
        2. Пріоритизації (priority 1-10)
        3. Контролю поведінки (should_scan, should_follow_links)

        ML Plugin Support: Якщо передано priority параметр - використовує його
        замість обчисленого пріоритету (для child_priorities від плагінів).

        Args:
            node: Вузол для додавання
            priority: Опціональний пріоритет від ML плагіну (перебиває всі інші)

        Returns:
            True якщо вузол додано, False якщо вже був у черзі або відфільтровано
        """
        if self.has_url(node.url):
            return False

        # Знаходимо перше правило що матчить URL
        matched_rule = self._match_rule(node.url)
        # URLRule використовує should_scan замість action
        if matched_rule and matched_rule.should_scan is False:
            logger.debug("Excluded by rule: %s", node.url)
            self.seen_urls.add(node.url)  # Додаємо щоб не перевіряти знову

            # Подія про виключення URL
            if (
                self.event_bus
                and _EVENTS_AVAILABLE
                and CrawlerEvent is not None
                and EventType is not None
            ):
                self.event_bus.publish(
                    CrawlerEvent.create(
                        EventType.URL_EXCLUDED,
                        data={
                            "url": node.url,
                            "pattern": matched_rule.pattern,
                            "reason": "excluded_by_rule",
                        },
                    )
                )
            return False

        #  ML PLUGIN SUPPORT: Використовуємо переданий priority якщо є
        if priority is not None:
            final_priority = priority
            logger.debug("Using ML plugin priority: %s for %s", final_priority, node.url)
        else:
            # Застосовуємо правило до ноди (пріоритет, should_scan, should_follow_links)
            final_priority = self._calculate_priority(node.url, matched_rule, node)

        self._apply_rule_to_node(node, matched_rule)

        # heapq - мінімальна купа, тому інвертуємо пріоритет (-priority)
        # Менше число = вища позиція в черзі
        # Економія RAM: ~1-3 KB на елемент при 10k елементів = ~10-30 MB
        self.counter += 1
        heapq.heappush(self.queue, (-final_priority, self.counter, node.url))
        self.seen_urls.add(node.url)

        logger.debug(
            f"Added node: {node.url} (priority={final_priority}, "
            f"should_scan={node.should_scan}, can_create_edges={node.can_create_edges})"
        )

        # Подія про додавання URL в чергу
        if (
            self.event_bus
            and _EVENTS_AVAILABLE
            and CrawlerEvent is not None
            and EventType is not None
        ):
            self.event_bus.publish(
                CrawlerEvent.create(
                    EventType.URL_ADDED_TO_QUEUE,
                    data={
                        "url": node.url,
                        "depth": node.depth,
                        "priority": final_priority,
                        "queue_size": len(self.queue),
                    },
                )
            )
            if final_priority != DEFAULT_URL_PRIORITY:
                self.event_bus.publish(
                    CrawlerEvent.create(
                        EventType.URL_PRIORITIZED,
                        data={
                            "url": node.url,
                            "priority": final_priority,
                            "pattern": matched_rule.pattern if matched_rule else None,
                            "from_ml_plugin": priority is not None,
                        },
                    )
                )

        return True

    async def add_node_async(self, node: Node, priority: Optional[int] = None) -> bool:
        """

        Використовує окремі locks для seen_urls та queue для запобігання
        race conditions при batch mode з asyncio.gather().

        Args:
            node: Вузол для додавання
            priority: Опціональний пріоритет від ML плагіну

        Returns:
            True якщо вузол додано, False якщо вже був у черзі або відфільтровано
        """
        async with self._seen_urls_lock:
            async with self._queue_lock:
                return self.add_node(node, priority)

    async def has_url_async(self, url: str) -> bool:
        """

        Args:
            url: URL для перевірки

        Returns:
            True якщо URL вже був побачений
        """
        async with self._seen_urls_lock:
            return url in self.seen_urls

    def get_next(self) -> Optional[Node]:
        """
        Повертає наступний вузол для сканування (з найвищим пріоритетом).
        Черга тепер тримає тільки URLs, Node об'єкт отримується з Graph
        або створюється новий якщо Graph не доступний.

        УВАГА: Для async batch mode використовуйте get_next_async() з lock.

        Returns:
            Вузол або None якщо черга порожня
        """
        if self.is_empty():
            return None

        priority, counter, url = heapq.heappop(self.queue)
        logger.debug("Getting next node: %s (priority=%s)", url, -priority)

        if self._graph is not None:
            node = self._graph.get_node_by_url(url, load_from_disk=True)
            if node is not None:
                if node.plugin_manager is None and self._plugin_manager is not None:
                    node.plugin_manager = self._plugin_manager
                return node
            logger.warning("Node not found in Graph for URL: %s", url)

        # Fallback: Створюємо мінімальний Node якщо Graph недоступний
        # Це для backward compatibility коли scheduler використовується без Graph
        node = Node(url=url, plugin_manager=self._plugin_manager)
        return node

    def set_graph(self, graph: Any) -> None:
        """Set the graph for lazy loading nodes.

        Викликається при ініціалізації CrawlCoordinator.

        Args:
            graph: Graph об'єкт для lazy loading нод
        """
        self._graph = graph
        logger.debug("Scheduler: Graph reference set for lazy loading")

    def set_plugin_manager(self, plugin_manager: Any) -> None:
        """

        Викликається при ініціалізації Spider для забезпечення
        передачі plugin_manager в ноди створені через get_next().

        Args:
            plugin_manager: Plugin manager для передачі в Node
        """
        self._plugin_manager = plugin_manager
        logger.debug("Scheduler: Plugin manager set for Node creation")

    def reprioritize_url(self, url: str, priority: int) -> bool:
        """
        Змінює пріоритет URL в черзі.

        Для AI Agent Integration - дозволяє AI підвищувати пріоритет
        URL які він вважає релевантними для задачі.

        Args:
            url: URL для зміни пріоритету
            priority: Новий пріоритет (вищий = раніше буде оброблено)

        Returns:
            True якщо URL знайдено і пріоритет змінено
        """
        # Шукаємо URL в черзі
        for i, (old_priority, counter, queued_url) in enumerate(self.queue):
            if queued_url == url:
                # Видаляємо старий запис
                self.queue[i] = self.queue[-1]
                self.queue.pop()
                heapq.heapify(self.queue)

                # Додаємо з новим пріоритетом
                self.counter += 1
                heapq.heappush(self.queue, (-priority, self.counter, url))

                logger.debug("Reprioritized URL: %s (new priority=%s)", url, priority)
                return True

        return False

    async def get_next_async(self) -> Optional[Node]:
        """

        Використовує lock для запобігання race conditions при batch mode
        з asyncio.gather(). heapq.heappop() не є thread-safe, тому потрібен lock.

        Returns:
            Вузол або None якщо черга порожня
        """
        async with self._queue_lock:
            return self.get_next()

    def _match_rule(self, url: str):
        """
        Знаходить перше правило що матчить URL.

        Args:
            url: URL для перевірки

        Returns:
            URLRule або None якщо немає збігів
        """
        for compiled_pattern, rule in self._compiled_rules:
            if compiled_pattern.search(url):
                return rule
        return None

    def _calculate_priority(self, url: str, matched_rule, node: Node) -> int:
        """
        Обчислює пріоритет URL.

         Підтримка динамічних пріоритетів від плагінів!

        Порядок перевірки:
        1. Node.priority атрибут (динамічний, від плагінів) - НАЙВИЩИЙ ПРІОРИТЕТ
        2. URLRule.priority (статичний, regex-based)
        3. DEFAULT_URL_PRIORITY (fallback)

        Args:
            url: URL для перевірки
            matched_rule: Правило що зматчилось або None
            node: Node об'єкт для перевірки динамічного пріоритету

        Returns:
            Пріоритет (1-10, default=DEFAULT_URL_PRIORITY)
        """
        # 1. НОВИЙ МЕХАНІЗМ: Перевіряємо чи Node має динамічний priority (від плагінів)
        # Правильна обробка @property у підкласах Pydantic
        node_priority = self._get_node_priority(node)
        if node_priority is not None:
            logger.debug("Using dynamic priority from node: %s for %s", node_priority, url)
            return node_priority

        # 2. URLRule priority (статичний)
        if matched_rule:
            return matched_rule.priority

        # 3. Fallback на default
        return DEFAULT_URL_PRIORITY

    def _get_node_priority(self, node: Node) -> Optional[int]:
        """
        Безпечно отримує priority з ноди.

        Args:
            node: Node об'єкт

        Returns:
            int priority або None
        """
        # Python автоматично викликає getter для @property
        priority = getattr(node, "priority", None)
        return priority if isinstance(priority, int) else None

    def _apply_rule_to_node(self, node: Node, matched_rule):
        """
        Застосовує правило до ноди (Tell, Don't Ask принцип).

        Args:
            node: Нода для модифікації
            matched_rule: Правило що зматчилось або None
        """
        if not matched_rule:
            return

        # Tell, Don't Ask: правило саме модифікує node
        # Замість того щоб питати значення та встановлювати їх тут
        matched_rule.apply_to_node(node)

    def is_empty(self) -> bool:
        """Перевіряє чи черга порожня."""
        return len(self.queue) == 0

    def size(self) -> int:
        """Повертає розмір черги."""
        return len(self.queue)

    def has_url(self, url: str) -> bool:
        """
        Перевіряє чи URL вже був побачений.
        """
        # Спочатку швидка перевірка в RAM
        if url in self.seen_urls:
            return True

        if self._low_memory_mode and self._eviction_storage:
            return self._eviction_storage.url_exists(url)

        return False

    def get_memory_statistics(self) -> dict:
        """
        Повертає статистику використання пам'яті.

        Returns:
            dict з полями:
                - use_bloom_filter: bool - чи використовується Bloom Filter
                - seen_urls_count: int - кількість seen URLs
                - queue_size: int - розмір черги
                - bloom_statistics: dict - статистика Bloom Filter (якщо використовується)
                - bloom_type: str - тип Bloom Filter (native_cython або pybloom_live)

        Example:
            >>> scheduler = CrawlScheduler(use_bloom_filter=True)
            >>> for i in range(10000):
            ...     scheduler.add_node(Node(url=f"https://example.com/page{i}"))
            >>> stats = scheduler.get_memory_statistics()
            >>> print(f"Memory usage: {stats['bloom_statistics']['memory_usage_mb']} MB")
        """
        stats = {
            "use_bloom_filter": self.use_bloom_filter,
            "queue_size": len(self.queue),
            "bloom_type": "native_cython" if _NATIVE_BLOOM_AVAILABLE else "pybloom_live",
        }

        if self.use_bloom_filter and hasattr(self.seen_urls, "get_statistics"):
            # Bloom filter версії підтримують get_statistics() та len()
            stats["seen_urls_count"] = len(self.seen_urls)  # type: ignore
            stats["bloom_statistics"] = self.seen_urls.get_statistics()  # type: ignore
        else:
            # Python set
            stats["seen_urls_count"] = len(self.seen_urls)  # type: ignore
            stats["bloom_statistics"] = None

        return stats

    def get_summary(self) -> str:
        """
        Повертає текстовий summary scheduler.

        Returns:
            Форматований рядок зі статистикою

        Example:
            >>> scheduler = CrawlScheduler(use_bloom_filter=True)
            >>> print(scheduler.get_summary())
        """
        stats = self.get_memory_statistics()

        lines = [
            " Crawler Scheduler Statistics",
            "" * 42,
            f"Queue Size:         {stats['queue_size']:,}",
            f"Seen URLs:          {stats['seen_urls_count']:,}",
            f"Using Bloom Filter: {'Yes ' if stats['use_bloom_filter'] else 'No (Python set)'}",
        ]

        if stats["bloom_statistics"]:
            bloom_stats = stats["bloom_statistics"]
            lines.extend(
                [
                    "",
                    " Bloom Filter Details:",
                    f"  Capacity:         {bloom_stats['capacity']:,}",
                    f"  Fill Ratio:       {bloom_stats['fill_ratio'] * 100:.2f}%",
                    f"  Memory Usage:     {bloom_stats['memory_usage_mb']:.2f} MB",
                    f"  Error Rate:       {bloom_stats['error_rate'] * 100:.2f}%",
                ]
            )

        return "\n".join(lines)
