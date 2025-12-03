"""Basic Example 2: Scan Timing and Delays

Цей приклад показує як контролювати час сканування та затримки.
Ви навчитеся:
- Встановленню timeout для сканування
- Затримкам між запитами
- Моніторингу швидкості сканування
- Оптимізації часу

Сайт для тестування: https://www.royalroad.com/
"""

from graph_crawler import crawl, Crawler
import logging
import time
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def example_1_basic_timing():
    """Приклад 1: Базовий контроль часу"""
    logger.info("=" * 60)
    logger.info("Example 1: Basic Timing Control")
    logger.info("=" * 60)

    start_time = time.time()

    # Простий краулінг з обмеженням часу
    graph = crawl(
        url="https://www.royalroad.com/",
        max_pages=20,
        max_depth=2,
        timeout=60  # Максимум 60 секунд
    )

    elapsed = time.time() - start_time
    stats = graph.get_stats()

    logger.info(f"⏱️  Час сканування: {elapsed:.2f} секунд")
    logger.info(f"📄 Відскановано сторінок: {stats['scanned_nodes']}")
    logger.info(f"🚀 Швидкість: {stats['scanned_nodes']/elapsed:.2f} pages/sec")

    return graph


def example_2_with_delays():
    """Приклад 2: Затримки між запитами"""
    logger.info("\n" + "=" * 60)
    logger.info("Example 2: Request Delays")
    logger.info("=" * 60)

    # Затримки між запитами важливі щоб не перевантажувати сервер
    start_time = time.time()

    graph = crawl(
        url="https://www.royalroad.com/",
        max_depth=2,
        max_pages=15,
        driver_config={'request_delay': 1.0}  # 1 секунда між запитами
    )

    elapsed = time.time() - start_time

    stats = graph.get_stats()
    logger.info(f"⏱️  Час сканування: {elapsed:.2f} секунд")
    logger.info(f"⏳ З затримкою 1.0s між запитами")
    logger.info(f"📄 Відскановано: {stats['scanned_nodes']} сторінок")

    return graph


def example_3_speed_monitoring():
    """Приклад 3: Моніторинг швидкості в реальному часі"""
    logger.info("\n" + "=" * 60)
    logger.info("Example 3: Real-time Speed Monitoring")
    logger.info("=" * 60)

    # Створюємо власний callback для моніторингу
    scanned_count = [0]
    start_time = [time.time()]

    def on_node_scanned(event_name, event_data):
        scanned_count[0] += 1
        if scanned_count[0] % 5 == 0:  # Кожні 5 сторінок
            elapsed = time.time() - start_time[0]
            speed = scanned_count[0] / elapsed if elapsed > 0 else 0
            logger.info(f"📊 Progress: {scanned_count[0]} pages, "
                        f"Speed: {speed:.2f} pages/sec")

    from graph_crawler.containers import ApplicationContainer
    container = ApplicationContainer()

    # Підписуємося на події
    event_bus = container.event_bus()
    event_bus.subscribe('NODE_SCANNED', on_node_scanned)

    crawler_service = container.crawler_service()
    graph = crawler_service.crawl(
        "https://www.royalroad.com/",
        max_pages=20,
        max_depth=2
    )

    total_elapsed = time.time() - start_time[0]
    logger.info(f"\nTotal time: {total_elapsed:.2f} seconds")
    logger.info(f"Average speed: {scanned_count[0]/total_elapsed:.2f} pages/sec")

    container.shutdown_resources()
    return graph


def example_4_timeout_handling():
    """Приклад 4: Обробка timeout"""
    logger.info("\n" + "=" * 60)
    logger.info("Example 4: Timeout Handling")
    logger.info("=" * 60)

    try:
        # Встановлюємо дуже малий timeout
        start_time = time.time()
        graph = crawl(
            url="https://www.royalroad.com/",
            max_pages=100,  # Багато сторінок
            max_depth=3,
            timeout=5  # Але тільки 5 секунд
        )
        elapsed = time.time() - start_time

        stats = graph.get_stats()
        logger.info(f"⏱️  Зупинилися після {elapsed:.2f} секунд (timeout: 5s)")
        logger.info(f"📄 Встигли відсканувати: {stats['scanned_nodes']} сторінок")
        logger.info(f"⚠️  Не відскановані: {stats['pending_nodes']} сторінок")

    except TimeoutError as e:
        logger.warning(f"⏰ Timeout досягнуто: {e}")
        logger.info("💡 Це нормально - краулінг зупинився за timeout")

    return None


def example_5_optimal_speed():
    """Приклад 5: Оптимальна швидкість сканування"""
    logger.info("\n" + "=" * 60)
    logger.info("Example 5: Optimal Crawling Speed")
    logger.info("=" * 60)

    # Тестуємо різні конфігурації
    configs = [
        {"name": "Fast (no delay)", "delay": 0.0},
        {"name": "Normal (0.5s delay)", "delay": 0.5},
        {"name": "Polite (1.0s delay)", "delay": 1.0},
    ]

    results = []

    for config in configs:
        logger.info(f"\n🧪 Testing: {config['name']}")

        start_time = time.time()
        graph = crawl(
            url="https://www.royalroad.com/",
            max_depth=2,
            max_pages=10,
            driver_config={'request_delay': config['delay']}
        )
        elapsed = time.time() - start_time

        stats = graph.get_stats()
        speed = stats['scanned_nodes'] / elapsed if elapsed > 0 else 0

        results.append({
            'name': config['name'],
            'time': elapsed,
            'pages': stats['scanned_nodes'],
            'speed': speed
        })

        logger.info(f"   ⏱️  Time: {elapsed:.2f}s")
        logger.info(f"   🚀 Speed: {speed:.2f} pages/sec")

    # Порівняння результатів
    logger.info("\n📊 Comparison:")
    for r in results:
        logger.info(f"   {r['name']}: {r['speed']:.2f} pages/sec in {r['time']:.2f}s")

    logger.info("\n💡 Recommendation:")
    logger.info("   - Fast: для внутрішніх/тестових сайтів")
    logger.info("   - Normal: для більшості випадків")
    logger.info("   - Polite: для production та великих сайтів")

    return results


if __name__ == "__main__":
    print("\n🚀 Starting Scan Timing Examples\n")

    try:
        example_1_basic_timing()
        example_2_with_delays()
        example_3_speed_monitoring()
        example_4_timeout_handling()
        example_5_optimal_speed()

        print("\n" + "=" * 60)
        print("All timing examples completed!")
        print("=" * 60)

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        raise
