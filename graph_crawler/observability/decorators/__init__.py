"""Модуль DECORATORS - Декоратори для додавання функціональності.

Декоратори дозволяють додавати cross-cutting concerns без зміни основної логіки:

**Доступні декоратори:**

1. **@retry** (decorators/retry.py)
   - Автоматичні повтори при помилках
   - Exponential backoff
   - Конфігуровані винятки

   Параметри:
   - max_attempts: int - максимум спроб (default: 3)
   - delay: float - затримка між спробами в секундах (default: 1.0)
   - exponential_backoff: bool - експоненційна затримка (default: True)
   - exceptions: Tuple - винятки для обробки (default: (Exception,))

2. **@log_execution** (decorators/log.py)
   - Логування виконання функцій
   - Логування помилок
   - Опціонально: аргументи та результат

   Параметри:
   - level: int - рівень логування (default: logging.INFO)
   - include_args: bool - включити аргументи (default: False)
   - include_result: bool - включити результат (default: False)

3. **@measure_time** (decorators/timing.py)
   - Вимірювання часу виконання
   - Логування тривалості
   - Корисно для performance profiling

   Параметри:
   - log_level: int - рівень логування (default: logging.DEBUG)

4. **@cache** (decorators/cache.py)
   - Кешування результатів функцій
   - In-memory або file-based cache
   - TTL (Time To Live)

   Параметри:
   - ttl: int - час життя кешу в секундах (default: 3600)
   - cache_type: str - тип кешу: 'memory' або 'file' (default: 'memory')

**Приклади використання:**

```python
import logging
from graph_crawler.decorators import retry, log_execution, measure_time, cache

# 1. Retry декоратор
@retry(max_attempts=3, delay=1.0, exponential_backoff=True)
def fetch_url(url: str):
    '''3 спроби з exponential backoff: 1s, 2s, 4s'''
    response = requests.get(url, timeout=30)
    return response.text

# 2. Logging декоратор
@log_execution(level=logging.DEBUG, include_args=True)
def process_data(data: dict):
    '''Логує початок, завершення, помилки'''
    return data['result']

# 3. Timing декоратор
@measure_time
def slow_operation():
    '''Вимірює та логує час виконання'''
    time.sleep(2)
    return "done"

# 4. Cache декоратор
@cache(ttl=3600, cache_type='memory')
def expensive_computation(n: int):
    '''Результат кешується на 1 годину'''
    return sum(range(n))

# 5. Комбінація декораторів
@log_execution(level=logging.INFO)
@retry(max_attempts=3, delay=1.0)
@measure_time
def robust_fetch(url: str):
    '''Логування + Retry + Timing'''
    return requests.get(url).text
```

**Використання в Драйверах:**

```python
from graph_crawler.infrastructure.transport import BaseDriver
from graph_crawler.decorators import retry, log_execution, measure_time

class HTTPDriver(BaseDriver):

    @log_execution(level=logging.DEBUG)
    @retry(max_attempts=3, delay=1.0)
    @measure_time
    def fetch(self, url: str) -> Optional[Dict[str, Any]]:
        '''Автоматично додає:
        - Логування
        - Повтори при помилці
        - Вимірювання часу
        '''
        response = self.session.get(url, timeout=30)
        return {
            'url': url,
            'html': response.text,
            'status_code': response.status_code,
        }
```

**Best Practices:**

1. **Порядок декораторів:**
   ```python
   @log_execution       # Зовнішній - логує все
   @retry               # Середній - повторює
   @measure_time        # Внутрішній - вимірює
   def function():
       pass
   ```

2. **Використання @retry:**
   - Тільки для network requests
   - Вказуйте конкретні винятки (ConnectionError, Timeout)
   - Обережно з exponential_backoff (може бути довго)

3. **Використання @log_execution:**
   - DEBUG рівень для детального логування
   - INFO рівень для важливих операцій
   - Не логуйте чутливі дані (passwords, tokens)

4. **Використання @cache:**
   - Тільки для pure functions (однакові входи = однакові виходи)
   - Встановіть TTL відповідно до частоти змін даних
   - Memory cache: швидко, але обмежено RAM
   - File cache: повільніше, але персистентне

**Переваги:**
- Чистий код - сепарація concerns
- DRY - не повторювати логіку
- Тестування - легко тестувати
- Композиція - комбінувати декоратори
"""

from .cache import cache
from .log import log_execution
from .retry import retry
from .timing import measure_time

__all__ = ["retry", "cache", "log_execution", "measure_time"]
