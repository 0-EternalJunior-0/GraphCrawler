"""VectorCrawlEnginePlugin - векторний плагін для ML-based пріоритизації.

ВАЖЛИВА ЛОГІКА РОБОТИ:
1. Якщо URL має priority від URLRule → ПРОПУСКАЄМО (користувач вже визначив)
2. Якщо should_scan=False → ПРОПУСКАЄМО (URL заблоковано)
3. Якщо можна сканувати І немає пріоритету → ВЕКТОРИЗУЄМО та виставляємо пріоритет

ВЕКТОРИЗАЦІЯ: Аналізуємо тільки PATH (після домену), бо домен може мати
назву що поламає векторизацію.

Приклад:
    https://example.com/j-o-b-s/developer
    ↓ Витягуємо PATH
    /j-o-b-s/developer
    ↓ Векторизуємо
    [0.1, 0.2, ...] → cosine_similarity → priority
"""

import logging
from typing import Any, Dict, List, Optional, Optional
from urllib.parse import unquote, urlparse

from graph_crawler.extensions.plugins.crawl_engine.base import (
    BaseEnginePlugin,
    EnginePluginContext,
    EnginePluginType,
)

logger = logging.getLogger(__name__)

_sentence_transformers = None
_sklearn_cosine = None
_numpy = None


def _load_ml_dependencies():
    """Lazy loading of ML dependencies."""
    global _sentence_transformers, _sklearn_cosine, _numpy

    if _sentence_transformers is None:
        try:
            import numpy as np
            from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]
            from sklearn.metrics.pairwise import cosine_similarity  # type: ignore[import-not-found]

            _sentence_transformers = SentenceTransformer
            _sklearn_cosine = cosine_similarity
            _numpy = np

            return True
        except ImportError as e:
            logger.error(
                "ML dependencies not installed: %s. "
                "Install with: pip install sentence-transformers scikit-learn", e
            )
            return False
    return True


class VectorCrawlEnginePlugin(BaseEnginePlugin):
    """
    Vector-based ML plugin for URL prioritization using embeddings.

    Key Logic:
    1. If URL has priority from URLRule -> SKIP (user already defined)
    2. If should_scan=False -> SKIP (URL blocked)
    3. If can scan AND no priority -> VECTORIZE and set priority

    Vectorization analyzes only PATH (after domain) because domain name
    might break vectorization accuracy.

    Example:
        >>> plugin = VectorCrawlEnginePlugin(
        ...     keywords=["python", "developer", "jobs"],
        ...     min_priority=1,
        ...     max_priority=6
        ... )
        >>> plugin.setup()  # Load model
        >>> priority = plugin.calculate_url_priority(context)
    """

    def __init__(
        self,
        keywords: List[str],
        min_priority: int = 1,
        max_priority: int = 6,
        model_name: str = "paraphrase-multilingual-MiniLM-L12-v2",
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Ініціалізує векторний плагін.

        Args:
            keywords: Список пріоритетних слів (багатомовні)
            min_priority: Мінімальний пріоритет (default: 1)
            max_priority: Максимальний пріоритет (default: 6)
            model_name: Багатомовна модель
            config: Додаткова конфігурація
        """
        super().__init__(config)

        if not keywords:
            raise ValueError("keywords не можуть бути порожніми")

        self.keywords = keywords
        self.min_priority = min_priority
        self.max_priority = max_priority
        self.model_name = model_name

        # Параметри з конфігу
        self.similarity_threshold = self.config.get("similarity_threshold", 0.35)

        # Ініціалізація моделі (lazy loading)
        self._model = None
        self._keywords_vector = None

        # Статистика
        self.stats = {
            "total_analyzed": 0,
            "skipped_has_priority": 0,
            "skipped_blocked": 0,
            "vectorized": 0,
            "assigned_priority": 0,
        }

        logger.info(
            "VectorCrawlEnginePlugin initialized: keywords=%s, priority_range=[%s, %s], model=%s",
            len(keywords), min_priority, max_priority, model_name
        )

    @property
    def plugin_type(self) -> EnginePluginType:
        return EnginePluginType.CALCULATE_PRIORITIES

    @property
    def name(self) -> str:
        return "VectorCrawlEnginePlugin"

    def setup(self):
        """Ініціалізує модель та векторизує ключові слова."""
        if not _load_ml_dependencies():
            raise RuntimeError(
                "ML dependencies not available. "
                "Install with: pip install sentence-transformers scikit-learn"
            )

        logger.info("Loading model: %s...", self.model_name)
        self._model = _sentence_transformers(self.model_name)

        # Векторизуємо ключові слова один раз
        keywords_text = " ".join(self.keywords)
        self._keywords_vector = self._model.encode([keywords_text])[0]

        logger.info("Model loaded. Keywords vectorized: '%s...'", keywords_text[:50])

    def calculate_url_priority(self, context: EnginePluginContext) -> Optional[int]:
        """
        Обчислює пріоритет через cosine similarity.

        ЛОГІКА:
        1. Перевіряємо чи є явний priority → SKIP
        2. Перевіряємо чи можна сканувати → SKIP якщо ні
        3. Витягуємо PATH (без домену)
        4. Векторизуємо PATH
        5. Рахуємо cosine similarity
        6. Конвертуємо в пріоритет

        Args:
            context: Контекст з URL

        Returns:
            int: Пріоритет в діапазоні [min_priority, max_priority]
            None: Якщо не можемо визначити або не потрібно
        """
        self.stats["total_analyzed"] += 1

        # КРОК 1: Якщо є priority від URLRule - пропускаємо
        # (Це потрібно перевіряти в Scheduler, але тут можемо додати логіку)
        # Припускаємо що якщо є user_data['explicit_priority'] - це від правил
        if context.user_data.get("explicit_priority") is not None:
            self.stats["skipped_has_priority"] += 1
            logger.debug("Skip %s - має явний priority від URLRule", context.url)
            return None

        # КРОК 2: Якщо URL заблокований - пропускаємо
        # (Перевіряємо через user_data або окремий should_scan_url)
        if context.user_data.get("should_scan") is False:
            self.stats["skipped_blocked"] += 1
            logger.debug("Skip %s - заблокований (should_scan=False)", context.url)
            return None

        # КРОК 3: Витягуємо PATH (без домену)
        # Домен може мати назву що поламає векторизацію
        url_path = self._extract_path(context.url)

        if not url_path or url_path == "/":
            # Пустий або root path - не векторизуємо
            return None

        # Перевіряємо що модель ініціалізована
        if self._model is None:
            logger.warning("Model not initialized. Call setup() first.")
            return None

        # КРОК 4-5: Векторизуємо PATH та рахуємо similarity
        self.stats["vectorized"] += 1

        url_vector = self._model.encode([url_path])[0]
        similarity = _sklearn_cosine([url_vector], [self._keywords_vector])[0][0]

        # КРОК 6: Якщо similarity нижче порогу - пропускаємо
        if similarity < self.similarity_threshold:
            logger.debug(
                "Skip %s - similarity %.3f < threshold %s",
                url_path, similarity, self.similarity_threshold
            )
            return None

        # КРОК 7: Конвертуємо similarity (0-1) в пріоритет
        priority = self._similarity_to_priority(similarity)

        self.stats["assigned_priority"] += 1
        logger.debug("Assigned priority %s to %s (similarity=%.3f)", priority, url_path, similarity)

        return priority

    def calculate_batch_priorities(self, contexts: List[EnginePluginContext]) -> Dict[str, int]:
        """
        Batch векторизація для ефективності.

        Векторизуємо всі PATH одразу (10-100x швидше ніж по одному).
        """
        result = {}

        # Перевіряємо що модель ініціалізована
        if self._model is None:
            logger.warning("Model not initialized. Call setup() first.")
            return result

        # Фільтруємо контексти які потрібно обробити
        valid_contexts = []
        valid_paths = []

        for ctx in contexts:
            self.stats["total_analyzed"] += 1

            # Пропускаємо якщо є явний priority
            if ctx.user_data.get("explicit_priority") is not None:
                self.stats["skipped_has_priority"] += 1
                continue

            # Пропускаємо якщо заблокований
            if ctx.user_data.get("should_scan") is False:
                self.stats["skipped_blocked"] += 1
                continue

            # Витягуємо PATH
            url_path = self._extract_path(ctx.url)
            if not url_path or url_path == "/":
                continue

            valid_contexts.append(ctx)
            valid_paths.append(url_path)

        if not valid_paths:
            return result

        # Векторизуємо всі PATH одразу (BATCH!)
        self.stats["vectorized"] += len(valid_paths)
        url_vectors = self._model.encode(valid_paths)

        # Рахуємо similarities
        similarities = _sklearn_cosine(url_vectors, [self._keywords_vector])[:, 0]

        # Конвертуємо в пріоритети
        for i, ctx in enumerate(valid_contexts):
            similarity = similarities[i]

            if similarity >= self.similarity_threshold:
                priority = self._similarity_to_priority(similarity)
                result[ctx.url] = priority
                self.stats["assigned_priority"] += 1

                logger.debug(
                    "Batch: priority %s for %s (similarity=%.3f)",
                    priority, valid_paths[i], similarity
                )

        return result

    def _extract_path(self, url: str) -> str:
        """
        Витягує PATH з URL (без домену).

        Example:
            https://example.com/j-o-b-s/developer?page=1
            → /j-o-b-s/developer

        Важливо: Домен може мати назву що поламає векторизацію,
        тому аналізуємо тільки path.
        """
        try:
            parsed = urlparse(url)
            path = parsed.path

            # Decode URL-encoded characters
            path = unquote(path)

            # Нормалізація: видаляємо trailing slash (крім root)
            if len(path) > 1 and path.endswith("/"):
                path = path[:-1]

            return path
        except Exception as e:
            logger.warning("Error extracting path from %s: %s", url, e)
            return ""

    def _similarity_to_priority(self, similarity: float) -> int:
        """
        Конвертує cosine similarity (0-1) в пріоритет.

        Використовує лінійну шкалу:
        similarity = threshold → min_priority (напр. 1)
        similarity = 1.0 → max_priority (напр. 6)

        Args:
            similarity: Cosine similarity (0.0 - 1.0)

        Returns:
            int: Пріоритет в діапазоні [min_priority, max_priority]
        """
        # Нормалізуємо від threshold до 1.0
        normalized = (similarity - self.similarity_threshold) / (1.0 - self.similarity_threshold)
        normalized = max(0.0, min(1.0, normalized))

        # Конвертуємо в діапазон priority
        priority_range = self.max_priority - self.min_priority
        priority = self.min_priority + int(normalized * priority_range)

        # Clamp до діапазону (на всяк випадок)
        priority = max(self.min_priority, min(self.max_priority, priority))

        return priority

    def get_stats(self) -> Dict[str, Any]:
        """Повертає статистику роботи плагіну."""
        total = max(self.stats["total_analyzed"], 1)
        vectorized = max(self.stats["vectorized"], 1)

        return {
            **self.stats,
            "skip_rate": (self.stats["skipped_has_priority"] + self.stats["skipped_blocked"])
            / total,
            "vectorization_rate": self.stats["vectorized"] / total,
            "assignment_rate": self.stats["assigned_priority"] / vectorized,
        }

    def teardown(self):
        """Логує статистику при завершенні."""
        stats = self.get_stats()
        logger.info(
            "VectorCrawlEnginePlugin teardown. Stats: "
            "Total analyzed: %s, Skipped (has priority): %s, Skipped (blocked): %s, "
            "Vectorized: %s, Assigned priority: %s, Skip rate: %.2f%%, "
            "Vectorization rate: %.2f%%, Assignment rate: %.2f%%",
            stats['total_analyzed'], stats['skipped_has_priority'], stats['skipped_blocked'],
            stats['vectorized'], stats['assigned_priority'],
            stats['skip_rate'] * 100, stats['vectorization_rate'] * 100, stats['assignment_rate'] * 100
        )

    def __repr__(self):
        return (
            f"VectorCrawlEnginePlugin("
            f"keywords={len(self.keywords)}, "
            f"priority=[{self.min_priority}, {self.max_priority}], "
            f"model={self.model_name})"
        )
