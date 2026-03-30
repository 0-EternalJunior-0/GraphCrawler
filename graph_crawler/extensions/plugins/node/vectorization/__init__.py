"""Плагіни векторизації тексту для Node.

Модуль містить плагіни для векторизації текстового контенту з веб-сторінок:
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
