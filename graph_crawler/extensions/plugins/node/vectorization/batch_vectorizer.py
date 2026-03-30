"""Batch text vectorizer for Node plugins.

Vectorizes text after crawl completion (AFTER_CRAWL stage).
Processes all graph nodes in batches for maximum performance.

Example:
    >>> from graph_crawler.extensions.plugins.node.vectorization import BatchVectorizerPlugin
    >>>
    >>> batch = BatchVectorizerPlugin(config={
    ...     'text_content': 'text',
    ...     'skip_nodes': {'not_vector'},
    ...     'batch_size': 64
    ... })
    >>>
    >>> # Using with GraphCrawler
    >>> graph = package_crawler.crawl(
    ...     url="https://example.com",
    ...     node_plugins=[batch]
    ... )
"""

import logging
from typing import Any, Dict, Optional, Optional

from graph_crawler.extensions.plugins.node.base import (
    BaseNodePlugin,
    NodePluginContext,
    NodePluginType,
)
from graph_crawler.extensions.plugins.node.vectorization.utils import (
    VectorizationError,
    vectorize_batch,
)

logger = logging.getLogger(__name__)


class BatchVectorizerPlugin(BaseNodePlugin):
    """
    Batch векторизатор тексту для Node.

    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Ініціалізує BatchVectorizerPlugin.

        Args:
            config: Словник з параметрами конфігурації

        Raises:
            ValueError: Якщо text_content не вказано в конфігурації
        """
        super().__init__(config)

        # Параметри векторизації
        self.model_name = self.config.get("model_name", "paraphrase-multilingual-MiniLM-L12-v2")
        self.vector_size = self.config.get("vector_size", 512)
        self.batch_size = self.config.get("batch_size", 64)

        # ОБОВ'ЯЗКОВИЙ параметр - яке поле векторизувати
        self.text_content = self.config.get("text_content")
        if not self.text_content:
            raise ValueError(
                "BatchVectorizerPlugin: 'text_content' parameter is required!\n"
                "Specify which field to vectorize, for example:\n"
                "  BatchVectorizerPlugin(config={'text_content': 'text'})\n"
                "  BatchVectorizerPlugin(config={'text_content': 'news_text'})"
            )

        # Параметри фільтрації
        skip_nodes_param = self.config.get("skip_nodes", {"not_vector"})
        # Перетворюємо в Set якщо передали інший тип
        if isinstance(skip_nodes_param, set):
            self.skip_nodes = skip_nodes_param
        elif isinstance(skip_nodes_param, (list, tuple)):
            self.skip_nodes = set(skip_nodes_param)
        elif isinstance(skip_nodes_param, str):
            self.skip_nodes = {skip_nodes_param}
        else:
            self.skip_nodes = {"not_vector"}

        self.vector_key = self.config.get("vector_key", "vector_512_batch")

        # Статистика
        self._stats = {
            "total_nodes": 0,
            "skipped_nodes": 0,
            "vectorized_nodes": 0,
            "failed_nodes": 0,
        }

        logger.info(
            f"BatchVectorizerPlugin initialized: "
            f"model={self.model_name}, size={self.vector_size}, "
            f"field={self.text_content}, skip_nodes={self.skip_nodes}, "
            f"batch_size={self.batch_size}"
        )

    @property
    def plugin_type(self) -> NodePluginType:
        """Тип плагіну - виконується після завершення краулінгу."""
        return NodePluginType.AFTER_CRAWL

    @property
    def name(self) -> str:
        """Назва плагіну."""
        return "BatchVectorizerPlugin"

    def execute(self, context: NodePluginContext) -> NodePluginContext:
        """
        Виконує batch векторизацію всіх нод в графі.

        На етапі AFTER_CRAWL context містить посилання на весь граф.
        Плагін отримує всі ноди, фільтрує їх, витягує тексти та
        векторизує батчами.

        Args:
            context: Контекст з даними (містить граф)

        Returns:
            Оновлений контекст
        """
        try:
            # Отримуємо граф з контексту
            graph = self._get_graph_from_context(context)

            if not graph:
                logger.error("BatchVectorizerPlugin: Cannot access graph from context")
                return context

            logger.info("Starting batch vectorization for %s nodes...", len(graph))

            # Збираємо ноди для векторизації
            nodes_to_vectorize = []
            texts_to_vectorize = []
            # Використовуємо iter_nodes() для streaming доступу
            for node in graph.iter_nodes():
                self._stats["total_nodes"] += 1

                # Перевіряємо чи потрібно пропустити
                if self._should_skip_node(node):
                    self._stats["skipped_nodes"] += 1
                    logger.debug("Skipping node %s: skip flag is set", node.url)
                    continue

                # Отримуємо текст
                text = self._get_text_from_node(node)

                if not text:
                    self._stats["skipped_nodes"] += 1
                    logger.debug(
                        f"Skipping node {node.url}: no text in field '{self.text_content}'"
                    )
                    continue

                nodes_to_vectorize.append(node)
                texts_to_vectorize.append(text)

            if not texts_to_vectorize:
                logger.warning(
                    f"No texts to vectorize! "
                    f"Checked {self._stats['total_nodes']} nodes, "
                    f"all were skipped or had no text in field '{self.text_content}'"
                )
                return context

            logger.info(
                f"Collected {len(texts_to_vectorize)} texts for vectorization "
                f"(skipped {self._stats['skipped_nodes']} nodes)"
            )

            # Векторизація батчами
            logger.info("Starting batch vectorization with batch_size=%s...", self.batch_size)
            vectors = vectorize_batch(
                texts=texts_to_vectorize,
                model_name=self.model_name,
                target_size=self.vector_size,
                clean=True,
                batch_size=self.batch_size,
            )

            for node, vector in zip(nodes_to_vectorize, vectors, strict=False):
                try:
                    node.user_data[self.vector_key] = vector.tolist()
                    self._stats["vectorized_nodes"] += 1
                except Exception as e:
                    logger.error("Failed to save vector for %s: %s", node.url, e)
                    self._stats["failed_nodes"] += 1

            # Виводимо статистику
            self._log_stats()

        except VectorizationError as e:
            logger.error("Batch vectorization error: %s", e)

        except Exception as e:
            logger.error("Unexpected error in BatchVectorizerPlugin: %s", e, exc_info=True)

        return context

    def _get_graph_from_context(self, context: NodePluginContext):
        """
        Отримує граф з контексту.

        На етапі AFTER_CRAWL контекст містить додаткові дані про граф.

        Args:
            context: Контекст ноди

        Returns:
            Graph об'єкт або None
        """
        # Спробуємо різні способи отримати граф

        # Спосіб 1: Через user_data
        if "graph" in context.user_data:
            return context.user_data["graph"]

        # Спосіб 2: Через node (якщо node має посилання на граф)
        if hasattr(context.node, "graph"):
            return context.node.graph

        # Спосіб 3: Через metadata
        if "graph" in context.metadata:
            return context.metadata["graph"]

        logger.error(
            "Cannot find graph in context! Make sure AFTER_CRAWL plugin receives graph reference."
        )
        return None

    def _should_skip_node(self, node) -> bool:
        """
        Перевіряє чи потрібно пропустити ноду.

        Args:
            node: Node об'єкт

        Returns:
            True якщо потрібно пропустити, False інакше
        """
        # Перевіряємо всі поля зі skip_nodes
        for skip_field in self.skip_nodes:
            # Перевіряємо в атрибутах ноди
            if hasattr(node, skip_field):
                skip_value = getattr(node, skip_field)
                if skip_value is True:
                    return True

            # Перевіряємо в user_data
            if skip_field in node.user_data:
                if node.user_data[skip_field] is True:
                    return True

        return False

    def _get_text_from_node(self, node) -> Optional[str]:
        """
        Отримує текст з ноди за вказаним полем.

        Args:
            node: Node об'єкт

        Returns:
            Текст або None якщо поле відсутнє/порожнє
        """
        # Спочатку шукаємо в атрибутах ноди
        if hasattr(node, self.text_content):
            text = getattr(node, self.text_content)
            if text and isinstance(text, str):
                return text

        # Потім в user_data
        if self.text_content in node.user_data:
            text = node.user_data[self.text_content]
            if text and isinstance(text, str):
                return text

        return None

    def _log_stats(self):
        """Виводить статистику векторизації."""
        logger.info("=" * 60)
        logger.info("Batch Vectorization Statistics:")
        logger.info("  Total nodes processed: %s", self._stats['total_nodes'])
        logger.info("  Skipped nodes: %s", self._stats['skipped_nodes'])
        logger.info("  Vectorized nodes: %s", self._stats['vectorized_nodes'])
        logger.info("  Failed nodes: %s", self._stats['failed_nodes'])

        if self._stats["total_nodes"] > 0:
            success_rate = (self._stats["vectorized_nodes"] / self._stats["total_nodes"]) * 100
            logger.info("  Success rate: %.1f%", success_rate)

        logger.info("=" * 60)

    def get_stats(self) -> Dict[str, int]:
        """
        Повертає статистику векторизації.

        Returns:
            Словник зі статистикою
        """
        return self._stats.copy()

    def __repr__(self):
        return (
            f"BatchVectorizerPlugin("
            f"model={self.model_name}, "
            f"vector_size={self.vector_size}, "
            f"field={self.text_content}, "
            f"batch_size={self.batch_size}, "
            f"enabled={self.enabled})"
        )
