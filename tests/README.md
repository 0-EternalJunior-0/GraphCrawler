# GraphCrawler Tests

Цей каталог містить тести для GraphCrawler v3.2.0.

## Структура

```
tests/
├── unit/                    # Юніт тести (пишуться іншою командою)
│   ├── domain/             # Тести domain layer
│   ├── application/        # Тести application layer
│   ├── infrastructure/     # Тести infrastructure layer
│   └── shared/             # Тести shared utilities
├── integration/            # Інтеграційні тести
│   ├── test_crawl_flow.py           # 26 тестів - краулінг flow
│   ├── test_spider_with_driver.py   # 17 тестів - Spider з драйверами
│   ├── test_spider_with_storage.py  # 17 тестів - Spider зі storage
│   └── test_plugins_integration.py  # 13 тестів - plugins інтеграція
├── e2e/                    # End-to-end тести
│   ├── test_full_crawl.py          # 15 тестів - повний E2E flow
│   └── test_distributed_crawl.py   # 7 тестів - distributed краулінг
├── fixtures/               # Тестові фікстури
│   ├── html/              # HTML фікстури
│   └── graphs/            # Graph фікстури
├── conftest.py            # Pytest фікстури
└── README.md              # Цей файл
```

## Запуск тестів

### Всі тести
```bash
pytest tests/
```

### Тільки юніт тести
```bash
pytest tests/unit/
```

### Тільки інтеграційні тести
```bash
pytest tests/integration/ -v
```

### Тільки E2E тести
```bash
pytest tests/e2e/ -v
```

### З покриттям коду
```bash
pytest tests/ --cov=graph_crawler --cov-report=html
```

### Конкретний файл
```bash
pytest tests/integration/test_crawl_flow.py -v
```

### Конкретний тест
```bash
pytest tests/integration/test_crawl_flow.py::TestBasicCrawlFlow::test_crawl_single_page_sync -v
```

## Markers

Тести позначені різними markers:

- `@pytest.mark.integration` - інтеграційні тести (потребують мережу)
- `@pytest.mark.e2e` - end-to-end тести (повний flow)
- `@pytest.mark.distributed` - distributed краулінг (потребує Celery + Redis)
- `@pytest.mark.playwright` - тести що потребують Playwright
- `@pytest.mark.asyncio` - async тести

### Запуск тестів за marker
```bash
# Тільки інтеграційні
pytest -m integration

# Тільки E2E
pytest -m e2e

# Виключити distributed (не потребують Celery)
pytest -m "not distributed"

# Тільки async тести
pytest -m asyncio
```

## Інтеграційні тести

### test_crawl_flow.py (26 тестів)
Тестує повний flow краулінгу з різними параметрами:
- Базовий краулінг (sync/async)
- Різні драйвери (HTTP, Async)
- Різні storage (memory, JSON, SQLite)
- Фільтри (domain, path, URL rules)
- Обробка помилок (404, timeout)
- Реальні сайти з багатьма посиланнями

**Використовувані сайти:**
- https://books.toscrape.com/ - багато категорій та книг
- https://quotes.toscrape.com/ - пагінація
- https://scrapethissite.com/ - різні типи даних
- https://httpbin.org/ - тестування HTTP функцій

### test_spider_with_driver.py (17 тестів)
Тестує Spider з різними драйверами:
- HTTP Driver (базовий)
- Async Driver (швидший)
- Обробка redirects, великого HTML
- Витягування посилань
- Concurrent краулінг
- Edge cases (порожні сторінки, циклічні посилання)

### test_spider_with_storage.py (17 тестів)
Тестує Spider з різними storage:
- Memory Storage (найшвидший)
- JSON Storage (персистентний)
- SQLite Storage (база даних)
- Порівняння продуктивності
- Збереження/завантаження графів
- Edge cases (порожні графи, великі графи)

### test_plugins_integration.py (13 тестів)
Тестує систему plugins:
- Базова інтеграція plugins
- Async plugins
- Множинні plugins
- Custom поведінка
- Обробка помилок в plugins

## E2E тести

### test_full_crawl.py (15 тестів)
Повний end-to-end flow:
- Комплексний краулінг реальних сайтів
- Краулінг з фільтрами
- Збереження в різні storage
- Async паралельний краулінг
- Краулінг складних сайтів (пагінація, категорії, глибока структура)
- Тести продуктивності

### test_distributed_crawl.py (7 тестів)
Distributed краулінг з Celery:
- Базовий distributed краулінг
- Паралельний краулінг декількох сайтів
- Великі сайти
- Fallback коли Celery недоступний

**Примітка:** Більшість distributed тестів пропускаються якщо Celery + Redis не налаштовані.

## Фікстури

### HTML фікстури (tests/fixtures/html/)
- `simple_page.html` - проста сторінка з посиланнями
- `complex_page.html` - складна сторінка з навігацією, статтями
- `nested_page.html` - вкладена структура посилань
- `with_metadata.html` - сторінка з багатими метаданими

### Фікстури в conftest.py
- `temp_dir` - тимчасова директорія
- `sample_node` - зразкова нода
- `sample_edge` - зразкове ребро
- `sample_graph` - зразковий граф
- `sample_html` - зразковий HTML
- `html_fixtures_dir` - шлях до HTML фікстур
- `load_html_fixture` - функція завантаження HTML фікстур

## CI/CD

Тести інтегровані в CI/CD pipeline (GitLab CI):

```yaml
test:integration:
  stage: test
  script:
    - pytest tests/integration/ -v
  allow_failure: false

test:e2e:
  stage: test
  script:
    - pytest tests/e2e/ -v -m "not distributed"
  allow_failure: false
```

## Coverage Goals

- **Unit tests:** 80%+ coverage (domain/application/infrastructure)
- **Integration tests:** Ключові сценарії
- **E2E tests:** Повний user flow

**Поточний прогрес:** ~25% → Ціль: 60%+

## Примітки

1. **Реальні сайти:** Інтеграційні та E2E тести використовують реальні сайти, тому потребують інтернет з'єднання.

2. **Request delay:** Всі тести використовують `request_delay=0.1` для ввічливості до серверів.

3. **Async тести:** Використовується `pytest-asyncio` для async тестів. Додайте `@pytest.mark.asyncio` до async тест функцій.

4. **Distributed тести:** Вимагають запущених Celery worker + Redis. Пропускаються автоматично якщо недоступні.

5. **Timeout:** Всі тести мають timeout 30 секунд (налаштовується в pytest.ini).

## Додавання нових тестів

### Integration test
```python
import pytest
from graph_crawler import crawl

@pytest.mark.integration
def test_my_integration():
    graph = crawl("https://example.com/", max_depth=1, max_pages=5)
    assert len(graph.nodes) > 0
```

### E2E test
```python
import pytest
from graph_crawler import crawl

@pytest.mark.e2e
def test_my_e2e():
    graph = crawl(
        "https://example.com/",
        max_depth=2,
        max_pages=20,
        storage="json",
        storage_dir="/tmp/crawl"
    )
    assert len(graph.nodes) > 5
```

### Async test
```python
import pytest
from graph_crawler import async_crawl

@pytest.mark.integration
@pytest.mark.asyncio
async def test_my_async():
    graph = await async_crawl("https://example.com/", max_depth=1)
    assert len(graph.nodes) > 0
```

## Troubleshooting

### Тести падають з timeout
- Збільшіть timeout в pytest.ini
- Або зменшіть max_pages в тесті

### Тести падають з мережевими помилками
- Перевірте інтернет з'єднання
- Деякі сайти можуть бути недоступні
- Можна skip мережеві тести: `pytest -m "not integration and not e2e"`

### Async тести не працюють
- Встановіть pytest-asyncio: `pip install pytest-asyncio`
- Додайте `asyncio_mode = auto` в pytest.ini

### Coverage не працює
- Встановіть pytest-cov: `pip install pytest-cov`
- Запустіть: `pytest --cov=graph_crawler`

## Контакти

Питання та issues: https://gitlab.com/demoprogrammer/web_graf/issues
