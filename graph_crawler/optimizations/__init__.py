"""
Оптимізації для GraphCrawler.

Цей модуль надає прискорені версії критичних функцій:
- SimHash обчислення (Numba JIT)
- Hamming distance (Numba JIT)

Автоматичний fallback на pure Python якщо Numba недоступна.

Usage:
    from graph_crawler.optimizations import (
        compute_simhash_fast,
        hamming_distance_fast,
        is_numba_available,
    )
"""

from .simhash_numba import (
    compute_simhash_fast,
    hamming_distance_fast,
    is_numba_available,
    get_optimization_status,
    benchmark_simhash,
)

__all__ = [
    "compute_simhash_fast",
    "hamming_distance_fast",
    "is_numba_available",
    "get_optimization_status",
    "benchmark_simhash",
]
