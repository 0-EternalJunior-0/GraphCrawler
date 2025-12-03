"""Плагіни векторизації тексту для Node.

Модуль містить плагіни для векторизації текстового контенту з веб-сторінок:
- RealTimeVectorizerPlugin: Векторизація під час краулінгу (ON_AFTER_SCAN)
- BatchVectorizerPlugin: Пакетна векторизація після краулінгу (AFTER_CRAWL)

Нові функції (Alpha v0.1):
- пошук / search: Векторний пошук по графу
- групування / cluster: Кластеризація нод
- порівняння / compare: Порівняння векторів (вектор-вектор, текст-вектор)

Приклад використання:
    >>> from graph_crawler.extensions.plugins.node.vectorization import (
    ...     RealTimeVectorizerPlugin, BatchVectorizerPlugin,
    ...     search, cluster, compare
    ... )
    >>>
    >>> # Векторний пошук
    >>> results = search(graph, "Python developer", top_k=10)
    >>>
    >>> # Кластеризація
    >>> clusters = cluster(graph, method='kmeans', n_clusters=5)
    >>>
    >>> # Порівняння векторів
    >>> result = compare(vector1, vector2)  # вектор vs вектор
    >>> result = compare(vector, "текст")   # вектор vs текст (автовекторизація)
"""

from graph_crawler.extensions.plugins.node.vectorization.batch_vectorizer import (
    BatchVectorizerPlugin,
)
from graph_crawler.extensions.plugins.node.vectorization.realtime_vectorizer import (
    RealTimeVectorizerPlugin,
)
from graph_crawler.extensions.plugins.node.vectorization.utils import (  # Англійське API (аліаси); Допоміжні
    ClusteringMethod,
    SimilarityMetric,
    clear_model_cache,
    cluster,
    compare,
    cosine_similarity,
    dot_product,
    euclidean_distance,
    search,
    vectorize_batch,
    vectorize_text,
)

__all__ = [
    # Плагіни
    "RealTimeVectorizerPlugin",
    "BatchVectorizerPlugin",
    "search",
    "cluster",
    "compare",
    # Метрики та методи
    "SimilarityMetric",
    "ClusteringMethod",
    # Утиліти
    "cosine_similarity",
    "euclidean_distance",
    "dot_product",
    "vectorize_text",
    "vectorize_batch",
    "clear_model_cache",
]
