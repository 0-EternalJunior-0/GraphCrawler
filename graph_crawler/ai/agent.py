"""AIAgent - High-level інтерфейс для AI-керованого краулінгу.

AIAgent є "thin wrapper" навколо існуючих core компонентів:
"""

import logging
from typing import Any, Dict, List, Optional, TypeVar, Union

from pydantic import BaseModel

from graph_crawler.ai.extraction_plugin import AIExtractionPlugin

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class AIAgent:
    """
    High-level AI інтерфейс для graph_crawler.

    AIAgent спрощує використання AI-керованого краулінгу:
    1. Інтегрує AIExtractionPlugin
    2. Автоматично збирає витягнуті дані
    3. Повертає типізований результат

    Attributes:
        model: LLM провайдер
        max_pages: Максимальна кількість сторінок
        max_depth: Максимальна глибина краулінгу
    """

    def __init__(
        self,
        model,  # ILanguageModel
        max_pages: int = 50,
        max_depth: int = 3,
    ):
        """
        Ініціалізує AIAgent.

        Args:
            model: Реалізація ILanguageModel
            max_pages: Safety limit - максимальна кількість сторінок
            max_depth: Максимальна глибина переходів
        """
        self.model = model
        self.max_pages = max_pages
        self.max_depth = max_depth

        # Стан останнього краулінгу
        self._last_extraction_plugin: Optional[AIExtractionPlugin] = None
        self._last_graph = None
        self._extracted_data: Dict[str, Any] = {}
        self._pages_visited: int = 0
        self._errors: List[str] = []

    async def crawl(
        self,
        url: str,
        task: str,
        output: Optional[type[T]] = None,
        **crawler_kwargs,
    ) -> Union[T, str, None]:
        """
        AI-керований краулінг.

        Args:
            url: Стартовий URL
            task: Завдання природною мовою
            output: Pydantic модель для результату (опціонально)
            **crawler_kwargs: Додаткові параметри для async_crawl
        Returns:
            - Pydantic model якщо вказано output
            - str якщо без output
            - None якщо нічого не знайдено
        Example:
            ```python
            result = await agent.crawl(
                "https://shop.com",
                task="Знайди ціну та назву продукту",
                output=ProductInfo
            )
        """
        logger.info("Starting AI crawl: url=%s, task='%s...'", url, task)

        # Reset стану
        self._extracted_data = {}
        self._pages_visited = 0
        self._errors = []

        # 1. Створюємо extraction plugin
        extraction_plugin = AIExtractionPlugin(
            model=self.model,
            task=task,
            output_schema=output,
        )
        self._last_extraction_plugin = extraction_plugin

        # 2. Підготовка плагінів
        plugins = crawler_kwargs.pop("plugins", [])
        plugins.append(extraction_plugin)

        try:
            from graph_crawler.api import async_crawl
            from graph_crawler.domain.context import CrawlContext

            # 3. Створюємо CrawlContext з result_schema для зупинки по result_complete
            crawl_context = CrawlContext(result_schema=output) if output else CrawlContext()

            # 4. Запуск краулінгу з crawl_context
            graph = await async_crawl(
                url,
                plugins=plugins,
                max_depth=self.max_depth,
                max_pages=self.max_pages,
                crawl_context=crawl_context,
                **crawler_kwargs,
            )

            self._last_graph = graph
            self._pages_visited = len(graph.nodes) if graph else 0

            # 4. Збір даних (streaming через iter_nodes)
            for node in graph.iter_nodes():
                if getattr(node, "user_data", None):
                    ai_data = node.user_data.get("ai_extracted")
                    if not ai_data:
                        continue

                    for key, value in ai_data.items():
                        if key not in self._extracted_data or not self._extracted_data[key]:
                            self._extracted_data[key] = value
                        elif isinstance(value, list) and isinstance(
                            self._extracted_data[key], list
                        ):
                            self._extracted_data[key].extend(value)

            # 5. Формування результату
            if output and self._extracted_data:
                try:
                    return output.model_validate(self._extracted_data)
                except Exception as e:
                    logger.warning("Validation failed: %s", e)

                    # fallback partial
                    try:
                        partial = {}
                        for name, field in output.model_fields.items():
                            if name in self._extracted_data:
                                partial[name] = self._extracted_data[name]
                            elif not field.is_required():
                                partial[name] = field.default
                        return output.model_validate(partial)
                    except Exception:
                        return None

            if self._extracted_data:
                return self._extracted_data.get("text_result", str(self._extracted_data))

            logger.warning("No data extracted")
            return None

        except Exception as e:
            logger.error("AI crawl failed: %s", e, exc_info=True)
            self._errors.append(str(e))
            raise

    @property
    def last_graph(self):
        """Граф останнього краулінгу."""
        return self._last_graph

    def get_crawl_stats(self) -> Dict[str, Any]:
        """Статистика останнього краулінгу."""
        return {
            "pages_visited": self._pages_visited,
            "target_found": bool(self._extracted_data),
            "result_complete": bool(self._extracted_data),
            "result_completeness": "100%" if self._extracted_data else "0%",
            "missing_fields": [],
            "errors_count": len(self._errors),
            "extracted_data": self._extracted_data,
        }

    def __repr__(self) -> str:
        return (
            f"AIAgent("
            f"model={self.model.model_name}, "
            f"max_pages={self.max_pages}, "
            f"max_depth={self.max_depth})"
        )
