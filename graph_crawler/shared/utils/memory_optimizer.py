"""
Memory Optimization Utilities.

Утіліти для оптимізації використання пам'яті GraphCrawler.

Includes:
- Memory profiling utilities
- __slots__ optimized classes
- Weak reference helpers
- Memory-efficient data structures

Target: < 100MB for 10K nodes
"""

import gc
import logging
import sys
import tracemalloc
import weakref
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional, Set

logger = logging.getLogger(__name__)


class MemoryProfiler:
    """
    Утіліта для профілювання використання пам'яті.

    Використовує tracemalloc для відстеження виділення пам'яті
    та ідентифікації найбільших споживачів.

    Example:
        >>> profiler = MemoryProfiler()
        >>> profiler.start()
        >>> # Ваш код
        >>> graph = Graph()
        >>> # ...
        >>> snapshot = profiler.stop()
        >>> profiler.print_top_allocations(snapshot, limit=10)
    """

    def __init__(self):
        self.snapshots: List[Any] = []
        self.is_running: bool = False

    def start(self) -> None:
        """Запускає memory profiling."""
        tracemalloc.start()
        self.is_running = True
        logger.info("Memory profiling started")

    def stop(self) -> Any:
        """
        Зупиняє memory profiling та повертає snapshot.

        Returns:
            Snapshot об'єкт з tracemalloc
        """
        if not self.is_running:
            logger.warning("  Memory profiler is not running")
            return None

        snapshot = tracemalloc.take_snapshot()
        tracemalloc.stop()
        self.is_running = False
        self.snapshots.append(snapshot)
        logger.info("Memory profiling stopped")
        return snapshot

    def get_current_memory(self) -> float:
        """
        Повертає поточне використання пам'яті у MB.

        Returns:
            Пам'ять у MB
        """
        if not self.is_running:
            return 0.0

        current, peak = tracemalloc.get_traced_memory()
        return current / (1024 * 1024)

    def get_peak_memory(self) -> float:
        """
        Повертає пікове використання пам'яті у MB.

        Returns:
            Пікова пам'ять у MB
        """
        if not self.is_running:
            return 0.0

        current, peak = tracemalloc.get_traced_memory()
        return peak / (1024 * 1024)

    @staticmethod
    def print_top_allocations(snapshot: Any, limit: int = 10) -> None:
        """
        Виводить топ N найбільших виділень пам'яті.

        Args:
            snapshot: Snapshot з tracemalloc
            limit: Кількість топ виділень
        """
        if not snapshot:
            logger.warning("  No snapshot available")
            return

        print(f"\n{'='*80}")
        print(f" TOP {limit} MEMORY ALLOCATIONS")
        print(f"{'='*80}\n")

        top_stats = snapshot.statistics("lineno")

        for index, stat in enumerate(top_stats[:limit], 1):
            size_mb = stat.size / (1024 * 1024)
            count = stat.count

            print(f"{index:2d}. {stat.traceback.format()[0]}")
            print(f"    Size: {size_mb:.2f} MB ({stat.size:,} bytes)")
            print(f"    Count: {count:,} allocations")
            print()

    @staticmethod
    def compare_snapshots(snapshot1: Any, snapshot2: Any, limit: int = 10) -> None:
        """
        Порівнює два snapshots та показує різницю.

        Args:
            snapshot1: Перший snapshot (baseline)
            snapshot2: Другий snapshot (after)
            limit: Кількість топ різниць
        """
        if not snapshot1 or not snapshot2:
            logger.warning("  Need 2 snapshots to compare")
            return

        print(f"\n{'='*80}")
        print(f" MEMORY DIFF (TOP {limit} CHANGES)")
        print(f"{'='*80}\n")

        top_stats = snapshot2.compare_to(snapshot1, "lineno")

        for index, stat in enumerate(top_stats[:limit], 1):
            size_diff_mb = stat.size_diff / (1024 * 1024)
            count_diff = stat.count_diff

            sign = "+" if stat.size_diff > 0 else ""
            print(f"{index:2d}. {stat.traceback.format()[0]}")
            print(
                f"    Size diff: {sign}{size_diff_mb:.2f} MB ({sign}{stat.size_diff:,} bytes)"
            )
            print(f"    Count diff: {sign}{count_diff:,} allocations")
            print()


@dataclass
class MemoryStats:
    """
    Статистика використання пам'яті.

    Attributes:
        current_mb: Поточна пам'ять (MB)
        peak_mb: Пікова пам'ять (MB)
        baseline_mb: Базова пам'ять (MB)
        used_mb: Використана пам'ять (MB)
        objects_count: Кількість об'єктів
        timestamp: Час вимірювання
    """

    current_mb: float
    peak_mb: float
    baseline_mb: float
    used_mb: float
    objects_count: int
    timestamp: datetime

    def __str__(self) -> str:
        return (
            f"MemoryStats(current={self.current_mb:.2f}MB, "
            f"peak={self.peak_mb:.2f}MB, used={self.used_mb:.2f}MB, "
            f"objects={self.objects_count:,})"
        )


class MemoryMonitor:
    """
    Монітор пам'яті для відстеження використання під час роботи.

    Example:
        >>> monitor = MemoryMonitor()
        >>> monitor.checkpoint("start")
        >>> # Створюємо 10K nodes
        >>> graph = create_large_graph(10000)
        >>> monitor.checkpoint("after_10k_nodes")
        >>> monitor.print_report()
    """

    def __init__(self):
        self.checkpoints: Dict[str, MemoryStats] = {}
        self.baseline_mb: float = 0.0
        tracemalloc.start()
        self.baseline_mb = tracemalloc.get_traced_memory()[0] / (1024 * 1024)

    def checkpoint(self, name: str) -> MemoryStats:
        """
        Створює checkpoint з поточним станом пам'яті.

        Args:
            name: Назва checkpoint

        Returns:
            MemoryStats об'єкт
        """
        current, peak = tracemalloc.get_traced_memory()
        current_mb = current / (1024 * 1024)
        peak_mb = peak / (1024 * 1024)
        used_mb = current_mb - self.baseline_mb

        # Підрахунок об'єктів
        gc.collect()
        objects_count = len(gc.get_objects())

        stats = MemoryStats(
            current_mb=current_mb,
            peak_mb=peak_mb,
            baseline_mb=self.baseline_mb,
            used_mb=used_mb,
            objects_count=objects_count,
            timestamp=datetime.now(),
        )

        self.checkpoints[name] = stats
        logger.info(f" Checkpoint '{name}': {stats}")
        return stats

    def print_report(self) -> None:
        """Виводить звіт по всім checkpoints."""
        if not self.checkpoints:
            print("  No checkpoints recorded")
            return

        print(f"\n{'='*80}")
        print(f" MEMORY MONITORING REPORT")
        print(f"{'='*80}\n")
        print(f"Baseline Memory: {self.baseline_mb:.2f} MB\n")

        print(
            f"{'Checkpoint':<30} {'Current (MB)':<15} {'Peak (MB)':<15} {'Used (MB)':<15}"
        )
        print(f"{'-'*30} {'-'*15} {'-'*15} {'-'*15}")

        for name, stats in self.checkpoints.items():
            print(
                f"{name:<30} {stats.current_mb:<15.2f} {stats.peak_mb:<15.2f} {stats.used_mb:<15.2f}"
            )

        print(f"\n{'='*80}\n")

    def stop(self) -> None:
        """Зупиняє моніторинг."""
        tracemalloc.stop()


class WeakValueGraph:
    """
    Граф з weak references для nodes.

      ЕКСПЕРИМЕНТАЛЬНО: Використовує weakref.WeakValueDictionary
    для автоматичного звільнення пам'яті для непотрібних nodes.

    ВАЖЛИВО:
    - Nodes можуть бути видалені garbage collector'ом
    - Підходить для large-scale crawling де не всі nodes потрібні одночасно
    - НЕ рекомендується для малих графів (overhead)

    Example:
        >>> weak_graph = WeakValueGraph()
        >>> node = Node(url="https://example.com", depth=0)
        >>> weak_graph.add_node(node)
        >>> # Node буде видалений GC коли більше немає strong references
    """

    def __init__(self):
        self._nodes: weakref.WeakValueDictionary = weakref.WeakValueDictionary()
        self._node_count: int = 0

    def add_node(self, node: Any) -> None:
        """
        Додає node з weak reference.

        Args:
            node: Node об'єкт
        """
        self._nodes[node.node_id] = node
        self._node_count += 1

    def get_node(self, node_id: str) -> Optional[Any]:
        """
        Отримує node за ID.

        Args:
            node_id: ID node

        Returns:
            Node або None якщо був видалений GC
        """
        return self._nodes.get(node_id)

    def __len__(self) -> int:
        """Повертає кількість живих nodes."""
        return len(self._nodes)

    def total_added(self) -> int:
        """Повертає загальну кількість доданих nodes."""
        return self._node_count


def get_object_size(obj: Any) -> int:
    """
    Обчислює розмір об'єкта у байтах (рекурсивно).

    Args:
        obj: Об'єкт для вимірювання

    Returns:
        Розмір у байтах
    """
    seen = set()

    def sizeof(o):
        if id(o) in seen:
            return 0
        seen.add(id(o))

        size = sys.getsizeof(o)

        if isinstance(o, dict):
            size += sum(sizeof(k) + sizeof(v) for k, v in o.items())
        elif isinstance(o, (list, tuple, set)):
            size += sum(sizeof(item) for item in o)

        return size

    return sizeof(obj)


def optimize_graph_memory(graph: Any) -> None:
    """
    Оптимізує використання пам'яті для існуючого графу.

    Виконує:
    - Garbage collection
    - Видалення порожніх metadata полів
    - Компактифікація структур даних

    Args:
        graph: Graph об'єкт
    """
    logger.info(" Optimizing graph memory...")

    # 1. Garbage collection
    collected = gc.collect()
    logger.info(f"   Collected {collected} garbage objects")

    # 2. Очистка порожніх metadata
    cleaned_count = 0
    for node in graph.nodes.values():
        # Видаляємо порожні dict
        if hasattr(node, "metadata"):
            empty_keys = [k for k, v in node.metadata.items() if not v]
            for key in empty_keys:
                del node.metadata[key]
                cleaned_count += 1

        if hasattr(node, "user_data"):
            empty_keys = [k for k, v in node.user_data.items() if not v]
            for key in empty_keys:
                del node.user_data[key]
                cleaned_count += 1

    logger.info(f"   Cleaned {cleaned_count} empty metadata fields")

    # 3. Видаляємо дублікати edges
    if hasattr(graph, "_edges") and hasattr(graph, "_edge_index"):
        unique_edges = []
        seen = set()

        for edge in graph._edges:
            edge_tuple = (edge.source_node_id, edge.target_node_id)
            if edge_tuple not in seen:
                seen.add(edge_tuple)
                unique_edges.append(edge)

        duplicates = len(graph._edges) - len(unique_edges)
        if duplicates > 0:
            graph._edges = unique_edges
            logger.info(f"   Removed {duplicates} duplicate edges")

    logger.info("Graph memory optimization complete")


def memory_efficient_node_iterator(nodes_dict: Dict) -> Iterator:
    """
    Ітератор для nodes що не створює проміжні списки.

    Замість:
        >>> nodes_list = list(graph.nodes.values())
        >>> for node in nodes_list:  # Створюється копія!

    Використовуйте:
        >>> for node in memory_efficient_node_iterator(graph.nodes):

    Args:
        nodes_dict: Словник nodes

    Yields:
        Node об'єкти
    """
    for node in nodes_dict.values():
        yield node


def estimate_graph_memory(
    num_nodes: int, num_edges: int, avg_metadata_size: int = 500
) -> float:
    """
    Оцінює використання пам'яті для графу.

    Args:
        num_nodes: Кількість nodes
        num_edges: Кількість edges
        avg_metadata_size: Середній розмір metadata (bytes)

    Returns:
        Оцінка пам'яті у MB
    """
    # Базовий розмір Node (Pydantic)
    node_base_size = 1000  # bytes (~1KB)
    node_size = node_base_size + avg_metadata_size

    # Базовий розмір Edge
    edge_base_size = 500  # bytes (~0.5KB)

    # Overhead для dict/list storage
    storage_overhead = 1.2  # 20% overhead

    total_bytes = (
        num_nodes * node_size + num_edges * edge_base_size
    ) * storage_overhead
    total_mb = total_bytes / (1024 * 1024)

    return total_mb


class MemoryEfficientNodeCache:
    """
    Memory-efficient cache для nodes з LRU eviction.

    Використовує обмежений розмір для запобігання OOM errors.
    Автоматично видаляє найдавніше використані nodes.

    Example:
        >>> cache = MemoryEfficientNodeCache(max_size=1000)
        >>> cache.add(node)
        >>> node = cache.get(node_id)
    """

    __slots__ = ("_cache", "_max_size", "_access_order")

    def __init__(self, max_size: int = 10000):
        """
        Ініціалізує cache.

        Args:
            max_size: Максимальна кількість nodes у cache
        """
        self._cache: Dict[str, Any] = {}
        self._max_size: int = max_size
        self._access_order: List[str] = []

    def add(self, node: Any) -> None:
        """Додає node до cache."""
        if len(self._cache) >= self._max_size:
            # Evict oldest
            oldest_id = self._access_order.pop(0)
            del self._cache[oldest_id]

        self._cache[node.node_id] = node
        self._access_order.append(node.node_id)

    def get(self, node_id: str) -> Optional[Any]:
        """
        Отримує node з cache.

        Args:
            node_id: ID node

        Returns:
            Node або None
        """
        if node_id in self._cache:
            # Move to end (most recently used)
            self._access_order.remove(node_id)
            self._access_order.append(node_id)
            return self._cache[node_id]
        return None

    def __len__(self) -> int:
        return len(self._cache)


# ============ Експорт ============

__all__ = [
    "MemoryProfiler",
    "MemoryStats",
    "MemoryMonitor",
    "WeakValueGraph",
    "get_object_size",
    "optimize_graph_memory",
    "memory_efficient_node_iterator",
    "estimate_graph_memory",
    "MemoryEfficientNodeCache",
]
