"""
Приклад використання плагінів векторизації з GraphCrawler.

Демонструє:
1. Створення кастомної Node з полями для векторизації
2. Використання RealTimeVectorizerPlugin для векторизації під час краулінгу
3. Використання BatchVectorizerPlugin для пакетної векторизації
4. Контроль векторизації через not_vector поле
5. Перевірку результатів векторизації
"""

import sys
import os
import logging
from typing import Optional, Any
from pydantic import Field

# Визначаємо шлях до кореня проекту динамічно
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from graph_crawler import GraphCrawlerClient
from graph_crawler.core.node import Node
from graph_crawler.core.models import URLRule, EdgeCreationStrategy
from graph_crawler.plugins.node.vectorization import RealTimeVectorizerPlugin, BatchVectorizerPlugin

# Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


class MyCustomNode(Node):
    """
    Кастомна Node для векторизації.
    
    Поля:
    - not_vector: Прапорець для пропуску векторизації (True = пропустити)
    - text: Текстовий контент сторінки для векторизації
    """
    not_vector: Optional[bool] = Field(default=False)
    text: Optional[str] = Field(default=None)
    
    def _update_from_context(self, context: Any):
        """Витягує текст після обробки HTML."""
        super()._update_from_context(context)
        
        # Витягуємо текст з HTML дерева
        if context.html_tree and context.parser:
            # Отримуємо весь текст без HTML тегів
            self.text = context.parser.text
            
            # Опціонально: можна додати логіку для пропуску певних сторінок
            # Наприклад, пропускаємо сторінки з мало текстом
            if len(self.text) < 100:
                self.not_vector = True
                logger.debug(f"Skipping vectorization for {self.url}: text too short")


def example_realtime_vectorization():
    """Приклад real-time векторизації."""
    logger.info("=" * 70)
    logger.info("ПРИКЛАД 1: Real-Time Векторизація (під час краулінгу)")
    logger.info("=" * 70)
    
    # Створюємо плагін
    realtime = RealTimeVectorizerPlugin(config={
        'enabled': True,
        'field_name': 'text',
        'skip_field': 'not_vector',
        'vector_size': 512,
        'model_name': 'paraphrase-multilingual-MiniLM-L12-v2'
    })
    
    logger.info(f"\n📦 Створено плагін: {realtime}")
    
    # Створюємо клієнта
    client = GraphCrawlerClient()
    
    # Запускаємо краулінг
    logger.info("\n🚀 Запускаємо краулінг з real-time векторизацією...")
    logger.info("   URL: https://example.com")
    logger.info("   Max pages: 10")
    
    try:
        graph = client.crawl(
            url="https://example.com",
            max_pages=10,
            max_depth=2,
            timeout=60,
            node_class=MyCustomNode,
            node_plugins=[realtime]
        )
        
        # Перевіряємо результати
        logger.info(f"\n✅ Краулінг завершено!")
        logger.info(f"   Всього нод: {len(graph.nodes)}")
        
        vectorized_count = 0
        skipped_count = 0
        
        for node_id, node in graph.nodes.items():
            if 'vector_512_realtime' in node.user_data:
                vectorized_count += 1
                vector = node.user_data['vector_512_realtime']
                logger.info(f"   ✓ {node.url}: vector size = {len(vector)}")
            else:
                skipped_count += 1
                logger.info(f"   ✗ {node.url}: skipped (not_vector={node.not_vector})")
        
        logger.info(f"\n📊 Статистика:")
        logger.info(f"   Векторизовано: {vectorized_count}")
        logger.info(f"   Пропущено: {skipped_count}")
        
    except Exception as e:
        logger.error(f"❌ Помилка краулінгу: {e}")


def example_batch_vectorization():
    """Приклад batch векторизації."""
    logger.info("\n" + "=" * 70)
    logger.info("ПРИКЛАД 2: Batch Векторизація (після краулінгу)")
    logger.info("=" * 70)
    
    # Створюємо плагін
    batch = BatchVectorizerPlugin(config={
        'text_content': 'text',
        'skip_nodes': {'not_vector'},
        'batch_size': 32,
        'vector_size': 512,
        'model_name': 'paraphrase-multilingual-MiniLM-L12-v2'
    })
    
    logger.info(f"\n📦 Створено плагін: {batch}")
    
    # Створюємо клієнта
    client = GraphCrawlerClient()
    
    # Запускаємо краулінг
    logger.info("\n🚀 Запускаємо краулінг з batch векторизацією...")
    logger.info("   URL: https://example.com")
    logger.info("   Max pages: 10")
    
    try:
        graph = client.crawl(
            url="https://example.com",
            max_pages=10,
            max_depth=2,
            timeout=60,
            node_class=MyCustomNode,
            node_plugins=[batch]
        )
        
        # Перевіряємо результати
        logger.info(f"\n✅ Краулінг завершено!")
        logger.info(f"   Всього нод: {len(graph.nodes)}")
        
        # Статистика з плагіна
        stats = batch.get_stats()
        logger.info(f"\n📊 Статистика векторизації:")
        logger.info(f"   Всього нод: {stats['total_nodes']}")
        logger.info(f"   Векторизовано: {stats['vectorized_nodes']}")
        logger.info(f"   Пропущено: {stats['skipped_nodes']}")
        logger.info(f"   Помилок: {stats['failed_nodes']}")
        
        # Показуємо приклади векторів
        logger.info(f"\n📄 Приклади векторизованих нод:")
        count = 0
        for node_id, node in graph.nodes.items():
            if 'vector_512_batch' in node.user_data and count < 3:
                vector = node.user_data['vector_512_batch']
                logger.info(f"   {node.url}")
                logger.info(f"      Vector size: {len(vector)}")
                logger.info(f"      Text length: {len(node.text) if node.text else 0} chars")
                count += 1
        
    except Exception as e:
        logger.error(f"❌ Помилка краулінгу: {e}")


def example_custom_fields():
    """Приклад векторизації кастомних полів."""
    logger.info("\n" + "=" * 70)
    logger.info("ПРИКЛАД 3: Векторизація кастомних полів")
    logger.info("=" * 70)
    
    # Кастомна Node з додатковим полем
    class NewsNode(Node):
        news_text: Optional[str] = Field(default=None)
        skip_vectorization: Optional[bool] = Field(default=False)
        
        def _update_from_context(self, context: Any):
            super()._update_from_context(context)
            
            # Витягуємо текст новин (приклад)
            if context.html_tree and context.parser:
                # Тут може бути логіка витягування специфічного контенту
                self.news_text = context.parser.text
    
    # Створюємо плагін для векторизації news_text
    batch = BatchVectorizerPlugin(config={
        'text_content': 'news_text',
        'skip_nodes': {'skip_vectorization'},
        'batch_size': 32,
        'vector_size': 512
    })
    
    logger.info(f"\n📦 Створено плагін для векторизації 'news_text': {batch}")
    logger.info("\n💡 Цей приклад показує як векторизувати будь-яке кастомне поле!")


def main():
    """Головна функція."""
    logger.info("\n" + "🔬" * 35)
    logger.info("ПРИКЛАДИ ВИКОРИСТАННЯ ПЛАГІНІВ ВЕКТОРИЗАЦІЇ")
    logger.info("🔬" * 35 + "\n")
    
    # Вибір прикладу
    logger.info("Виберіть приклад для запуску:")
    logger.info("  1. Real-Time Векторизація (під час краулінгу)")
    logger.info("  2. Batch Векторизація (після краулінгу)")
    logger.info("  3. Векторизація кастомних полів")
    logger.info("  4. Запустити всі приклади")
    
    choice = input("\nВаш вибір (1-4): ").strip()
    
    if choice == "1":
        example_realtime_vectorization()
    elif choice == "2":
        example_batch_vectorization()
    elif choice == "3":
        example_custom_fields()
    elif choice == "4":
        example_realtime_vectorization()
        example_batch_vectorization()
        example_custom_fields()
    else:
        logger.error("❌ Невірний вибір!")
        return
    
    logger.info("\n" + "=" * 70)
    logger.info("✅ ПРИКЛАДИ ЗАВЕРШЕНО")
    logger.info("=" * 70)
    
    logger.info("\n📚 Додаткові ресурси:")
    logger.info("  - Документація: docs/VECTORIZATION.md")
    logger.info("  - Тести: tests/")
    logger.info("  - Вихідний код: graph_crawler/plugins/node/vectorization/")


if __name__ == "__main__":
    # Для швидкого тесту без інпуту
    if len(sys.argv) > 1:
        example_code = sys.argv[1]
        if example_code == "1":
            example_realtime_vectorization()
        elif example_code == "2":
            example_batch_vectorization()
        elif example_code == "3":
            example_custom_fields()
    else:
        main()
