"""
Приклад використання EasyDistributedCrawler.

Цей скрипт демонструє як запустити розподілений краулінг з YAML конфігом.
"""

import logging
from graph_crawler.distributed import EasyDistributedCrawler

# Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """Головна функція для запуску distributed crawling."""
    
    logger.info("=" * 60)
    logger.info("🚀 Starting Distributed Crawling")
    logger.info("=" * 60)
    
    # 1. Створюємо crawler з YAML конфігу
    logger.info("Завантаження конфігурації з config.yaml...")
    crawler = EasyDistributedCrawler.from_yaml("config.yaml")
    
    # 2. Запускаємо краулінг
    logger.info("Запуск distributed crawling...")
    logger.info("ВАЖЛИВО: Переконайтесь що Redis, MongoDB і Celery workers запущені!")
    logger.info("")
    logger.info("Як запустити workers:")
    logger.info("  celery -A graph_crawler worker --loglevel=info --concurrency=4")
    logger.info("")
    
    try:
        results = crawler.crawl()
        
        # 3. Отримуємо статистику
        stats = results.get_stats()
        logger.info("")
        logger.info("=" * 60)
        logger.info("📊 РЕЗУЛЬТАТИ КРАУЛІНГУ")
        logger.info("=" * 60)
        logger.info(f"Знайдено сторінок: {stats['total_nodes']}")
        logger.info(f"Знайдено посилань: {stats['total_edges']}")
        
        # 4. Аналізуємо extractors результати
        logger.info("")
        logger.info("=" * 60)
        logger.info("📞 ВИТЯГНУТІ ДАНІ")
        logger.info("=" * 60)
        
        total_phones = 0
        total_emails = 0
        total_prices = 0
        
        for node in results.nodes.values():
            phones = node.user_data.get('phones', [])
            emails = node.user_data.get('emails', [])
            prices = node.user_data.get('prices', [])
            
            total_phones += len(phones)
            total_emails += len(emails)
            total_prices += len(prices)
            
            # Виводимо тільки сторінки з даними
            if phones or emails or prices:
                logger.info(f"\n📄 {node.url}")
                if phones:
                    logger.info(f"  📞 Телефони: {phones}")
                if emails:
                    logger.info(f"  ✉️  Emails: {emails}")
                if prices:
                    logger.info(f"  💰 Ціни: {[p['value'] for p in prices]}")
        
        logger.info("")
        logger.info("=" * 60)
        logger.info("📈 ПІДСУМОК")
        logger.info("=" * 60)
        logger.info(f"Всього телефонів: {total_phones}")
        logger.info(f"Всього emails: {total_emails}")
        logger.info(f"Всього цін: {total_prices}")
        logger.info("")
        logger.info("✅ Краулінг завершено успішно!")
        
    except Exception as e:
        logger.error(f"❌ Помилка під час краулінгу: {e}")
        logger.exception(e)
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
