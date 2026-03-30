"""
Numba-оптимізоване обчислення SimHash.

Забезпечує 10-50x прискорення для числових операцій SimHash.
Автоматичний fallback на pure Python якщо Numba недоступна.

Usage:
    from graph_crawler.optimizations.simhash_numba import (
        compute_simhash_fast,
        hamming_distance_fast,
        is_numba_available,
    )

    # Обчислення SimHash
    tokens = ["hello world", "world is", "is beautiful"]
    simhash = compute_simhash_fast(tokens)

    # Hamming distance
    dist = hamming_distance_fast(simhash1, simhash2)
"""

import hashlib
import logging
from typing import List

logger = logging.getLogger(__name__)
try:
    import numba  # type: ignore[import-not-found]
    import numpy as np

    NUMBA_AVAILABLE = True
    logger.info(" Numba %s loaded - SimHash acceleration enabled", numba.__version__)
except ImportError:
    NUMBA_AVAILABLE = False
    logger.info("Numba not available - using pure Python SimHash (slower)")
if NUMBA_AVAILABLE:

    @numba.jit(nopython=True, cache=True, fastmath=True)
    def _update_vector_numba(v: np.ndarray, hash_int: np.int64, bits: int) -> None:
        """
        Оновлює вектор підрахунку для SimHash (JIT-compiled).

        Для кожного біта hash:
        - якщо біт=1: v[i] += 1
        - якщо біт=0: v[i] -= 1

        Args:
            v: numpy array для підрахунку
            hash_int: хеш токена як int64
            bits: кількість біт
        """
        temp = np.int64(hash_int)
        for i in range(bits):
            if temp & np.int64(1):
                v[i] += 1
            else:
                v[i] -= 1
            temp >>= 1

    @numba.jit(nopython=True, cache=True)
    def _finalize_simhash_numba(v: np.ndarray, bits: int) -> int:
        """
        Згортає вектор в SimHash (JIT-compiled).

        Біт = 1 якщо v[i] >= 0, інакше 0.

        Args:
            v: вектор підрахунку
            bits: кількість біт

        Returns:
            SimHash як int64
        """
        simhash = np.int64(0)
        for i in range(bits):
            if v[i] >= 0:
                simhash |= np.int64(1) << i
        return simhash

    @numba.jit(nopython=True, cache=True)
    def _hamming_distance_numba(hash1: int, hash2: int) -> int:
        """
        Numba-оптимізований Hamming distance.

        Використовує Brian Kernighan's algorithm для підрахунку бітів.

        Args:
            hash1: перший хеш як int
            hash2: другий хеш як int

        Returns:
            Hamming distance (кількість різних бітів)
        """
        xor = hash1 ^ hash2
        count = 0
        while xor:
            count += 1
            xor &= xor - 1  # Clear lowest set bit
        return count

    def compute_simhash_fast(tokens: List[str], bits: int = 64) -> str:
        """
        Numba-оптимізоване обчислення SimHash.

        Прискорення 10-50x порівняно з pure Python.

        Args:
            tokens: Список токенів (n-grams)
            bits: Кількість біт (default: 64)

        Returns:
            SimHash як hex string (16 символів для 64 біт)

        Example:
            >>> tokens = ["hello world", "world is", "is great"]
            >>> simhash = compute_simhash_fast(tokens)
            >>> print(simhash)  # e.g., "a1b2c3d4e5f67890"
        """
        if not tokens:
            return "0" * (bits // 4)

        v = np.zeros(bits, dtype=np.int32)
        # Для 64-бітної маски використовуємо Python int, не numpy
        mask = (1 << bits) - 1

        for token in tokens:
            # MD5 hash токена (беремо перші 64 біти)
            # usedforsecurity=False - MD5 для fingerprinting, не для безпеки
            token_hash = hashlib.md5(token.encode("utf-8"), usedforsecurity=False).hexdigest()
            # Обмежуємо значення до signed int64 range
            hash_int = int(token_hash[: bits // 4], 16) & mask
            # Конвертуємо в numpy int64 для Numba
            hash_int_np = np.int64(hash_int if hash_int < (1 << 63) else hash_int - (1 << 64))

            # Numba JIT call - основне прискорення тут
            _update_vector_numba(v, hash_int_np, bits)

        # Finalize (також JIT)
        simhash = _finalize_simhash_numba(v, bits)
        return format(int(simhash) & mask, f"0{bits // 4}x")

    def hamming_distance_fast(simhash1: str, simhash2: str) -> int:
        """
        Numba-оптимізований Hamming distance.

        Args:
            simhash1: Перший SimHash (hex string)
            simhash2: Другий SimHash (hex string)

        Returns:
            Hamming distance (0-64 для 64-бітного хешу)
        """
        hash1 = int(simhash1, 16)
        hash2 = int(simhash2, 16)
        return _hamming_distance_numba(hash1, hash2)

else:

    def compute_simhash_fast(tokens: List[str], bits: int = 64) -> str:
        """
        Pure Python fallback для SimHash.

        Використовується коли Numba недоступна.

        Args:
            tokens: Список токенів (n-grams)
            bits: Кількість біт (default: 64)

        Returns:
            SimHash як hex string
        """
        from array import array

        if not tokens:
            return "0" * (bits // 4)

        v = array("i", [0] * bits)
        mask = (1 << bits) - 1

        for token in tokens:
            # usedforsecurity=False - MD5 для fingerprinting, не для безпеки
            token_hash = hashlib.md5(token.encode("utf-8"), usedforsecurity=False).hexdigest()
            hash_int = int(token_hash[: bits // 4], 16) & mask

            for i in range(bits):
                v[i] += ((hash_int & 1) << 1) - 1
                hash_int >>= 1

        simhash = 0
        for i in range(bits):
            if v[i] >= 0:
                simhash |= 1 << i

        return format(simhash, f"0{bits // 4}x")

    def hamming_distance_fast(simhash1: str, simhash2: str) -> int:
        """
        Pure Python fallback для Hamming distance.

        Args:
            simhash1: Перший SimHash (hex string)
            simhash2: Другий SimHash (hex string)

        Returns:
            Hamming distance
        """
        hash1 = int(simhash1, 16)
        hash2 = int(simhash2, 16)
        xor_result = hash1 ^ hash2
        return bin(xor_result).count("1")


def is_numba_available() -> bool:
    """
    Перевіряє чи Numba доступна.

    Returns:
        True якщо Numba встановлена та працює
    """
    return NUMBA_AVAILABLE


def get_optimization_status() -> dict:
    """
    Повертає статус оптимізацій.

    Returns:
        Dict з інформацією про оптимізації
    """
    import sys

    status = {
        "numba_available": NUMBA_AVAILABLE,
        "implementation": "numba_jit" if NUMBA_AVAILABLE else "pure_python",
        "expected_speedup": "10-50x" if NUMBA_AVAILABLE else "1x (baseline)",
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
    }

    if NUMBA_AVAILABLE:
        status["numba_version"] = numba.__version__
        status["numpy_version"] = np.__version__

    return status


def benchmark_simhash(n_tokens: int = 1000, n_iterations: int = 100) -> dict:
    """
    Бенчмарк SimHash обчислень.

    Args:
        n_tokens: Кількість токенів
        n_iterations: Кількість ітерацій

    Returns:
        Dict з результатами бенчмарку
    """
    import time

    # Генеруємо тестові токени
    tokens = [f"token_{i} next_{i + 1} word_{i + 2}" for i in range(n_tokens)]

    # Warmup (важливо для Numba JIT)
    for _ in range(3):
        compute_simhash_fast(tokens[:10])

    # Benchmark
    start = time.perf_counter()
    for _ in range(n_iterations):
        compute_simhash_fast(tokens)
    elapsed = time.perf_counter() - start

    avg_time_ms = (elapsed / n_iterations) * 1000

    return {
        "implementation": "numba_jit" if NUMBA_AVAILABLE else "pure_python",
        "n_tokens": n_tokens,
        "n_iterations": n_iterations,
        "total_time_sec": round(elapsed, 3),
        "avg_time_ms": round(avg_time_ms, 3),
        "tokens_per_second": round(n_tokens * n_iterations / elapsed),
    }


__all__ = [
    "compute_simhash_fast",
    "hamming_distance_fast",
    "is_numba_available",
    "get_optimization_status",
    "benchmark_simhash",
]
