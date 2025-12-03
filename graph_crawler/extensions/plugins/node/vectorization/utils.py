"""Утиліти для векторизації тексту.

Модуль надає функції для:
- Lazy loading моделі sentence-transformers
- Векторизації тексту з фіксованим розміром
- Кешування моделі для швидкості
- Векторний пошук (search)
- Групування/кластеризація (clustering)
- Порівняння векторів (similarity)

Використовує існуючі утиліти graph_crawler:
- HTMLUtils для очищення тексту
- Константи з constants.py
"""

import logging
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

from graph_crawler.shared.constants import MAX_TEXT_LENGTH

# Використовуємо існуючі утиліти замість дублювання коду
from graph_crawler.shared.utils.html_utils import HTMLUtils


class SimilarityMetric(Enum):
    """Метрики схожості для порівняння векторів."""

    COSINE = "cosine"  # Косинусна схожість (індустріальний стандарт)
    EUCLIDEAN = "euclidean"  # Евклідова відстань
    DOT = "dot"  # Скалярний добуток


class ClusteringMethod(Enum):
    """Методи кластеризації."""

    KMEANS = "kmeans"  # K-Means (швидкий, потребує k)
    DBSCAN = "dbscan"  # DBSCAN (автоматично визначає кластери)
    HIERARCHICAL = "hierarchical"  # Ієрархічна кластеризація


logger = logging.getLogger(__name__)

# Глобальний кеш моделі (Singleton pattern)
_model_cache = {}


class VectorizationError(Exception):
    """Помилка векторизації."""

    pass


def clean_text(text: str) -> str:
    """
    Очищає текст для векторизації.

    Використовує HTMLUtils.sanitize_text але без обмеження довжини
    та без HTML escape (для векторизації нам потрібен чистий текст).

    Args:
        text: Вхідний текст

    Returns:
        Очищений текст
    """
    if not text:
        return ""

    # Видаляємо зайві пробіли (як у HTMLUtils)
    text = " ".join(text.split())

    return text.strip()


def get_model(model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"):
    """
    Отримує модель sentence-transformers з кешу або завантажує нову.

    Lazy Loading: Модель завантажується тільки при першому виклику.
    Singleton Pattern: Одна модель на всю програму для економії пам'яті.

    Args:
        model_name: Назва моделі з HuggingFace Hub

    Returns:
        SentenceTransformer модель

    Raises:
        VectorizationError: Якщо модель не вдалося завантажити
    """
    # Перевіряємо кеш
    if model_name in _model_cache:
        logger.debug(f"Using cached model: {model_name}")
        return _model_cache[model_name]

    try:
        # Lazy import - sentence-transformers завантажується тільки коли потрібен
        from sentence_transformers import SentenceTransformer

        logger.info(f"Loading sentence-transformers model: {model_name}...")
        model = SentenceTransformer(model_name)

        # Кешуємо модель
        _model_cache[model_name] = model
        logger.info(
            f"Model {model_name} loaded successfully. "
            f"Vector dimension: {model.get_sentence_embedding_dimension()}"
        )

        return model

    except ImportError as e:
        raise VectorizationError(
            f"sentence-transformers is not installed. "
            f"Please install it: pip install sentence-transformers\n"
            f"Error: {e}"
        )
    except Exception as e:
        raise VectorizationError(
            f"Failed to load model '{model_name}': {e}\n"
            f"Make sure the model name is correct and you have internet connection."
        )


def vectorize_text(
    text: str,
    model_name: str = "paraphrase-multilingual-MiniLM-L12-v2",
    target_size: int = 512,
    clean: bool = True,
) -> np.ndarray:
    """
    Векторизує текст в числовий вектор фіксованого розміру.

    Args:
        text: Вхідний текст для векторизації
        model_name: Назва моделі sentence-transformers
        target_size: Цільовий розмір вектору (за замовчуванням 512)
        clean: Чи очищати текст перед векторизацією

    Returns:
        numpy array з вектором розміру target_size

    Raises:
        VectorizationError: Якщо векторизація не вдалася
    """
    if not text or not text.strip():
        logger.warning("Empty text provided for vectorization, returning zero vector")
        return np.zeros(target_size, dtype=np.float32)

    try:
        # Очищення тексту
        if clean:
            text = clean_text(text)
            if not text:
                logger.warning(
                    "Text became empty after cleaning, returning zero vector"
                )
                return np.zeros(target_size, dtype=np.float32)

        # Отримуємо модель
        model = get_model(model_name)

        # Векторизація
        embedding = model.encode(text, convert_to_numpy=True)

        # Перевіряємо розмір
        original_size = embedding.shape[0]

        if original_size == target_size:
            return embedding.astype(np.float32)
        elif original_size < target_size:
            # Розширюємо вектор (padding нулями)
            logger.debug(f"Padding vector from {original_size} to {target_size}")
            padded = np.zeros(target_size, dtype=np.float32)
            padded[:original_size] = embedding
            return padded
        else:
            # Зменшуємо вектор (truncate)
            logger.debug(f"Truncating vector from {original_size} to {target_size}")
            return embedding[:target_size].astype(np.float32)

    except VectorizationError:
        raise
    except Exception as e:
        raise VectorizationError(f"Failed to vectorize text: {e}")


def vectorize_batch(
    texts: List[str],
    model_name: str = "paraphrase-multilingual-MiniLM-L12-v2",
    target_size: int = 512,
    clean: bool = True,
    batch_size: int = 64,
) -> List[np.ndarray]:
    """
    Векторизує список текстів батчами для швидкості.

    Batch-обробка значно швидша ніж векторизація по одному тексту,
    оскільки модель може використовувати GPU паралелізм.

    Args:
        texts: Список текстів для векторизації
        model_name: Назва моделі sentence-transformers
        target_size: Цільовий розмір вектору
        clean: Чи очищати тексти перед векторизацією
        batch_size: Розмір батчу для обробки

    Returns:
        Список numpy arrays з векторами

    Raises:
        VectorizationError: Якщо векторизація не вдалася
    """
    if not texts:
        return []

    try:
        # Очищення текстів
        if clean:
            cleaned_texts = [clean_text(text) if text else "" for text in texts]
        else:
            cleaned_texts = texts

        # Отримуємо модель
        model = get_model(model_name)

        # Векторизація батчами
        all_embeddings = []

        for i in range(0, len(cleaned_texts), batch_size):
            batch_texts = cleaned_texts[i : i + batch_size]

            logger.debug(
                f"Vectorizing batch {i // batch_size + 1}/{(len(cleaned_texts) + batch_size - 1) // batch_size}: "
                f"{len(batch_texts)} texts"
            )

            # Обробляємо порожні тексти
            batch_embeddings = []
            for text in batch_texts:
                if not text or not text.strip():
                    batch_embeddings.append(np.zeros(target_size, dtype=np.float32))
                else:
                    embedding = model.encode(text, convert_to_numpy=True)

                    # Підгонка до цільового розміру
                    if len(embedding) == target_size:
                        batch_embeddings.append(embedding.astype(np.float32))
                    elif len(embedding) < target_size:
                        padded = np.zeros(target_size, dtype=np.float32)
                        padded[: len(embedding)] = embedding
                        batch_embeddings.append(padded)
                    else:
                        batch_embeddings.append(
                            embedding[:target_size].astype(np.float32)
                        )

            all_embeddings.extend(batch_embeddings)

        logger.info(f"Vectorized {len(all_embeddings)} texts successfully")
        return all_embeddings

    except VectorizationError:
        raise
    except Exception as e:
        raise VectorizationError(f"Failed to vectorize batch: {e}")


def clear_model_cache():
    """
    Очищає кеш моделей для звільнення пам'яті.

    Викликайте цю функцію після завершення векторизації,
    якщо потрібно звільнити пам'ять.
    """
    global _model_cache
    if _model_cache:
        logger.info(f"Clearing model cache ({len(_model_cache)} models)")
        _model_cache.clear()


# =============================================================================
# НОВІ ФУНКЦІЇ: Пошук, Порівняння, Групування
# =============================================================================


def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """
    Обчислює косинусну схожість між двома векторами.

    Косинусна схожість - індустріальний стандарт для семантичного пошуку.
    Значення від -1 до 1, де 1 = ідентичні, 0 = ортогональні, -1 = протилежні.

    Args:
        vec1: Перший вектор
        vec2: Другий вектор

    Returns:
        Значення схожості від -1 до 1
    """
    vec1 = np.asarray(vec1, dtype=np.float32)
    vec2 = np.asarray(vec2, dtype=np.float32)

    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return float(np.dot(vec1, vec2) / (norm1 * norm2))


def euclidean_distance(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """
    Обчислює евклідову відстань між двома векторами.

    Менше значення = більша схожість.

    Args:
        vec1: Перший вектор
        vec2: Другий вектор

    Returns:
        Евклідова відстань (>= 0)
    """
    vec1 = np.asarray(vec1, dtype=np.float32)
    vec2 = np.asarray(vec2, dtype=np.float32)
    return float(np.linalg.norm(vec1 - vec2))


def dot_product(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """
    Обчислює скалярний добуток двох векторів.

    Args:
        vec1: Перший вектор
        vec2: Другий вектор

    Returns:
        Скалярний добуток
    """
    vec1 = np.asarray(vec1, dtype=np.float32)
    vec2 = np.asarray(vec2, dtype=np.float32)
    return float(np.dot(vec1, vec2))


def compare(
    input1: Union[np.ndarray, List[float], str],
    input2: Union[np.ndarray, List[float], str],
    metric: Union[SimilarityMetric, str] = SimilarityMetric.COSINE,
    model_name: str = "paraphrase-multilingual-MiniLM-L12-v2",
    vector_size: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Порівнює два вектори або текст з вектором.

    Підтримує:
    - Вектор vs Вектор
    - Текст vs Вектор (автовекторизація тексту)
    - Текст vs Текст

    Args:
        input1: Перший вектор або текст
        input2: Другий вектор або текст
        metric: Метрика схожості (cosine за замовчуванням - індустріальний стандарт)
        model_name: Назва моделі для автовекторизації тексту
        vector_size: Розмір вектору (автоматично визначається з вхідних векторів)

    Returns:
        Словник з результатами:
        {
            'similarity': float,  # Значення схожості
            'metric': str,        # Використана метрика
            'is_similar': bool,   # True якщо схожість > 0.5 (для cosine)
            'input1_type': str,   # 'vector' або 'text'
            'input2_type': str    # 'vector' або 'text'
        }

    Приклад:
        >>> # Порівняння двох векторів
        >>> result = compare(vector1, vector2)
        >>> print(result['similarity'])

        >>> # Порівняння тексту з вектором
        >>> result = compare(vector, "Привіт світ")
        >>> print(result['similarity'])
    """
    # Нормалізуємо метрику
    if isinstance(metric, str):
        metric = SimilarityMetric(metric.lower())

    # Автоматичне визначення розміру вектора
    auto_vector_size = vector_size

    # Визначаємо розмір з першого input, якщо це вектор
    if auto_vector_size is None:
        if isinstance(input1, (np.ndarray, list)) and not isinstance(input1, str):
            auto_vector_size = (
                len(input1) if isinstance(input1, list) else input1.shape[0]
            )
        elif isinstance(input2, (np.ndarray, list)) and not isinstance(input2, str):
            auto_vector_size = (
                len(input2) if isinstance(input2, list) else input2.shape[0]
            )
        else:
            # Обидва текст - використовуємо натуральний розмір моделі
            model = get_model(model_name)
            auto_vector_size = model.get_sentence_embedding_dimension()

    logger.debug(f"Auto-detected vector_size: {auto_vector_size}")

    # Визначаємо типи входів та конвертуємо
    def to_vector(inp) -> Tuple[np.ndarray, str]:
        if isinstance(inp, str):
            # Це текст - векторизуємо з автоматичним розміром
            vec = vectorize_text(
                inp, model_name=model_name, target_size=auto_vector_size
            )
            return vec, "text"
        elif isinstance(inp, list):
            return np.array(inp, dtype=np.float32), "vector"
        else:
            return np.asarray(inp, dtype=np.float32), "vector"

    vec1, type1 = to_vector(input1)
    vec2, type2 = to_vector(input2)

    # Обчислюємо схожість
    if metric == SimilarityMetric.COSINE:
        similarity = cosine_similarity(vec1, vec2)
        is_similar = similarity > 0.5
    elif metric == SimilarityMetric.EUCLIDEAN:
        distance = euclidean_distance(vec1, vec2)
        # Конвертуємо відстань в схожість (0-1)
        similarity = 1.0 / (1.0 + distance)
        is_similar = similarity > 0.5
    elif metric == SimilarityMetric.DOT:
        similarity = dot_product(vec1, vec2)
        is_similar = similarity > 0.0
    else:
        raise ValueError(f"Невідома метрика: {metric}")

    return {
        "similarity": similarity,
        "metric": metric.value,
        "is_similar": is_similar,
        "input1_type": type1,
        "input2_type": type2,
    }


def search(
    graph,
    query: str,
    top_k: int = 10,
    metric: Union[SimilarityMetric, str] = SimilarityMetric.COSINE,
    vector_key: str = "vector_512_realtime",  # змінено default на realtime
    model_name: str = "paraphrase-multilingual-MiniLM-L12-v2",
    vector_size: int = 512,
    threshold: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Векторний пошук по графу - знаходить найбільш схожі ноди за текстовим запитом.

    Це основа всього - must-have функція для семантичного пошуку.

    Args:
        graph: Граф з нодами (має атрибут .nodes)
        query: Текстовий запит для пошуку
        top_k: Кількість результатів (за замовчуванням 10)
        metric: Метрика схожості (cosine за замовчуванням)
        vector_key: Ключ вектора в user_data ноди (default: 'vector_512_realtime')
        model_name: Назва моделі для векторизації запиту
        vector_size: Розмір вектору
        threshold: Мінімальний поріг схожості (опціонально)

    Returns:
        Список результатів, відсортований за схожістю:
        [
            {
                'node_id': str,
                'url': str,
                'similarity': float,
                'rank': int
            },
            ...
        ]

    Приклад:
        >>> results = search(graph, "Python розробник", top_k=5)
        >>> for r in results:
        ...     print(f"{r['rank']}. {r['url']} - {r['similarity']:.3f}")
    """
    # Нормалізуємо метрику
    if isinstance(metric, str):
        metric = SimilarityMetric(metric.lower())

    # Векторизуємо запит
    logger.info(f"Пошук: '{query[:50]}...' (top_k={top_k}, metric={metric.value})")
    query_vector = vectorize_text(query, model_name=model_name, target_size=vector_size)

    # Збираємо всі ноди з векторами
    results = []
    nodes_without_vectors = 0

    # Отримуємо ноди з графа
    if hasattr(graph, "nodes"):
        nodes = graph.nodes
    elif isinstance(graph, dict):
        nodes = graph
    else:
        raise ValueError("graph має бути об'єктом з атрибутом .nodes або словником")

    for node_id, node in nodes.items():
        # Отримуємо вектор з user_data
        node_vector = None

        if hasattr(node, "user_data") and vector_key in node.user_data:
            node_vector = node.user_data[vector_key]
        elif isinstance(node, dict) and vector_key in node:
            node_vector = node[vector_key]

        if node_vector is None:
            nodes_without_vectors += 1
            continue

        # Обчислюємо схожість
        node_vector = np.array(node_vector, dtype=np.float32)

        if metric == SimilarityMetric.COSINE:
            similarity = cosine_similarity(query_vector, node_vector)
        elif metric == SimilarityMetric.EUCLIDEAN:
            distance = euclidean_distance(query_vector, node_vector)
            similarity = 1.0 / (1.0 + distance)
        elif metric == SimilarityMetric.DOT:
            similarity = dot_product(query_vector, node_vector)

        # Фільтруємо за порогом
        if threshold is not None and similarity < threshold:
            continue

        # Отримуємо URL
        url = getattr(node, "url", None) or (
            node.get("url") if isinstance(node, dict) else str(node_id)
        )

        results.append(
            {
                "node_id": str(node_id),
                "url": url,
                "similarity": similarity,
                "node": node,
            }
        )

    if nodes_without_vectors > 0:
        logger.warning(
            f"Пропущено {nodes_without_vectors} нод без векторів (ключ: {vector_key})"
        )

    # Сортуємо за схожістю (від більшого до меншого)
    results.sort(key=lambda x: x["similarity"], reverse=True)

    # Обмежуємо результати
    results = results[:top_k]

    # Додаємо ранг
    for i, r in enumerate(results):
        r["rank"] = i + 1

    logger.info(f"Знайдено {len(results)} результатів")
    return results


def cluster(
    graph,
    method: Union[ClusteringMethod, str] = ClusteringMethod.KMEANS,
    n_clusters: int = 5,
    vector_key: str = "vector_512_realtime",
    **kwargs,
) -> Dict[str, Any]:
    """
    Групує (кластеризує) ноди графу за векторами.

    Дозволяє робити категоризацію, теми, структуру контенту.

    Args:
        graph: Граф з нодами
        method: Метод кластеризації (kmeans за замовчуванням)
        n_clusters: Кількість кластерів (для kmeans)
        vector_key: Ключ вектора в user_data ноди
        **kwargs: Додаткові параметри для алгоритму:
            - eps: Радіус сусідства для DBSCAN (за замовчуванням 0.5)
            - min_samples: Мін. точок для DBSCAN (за замовчуванням 2)

    Returns:
        Словник з результатами:
        {
            'clusters': {
                0: [node_id1, node_id2, ...],
                1: [node_id3, ...],
                ...
            },
            'labels': {node_id: cluster_label, ...},
            'n_clusters': int,
            'method': str,
            'stats': {
                'total_nodes': int,
                'clustered_nodes': int,
                'noise_nodes': int  # Для DBSCAN
            }
        }

    Приклад:
        >>> result = cluster(graph, method='kmeans', n_clusters=5)
        >>> for cluster_id, nodes in result['clusters'].items():
        ...     print(f"Кластер {cluster_id}: {len(nodes)} нод")
    """
    # Нормалізуємо метод
    if isinstance(method, str):
        method = ClusteringMethod(method.lower())

    logger.info(f"Групування: method={method.value}, n_clusters={n_clusters}")

    # Збираємо вектори з графа
    node_ids = []
    vectors = []

    if hasattr(graph, "nodes"):
        nodes = graph.nodes
    elif isinstance(graph, dict):
        nodes = graph
    else:
        raise ValueError("graph має бути об'єктом з атрибутом .nodes або словником")

    for node_id, node in nodes.items():
        node_vector = None

        if hasattr(node, "user_data") and vector_key in node.user_data:
            node_vector = node.user_data[vector_key]
        elif isinstance(node, dict) and vector_key in node:
            node_vector = node[vector_key]

        if node_vector is not None:
            node_ids.append(str(node_id))
            vectors.append(np.array(node_vector, dtype=np.float32))

    if len(vectors) < 2:
        logger.warning(f"Недостатньо нод з векторами для кластеризації: {len(vectors)}")
        return {
            "clusters": {},
            "labels": {},
            "n_clusters": 0,
            "method": method.value,
            "stats": {
                "total_nodes": len(nodes) if hasattr(nodes, "__len__") else 0,
                "clustered_nodes": len(vectors),
                "noise_nodes": 0,
            },
        }

    # Конвертуємо в numpy array
    X = np.array(vectors)

    # Кластеризація
    try:
        from sklearn.cluster import DBSCAN, AgglomerativeClustering, KMeans
    except ImportError:
        raise VectorizationError(
            "scikit-learn не встановлено. Встановіть: pip install scikit-learn"
        )

    if method == ClusteringMethod.KMEANS:
        # K-Means - швидкий, потребує визначення k
        actual_clusters = min(n_clusters, len(vectors))
        model = KMeans(n_clusters=actual_clusters, random_state=42, n_init=10)
        labels = model.fit_predict(X)

    elif method == ClusteringMethod.DBSCAN:
        # DBSCAN - автоматично визначає кількість кластерів
        eps = kwargs.get("eps", 0.5)
        min_samples = kwargs.get("min_samples", 2)
        model = DBSCAN(eps=eps, min_samples=min_samples, metric="cosine")
        labels = model.fit_predict(X)

    elif method == ClusteringMethod.HIERARCHICAL:
        # Ієрархічна кластеризація
        actual_clusters = min(n_clusters, len(vectors))
        model = AgglomerativeClustering(n_clusters=actual_clusters)
        labels = model.fit_predict(X)

    else:
        raise ValueError(f"Невідомий метод кластеризації: {method}")

    # Формуємо результати
    clusters = {}
    labels_dict = {}
    noise_count = 0

    for node_id, label in zip(node_ids, labels):
        label = int(label)
        labels_dict[node_id] = label

        if label == -1:
            # Шум (для DBSCAN)
            noise_count += 1
            continue

        if label not in clusters:
            clusters[label] = []
        clusters[label].append(node_id)

    n_actual_clusters = len(clusters)

    logger.info(
        f"Кластеризація завершена: {n_actual_clusters} кластерів, {noise_count} шуму"
    )

    return {
        "clusters": clusters,
        "labels": labels_dict,
        "n_clusters": n_actual_clusters,
        "method": method.value,
        "stats": {
            "total_nodes": len(nodes) if hasattr(nodes, "__len__") else 0,
            "clustered_nodes": len(vectors) - noise_count,
            "noise_nodes": noise_count,
        },
    }
