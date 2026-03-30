"""Real-time векторизатор тексту для Node плагінів.

Векторизує текст під час краулінгу (ON_AFTER_SCAN).
"""

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any, Dict, Optional, Optional

from graph_crawler.extensions.plugins.node.base import (
    BaseNodePlugin,
    NodePluginContext,
    NodePluginType,
)
from graph_crawler.extensions.plugins.node.vectorization.utils import (
    VectorizationError,
    vectorize_text,
)

# ThreadPoolExecutor для CPU-bound векторизації (не блокує event loop!)
_vectorization_executor = ThreadPoolExecutor(
    max_workers=min(4, (os.cpu_count() or 2)), thread_name_prefix="vectorizer_"
)

logger = logging.getLogger(__name__)


class RealTimeVectorizerPlugin(BaseNodePlugin):
    """
    Real-time векторизатор тексту для Node.

    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Ініціалізує RealTimeVectorizerPlugin.

        Args:
            config: Словник з параметрами конфігурації
        """
        super().__init__(config)

        # Параметри векторизації
        self.model_name = self.config.get("model_name", "paraphrase-multilingual-MiniLM-L12-v2")
        self.vector_size = self.config.get("vector_size", 512)

        # Параметри полів
        self.field_name = self.config.get("field_name", "text")
        self.skip_field = self.config.get("skip_field", "not_vector")
        self.vector_key = self.config.get("vector_key", "vector_512_realtime")

        logger.info(
            "RealTimeVectorizerPlugin initialized: model=%s, size=%s, field=%s, skip_field=%s",
            self.model_name, self.vector_size, self.field_name, self.skip_field
        )

    @property
    def plugin_type(self) -> NodePluginType:
        """Тип плагіну - виконується після сканування."""
        return NodePluginType.ON_AFTER_SCAN

    @property
    def name(self) -> str:
        """Назва плагіну."""
        return "RealTimeVectorizerPlugin"

    async def execute(self, context: NodePluginContext) -> NodePluginContext:
        """
        ASYNC виконує векторизацію тексту з ноди.

        CPU-bound vectorize_text() виконується в ThreadPoolExecutor,
        не блокуючи async event loop.

        Args:
            context: Контекст з даними ноди

        Returns:
            Оновлений контекст з вектором в user_data
        """
        try:
            # Перевірка чи не потрібно пропустити векторизацію
            if self._should_skip(context):
                logger.debug("Skipping vectorization for %s: skip flag is set", context.url)
                return context

            # Отримуємо текст з ноди
            text = self._get_text_from_node(context)

            if not text:
                logger.debug(
                    "No text found in field '%s' for %s, skipping",
                    self.field_name, context.url
                )
                return context

            # ASYNC Векторизація через ThreadPoolExecutor (НЕ БЛОКУЄ event loop!)
            logger.debug("Vectorizing text for %s (length: %s chars)", context.url, len(text))

            loop = asyncio.get_event_loop()

            vectorize_func = partial(
                vectorize_text,
                text=text,
                model_name=self.model_name,
                target_size=self.vector_size,
                clean=True,
            )

            # Виконуємо CPU-bound операцію в окремому потоці
            vector = await loop.run_in_executor(_vectorization_executor, vectorize_func)

            context.user_data[self.vector_key] = vector.tolist()

            logger.info(
                "[VECTORIZE] Completed %s: text_len=%s, vector_size=%s",
                context.url, len(text), len(vector)
            )

        except VectorizationError as e:
            logger.error("Vectorization error for %s: %s", context.url, e)
            # Не падаємо - продовжуємо краулінг

        except Exception as e:
            logger.error(
                "Unexpected error in RealTimeVectorizerPlugin for %s: %s",
                context.url, e, exc_info=True
            )

        return context

    def _should_skip(self, context: NodePluginContext) -> bool:
        """
        Перевіряє чи потрібно пропустити векторизацію.

        Args:
            context: Контекст ноди

        Returns:
            True якщо потрібно пропустити, False інакше
        """
        node = context.node

        # Перевіряємо поле-прапорець в ноді
        if hasattr(node, self.skip_field):
            skip_value = getattr(node, self.skip_field)
            if skip_value is True:
                return True

        # Перевіряємо в user_data
        if self.skip_field in context.user_data:
            if context.user_data[self.skip_field] is True:
                return True

        return False

    def _get_text_from_node(self, context: NodePluginContext) -> Optional[str]:
        """
        Отримує текст з ноди за вказаним полем.

        Args:
            context: Контекст ноди

        Returns:
            Текст або None якщо поле відсутнє/порожнє
        """
        node = context.node

        # Спочатку шукаємо в атрибутах ноди (для кастомних Node класів)
        if hasattr(node, self.field_name):
            text = getattr(node, self.field_name)
            if text and isinstance(text, str):
                return text

        # Потім в user_data
        if self.field_name in context.user_data:
            text = context.user_data[self.field_name]
            if text and isinstance(text, str):
                return text

        # Якщо поле не знайдено
        logger.debug(
            "Field '%s' not found in node %s. Available node attributes: %s",
            self.field_name, context.url,
            [attr for attr in dir(node) if not attr.startswith('_')]
        )

        return None

    def __repr__(self):
        return (
            f"RealTimeVectorizerPlugin("
            f"model={self.model_name}, "
            f"vector_size={self.vector_size}, "
            f"field={self.field_name}, "
            f"enabled={self.enabled})"
        )
