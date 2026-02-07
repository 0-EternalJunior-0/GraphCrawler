"""Priority Provider - абстракція для передачі пріоритетів в Scheduler.

Цей модуль забезпечує розділення між Scheduler та Engine плагінами:
- Scheduler НЕ знає про плагіни
- Плагіни НЕ знають про Scheduler
- Provider є посередником (Dependency Inversion)
"""

import logging
from typing import Dict, List, Optional

from graph_crawler.extensions.plugins.crawl_engine.base import (
    BaseEnginePlugin,
    EnginePluginContext,
    EnginePluginType,
)

logger = logging.getLogger(__name__)


class EnginePriorityProvider:
    """Provider для обчислення пріоритетів через Engine плагіни.
    
    Абстракція між Scheduler та Engine плагінами.
    Scheduler може опціонально використовувати Provider для пріоритизації.
    
    Архітектурні переваги:
    1. Scheduler залишається незалежним (не знає про плагіни)
    2. Плагіни не завязані на Scheduler (можна використовувати окремо)
    3. Зворотна сумісність (якщо provider немає - працює як раніше)
    
    Example:
        >>> plugin = SmartCrawlEnginePlugin(search_prompt="...")
        >>> provider = EnginePriorityProvider(plugins=[plugin])
        >>> 
        >>> # Scheduler опціонально використовує provider
        >>> priority = provider.get_priority_for_url(
        ...     url="https://example.com/page",
        ...     depth=1,
        ...     parent_url="https://example.com"
        ... )
    """
    
    def __init__(self, plugins: List[BaseEnginePlugin] = None):
        """
        Ініціалізує Provider з плагінами.
        
        Args:
            plugins: Список Engine плагінів
        """
        self.plugins = plugins or []
        
        # Групуємо плагіни по типу для швидшого доступу
        self._plugins_by_type: Dict[EnginePluginType, List[BaseEnginePlugin]] = {}
        for plugin in self.plugins:
            if plugin.enabled:
                plugin_type = plugin.plugin_type
                if plugin_type not in self._plugins_by_type:
                    self._plugins_by_type[plugin_type] = []
                self._plugins_by_type[plugin_type].append(plugin)
                plugin.setup()
        
        logger.info(
            f"EnginePriorityProvider initialized with {len(self.plugins)} plugins: "
            f"{[p.name for p in self.plugins]}"
        )
    
    def get_priority_for_url(
        self,
        url: str,
        depth: int = 0,
        parent_url: Optional[str] = None,
        parent_score: Optional[float] = None,
        parent_context: Optional[Dict] = None,
    ) -> Optional[int]:
        """Обчислює пріоритет для URL через плагіни.
        
        Викликає всі CALCULATE_PRIORITIES плагіни і повертає найвищий пріоритет.
        
        Args:
            url: URL для пріоритизації
            depth: Глибина URL
            parent_url: URL батьківської сторінки
            parent_score: Relevance score батьківської сторінки
            parent_context: Контекст батьківської сторінки
            
        Returns:
            int: Пріоритет 1-15 або None якщо жоден плагін не визначив
        """
        # Отримуємо плагіни для пріоритизації
        plugins = self._plugins_by_type.get(
            EnginePluginType.CALCULATE_PRIORITIES, []
        )
        
        if not plugins:
            return None
        
        context = EnginePluginContext(
            url=url,
            url_text=url.lower(),
            depth=depth,
            parent_url=parent_url,
            parent_score=parent_score,
            parent_context=parent_context or {},
        )
        
        # Збираємо пріоритети від всіх плагінів
        priorities = []
        for plugin in plugins:
            try:
                priority = plugin.calculate_url_priority(context)
                if priority is not None:
                    priorities.append((priority, plugin.name))
                    logger.debug(
                        f"Plugin '{plugin.name}' set priority {priority} for {url}"
                    )
            except Exception as e:
                logger.error(
                    f"Error in plugin '{plugin.name}' calculating priority: {e}",
                    exc_info=True
                )
        
        if priorities:
            max_priority, plugin_name = max(priorities, key=lambda x: x[0])
            logger.debug(
                f"Selected priority {max_priority} from plugin '{plugin_name}' for {url}"
            )
            return max_priority
        
        return None
    
    def get_batch_priorities(
        self,
        urls: List[str],
        depth: int = 0,
        parent_url: Optional[str] = None,
        parent_score: Optional[float] = None,
        parent_context: Optional[Dict] = None,
    ) -> Dict[str, int]:
        """Обчислює пріоритети для batch URL (ефективніше для ML).
        
        Args:
            urls: Список URL
            depth: Глибина URL
            parent_url: URL батьківської сторінки
            parent_score: Relevance score батьківської сторінки
            parent_context: Контекст батьківської сторінки
            
        Returns:
            Dict[url, priority]: Мапа URL -> пріоритет
        """
        plugins = self._plugins_by_type.get(
            EnginePluginType.CALCULATE_PRIORITIES, []
        )
        
        if not plugins:
            return {}
        
        contexts = [
            EnginePluginContext(
                url=url,
                url_text=url.lower(),
                depth=depth,
                parent_url=parent_url,
                parent_score=parent_score,
                parent_context=parent_context or {},
            )
            for url in urls
        ]
        
        # Збираємо пріоритети від всіх плагінів
        all_priorities: Dict[str, List[int]] = {url: [] for url in urls}
        
        for plugin in plugins:
            try:
                batch_result = plugin.calculate_batch_priorities(contexts)
                
                for url, priority in batch_result.items():
                    all_priorities[url].append(priority)
                    
            except Exception as e:
                logger.error(
                    f"Error in plugin '{plugin.name}' batch calculation: {e}",
                    exc_info=True
                )
        
        # Для кожного URL вибираємо максимальний пріоритет
        result = {}
        for url, priorities in all_priorities.items():
            if priorities:
                result[url] = max(priorities)
        
        return result
    
    def should_scan_url(
        self,
        url: str,
        depth: int = 0,
        parent_url: Optional[str] = None,
    ) -> Optional[bool]:
        """Перевіряє чи потрібно сканувати URL через плагіни.
        
        Args:
            url: URL для перевірки
            depth: Глибина URL
            parent_url: URL батьківської сторінки
            
        Returns:
            True: Точно сканувати
            False: Точно НЕ сканувати
            None: Немає явного рішення
        """
        plugins = self._plugins_by_type.get(
            EnginePluginType.BEFORE_URL_ADDED, []
        )
        
        if not plugins:
            return None
        
        context = EnginePluginContext(
            url=url,
            url_text=url.lower(),
            depth=depth,
            parent_url=parent_url,
        )
        
        # Якщо хоча б один плагін каже False - не сканувати
        # Якщо хоча б один каже True і жоден не каже False - сканувати
        has_true = False
        
        for plugin in plugins:
            try:
                decision = plugin.should_scan_url(context)
                if decision is False:
                    logger.debug(f"Plugin '{plugin.name}' blocked {url}")
                    return False
                elif decision is True:
                    has_true = True
            except Exception as e:
                logger.error(
                    f"Error in plugin '{plugin.name}' scan decision: {e}",
                    exc_info=True
                )
        
        return True if has_true else None
    
    def teardown(self):
        """Закриває всі плагіни."""
        for plugin in self.plugins:
            try:
                plugin.teardown()
            except Exception as e:
                logger.error(f"Error tearing down plugin '{plugin.name}': {e}")
        
        logger.info("EnginePriorityProvider teardown complete")
    
    def __repr__(self):
        return (
            f"EnginePriorityProvider("
            f"plugins={len(self.plugins)}, "
            f"enabled={sum(1 for p in self.plugins if p.enabled)})"
        )
