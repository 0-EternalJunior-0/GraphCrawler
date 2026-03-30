"""SmartCrawlEnginePlugin - ML плагін для інтелектуального краулінгу.

Розширена версія SmartPageFinderPlugin, але працює на Engine рівні:
- Приоритизує URL ПЕРЕД скануванням (не після)
- Може блокувати нерелевантні URL без сканування

Відмінності від Node плагіну:
- Node плагін: аналізує HTML після сканування
- Engine плагін: аналізує URL перед скануванням (економить ресурси)

Note: g4f (GPT4Free) integration is deprecated and will be removed.
Consider using official LLM APIs with proper API keys.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Optional

from graph_crawler.extensions.plugins.crawl_engine.base import (
    BaseEnginePlugin,
    EnginePluginContext,
    EnginePluginType,
)
from graph_crawler.shared.utils.text_utils import extract_keywords
from graph_crawler.shared.utils.url_patterns import (
    CONTENT_PAGE_PATTERNS,
    NAVIGATION_PATTERNS,
    IGNORE_PATTERNS,
    is_content_url,
)

logger = logging.getLogger(__name__)


class SmartCrawlEnginePlugin(BaseEnginePlugin):
    """
    ML plugin for intelligent crawl prioritization.

    Extended version of SmartPageFinderPlugin that works at Engine level:
    - Prioritizes URLs BEFORE scanning (not after)
    - Can block irrelevant URLs without scanning

    Differences from Node plugin:
    - Node plugin: analyzes HTML after scanning
    - Engine plugin: analyzes URL before scanning (saves resources)
    """

    def __init__(self, search_prompt: str, config: Optional[Dict[str, Any]] = None):
        """
        Ініціалізує SmartCrawlEnginePlugin.

        Args:
            search_prompt: Опис того що шукаємо (обов'язковий)
            config: Словник з параметрами конфігурації
        """
        super().__init__(config)

        if not search_prompt or not search_prompt.strip():
            raise ValueError("search_prompt не може бути порожнім")

        self.search_prompt = search_prompt.strip()

        # Параметри
        self.min_relevance_score = self.config.get("min_relevance_score", 0.7)
        self.priority_boost = self.config.get("priority_boost", 5)
        self.use_llm = self.config.get("use_llm", False)
        self.aggressive_filtering = self.config.get("aggressive_filtering", False)

        # Витягуємо keywords з промпту
        self.keywords = self._extract_keywords(self.search_prompt)

        # g4f клієнт (ліниве завантаження)
        self._g4f_client = None
        self._g4f_available = None

        logger.info(
            "SmartCrawlEnginePlugin initialized: prompt='%s...', keywords=%s, use_llm=%s",
            self.search_prompt[:50], self.keywords[:5], self.use_llm
        )

    @property
    def plugin_type(self) -> EnginePluginType:
        """Тип плагіну."""
        return EnginePluginType.CALCULATE_PRIORITIES

    @property
    def name(self) -> str:
        """Назва плагіну."""
        return "SmartCrawlEnginePlugin"

    def calculate_url_priority(self, context: EnginePluginContext) -> Optional[int]:
        """
        Обчислює пріоритет для URL на основі релевантності.

        Args:
            context: Контекст з URL

        Returns:
            int: Пріоритет 1-15 або None
        """
        url = context.url
        url_lower = url.lower()

        # 1. Швидка перевірка - keywords в URL
        keyword_matches = sum(1 for kw in self.keywords if kw.lower() in url_lower)

        if keyword_matches == 0:
            # Немає жодного keyword - низький пріоритет
            priority = 3
        elif keyword_matches >= 3:
            # Багато keywords - дуже високий пріоритет
            priority = 15
        elif keyword_matches == 2:
            priority = 12
        else:
            priority = 9

        # 2. Перевіряємо контентні патерни (book pages, articles тощо)
        priority = self._adjust_priority_by_patterns(url_lower, priority)

        # 3. Бонус якщо parent релевантний
        if context.parent_score and context.parent_score >= 0.7:
            priority = min(15, priority + 2)

        # 4. LLM аналіз якщо увімкнено (дорожче)
        if self.use_llm and priority >= 8:
            # Використовуємо LLM тільки для потенційно релевантних URL
            llm_priority = self._analyze_with_llm(context)
            if llm_priority is not None:
                priority = llm_priority

        logger.debug(
            "Priority %s for %s (keywords=%s, parent_score=%s)",
            priority, url, keyword_matches, context.parent_score
        )

        return priority

    def calculate_batch_priorities(self, contexts: List[EnginePluginContext]) -> Dict[str, int]:
        """
        Batch обробка URL для ефективності.

        Args:
            contexts: Список контекстів

        Returns:
            Dict[url, priority]
        """
        result = {}

        # Для keyword-based аналізу batch не дає переваг
        # Просто викликаємо для кожного
        for ctx in contexts:
            priority = self.calculate_url_priority(ctx)
            if priority is not None:
                result[ctx.url] = priority

        return result

    def should_scan_url(self, context: EnginePluginContext) -> Optional[bool]:
        """
        Визначає чи потрібно сканувати URL.

        Якщо aggressive_filtering=True, блокує низькорелевантні URL.

        Args:
            context: Контекст з URL

        Returns:
            False: Блокувати сканування
            None: Немає явного рішення
        """
        if not self.aggressive_filtering:
            return None

        url_lower = context.url.lower()

        # Use shared ignore patterns
        for pattern in IGNORE_PATTERNS:
            if re.search(pattern, url_lower):
                logger.debug("Blocked %s by pattern %s", context.url, pattern)
                return False

        # Якщо немає жодного keyword і не content page - блокуємо
        keyword_matches = sum(1 for kw in self.keywords if kw.lower() in url_lower)

        if keyword_matches == 0 and not is_content_url(url_lower):
            logger.debug("Blocked %s - no keywords and not content page", context.url)
            return False

        return None

    def _extract_keywords(self, text: str) -> List[str]:
        """Витягує ключові слова з тексту (uses shared utility)."""
        return extract_keywords(text, max_keywords=10)

    def _adjust_priority_by_patterns(self, url: str, base_priority: int) -> int:
        """Коригує пріоритет на основі URL патернів."""
        priority = base_priority

        # Use shared content patterns
        for pattern in CONTENT_PAGE_PATTERNS:
            if re.search(pattern, url):
                priority = min(15, priority + 2)
                break

        # Use shared navigation patterns
        for pattern in NAVIGATION_PATTERNS:
            if re.search(pattern, url):
                priority = min(13, priority + 1)
                break

        return priority

    def _is_content_page(self, url: str) -> bool:
        """Перевіряє чи це контентна сторінка (uses shared utility)."""
        return is_content_url(url)

    def _init_g4f(self) -> bool:
        """Ініціалізує g4f клієнт."""
        if self._g4f_available is not None:
            return self._g4f_available

        try:
            import warnings
            warnings.warn(
                "g4f (GPT4Free) is deprecated and will be removed in future versions. "
                "Consider using official LLM APIs with proper API keys.",
                DeprecationWarning,
                stacklevel=2
            )
            import g4f  # type: ignore[import-not-found]
            from g4f.client import Client  # type: ignore[import-not-found]

            self._g4f_client = Client()
            self._g4f_available = True
            logger.warning(
                "[DEPRECATED] g4f initialized for SmartCrawlEnginePlugin. "
                "Consider using official LLM APIs."
            )
            return True

        except ImportError:
            logger.warning("g4f not installed. Using keyword-based analysis only.")
            self._g4f_available = False
            return False
        except Exception as e:
            logger.error("Error initializing g4f: %s", e)
            self._g4f_available = False
            return False

    def _analyze_with_llm(self, context: EnginePluginContext) -> Optional[int]:
        """Аналізує URL за допомогою LLM (опціонально)."""
        if not self._init_g4f():
            return None

        try:
            prompt = f"""Analyze this URL for relevance to search query.
Search query: {self.search_prompt}
URL: {context.url}

Rate priority 1-15 (15=highest). Respond with ONLY a number."""

            response = self._g4f_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
            )

            content = response.choices[0].message.content.strip()
            # Витягуємо число з відповіді
            match = re.search(r"\b(\d+)\b", content)
            if match:
                priority = int(match.group(1))
                return max(1, min(15, priority))  # Clamp 1-15

        except Exception as e:
            logger.debug("LLM analysis failed: %s", e)

        return None

    def __repr__(self):
        return (
            f"SmartCrawlEnginePlugin("
            f"prompt='{self.search_prompt[:30]}...', "
            f"keywords={len(self.keywords)}, "
            f"use_llm={self.use_llm}, "
            f"aggressive={self.aggressive_filtering})"
        )
