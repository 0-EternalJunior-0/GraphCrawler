"""
Демонстрація гнучкого ядра GraphCrawler v3.0.

Показує 3 нові механізми:
1. Dynamic Priority Support - плагіни можуть встановлювати пріоритети
2. Explicit Filter Override - плагіни можуть перебивати фільтри
3. Post-Scan Hooks - плагіни можуть обробляти результати між scan та process

Приклад: ML-краулер для пошуку вакансій
"""

import asyncio
import logging
from typing import List, Dict, Optional
from graph_crawler import GraphCrawlerClient
from graph_crawler.core.node import Node
from graph_crawler.plugins.node import BaseNodePlugin, NodePluginType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ===============================================
# ПРИКЛАД 1: Custom Node з динамічним пріоритетом
# ===============================================

class MLNode(Node):
    """
    Custom Node з підтримкою ML-пріоритетів.
    
    Механізм: Dynamic Priority Support
    Використання: Scheduler автоматично прочитає node.priority
    """
    ml_priority: Optional[int] = None
    ml_score: Optional[float] = None
    ml_reasoning: Optional[str] = None


# ===============================================
# ПРИКЛАД 2: ML Decision Plugin
# ===============================================

class MLDecisionPlugin(BaseNodePlugin):
    """
    ML плагін для інтелектуального вибору посилань.
    
    Використовує всі 3 механізми:
    1. Встановлює динамічні пріоритети для child нод
    2. Перебиває фільтри через explicit_scan_decisions
    3. Фільтрує посилання на основі ML аналізу
    """
    
    def __init__(self, target_keywords: List[str] = None):
        super().__init__()
        self.target_keywords = target_keywords or ["вакансія", "робота", "vacancy", "job"]
    
    @property
    def plugin_type(self):
        return NodePluginType.ON_AFTER_SCAN
    
    def execute(self, context):
        """
        Аналізує контент та приймає рішення про посилання.
        """
        # Отримуємо текст сторінки
        text = self._get_text_from_context(context)
        
        # Простий ML аналіз: рахуємо ключові слова
        relevance_score = self._calculate_relevance(text)
        
        # Зберігаємо результати в node
        context.node.ml_score = relevance_score
        
        # Якщо релевантність низька - пропускаємо всі посилання
        if relevance_score < 0.3:
            logger.info(f"Low relevance ({relevance_score:.2f}), skipping links: {context.url}")
            context.extracted_links = []
            return context
        
        # Аналізуємо посилання
        links = context.extracted_links or []
        selected_links = []
        priorities = {}
        explicit_decisions = {}
        
        for link in links:
            # Оцінюємо посилання
            link_score = self._score_link(link)
            
            if link_score > 0.5:
                selected_links.append(link)
                
                # МЕХАНІЗМ 1: Встановлюємо динамічний пріоритет
                if link_score > 0.8:
                    priorities[link] = 10  # Високий пріоритет
                elif link_score > 0.6:
                    priorities[link] = 7   # Середній пріоритет
                else:
                    priorities[link] = 5   # Низький пріоритет
                
                # МЕХАНІЗМ 2: Дозволяємо зовнішні домени (перебиваємо фільтри)
                if link_score > 0.9:
                    explicit_decisions[link] = True
                    logger.info(f"High-value external link allowed: {link}")
        
        # Зберігаємо рішення
        context.extracted_links = selected_links
        context.user_data['ml_decision'] = {
            'relevance_score': relevance_score,
            'selected_count': len(selected_links),
            'priorities': priorities
        }
        
        # МЕХАНІЗМ 2: Explicit decisions для перебивання фільтрів
        context.user_data['explicit_scan_decisions'] = explicit_decisions
        
        # МЕХАНІЗМ 1: Зберігаємо пріоритети для child нод
        context.user_data['child_priorities'] = priorities
        
        logger.info(
            f"ML Decision for {context.url}: "
            f"score={relevance_score:.2f}, links={len(selected_links)}/{len(links)}"
        )
        
        return context
    
    def _get_text_from_context(self, context) -> str:
        """Витягує текст зі сторінки."""
        if context.html_tree and context.parser:
            return context.parser.text[:5000]  # Перші 5000 символів
        return ""
    
    def _calculate_relevance(self, text: str) -> float:
        """Обчислює релевантність сторінки (простий ML)."""
        if not text:
            return 0.0
        
        text_lower = text.lower()
        matches = sum(1 for keyword in self.target_keywords if keyword in text_lower)
        
        # Нормалізуємо до [0, 1]
        return min(matches / len(self.target_keywords), 1.0)
    
    def _score_link(self, link: str) -> float:
        """Оцінює посилання (простий ML)."""
        link_lower = link.lower()
        
        # Високий score якщо URL містить ключові слова
        if any(keyword in link_lower for keyword in ["job", "vacancy", "career", "work"]):
            return 0.9
        
        # Середній score для розділів компанії
        if any(word in link_lower for word in ["about", "company", "contact"]):
            return 0.6
        
        # Низький score для всього іншого
        return 0.3


# ===============================================
# ПРИКЛАД 3: Post-Scan Hook для Analytics
# ===============================================

async def analytics_hook(node: Node, links: List[str]) -> List[str]:
    """
    МЕХАНІЗМ 3: Post-Scan Hook для збору аналітики.
    
    Викликається ПІСЛЯ сканування, ДО обробки посилань.
    Може модифікувати список посилань.
    """
    logger.info(f"Analytics hook: {node.url} -> {len(links)} links")
    
    # Збираємо статистику
    analytics = {
        'url': node.url,
        'depth': node.depth,
        'links_count': len(links),
        'ml_score': getattr(node, 'ml_score', None)
    }
    
    # Зберігаємо в node для подальшого аналізу
    node.user_data['analytics'] = analytics
    
    # Повертаємо посилання без змін (тільки спостерігаємо)
    return links


async def ml_filter_hook(node: Node, links: List[str]) -> List[str]:
    """
    МЕХАНІЗМ 3: Post-Scan Hook для додаткової фільтрації.
    
    Приклад: фільтруємо посилання на основі зовнішніх даних.
    """
    # Симуляція виклику ML API
    await asyncio.sleep(0.1)  # Async затримка
    
    # Фільтруємо тільки унікальні домени
    seen_domains = set()
    filtered = []
    
    for link in links:
        from urllib.parse import urlparse
        domain = urlparse(link).netloc
        
        if domain not in seen_domains:
            seen_domains.add(domain)
            filtered.append(link)
    
    if len(filtered) < len(links):
        logger.info(f"ML Filter hook: reduced {len(links)} -> {len(filtered)} links")
    
    return filtered


# ===============================================
# ПРИКЛАД 4: Використання всіх механізмів разом
# ===============================================

async def main():
    """
    Демонстрація гнучкого ядра GraphCrawler v3.0.
    """
    
    # Створюємо ML плагін
    ml_plugin = MLDecisionPlugin(
        target_keywords=["вакансія", "робота", "vacancy", "job", "career"]
    )
    
    # Створюємо post-scan hooks
    hooks = [
        analytics_hook,      # Збір аналітики
        ml_filter_hook,      # Додаткова фільтрація
    ]
    
    # Краулінг з усіма механізмами
    client = GraphCrawlerClient()
    
    logger.info("=" * 60)
    logger.info("ДЕМОНСТРАЦІЯ ГНУЧКОГО ЯДРА GraphCrawler v3.0")
    logger.info("=" * 60)
    logger.info("")
    logger.info("Механізми:")
    logger.info("1. Dynamic Priority - ML встановлює пріоритети (10/7/5)")
    logger.info("2. Explicit Filter Override - ML дозволяє зовнішні домени")
    logger.info("3. Post-Scan Hooks - Analytics + ML фільтрація")
    logger.info("")
    
    # Приклад виклику (закоментовано, бо потрібен реальний URL)
    # graph = await client.crawl(
    #     url="https://work.ua",
    #     max_pages=50,
    #     max_depth=3,
    #     node_class=MLNode,
    #     node_plugins=[ml_plugin],
    #     post_scan_hooks=hooks,  # НОВИЙ ПАРАМЕТР!
    # )
    
    logger.info("Приклад коду готовий!")
    logger.info("Розкоментуйте виклик crawl() для реального тестування")
    
    # Демонстрація як працює кожен механізм
    logger.info("")
    logger.info("=" * 60)
    logger.info("ЯК ЦЕ ПРАЦЮЄ:")
    logger.info("=" * 60)
    
    logger.info("")
    logger.info("1. DYNAMIC PRIORITY:")
    logger.info("   MLNode створюється з priority=None")
    logger.info("   → ML плагін встановлює child_priorities: {url: 10}")
    logger.info("   → LinkProcessor створює child node: node.priority = 10")
    logger.info("   → Scheduler читає node.priority (замість URLRule)")
    logger.info("   → Результат: високопріоритетні URL скануються першими")
    
    logger.info("")
    logger.info("2. EXPLICIT FILTER OVERRIDE:")
    logger.info("   ML плагін знаходить важливий зовнішній URL")
    logger.info("   → Встановлює: explicit_scan_decisions = {external_url: True}")
    logger.info("   → LinkProcessor перевіряє explicit_decisions ПЕРЕД фільтрами")
    logger.info("   → Результат: зовнішній URL дозволений (фільтри перебиті)")
    
    logger.info("")
    logger.info("3. POST-SCAN HOOKS:")
    logger.info("   Scanner завершує scan_node() → повертає links")
    logger.info("   → CrawlCoordinator викликає hooks: links = await hook(node, links)")
    logger.info("   → analytics_hook: збирає статистику (не модифікує)")
    logger.info("   → ml_filter_hook: фільтрує дублікати (модифікує)")
    logger.info("   → LinkProcessor отримує вже відфільтровані links")
    logger.info("   → Результат: зовнішні модулі контролюють процес")
    
    logger.info("")
    logger.info("=" * 60)
    logger.info("ПЕРЕВАГИ ГНУЧКОГО ЯДРА:")
    logger.info("=" * 60)
    logger.info("✅ Ядро не знає про ML, SEO, Analytics")
    logger.info("✅ Зовнішні модулі мають повний контроль")
    logger.info("✅ Комбінування декількох плагінів без конфліктів")
    logger.info("✅ Всього ~10 рядків коду в ядрі")
    logger.info("✅ Backward compatible - існуючий код працює")


if __name__ == "__main__":
    asyncio.run(main())
