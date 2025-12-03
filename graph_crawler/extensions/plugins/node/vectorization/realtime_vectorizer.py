"""Real-time векторизатор тексту для Node плагінів.

Векторизує текст під час краулінгу (ON_AFTER_SCAN).
Працює для кожної ноди окремо відразу після сканування.

Приклад використання:
    >>> from graph_crawler.extensions.plugins.node.vectorization import RealTimeVectorizerPlugin
    >>>
    >>> realtime = RealTimeVectorizerPlugin(config={
    ...     'enabled': True,
    ...     'model_name': 'paraphrase-multilingual-MiniLM-L12-v2',
    ...     'vector_size': 512,
    ...     'field_name': 'text'
    ... })
    >>>
    >>> # Використання з GraphCrawler
    >>> graph = crawler.crawl(
    ...     url="https://example.com",
    ...     node_plugins=[realtime]
    ... )
"""

import logging
from typing import Any, Dict, Optional

from graph_crawler.extensions.plugins.node.base import (
    BaseNodePlugin,
    NodePluginContext,
    NodePluginType,
)
from graph_crawler.extensions.plugins.node.vectorization.utils import (
    VectorizationError,
    vectorize_text,
)

logger = logging.getLogger(__name__)


class RealTimeVectorizerPlugin(BaseNodePlugin):
    """
    Real-time векторизатор тексту для Node.

    Працює на етапі ON_AFTER_SCAN - після сканування HTML.
    Витягує текст з ноди, векторизує його та зберігає результат.

    Параметри конфігурації:
        enabled (bool): Чи увімкнено плагін (за замовчуванням True)
        model_name (str): Назва моделі sentence-transformers
            (за замовчуванням 'paraphrase-multilingual-MiniLM-L12-v2')
        vector_size (int): Розмір вектору (за замовчуванням 512)
        field_name (str): Ім'я поля в ноді з текстом (за замовчуванням 'text')
        skip_field (str): Ім'я поля-прапорця для пропуску векторизації
            (за замовчуванням 'not_vector')
        vector_key (str): Ключ для збереження вектору в user_data
            (за замовчуванням 'vector_512_realtime')

    Контроль виконання:
        Плагін пропускає ноду якщо:
        - node.not_vector == True (або інше поле зазначене в skip_field)
        - Поле з текстом відсутнє або порожнє

    Приклад з кастомною Node:
        >>> class MyCustomNode(Node):
        ...     not_vector: Optional[bool] = Field(default=False)
        ...     text: Optional[str] = Field(default=None)
        ...
        ...     def _update_from_context(self, context):
        ...         super()._update_from_context(context)
        ...         if context.html_tree:
        ...             self.text = context.html_tree.text
        >>>
        >>> # Векторизація буде працювати тільки якщо not_vector=False
        >>> realtime = RealTimeVectorizerPlugin()
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        Ініціалізує RealTimeVectorizerPlugin.

        Args:
            config: Словник з параметрами конфігурації
        """
        super().__init__(config)

        # Параметри векторизації
        self.model_name = self.config.get(
            "model_name", "paraphrase-multilingual-MiniLM-L12-v2"
        )
        self.vector_size = self.config.get("vector_size", 512)

        # Параметри полів
        self.field_name = self.config.get("field_name", "text")
        self.skip_field = self.config.get("skip_field", "not_vector")
        self.vector_key = self.config.get("vector_key", "vector_512_realtime")

        logger.info(
            f"RealTimeVectorizerPlugin initialized: "
            f"model={self.model_name}, size={self.vector_size}, "
            f"field={self.field_name}, skip_field={self.skip_field}"
        )

    @property
    def plugin_type(self) -> NodePluginType:
        """Тип плагіну - виконується після сканування."""
        return NodePluginType.ON_AFTER_SCAN

    @property
    def name(self) -> str:
        """Назва плагіну."""
        return "RealTimeVectorizerPlugin"

    def execute(self, context: NodePluginContext) -> NodePluginContext:
        """
        Виконує векторизацію тексту з ноди.

        Args:
            context: Контекст з даними ноди

        Returns:
            Оновлений контекст з вектором в user_data
        """
        try:
            # Перевірка чи не потрібно пропустити векторизацію
            if self._should_skip(context):
                logger.debug(
                    f"Skipping vectorization for {context.url}: skip flag is set"
                )
                return context

            # Отримуємо текст з ноди
            text = self._get_text_from_node(context)

            if not text:
                logger.debug(
                    f"No text found in field '{self.field_name}' for {context.url}, skipping"
                )
                return context

            # Векторизація
            logger.debug(
                f"Vectorizing text for {context.url} (length: {len(text)} chars)"
            )
            vector = vectorize_text(
                text=text,
                model_name=self.model_name,
                target_size=self.vector_size,
                clean=True,
            )

            # Зберігаємо вектор в user_data
            context.user_data[self.vector_key] = vector.tolist()

            logger.info(
                f" Vectorized {context.url}: "
                f"text_len={len(text)}, vector_size={len(vector)}"
            )

        except VectorizationError as e:
            logger.error(f"Vectorization error for {context.url}: {e}")
            # Не падаємо - продовжуємо краулінг

        except Exception as e:
            logger.error(
                f"Unexpected error in RealTimeVectorizerPlugin for {context.url}: {e}",
                exc_info=True,
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
            f"Field '{self.field_name}' not found in node {context.url}. "
            f"Available node attributes: {[attr for attr in dir(node) if not attr.startswith('_')]}"
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
