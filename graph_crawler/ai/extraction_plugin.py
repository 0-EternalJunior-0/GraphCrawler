"""AIExtractionPlugin - плагін для AI-based extraction даних.

Використовує LLM для витягування структурованих даних з HTML сторінок.
"""

import logging
from typing import Any, Dict, List, Optional, Set, Type
from urllib.parse import urljoin, urlparse

from pydantic import BaseModel, Field

from graph_crawler.domain.interfaces import ILanguageModel, LLMError
from graph_crawler.extensions.plugins.node.base import (
    BaseNodePlugin,
    NodePluginContext,
    NodePluginType,
)
from graph_crawler.shared.utils.markdown.generator import MarkdownGenerator
from graph_crawler.shared.utils.markdown.options import MarkdownOptions
from graph_crawler.shared.utils.markdown.result import MarkdownResult

logger = logging.getLogger(__name__)


class ExtractedLinks(BaseModel):
    """Структура для посилань зі сторінки."""

    relevant_links: List[str] = Field(
        default_factory=list, description="Посилання які варто відвідати для задачі"
    )
    reasoning: str = Field(default="", description="Чому ці посилання релевантні")


class AIExtractionPlugin(BaseNodePlugin):
    """
    Плагін для AI-based extraction даних з HTML сторінок.

    Ключові особливості:
    - Використовує MarkdownGenerator для конвертації HTML -> Markdown
    - Фільтрує вже відвідані посилання
    - Пропонує LLM релевантні посилання для наступних кроків
    - Автоматично агрегує результати в CrawlContext

    Attributes:
        model: Реалізація ILanguageModel
        task: Завдання природною мовою
        output_schema: Pydantic схема для результату
        max_content_length: Максимальна довжина контенту для LLM
        suggest_links: Чи пропонувати посилання для відвідування
    """

    def __init__(
        self,
        model: ILanguageModel,
        task: str,
        output_schema: Optional[Type[BaseModel]] = None,
        max_content_length: int = 12000,
        suggest_links: bool = True,
        markdown_options: Optional[MarkdownOptions] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Ініціалізує AIExtractionPlugin.

        Args:
            model: LLM провайдер (OpenAIModel, AnthropicModel, etc.)
            task: Завдання природною мовою
            output_schema: Pydantic модель для валідації результату
            max_content_length: Максимальна кількість символів для LLM
            suggest_links: Пропонувати посилання для відвідування
            markdown_options: Налаштування MarkdownGenerator
            config: Додаткова конфігурація плагіна
        """
        super().__init__(config or {})
        self.model = model
        self.task = task
        self.output_schema = output_schema
        self.max_content_length = max_content_length
        self.suggest_links = suggest_links

        # Налаштування Markdown генератора
        self._md_options = markdown_options or MarkdownOptions(
            include_links=True,
            include_images=False,  # Зменшуємо розмір
            include_tables=True,
            include_lists=True,
            include_code_blocks=True,
            remove_nav=True,
            remove_header=True,
            remove_footer=True,
            remove_aside=False,  # Sidebar може містити важливу інфо
            remove_ads=True,
            generate_citations=False,  # Не потрібно для extraction
            normalize_whitespace=True,
        )
        self._md_generator = MarkdownGenerator(self._md_options)

    @property
    def plugin_type(self) -> NodePluginType:
        """Тип плагіну - виконується після парсингу HTML."""
        return NodePluginType.ON_HTML_PARSED

    @property
    def name(self) -> str:
        """Назва плагіну."""
        return "AIExtractionPlugin"

    async def execute(self, context: NodePluginContext) -> NodePluginContext:
        """
        Виконує AI extraction на HTML контенті.

        Args:
            context: Контекст з HTML та метаданими

        Returns:
            Оновлений контекст з витягнутими даними
        """
        if not context.html:
            logger.debug("No HTML content for %s, skipping extraction", context.url)
            return context

        # 1. Конвертуємо HTML в Markdown
        md_result = self._md_generator.generate_from_html(context.html)

        if not md_result or not md_result.fit_markdown:
            logger.debug("Empty markdown for %s", context.url)
            return context

        # 2. Отримуємо відвідані URL для фільтрації
        visited_urls = self._get_visited_urls(context)

        # 3. Збираємо посилання зі сторінки
        page_links = self._extract_links_from_html(context.html, context.url)

        # 4. Фільтруємо вже відвідані
        unvisited_links = [url for url in page_links if url not in visited_urls]

        # 5. Формуємо контент для LLM з глобальним контекстом
        content = self._prepare_content_for_llm(
            md_result=md_result,
            url=context.url,
            available_links=unvisited_links,
            crawl_context=context.crawl_context,
        )

        # 6. Формуємо промпт з глобальним контекстом
        prompt = self._build_prompt(context.url, content, unvisited_links, context.crawl_context)

        try:
            # 7. Витягуємо дані через LLM
            if self.output_schema:
                extracted = await self.model.complete_structured(prompt, self.output_schema)
                data = extracted.model_dump(exclude_none=True)
            else:
                text_result = await self.model.complete(prompt)
                data = {"text_result": text_result}

            # 8. Фільтруємо порожні значення
            data = {k: v for k, v in data.items() if v is not None and v != ""}

            if data:
                # Зберігаємо в глобальний контекст
                context.add_extracted_to_context(data)

                # Зберігаємо в user_data для локального доступу
                context.user_data["ai_extracted"] = data
                context.user_data["ai_model"] = self.model.model_name
                context.user_data["ai_content_type"] = "markdown"

                logger.info(
                    f"AI extracted {len(data)} fields from {context.url} "
                    f"using {self.model.model_name}"
                )

                # Phase 1: Агрегуємо результати в crawl_context.results
                if context.crawl_context:
                    # Додаємо в список results якщо є output_schema
                    if self.output_schema:
                        try:
                            result_item = self.output_schema.model_validate(data)
                            results = context.crawl_context.get("results", [])
                            results.append(result_item)
                            context.crawl_context.set("results", results)
                            logger.debug("Added result to context.results, total: %s", len(results))
                        except Exception as e:
                            logger.debug("Could not add to results list: %s", e)
                    if context.crawl_context.result_complete:
                        context.crawl_context.target_found = True
                        context.request_stop("All required data found by AI extraction")
                        logger.info("Result complete, requesting stop")
            else:
                logger.debug("No data extracted from %s", context.url)

            # 9. Якщо потрібно - просимо LLM вибрати релевантні посилання
            if (
                self.suggest_links
                and unvisited_links
                and not (context.crawl_context and context.crawl_context.result_complete)
            ):
                await self._suggest_relevant_links(context, unvisited_links, md_result)

        except LLMError as e:
            logger.error("LLM error for %s: %s", context.url, e)
            if context.crawl_context:
                context.crawl_context.add_error(
                    f"LLM extraction failed: {e}", url=context.url, model=self.model.model_name
                )
        except Exception as e:
            logger.error("Extraction error for %s: %s", context.url, e, exc_info=True)
            if context.crawl_context:
                context.crawl_context.add_error(f"Extraction error: {e}", url=context.url)

        return context

    def _get_visited_urls(self, context: NodePluginContext) -> Set[str]:
        """
        Отримує множину вже відвіданих URL.

        Args:
            context: NodePluginContext

        Returns:
            Set відвіданих URL
        """
        visited = set()

        if context.crawl_context:
            # З navigation_history
            history = context.crawl_context.navigation_history
            if history:
                visited.update(history)

            # Поточний URL також "відвіданий"
            visited.add(context.url)

        return visited

    def _extract_links_from_html(self, html: str, base_url: str) -> List[str]:
        """
        Витягує посилання з HTML.

        Args:
            html: HTML контент
            base_url: Базовий URL для відносних посилань

        Returns:
            Список абсолютних URL
        """
        try:
            from bs4 import BeautifulSoup  # type: ignore[import-not-found]

            soup = BeautifulSoup(html, "lxml")
        except Exception:
            return []

        links = []
        base_domain = urlparse(base_url).netloc

        for a in soup.find_all("a", href=True):
            href_val = a.get("href", "")
            # href може бути списком, беремо перший елемент
            href = href_val[0] if isinstance(href_val, list) else href_val
            href = str(href).strip() if href else ""

            if not href or href.startswith("#") or href.startswith("javascript:"):
                continue

            # Конвертуємо в абсолютний URL
            absolute_url = urljoin(base_url, href)

            # Фільтруємо зовнішні домени (опціонально)
            parsed = urlparse(absolute_url)
            if parsed.netloc == base_domain:
                # Нормалізуємо URL (без фрагментів)
                clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                if parsed.query:
                    clean_url += f"?{parsed.query}"

                if clean_url not in links:
                    links.append(clean_url)

        return links

    def _prepare_content_for_llm(
        self,
        md_result: MarkdownResult,
        url: str,
        available_links: List[str],
        crawl_context: Optional[Any] = None,
    ) -> str:
        """
        Готує контент для відправки в LLM.

        Args:
            md_result: Результат MarkdownGenerator
            url: Поточний URL
            available_links: Доступні посилання
            crawl_context: Глобальний контекст краулінгу

        Returns:
            Форматований контент
        """
        content_parts = []
        # Це дозволяє LLM розуміти "де він знаходиться" в контексті всього краулінгу
        if crawl_context:
            content_parts.append("## Crawl Context (Global State)")

            # Історія навігації - де вже були
            nav_history = crawl_context.navigation_history
            if nav_history:
                content_parts.append(f"**Pages visited ({len(nav_history)}):**")
                # Показуємо останні 10 сторінок
                recent_pages = nav_history[-10:] if len(nav_history) > 10 else nav_history
                for page_url in recent_pages:
                    content_parts.append(f"  - {page_url}")
                if len(nav_history) > 10:
                    content_parts.append(f"  ... and {len(nav_history) - 10} more")

            # Вже зібрані дані - що ми вже знайшли
            extracted = crawl_context.extracted_data
            if extracted:
                content_parts.append("\n**Already extracted data:**")
                for key, value in extracted.items():
                    if value:
                        # Обмежуємо довжину значення
                        str_value = str(value)
                        if len(str_value) > 100:
                            str_value = str_value[:100] + "..."
                        content_parts.append(f"  - {key}: {str_value}")

            # Прогрес виконання задачі
            if crawl_context.result_schema:
                completeness = crawl_context.result_completeness
                missing = crawl_context.get_missing_fields()
                content_parts.append(f"\n**Task progress:** {completeness:.0%} complete")
                if missing:
                    content_parts.append(f"**Still looking for:** {', '.join(missing)}")

            content_parts.append("")  # Пустий рядок
        content_parts.append("## Current Page")
        if md_result.title:
            content_parts.append(f"**Page Title:** {md_result.title}")
        if md_result.h1 and md_result.h1 != md_result.title:
            content_parts.append(f"**Main Heading:** {md_result.h1}")
        if md_result.description:
            content_parts.append(f"**Description:** {md_result.description}")

        content_parts.append("")  # Пустій рядок
        markdown = md_result.fit_markdown

        # Обрізаємо якщо занадто довгий
        if len(markdown) > self.max_content_length:
            markdown = markdown[: self.max_content_length] + "\n\n... [content truncated]"

        content_parts.append("## Page Content")
        content_parts.append(markdown)
        if available_links:
            content_parts.append("")
            content_parts.append("## Available Links (not yet visited)")
            for i, link in enumerate(available_links[:30], 1):  # Максимум 30 посилань
                content_parts.append(f"{i}. {link}")

        return "\n".join(content_parts)

    def _build_prompt(
        self,
        url: str,
        content: str,
        available_links: List[str],
        crawl_context: Optional[Any] = None,
    ) -> str:
        """
        Створює промпт для LLM з урахуванням глобального контексту.

        Args:
            url: URL сторінки
            content: Підготовлений контент
            available_links: Доступні посилання
            crawl_context: Глобальний контекст краулінгу

        Returns:
            Сформований промпт
        """
        if self.output_schema:
            fields = []
            for name, field in self.output_schema.model_fields.items():
                required = "required" if field.is_required() else "optional"
                field_type = str(field.annotation).replace("typing.", "")
                fields.append(f"  - {name} ({field_type}, {required})")
            # schema_hint used in prompt building
            _ = "\n\n**Expected fields to extract:**\n" + "\n".join(fields)

        # links_hint used for context
        _ = ""
        if available_links and self.suggest_links:
            _ = (
                "\n\n**Note:** The page contains links that haven't been visited yet. "
                "If you need more information to complete the task, mention which links "
                "might be helpful to visit next."
            )

        # Додаємо контекст про прогрес задачі
        # progress_hint used for priority context
        if crawl_context:
            missing = crawl_context.get_missing_fields()
            if missing:
                _ = f"\n\n**Priority:** Focus on finding these missing fields: {', '.join(missing)}"
            elif crawl_context.result_complete:
                _ = (
                    "\n\n**Status:** All required data has been found. "
                    "Only extract if you find better/more complete information."
                )

        return f"""**Task:** {self.task}

**Current URL:** {url}
7. Return only the extracted data in the requested format"""

    async def _suggest_relevant_links(
        self,
        context: NodePluginContext,
        available_links: List[str],
        md_result: MarkdownResult,
    ) -> None:
        """
        Просить LLM вибрати релевантні посилання для подальшого краулінгу.

        Args:
            context: NodePluginContext
            available_links: Невідвідані посилання
            md_result: Результат Markdown
        """
        if not available_links:
            return

        # Обмежуємо кількість посилань для аналізу
        links_to_analyze = available_links[:20]

        prompt = f"""**Task context:** {self.task}

**Current page:** {context.url}
**Page title:** {md_result.title or "Unknown"}

**Available links to visit (not yet crawled):**
{chr(10).join(f"{i + 1}. {link}" for i, link in enumerate(links_to_analyze))}

**Question:** Which of these links are most likely to contain relevant information for the task?

Select up to 5 most relevant links. Return ONLY the numbers (e.g., "1, 3, 7") or "none" if no links seem relevant.
Consider URL structure and likely page content based on the URL path."""

        try:
            response = await self.model.complete(prompt)
            response = response.strip().lower()

            if response == "none" or not response:
                return

            # Парсимо номери посилань
            import re

            numbers = re.findall(r"\d+", response)

            suggested_links = []
            for num_str in numbers[:5]:  # Максимум 5
                idx = int(num_str) - 1
                if 0 <= idx < len(links_to_analyze):
                    suggested_links.append(links_to_analyze[idx])

            if suggested_links:
                context.user_data["ai_suggested_links"] = suggested_links
                logger.info("AI suggested %s links to visit", len(suggested_links))

                # Підвищуємо пріоритет цих посилань
                for link in suggested_links:
                    context.reprioritize_url(link, new_priority=8)

        except Exception as e:
            logger.debug("Failed to get link suggestions: %s", e)

    def __repr__(self) -> str:
        return (
            f"AIExtractionPlugin("
            f"model={self.model.model_name}, "
            f"task='{self.task[:50]}...', "
            f"schema={self.output_schema.__name__ if self.output_schema else None}, "
            f"suggest_links={self.suggest_links})"
        )
