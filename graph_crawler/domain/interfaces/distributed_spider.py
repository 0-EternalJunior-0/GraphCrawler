"""Protocol для розподілених краулерів (Celery/Multiprocess).

Цей інтерфейс відрізняється від ISpider тим, що:
- Sync API замість async (для сумісності з Celery/Multiprocess)
- Не потребує pause/resume (керуються через Celery/Task manager)
- Має методи для роботи з batch tasks та worker pools

"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class IDistributedSpider(Protocol):
    """
    Sync інтерфейс для розподілених краулерів.
    
    Використовується для:
    - CeleryBatchSpider (Celery batch tasks)
    - MultiprocessSpider (local multiprocessing)
    - CelerySpider (deprecated, single URL per task)
    
    На відміну від ISpider:
    - Sync API (не async) - для сумісності з Celery/Multiprocess
    - Без pause/resume - керування через Celery/Task manager
    - Підтримка часткових результатів (get_partial_graph)
    """

    def crawl(self):
        """
        Sync запуск процесу краулінгу.
        
        Returns:
            Graph з результатами краулінгу
        """
        ...

    def get_stats(self) -> dict:
        """
        Повертає статистику краулінгу.
        
        Returns:
            Dict з метриками:
            - pages_crawled: кількість просканованих сторінок
            - mode: режим роботи (celery_batch/multiprocess/celery)
            - workers/batch_size: параметри паралелізації
            - elapsed_time: час роботи
        """
        ...

    def get_partial_graph(self):
        """
        Повертає частковий граф (для випадку timeout/shutdown).
        
        Корисно для:
        - Graceful shutdown
        - Timeout handling
        - Часткові результати при помилках
        
        Returns:
            Поточний стан Graph
        """
        ...
