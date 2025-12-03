"""Basic Example 4: API Levels v2.0

Цей приклад показує різні рівні API для роботи з GraphCrawler v2.0:
- Level 1: gc.crawl() - найпростіший (як requests.get)
- Level 2: gc.Crawler - reusable (як requests.Session)
- Level 3: ApplicationContainer - для експертів

Ви навчитеся:
- Коли використовувати який рівень API
- Extension points в кожному рівні
- String shortcuts для driver/storage
- Callbacks для моніторингу

Сайт для тестування: https://www.royalroad.com/
"""

import logging
import graph_crawler as gc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def level_1_simple_crawl():
    """
    Level 1: gc.crawl() - Найпростіший спосіб

    Як requests.get() - одна функція!

    Переваги:
    - Одна функція - просто викликати
    - Всі extension points доступні
    - Автоматичне управління ресурсами

    ❌ Обмеження:
    - Не reusable
    - Новий container кожен раз
    """
    logger.info("=" * 60)
    logger.info("Level 1: gc.crawl() - Найпростіший")
    logger.info("=" * 60)

    # Просто викликаємо функцію!
    graph = gc.crawl(
        url="https://www.royalroad.com/",
        max_pages=15,
        max_depth=2,
        same_domain=True
    )

    stats = graph.get_stats()
    logger.info(f"\nРезультат:")
    logger.info(f"   📄 Сторінок: {stats['total_nodes']}")
    logger.info(f"   🔗 Посилань: {stats['total_edges']}")
    logger.info(f"\n💡 Використовуйте коли: швидке тестування, прості скрипти")

    return graph


def level_1_with_extensions():
    """
    Level 1b: gc.crawl() з extension points

    Показує що всі можливості збережені!
    """
    logger.info("\n" + "=" * 60)
    logger.info("Level 1b: gc.crawl() з всіма extension points")
    logger.info("=" * 60)

    # Callback для прогресу
    def on_progress(data):
        logger.info(f"   📈 Progress: {data.get('progress_pct', 0)}%")

    # З усіма extension points
    graph = gc.crawl(
        url="https://www.royalroad.com/",
        max_depth=2,
        max_pages=15,
        same_domain=True,

        # Driver - string shortcut!
        driver="http",  # або "async", "playwright", CustomDriver()

        # Storage - string shortcut!
        storage="memory",  # або "json", "sqlite", CustomStorage()

        # Plugins
        # plugins=[CustomPlugin()],

        # Custom Node class
        # node_class=MyNode,

        # URL rules
        # url_rules=[URLRule(...)],

        # Callbacks
        # on_progress=on_progress,
        # on_node_scanned=lambda d: print(f"Scanned: {d.get('url')}"),
        # on_error=lambda d: print(f"Error: {d}"),

        # Advanced
        request_delay=0.5,
    )

    stats = graph.get_stats()
    logger.info(f"\nЗ extension points:")
    logger.info(f"   📄 Сторінок: {stats['total_nodes']}")
    logger.info(f"\n💡 Всі extension points доступні в gc.crawl()!")

    return graph


def level_2_crawler_class():
    """
    Level 2: gc.Crawler - Reusable (як requests.Session)

    Переваги:
    - Можна використовувати багато разів
    - Методи save/load
    - Default налаштування

    ❌ Обмеження:
    - Потрібно закривати (або with)
    """
    logger.info("\n" + "=" * 60)
    logger.info("Level 2: gc.Crawler - Reusable")
    logger.info("=" * 60)

    # Створюємо crawler з default налаштуваннями
    crawler = gc.Crawler(
        max_depth=2,
        max_pages=15,
        driver="http",
    )

    try:
        # Можемо викликати багато разів!
        graph1 = crawler.crawl(
            url="https://www.royalroad.com/",
            timeout=60
        )

        stats1 = graph1.get_stats()
        logger.info(f"\nПерший краулінг:")
        logger.info(f"   📄 Сторінок: {stats1['total_nodes']}")

        # Можна краулити інший сайт!
        # graph2 = crawler.crawl("https://example.org")

        # Можна зберегти
        # crawler.save(graph1, "royalroad")

        logger.info(f"\n💡 Використовуйте коли: багато краулів, save/load")

        return graph1

    finally:
        crawler.close()


def level_2_with_context_manager():
    """
    Level 2b: gc.Crawler з context manager (РЕКОМЕНДОВАНО!)

    Автоматичне закриття ресурсів.
    """
    logger.info("\n" + "=" * 60)
    logger.info("Level 2b: gc.Crawler з context manager")
    logger.info("=" * 60)

    # with автоматично закриє ресурси
    with gc.Crawler(max_depth=2, max_pages=15) as crawler:
        graph = crawler.crawl("https://www.royalroad.com/")

        stats = graph.get_stats()
        logger.info(f"\nРезультат:")
        logger.info(f"   📄 Сторінок: {stats['total_nodes']}")
        logger.info(f"\n💡 Краще з with - не забудете закрити!")

        return graph


def level_3_full_container():
    """
    Level 3: ApplicationContainer - Для експертів

    Переваги:
    - Повний контроль над всіма компонентами
    - Event bus для подій
    - Dependency Injection

    ❌ Складніше:
    - Більше коду
    - Потрібно розуміти архітектуру
    """
    logger.info("\n" + "=" * 60)
    logger.info("Level 3: ApplicationContainer - Експертний")
    logger.info("=" * 60)

    from graph_crawler.containers import ApplicationContainer
    from graph_crawler.core.configs import CrawlerConfig

    container = ApplicationContainer()

    try:
        config = CrawlerConfig(
            max_depth=2,
            max_pages=15,
            request_delay=0.5
        )
        container.config.override(config)

        # Event bus для подій
        event_bus = container.event_bus()

        def on_node_scanned(event_name, event_data):
            logger.info(f"   🔍 Scanned: {event_data.get('url', 'unknown')[:40]}...")

        event_bus.subscribe('NODE_SCANNED', on_node_scanned)

        # Crawler service
        crawler_service = container.crawler_service()

        logger.info("\n🚀 Starting crawl with events:")
        graph = crawler_service.crawl("https://www.royalroad.com/")

        stats = graph.get_stats()
        logger.info(f"\nРезультат:")
        logger.info(f"   📄 Сторінок: {stats['total_nodes']}")
        logger.info(f"\n💡 Використовуйте коли: production, складна логіка")

        return graph

    finally:
        container.shutdown_resources()


def comparison_table():
    """Порівняльна таблиця всіх рівнів API v2.0"""
    logger.info("\n" + "=" * 80)
    logger.info("📊 API LEVELS COMPARISON v2.0")
    logger.info("=" * 80)

    comparison = """
┌────────────────┬──────────────────┬──────────────────┬──────────────────┐
│ Feature        │ L1: gc.crawl()   │ L2: gc.Crawler   │ L3: Container    │
├────────────────┼──────────────────┼──────────────────┼──────────────────┤
│ Простота        │ ⭐⭐⭐⭐⭐           │ ⭐⭐⭐⭐             │ ⭐⭐               │
│ Гнучкість       │ ⭐⭐⭐⭐            │ ⭐⭐⭐⭐             │ ⭐⭐⭐⭐⭐           │
│ Reusable       │ ❌               │ так            │ так            │
│ Код (рядків)   │ 1-5             │ 5-15            │ 15-30           │
├────────────────┼──────────────────┼──────────────────┼──────────────────┤
│ Коли           │ Швидкі скрипти  │ Багато краулів   │ Production      │
│ використ.      │ Тестування       │ Save/Load       │ Складна логіка  │
│                │ Прототипи        │                  │ Events          │
└────────────────┴──────────────────┴──────────────────┴──────────────────┘

🎯 EXTENSION POINTS (ВСІ збережені в новому API!):

   driver="http"           # або "async", "playwright", CustomDriver()
   storage="memory"        # або "json", "sqlite", CustomStorage()
   plugins=[Plugin()]      # ваші плагіни
   node_class=MyNode       # кастомний Node
   url_rules=[URLRule()]   # фільтрація URL
   on_progress=callback    # callbacks
"""

    logger.info(comparison)


def best_practices():
    """Найкращі практики v2.0"""
    logger.info("\n" + "=" * 80)
    logger.info("BEST PRACTICES v2.0")
    logger.info("=" * 80)

    practices = """
📌 Level 1 (gc.crawl):
   DO:
      graph = gc.crawl("https://example.com", max_pages=100)
      graph = gc.crawl(..., driver="playwright")  # String shortcut!
      graph = gc.crawl(..., on_progress=callback)  # Callbacks!
   
   ❌ DON'T:
      # Не використовуйте в циклах (новий container кожен раз)

📌 Level 2 (gc.Crawler):
   DO:
      with gc.Crawler(max_depth=5) as crawler:  # Context manager!
          graph1 = crawler.crawl("https://site1.com")
          graph2 = crawler.crawl("https://site2.com")
          crawler.save(graph1, "site1")
   
   ❌ DON'T:
      crawler = gc.Crawler()
      graph = crawler.crawl(...)  # Забули crawler.close()!

📌 Level 3 (Container):
   DO:
      # Використовуйте коли потрібен повний контроль
      # Підписуйтесь на події для моніторингу
      container.shutdown_resources()  # Завжди!
   
   ❌ DON'T:
      # Не використовуйте якщо gc.crawl() достатньо
"""

    logger.info(practices)


if __name__ == "__main__":
    print("\n🚀 GraphCrawler v2.0 API Levels Examples\n")

    try:
        # Показуємо всі рівні
        graph1 = level_1_simple_crawl()
        graph2 = level_1_with_extensions()
        graph3 = level_2_crawler_class()
        graph4 = level_2_with_context_manager()
        graph5 = level_3_full_container()

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
