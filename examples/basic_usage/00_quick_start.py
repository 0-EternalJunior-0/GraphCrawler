"""Quick Start Guide - Simple API v3.1 (Sync-First)

Цей файл показує новий простий API як requests.
Принцип: "Просто для початківців, потужно для експертів"

v3.1: Sync-First - не потрібно знати async/await!

Рівні API:
1. crawl() function - синхронна, найпростіша (як requests.get)
2. Crawler class - синхронна, reusable (як requests.Session)
3. async_crawl() / AsyncCrawler - для досвідчених (паралельний краулінг)
4. ApplicationContainer - для експертів (повний контроль)

Сайт для тестування: https://www.royalroad.com/
"""

import logging
import graph_crawler as gc

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


def quick_level_1():
    """
    LEVEL 1: crawl() function - Найпростіший спосіб

    Синхронна функція як requests.get() - один рядок!
    Не потрібно знати async/await!

    Підтримувані параметри:
    - url: str (обов'язковий)
    - max_depth: int = 3
    - max_pages: int = 100
    - same_domain: bool = True
    - driver: "http", "async", "playwright" або CustomDriver()
    - storage: "memory", "json", "sqlite" або CustomStorage()
    - plugins: List[BaseNodePlugin]
    - on_progress, on_node_scanned, on_error, on_completed: callbacks
    """
    print("\n" + "="*60)
    print("LEVEL 1: gc.crawl() - Синхронна функція!")
    print("="*60)

    # Мінімальний виклик - один рядок!
    graph = gc.crawl(
        "https://www.royalroad.com/",
        max_pages=10,
        max_depth=2
    )

    stats = graph.get_stats()
    print(f"Знайдено: {stats['total_nodes']} сторінок")
    print(f"Посилань: {stats['total_edges']}")
    print(f"💡 Код: всього 1 рядок!")

    return graph


def quick_level_1_with_params():
    """
    LEVEL 1b: crawl() з параметрами

    Показує всі extension points.
    """
    print("\n" + "="*60)
    print("LEVEL 1b: gc.crawl() з параметрами")
    print("="*60)

    # Callback для прогресу
    def show_progress(data):
        progress = data.get('progress_pct', 0)
        print(f"  📈 Progress: {progress}%")

    # З параметрами
    graph = gc.crawl(
        "https://www.royalroad.com/",
        max_depth=2,
        max_pages=10,
        same_domain=True,
        driver="http",          # String shortcut!
        storage="memory",       # String shortcut!
        driver_config={'request_delay': 0.5},  # Затримка між запитами
        # on_progress=show_progress,  # Callback
    )

    stats = graph.get_stats()
    print(f"Знайдено: {stats['total_nodes']} сторінок")
    print(f"💡 Всі extension points доступні!")

    return graph


def quick_level_2():
    """
    LEVEL 2: Crawler class - Reusable (як requests.Session)

    Створюється один раз, використовується багато разів.
    """
    print("\n" + "="*60)
    print("LEVEL 2: gc.Crawler - Reusable!")
    print("="*60)

    # Створюємо crawler з default налаштуваннями
    crawler = gc.Crawler(
        max_depth=2,
        max_pages=10,
        driver="http",
    )

    try:
        # Можемо викликати багато разів!
        graph1 = crawler.crawl("https://www.royalroad.com/")
        print(f"Site 1: {len(graph1.nodes)} сторінок")

        # Можна перевизначити параметри
        # graph2 = crawler.crawl("https://example.org", max_depth=1)

        # Можна зберегти
        # crawler.save(graph1, "royalroad")

        print(f"💡 Можна використовувати багато разів!")

        return graph1

    finally:
        crawler.close()


def quick_level_2_context_manager():
    """
    LEVEL 2b: Crawler з context manager (РЕКОМЕНДОВАНО!)

    Автоматичне закриття ресурсів.
    """
    print("\n" + "="*60)
    print("LEVEL 2b: gc.Crawler з context manager")
    print("="*60)

    with gc.Crawler(max_depth=2, max_pages=10) as crawler:
        graph = crawler.crawl("https://www.royalroad.com/")

        stats = graph.get_stats()
        print(f"Знайдено: {stats['total_nodes']} сторінок")
        print(f"💡 Ресурси закриваються автоматично!")

        return graph


def quick_level_3():
    """
    LEVEL 3: ApplicationContainer - Для експертів

    Повний контроль над всіма компонентами.
    Використовуйте тільки якщо потрібен повний контроль.
    """
    print("\n" + "="*60)
    print("LEVEL 3: ApplicationContainer - Експертний")
    print("="*60)

    from graph_crawler.containers import ApplicationContainer
    from graph_crawler.core.configs import CrawlerConfig

    container = ApplicationContainer()

    try:
        config = CrawlerConfig(
            url="https://www.royalroad.com/",
            max_depth=2,
            max_pages=10
        )
        container.config.from_pydantic(config)

        client = container.client()

        # Можемо підписатися на події!
        event_bus = container.core.event_bus()

        # def on_scan(event_name, data):
        #     print(f"  🔍 Scanned: {data.get('url', 'unknown')[:50]}...")
        #
        # event_bus.subscribe('NODE_SCANNED', on_scan)

        graph = client.crawl(
            "https://www.royalroad.com/",
            max_depth=2,
            max_pages=10
        )

        stats = graph.get_stats()
        print(f"\nЗнайдено: {stats['total_nodes']} сторінок")
        print(f"💡 Повний контроль: events, storage, drivers!")

        return graph

    finally:
        container.shutdown_resources()


def show_api_comparison():
    """Порівняльна таблиця всіх рівнів"""

    print("\n" + "="*80)
    print("📊 API LEVELS COMPARISON v3.1 (Sync-First)")
    print("="*80)

    comparison = """
┌────────────────┬──────────────────┬──────────────────┬──────────────────┬──────────────────┐
│ Feature        │ L1: gc.crawl()   │ L2: gc.Crawler   │ L3: AsyncCrawler │ L4: Container    │
├────────────────┼──────────────────┼──────────────────┼──────────────────┼──────────────────┤
│ Простота        │ ⭐⭐⭐⭐⭐           │ ⭐⭐⭐⭐             │ ⭐⭐⭐              │ ⭐⭐               │
│ Гнучкість       │ ⭐⭐⭐⭐            │ ⭐⭐⭐⭐             │ ⭐⭐⭐⭐⭐           │ ⭐⭐⭐⭐⭐           │
│ Синхронний      │ ✅ так            │ ✅ так            │ ❌ async          │ async           │
│ Паралельний     │ ❌ ні             │ ❌ ні             │ ✅ так!           │ ✅ так!          │
│ Reusable       │ ❌ ні             │ ✅ так            │ ✅ так            │ ✅ так           │
├────────────────┼──────────────────┼──────────────────┼──────────────────┼──────────────────┤
│ driver=        │ "http", etc.  │ "http", etc.  │ "http", etc.  │ config        │
│ storage=       │ "memory", etc.│ "memory", etc.│ "memory", etc.│ config        │
│ plugins=       │ [плагіни]     │ [плагіни]     │ [плагіни]     │ config        │
│ callbacks      │ on_progress   │ on_progress   │ on_progress   │ event_bus     │
├────────────────┼──────────────────┼──────────────────┼──────────────────┼──────────────────┤
│ Код (рядків)   │ 1-5             │ 5-15            │ 10-20           │ 15-30           │
│ Коли використ. │ Швидкі скрипти  │ Багато краулів   │ Паралельність   │ Production      │
└────────────────┴──────────────────┴──────────────────┴──────────────────┴──────────────────┘

🎯 v3.1 SYNC-FIRST:
   - crawl(), Crawler - СИНХРОННІ, не потрібно async/await!
   - async_crawl(), AsyncCrawler - для паралельного краулінгу
   
🎯 EXTENSION POINTS (всі збережені!):
   driver: "http", "async", "playwright" або CustomDriver()
   storage: "memory", "json", "sqlite" або CustomStorage()
   plugins: [ваші плагіни]
   node_class: ваш кастомний Node клас
   url_rules: фільтрація URL
   callbacks: on_progress, on_node_scanned, on_error
"""

    print(comparison)


if __name__ == "__main__":
    print("\n🚀 GraphCrawler v3.1 Quick Start (Sync-First)\n")

    try:
        # Показуємо всі рівні
        graph1 = quick_level_1()
        graph2 = quick_level_1_with_params()
        graph3 = quick_level_2()
        graph4 = quick_level_2_context_manager()
        graph5 = quick_level_3()

        # Порівняльна таблиця
        show_api_comparison()

        print("\n" + "="*80)
        print("All API levels working correctly!")
        print("="*80)
        print("\n💡 Рекомендація:")
        print("   - Новачок? gc.crawl() - синхронна функція!")
        print("   - Багато краулів? gc.Crawler - reusable context manager")
        print("   - Паралельний краулінг? gc.AsyncCrawler - async для досвідчених")
        print("   - Production? ApplicationContainer - повний контроль")
        print("\n")

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        raise
