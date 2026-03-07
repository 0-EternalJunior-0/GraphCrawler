"""Markdown Generation Utilities.

Standalone модуль для генерації Markdown з HTML.
Використовується вибірково - Node класи вирішують коли викликати.

Приклад використання:
    >>> from graph_crawler.shared.utils.markdown import MarkdownGenerator, MarkdownOptions
    >>>
    >>> # В кастомному Node (як JobsNode)
    >>> if self.is_jobs_url:  # Тільки для потрібних сторінок!
    ...     md = MarkdownGenerator()
    ...     result = md.generate(context.html)
    ...     self.text = result.text
    ...     self.text_markdown = result.fit_markdown
"""

from graph_crawler.shared.utils.markdown.generator import MarkdownGenerator
from graph_crawler.shared.utils.markdown.options import MarkdownOptions
from graph_crawler.shared.utils.markdown.result import MarkdownResult

__all__ = [
    "MarkdownGenerator",
    "MarkdownOptions",
    "MarkdownResult",
]
