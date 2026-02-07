# Native Acceleration Layer v4.3

## ⚠️ ВАЖЛИВО: Cross-Platform Build

**НЕ комітьте `.so` файли!** Вони platform-specific.

Кожна платформа потребує власної збірки:
- Linux x86_64: `_*.cpython-3XX-x86_64-linux-gnu.so`
- Linux ARM64: `_*.cpython-3XX-aarch64-linux-gnu.so`
- macOS: `_*.cpython-3XX-darwin.so`
- Windows: `_*.cpython-3XX-win_amd64.pyd`

## Швидкий старт

```bash
# 1. Встановити залежності
pip install cython>=3.0.0 mmh3>=3.0.0 setuptools wheel

# 2. Зібрати extensions для ВАШОЇ платформи
cd graph_crawler/native
python setup.py build_ext --inplace

# 3. Перевірити
python -c "
from graph_crawler.native import get_native_status
print(get_native_status())
"
```

## Fallback Механізм

Якщо native extensions не скомпільовані або несумісні, автоматично використовується pure Python:

```python
from graph_crawler.native import is_valid_url_fast
# Працює завжди - або native (швидко), або pure Python (повільніше)
```

## Скомпільовані модулі

| Модуль | Файл | Опис |
|--------|------|------|
| URL Utils | `_url_utils.so` | Швидкі URL операції |
| HTML Parser | `_html_parser.so` | Витягування посилань |
| Bloom Filter | `_bloom_filter.so` | Швидкий фільтр seen URLs |

## Benchmark результати

| Оптимізація | Швидше ніж fallback |
|-------------|---------------------|
| HTML Parser (Native) | **24x** швидше ніж BeautifulSoup |
| HTML Parser (selectolax) | **19x** швидше ніж BeautifulSoup |
| JSON (orjson) | **10x** швидше ніж stdlib json |
| Bloom Filter (Native) | **2.7x** швидше ніж pybloom-live |
| URL Utils (Native) | **1.1x** швидше (Python вже кешований) |

**Загальне прискорення: ~8x!**

## Доступні функції

### URL Utils (`_url_utils.so`)
```python
from _url_utils import (
    is_valid_url_fast,      # Перевірка валідності URL
    normalize_url_fast,     # Нормалізація (видалення #fragment)
    get_domain_fast,        # Витягування домену
    make_absolute_fast,     # Перетворення відносного URL в абсолютний
    filter_valid_urls,      # Batch фільтрація валідних URL
    normalize_urls,         # Batch нормалізація
)
```

### HTML Parser (`_html_parser.so`)
```python
from _html_parser import (
    parse_links_fast,       # Витягування посилань з HTML
    parse_all_urls_fast,    # Витягування всіх URL (href, src)
    count_links,            # Підрахунок посилань
)
```

### Bloom Filter (`_bloom_filter.so`)
```python
from _bloom_filter import BloomFilterFast

bloom = BloomFilterFast(capacity=10_000_000, error_rate=0.001)
bloom.add("https://example.com")
print("https://example.com" in bloom)  # True
print(bloom.get_statistics())
```

## Fallback

Якщо native extensions не скомпільовані, автоматично використовується pure Python версія:

```python
from graph_crawler.native import is_valid_url_fast
# Працює завжди - або native, або fallback
```

## Запуск бенчмарку

```bash
cd /app/web_graf
python benchmark_optimizations.py
```

