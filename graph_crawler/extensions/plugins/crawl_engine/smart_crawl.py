"""SmartCrawlEnginePlugin - ML плагін для інтелектуального краулінгу.

Розширена версія SmartPageFinderPlugin, але працює на Engine рівні:
- Приоритизує URL ПЕРЕД скануванням (не після)
- Використовує g4f для аналізу URL patterns
- Може блокувати нерелевантні URL без сканування

Відмінності від Node плагіну:
- Node плагін: аналізує HTML після сканування
- Engine плагін: аналізує URL перед скануванням (економить ресурси)
"""

import logging
import re
from typing import Any, Dict, List, Optional

from graph_crawler.extensions.plugins.crawl_engine.base import (
    BaseEnginePlugin,
    EnginePluginContext,
    EnginePluginType,
)

logger = logging.getLogger(__name__)


class SmartCrawlEnginePlugin(BaseEnginePlugin):
    """
    ML плагін для інтелектуального керування краулінгом.
    
    Використовує search_prompt для визначення пріоритетів URL без сканування.
    Економить ресурси - не сканує нерелевантні сторінки.
    
    Features:
    - Keyword matching в URL для швидкої пріоритизації
    - Підтримка g4f для ML аналізу (опціонально)
    - Pattern matching для різних типів контенту
    - Fallback на keyword-based аналіз якщо g4f недоступний
    
    Параметри конфігурації:
        enabled (bool): Чи увімкнено плагін (default: True)
        min_relevance_score (float): Мінімальний score (default: 0.7)
        priority_boost (int): Додатковий пріоритет (default: 5)
        use_llm (bool): Використовувати g4f для аналізу (default: False, економніше)
        aggressive_filtering (bool): Блокувати низькорелевантні URL (default: False)
        
    Example:
        >>> plugin = SmartCrawlEnginePlugin(
        ...     search_prompt="Шукаю статті про Гаррі Поттера",
        ...     config={
        ...         'min_relevance_score': 0.6,
        ...         'use_llm': False,  # keyword-based швидше
        ...         'aggressive_filtering': True  # блокувати нерелевантні
        ...     }
        ... )
        >>> 
        >>> provider = EnginePriorityProvider(plugins=[plugin])
        >>> graph = gc.crawl("https://example.com", provider=provider)
    """
    
    def __init__(self, search_prompt: str, config: Dict[str, Any] = None):
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
            f"SmartCrawlEnginePlugin initialized: "
            f"prompt='{self.search_prompt[:50]}...', "
            f"keywords={self.keywords[:5]}, "
            f"use_llm={self.use_llm}"
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
            f"Priority {priority} for {url} "
            f"(keywords={keyword_matches}, parent_score={context.parent_score})"
        )
        
        return priority
    
    def calculate_batch_priorities(
        self, 
        contexts: List[EnginePluginContext]
    ) -> Dict[str, int]:
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
        
        # Блокуємо явно нерелевантні патерни
        ignore_patterns = [
            r'/login', r'/register', r'/signup', r'/signin',
            r'/cart', r'/checkout', r'/payment',
            r'/privacy', r'/terms', r'/cookie',
            r'/profile/\d+$', r'/user/', r'/account',
            r'/forums?/', r'/comment',
            r'\.(pdf|doc|docx|zip|rar|exe)$',
            r'/admin', r'/api/',
        ]
        
        for pattern in ignore_patterns:
            if re.search(pattern, url_lower):
                logger.debug(f"Blocked {context.url} by pattern {pattern}")
                return False
        
        # Якщо немає жодного keyword і не content page - блокуємо
        keyword_matches = sum(1 for kw in self.keywords if kw.lower() in url_lower)
        is_content_page = self._is_content_page(url_lower)
        
        if keyword_matches == 0 and not is_content_page:
            logger.debug(f"Blocked {context.url} - no keywords and not content page")
            return False
        
        return None
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Витягує ключові слова з тексту."""
        stop_words = {
            'і', 'та', 'або', 'а', 'але', 'що', 'як', 'це', 'на', 'в', 'у', 'з',
            'до', 'від', 'про', 'для', 'по', 'за', 'шукаю', 'знайти', 'сторінки',
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'have', 'has',
            'do', 'does', 'did', 'will', 'would', 'to', 'of', 'in', 'for', 'on',
            'find', 'search', 'looking', 'pages', 'page', 'content'
        }
        
        words = re.findall(r'\b\w+\b', text.lower())
        keywords = [w for w in words if len(w) >= 3 and w not in stop_words]
        return list(set(keywords))[:10]  # Топ 10 унікальних
    
    def _adjust_priority_by_patterns(self, url: str, base_priority: int) -> int:
        """Коригує пріоритет на основі URL патернів."""
        priority = base_priority
        
        # Контентні сторінки
        content_patterns = [
            r'/fiction/\d+', r'/book/\d+', r'/novel/\d+', r'/story/\d+',
            r'/article/', r'/post/', r'/product/', r'/item/', r'/details/',
        ]
        
        for pattern in content_patterns:
            if re.search(pattern, url):
                priority = min(15, priority + 2)
                break
        
        # Навігаційні сторінки (можуть вести до контенту)
        navigation_patterns = [
            r'\?page=\d+', r'/page/\d+', r'/category/', r'/tag/', r'/genre/',
            r'/list', r'/browse', r'best-rated', r'popular',
        ]
        
        for pattern in navigation_patterns:
            if re.search(pattern, url):
                priority = min(13, priority + 1)
                break
        
        return priority
    
    def _is_content_page(self, url: str) -> bool:
        """Перевіряє чи це контентна сторінка."""
        content_indicators = [
            r'/fiction/\d+', r'/book/\d+', r'/novel/\d+', r'/chapter/',
            r'/article/', r'/post/', r'/story/', r'/details/',
        ]
        
        return any(re.search(pattern, url) for pattern in content_indicators)
    
    def _init_g4f(self) -> bool:
        """Ініціалізує g4f клієнт."""
        if self._g4f_available is not None:
            return self._g4f_available
        
        try:
            import g4f
            from g4f.client import Client
            
            self._g4f_client = Client()
            self._g4f_available = True
            logger.info("g4f initialized for SmartCrawlEnginePlugin")
            return True
            
        except ImportError:
            logger.warning("g4f not installed. Using keyword-based analysis only.")
            self._g4f_available = False
            return False
        except Exception as e:
            logger.error(f"Error initializing g4f: {e}")
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
            match = re.search(r'\b(\d+)\b', content)
            if match:
                priority = int(match.group(1))
                return max(1, min(15, priority))  # Clamp 1-15
            
        except Exception as e:
            logger.debug(f"LLM analysis failed: {e}")
        
        return None
    
    def __repr__(self):
        return (
            f"SmartCrawlEnginePlugin("
            f"prompt='{self.search_prompt[:30]}...', "
            f"keywords={len(self.keywords)}, "
            f"use_llm={self.use_llm}, "
            f"aggressive={self.aggressive_filtering})"
        )
