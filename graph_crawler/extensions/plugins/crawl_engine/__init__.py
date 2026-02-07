"""Crawl Engine плагіни - ML-керований краулінг.

Crawl Engine плагіни працюють на вищому рівні ніж Node плагіни і можуть:
- Приоритизувати URL перед скануванням
- Вирішувати чи сканувати конкретний URL
- Використовувати ML для оптимізації послідовності краулінгу
- Впливати на Scheduler через абстракцію (без прямого зв'язування)

Архітектура:
1. BaseEnginePlugin - базовий клас для crawl engine плагінів
2. EnginePriorityProvider - абстракція для передачі пріоритетів в Scheduler
3. SmartCrawlEnginePlugin - ML плагін для інтелектуального краулінгу
4. VectorCrawlEnginePlugin - векторний плагін для cosine similarity пріоритизації

Приклад використання:
    >>> from graph_crawler.extensions.plugins.crawl_engine import (
    ...     SmartCrawlEnginePlugin,
    ...     VectorCrawlEnginePlugin,
    ...     EnginePriorityProvider
    ... )
    >>> 
    >>> # Створюємо ML плагін
    >>> ml_plugin = SmartCrawlEnginePlugin(
    ...     search_prompt="Шукаю контент про Гаррі Поттера",
    ...     config={'min_relevance_score': 0.7}
    ... )
    >>> 
    >>> # Або векторний плагін для пошуку вакансій
    >>> vector_plugin = VectorCrawlEnginePlugin(
    ...     keywords=['jobs', 'vacancy', 'career', 'робота', 'вакансія'],
    ...     min_priority=1,
    ...     max_priority=6,
    ... )
    >>> 
    >>> # Створюємо provider для Scheduler
    >>> provider = EnginePriorityProvider(plugins=[ml_plugin])
    >>> 
    >>> # Краулер автоматично використає пріоритизацію
    >>> graph = gc.crawl("https://example.com", engine_plugins=[ml_plugin])

Різниця з Node плагінами:
- Node плагіни: працюють ПІСЛЯ сканування HTML (аналіз контенту)
- Engine плагіни: працюють ПЕРЕД скануванням (керування послідовністю)
"""

from graph_crawler.extensions.plugins.crawl_engine.base import (
    BaseEnginePlugin,
    EnginePluginContext,
    EnginePluginType,
)
from graph_crawler.extensions.plugins.crawl_engine.priority_provider import (
    EnginePriorityProvider,
)
from graph_crawler.extensions.plugins.crawl_engine.smart_crawl import (
    SmartCrawlEnginePlugin,
)
from graph_crawler.extensions.plugins.crawl_engine.vector_crawl import (
    VectorCrawlEnginePlugin,
)

__all__ = [
    "BaseEnginePlugin",
    "EnginePluginContext",
    "EnginePluginType",
    "EnginePriorityProvider",
    "SmartCrawlEnginePlugin",
    "VectorCrawlEnginePlugin",
]
