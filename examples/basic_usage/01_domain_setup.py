"""Basic Example 4: Different API Levels

Цей приклад показує ТРИ рівні API для роботи з GraphCrawler:
- Level 1: Простий crawl() - найпростіше використання
- Level 2: GraphCrawler клас - більше можливостей
- Level 3: ApplicationContainer - повний контроль

Ви навчитеся:
- Коли використовувати який рівень API
- Різниця між підходами
- Можливості кожного рівня
- Як переходити від простого до складного

Сайт для тестування: https://www.royalroad.com/
"""

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def level_1_simple_crawl():
    """Level 1: Найпростіший спосіб - одна функція crawl()

    Переваги:
    - Одна функція - просто викликати
    - Мінімум коду
    - Автоматичне управління ресурсами

    ❌ Обмеження:
    - Менше контролю над процесом
    - Неможливо повторно використати crawler
    - Базові налаштування
    """
    logger.info("=" * 60)
    logger.info("Level 1: Simple crawl() Function")
    logger.info("=" * 60)

    from graph_crawler import crawl

    # Просто викликаємо функцію!
    graph = crawl(
        url="https://www.royalroad.com/",
        max_pages=15,
        max_depth=2,
        same_domain_only=True
    )

    stats = graph.get_stats()
    logger.info(f"\nРезультат:")
    logger.info(f"   📄 Сторінок: {stats['total_nodes']}")
    logger.info(f"   🔗 Посилань: {stats['total_edges']}")
    logger.info(f"\n💡 Використовуйте коли: швидке тестування, прості скрипти")

    return graph


def level_2_crawler_class():
    """Level 2: GraphCrawler клас - середній рівень

    Переваги:
    - Можна повторно використовувати
    - Більше методів (save, load, export)
    - Context manager підтримка
    - Кращий контроль

    ❌ Обмеження:
    - Все ще обмежені деякі налаштування
    - Немає доступу до внутрішніх компонентів
    """
    logger.info("\n" + "=" * 60)
    logger.info("Level 2: GraphCrawler Class")
    logger.info("=" * 60)

    from graph_crawler import GraphCrawler

    # Створюємо crawler об'єкт
    crawler = GraphCrawler(
        max_depth=2,
        max_pages=15
    )

    try:
        # Можемо викликати багато разів! timeout передаємо в crawl()
        graph1 = crawler.crawl(
            url="https://www.royalroad.com/",
            timeout=60  # timeout тут, а не в __init__
        )

        # Зберегти граф
        # crawler.save_graph(graph1, "royalroad_graph")

        # Статистика
        stats1 = graph1.get_stats()
        logger.info(f"\nПерший краулінг:")
        logger.info(f"   📄 Сторінок: {stats1['total_nodes']}")

        # Можна краулити інший сайт тим самим crawler!
        # graph2 = crawler.crawl("https://www.royalroad.com/fictions/trending")

        logger.info(f"\n💡 Використовуйте коли: потрібно багато разів краулити")
        logger.info(f"   або зберігати/завантажувати графи")

        return graph1

    finally:
        # Важливо закрити ресурси!
        crawler.close()


def level_2_with_context_manager():
    """Level 2b: GraphCrawler з context manager (рекомендовано)

    Переваги всі ті самі + автоматичне закриття ресурсів
    """
    logger.info("\n" + "=" * 60)
    logger.info("Level 2b: GraphCrawler with Context Manager")
    logger.info("=" * 60)

    from graph_crawler import GraphCrawler

    # with автоматично закриє ресурси
    with GraphCrawler(max_depth=2, max_pages=15) as crawler:
        graph = crawler.crawl("https://www.royalroad.com/")

        stats = graph.get_stats()
        logger.info(f"\nРезультат:")
        logger.info(f"   📄 Сторінок: {stats['total_nodes']}")
        logger.info(f"\n💡 Краще використовувати with - не забудете закрити!")

        return graph


def level_3_full_container():
    """Level 3: ApplicationContainer - повний контроль

    Переваги:
    - Повний контроль над всіма компонентами
    - Доступ до event bus, storage, drivers
    - Можна змінити будь-який компонент
    - Dependency Injection

    ❌ Складніше:
    - Більше коду
    - Потрібно розуміти архітектуру
    """
    logger.info("\n" + "=" * 60)
    logger.info("Level 3: Full ApplicationContainer Control")
    logger.info("=" * 60)

    from graph_crawler.containers import ApplicationContainer
    from graph_crawler.core.configs import CrawlerConfig

    # Створюємо контейнер
    container = ApplicationContainer()

    try:
        # Налаштовуємо конфігурацію
        config = CrawlerConfig(
            url="https://www.royalroad.com/",
            max_depth=2,
            max_pages=15,
            allowed_domains = ["domain+subdomains", 'www.facebook.com']
        )
        container.config.from_pydantic(config)

        # Отримуємо crawler service через DI
        client = container.client()

        # Можемо отримати доступ до event bus!
        event_bus = container.core.event_bus()

        # Підписуємося на події
        def on_node_scanned(event_name, event_data):
            logger.info(f"   🔍 Scanned: {event_data.get('url', 'unknown')}")

        event_bus.subscribe('NODE_SCANNED', on_node_scanned)

        # Краулінг
        logger.info("\n🚀 Starting crawl with event tracking:")
        graph = client.crawl("https://www.royalroad.com/")

        stats = graph.get_stats()
        logger.info(f"\nРезультат:")
        logger.info(f"   📄 Сторінок: {stats['total_nodes']}")
        logger.info(f"\n💡 Використовуйте коли: потрібен повний контроль,")
        logger.info(f"   custom компоненти, або складна логіка")

        return graph

    finally:
        # Закриваємо всі ресурси контейнера
        container.shutdown_resources()


def level_3_with_custom_config():
    """Level 3b: Кастомна конфігурація через Container

    Показує як налаштувати різні компоненти
    """
    logger.info("\n" + "=" * 60)
    logger.info("Level 3b: Custom Configuration")
    logger.info("=" * 60)

    from graph_crawler.containers import ApplicationContainer
    from graph_crawler.core.models import URLRule
    from graph_crawler.core.configs import CrawlerConfig, DriverConfig

    container = ApplicationContainer()

    try:
        # Детальна конфігурація
        config = CrawlerConfig(
            url="https://www.royalroad.com/",
            max_depth=3,
            max_pages=20,
            driver=DriverConfig(
                request_delay=1.0,
                request_timeout=120,
            ),
            url_rules=[
                URLRule(pattern=r".*/fiction/.*", priority=10, should_scan=True),
                URLRule(pattern=r".*/forums/.*", should_scan=False),
            ]
        )

        container.config.from_pydantic(config)

        crawler_service = container.client()
        graph = crawler_service.crawl("https://www.royalroad.com/")

        stats = graph.get_stats()
        logger.info(f"\nЗ кастомною конфігурацією:")
        logger.info(f"   📄 Сторінок: {stats['total_nodes']}")
        logger.info(f"   ⏱️ Request delay: 1.0s")
        logger.info(f"   🎯 З URL filtering")

        return graph

    finally:
        container.shutdown_resources()


def comparison_table():
    """Порівняльна таблиця всіх рівнів API"""
    logger.info("\n" + "=" * 80)
    logger.info("📊 API LEVELS COMPARISON")
    logger.info("=" * 80)

    comparison = """
┌─────────────┬──────────────────┬──────────────────┬──────────────────┐
│ Feature     │ Level 1: crawl() │ Level 2: Class   │ Level 3: Container│
├─────────────┼──────────────────┼──────────────────┼──────────────────┤
│ Простота    │ ⭐⭐⭐⭐⭐          │ ⭐⭐⭐⭐            │ ⭐⭐               │
│ Гнучкість   │ ⭐⭐              │ ⭐⭐⭐⭐            │ ⭐⭐⭐⭐⭐          │
│ Контроль    │ ⭐⭐              │ ⭐⭐⭐             │ ⭐⭐⭐⭐⭐          │
│ Код (рядків)│ 3-5 рядків       │ 10-15 рядків     │ 20-30 рядків     │
├─────────────┼──────────────────┼──────────────────┼──────────────────┤
│ Коли        │ Швидкі скрипти   │ Середні проекти  │ Production       │
│ використати │ Тестування       │ Багато краулів   │ Складна логіка   │
│             │ Прототипи        │ Save/Load графів │ Custom компоненти│
└─────────────┴──────────────────┴──────────────────┴──────────────────┘
"""

    logger.info(comparison)

    logger.info("\n💡 Рекомендації:")
    logger.info("   🟢 Новачок? Починайте з Level 1 (crawl)")
    logger.info("   🟡 Є досвід? Використовуйте Level 2 (GraphCrawler)")
    logger.info("   🔴 Production? Переходьте на Level 3 (Container)")


def best_practices():
    """Best practices для кожного рівня"""
    logger.info("\n" + "=" * 80)
    logger.info("BEST PRACTICES")
    logger.info("=" * 80)

    practices = """
    
📌 Level 1 (crawl function):
   DO:
      - Використовуйте для швидких тестів
      - Завжди встановлюйте max_pages
      - Додавайте timeout
   
   ❌ DON'T:
      - Не використовуйте в циклах (створює нові ресурси)
      - Не використовуйте для великих проектів

📌 Level 2 (GraphCrawler class):
   DO:
      - Використовуйте with statement (context manager)
      - Переіспользуйте crawler для різних сайтів
      - Використовуйте save/load для кешування
   
   ❌ DON'T:
      - Не забувайте викликати close() без with
      - Не створюйте багато екземплярів одночасно

📌 Level 3 (ApplicationContainer):
   DO:
      - Підписуйтесь на події для моніторингу
      - Налаштовуйте всі компоненти через config
      - Використовуйте для складної бізнес-логіки
   
   ❌ DON'T:
      - Не використовуйте якщо не потрібен повний контроль
      - Завжди викликайте shutdown_resources()
"""

    logger.info(practices)


if __name__ == "__main__":
    print("\n🚀 Starting API Levels Examples\n")

    try:
        # Показуємо всі три рівні
        # graph1 = level_1_simple_crawl()
        # graph2 = level_2_crawler_class()
        # graph3 = level_2_with_context_manager()
        # graph4 = level_3_full_container()
        graph5 = level_3_with_custom_config()

        # Порівняльна таблиця
        comparison_table()

        # Best practices
        best_practices()

        print("\n" + "=" * 80)
        print("All API levels demonstrated successfully!")
        print("=" * 80)

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        raise
