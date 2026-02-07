# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
"""Fast Bloom Filter implementation using Cython.

10-20x швидше за pybloom-live для __contains__ операції.

Build:
    cythonize -i bloom_filter.pyx
"""

from libc.stdint cimport uint8_t, uint32_t, uint64_t
from libc.stdlib cimport malloc, free, calloc
from libc.string cimport memset
from libc.math cimport log
import mmh3


cdef class BloomFilterFast:
    """
    Fast Bloom Filter using Cython + bit array.
    
    Використовує:
    - C bit array (uint8_t*) для мінімальної пам'яті
    - MurmurHash3 для hash functions
    - Inline C операції для швидкості
    
    Memory limits:
    - Default max: 512MB
    - Can be overridden with max_memory_mb parameter
    
    Usage:
        >>> bloom = BloomFilterFast(10_000_000, 0.001)
        >>> bloom.add("https://example.com")
        >>> "https://example.com" in bloom
        True
    """
    
    cdef uint8_t* bits
    cdef uint64_t size
    cdef uint64_t byte_size
    cdef int num_hashes
    cdef uint64_t count
    cdef double error_rate
    cdef uint64_t capacity
    cdef uint64_t max_memory_bytes
    
    # Default memory limit: 512MB
    DEF DEFAULT_MAX_MEMORY_MB = 512
    
    def __cinit__(self, uint64_t capacity=10_000_000, double error_rate=0.001, 
                  uint64_t max_memory_mb=DEFAULT_MAX_MEMORY_MB):
        """
        Ініціалізує Bloom Filter.
        
        Args:
            capacity: Очікувана кількість елементів (default: 10M)
            error_rate: Бажана ймовірність false positive (default: 0.001 = 0.1%)
            max_memory_mb: Максимальний розмір пам'яті в MB (default: 512MB)
            
        Raises:
            ValueError: Якщо параметри некоректні або перевищено ліміт пам'яті
            MemoryError: Якщо не вдалося виділити пам'ять
        """
        # Валідація параметрів
        if capacity == 0:
            raise ValueError("capacity must be > 0")
        if error_rate <= 0 or error_rate >= 1:
            raise ValueError("error_rate must be between 0 and 1 (exclusive)")
        if max_memory_mb == 0:
            raise ValueError("max_memory_mb must be > 0")
        
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        
        # Обчислюємо оптимальний розмір
        # m = -(n * ln(p)) / (ln(2)^2)
        cdef double ln2_sq = 0.4804530139182014  # (ln 2)^2
        self.size = <uint64_t>(-(capacity * log(error_rate)) / ln2_sq)
        
        # Мінімальний розмір
        if self.size < 64:
            self.size = 64
        
        # Обчислюємо кількість hash functions
        # k = (m / n) * ln(2)
        self.num_hashes = <int>((self.size / capacity) * 0.693147180559945)  # ln(2)
        
        if self.num_hashes < 1:
            self.num_hashes = 1
        elif self.num_hashes > 20:
            self.num_hashes = 20
        
        # Обчислюємо розмір в байтах
        self.byte_size = (self.size + 7) // 8
        
        # MEMORY LIMIT CHECK - захист від надмірного виділення пам'яті
        if self.byte_size > self.max_memory_bytes:
            raise ValueError(
                f"Bloom filter size ({self.byte_size / (1024*1024):.1f}MB) exceeds "
                f"memory limit ({max_memory_mb}MB). "
                f"Reduce capacity ({capacity:,}) or increase error_rate ({error_rate})"
            )
        
        # Виділяємо пам'ять (bit array)
        self.bits = <uint8_t*>calloc(self.byte_size, sizeof(uint8_t))
        if self.bits == NULL:
            raise MemoryError(
                f"Cannot allocate {self.byte_size / (1024*1024):.1f}MB for Bloom Filter"
            )
        
        self.count = 0
        self.error_rate = error_rate
        self.capacity = capacity
    
    def __dealloc__(self):
        """Звільняє пам'ять."""
        if self.bits != NULL:
            free(self.bits)
            self.bits = NULL
    
    cdef inline void _set_bit(self, uint64_t pos) noexcept nogil:
        """Встановлює біт в позиції pos."""
        cdef uint64_t byte_pos = pos >> 3  # pos // 8
        cdef uint8_t bit_pos = pos & 7      # pos % 8
        self.bits[byte_pos] = self.bits[byte_pos] | (1 << bit_pos)
    
    cdef inline bint _get_bit(self, uint64_t pos) noexcept nogil:
        """Перевіряє чи встановлений біт в позиції pos."""
        cdef uint64_t byte_pos = pos >> 3
        cdef uint8_t bit_pos = pos & 7
        return (self.bits[byte_pos] & (1 << bit_pos)) != 0
    
    cpdef void add(self, str item):
        """
        Додає елемент до Bloom Filter.
        
        Args:
            item: Елемент для додавання (str)
        """
        cdef bytes item_bytes = item.encode('utf-8')
        cdef int i
        cdef uint64_t hash_val
        cdef uint64_t pos
        
        for i in range(self.num_hashes):
            # MurmurHash3 з різними seeds
            hash_val = <uint64_t>(mmh3.hash(item_bytes, i) & 0xFFFFFFFF)
            pos = hash_val % self.size
            self._set_bit(pos)
        
        self.count += 1
    
    def __contains__(self, item):
        """
        Перевіряє чи елемент (можливо) є в Bloom Filter.
        
        Args:
            item: Елемент для перевірки
            
        Returns:
            True якщо можливо є (або false positive)
            False якщо точно немає
        """
        if not isinstance(item, str):
            return False
        
        cdef bytes item_bytes = item.encode('utf-8')
        cdef int i
        cdef uint64_t hash_val
        cdef uint64_t pos
        
        for i in range(self.num_hashes):
            hash_val = <uint64_t>(mmh3.hash(item_bytes, i) & 0xFFFFFFFF)
            pos = hash_val % self.size
            if not self._get_bit(pos):
                return False
        
        return True
    
    cpdef bint contains(self, str item):
        """
        Перевіряє чи елемент є в Bloom Filter (typed version).
        
        Args:
            item: str для перевірки
            
        Returns:
            True/False
        """
        cdef bytes item_bytes = item.encode('utf-8')
        cdef int i
        cdef uint64_t hash_val
        cdef uint64_t pos
        
        for i in range(self.num_hashes):
            hash_val = <uint64_t>(mmh3.hash(item_bytes, i) & 0xFFFFFFFF)
            pos = hash_val % self.size
            if not self._get_bit(pos):
                return False
        
        return True
    
    def __len__(self):
        """Повертає кількість доданих елементів."""
        return self.count
    
    @property
    def num_items(self):
        """Кількість доданих елементів."""
        return self.count
    
    @property
    def filter_capacity(self):
        """Capacity bloom filter."""
        return self.capacity
    
    @property
    def bit_size(self):
        """Розмір bit array."""
        return self.size
    
    @property
    def hash_count(self):
        """Кількість hash functions."""
        return self.num_hashes
    
    cpdef dict get_statistics(self):
        """
        Повертає статистику Bloom Filter.
        
        Returns:
            dict з статистикою
        """
        cdef double fill_ratio = <double>self.count / <double>self.capacity if self.capacity > 0 else 0.0
        cdef double memory_mb = <double>self.byte_size / (1024.0 * 1024.0)
        cdef double max_memory_mb = <double>self.max_memory_bytes / (1024.0 * 1024.0)
        
        return {
            "count": self.count,
            "capacity": self.capacity,
            "error_rate": self.error_rate,
            "bit_size": self.size,
            "byte_size": self.byte_size,
            "num_hashes": self.num_hashes,
            "memory_usage_bytes": self.byte_size,
            "memory_usage_mb": memory_mb,
            "max_memory_mb": max_memory_mb,
            "fill_ratio": fill_ratio,
            "implementation": "cython_native",
        }
    
    cpdef void clear(self):
        """Очищує Bloom Filter."""
        memset(self.bits, 0, self.byte_size)
        self.count = 0
