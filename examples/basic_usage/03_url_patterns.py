"""Basic Example 3: URL Patterns and Filtering

Цей приклад показує як працювати з URL patterns - що сканувати, що пропускати.
Ви навчитеся:
- URLRule для фільтрації
- Regex patterns для URL
- Пріоритетам сканування
- Ігноруванню файлів (PDF, images, тощо)

Сайт для тестування: https://www.royalroad.com/
"""

from graph_crawler import crawl
from graph_crawler.core.models import URLRule
import logging
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def example_1_basic_url_rules():
    """Приклад 1: Базові URL rules"""
    logger.info("=" * 60)
    logger.info("Example 1: Basic URL Rules")
    logger.info("=" * 60)

    # URLRule дозволяє контролювати які URL сканувати
    url_rules = [
        # Сканувати тільки сторінки fiction
        URLRule(
            pattern=r".*/fiction/.*",  # Regex pattern
            should_scan=True,
            priority=10  # Висо��ий пріоритет
        ),
        # Ігнорувати форум
        URLRule(
            pattern=r".*/forums/.*",
            should_scan=False
        ),
    ]

    graph = crawl(
        url="https://www.royalroad.com/",
        max_pages=30,
        max_depth=2,
        url_rules=url_rules
    )

    # Аналізуємо результати
    fiction_pages = 0
    forum_pages = 0
    other_pages = 0

    for node in graph.nodes.values():
        if hasattr(node, 'url'):
            if '/fiction/' in node.url:
                fiction_pages += 1
            elif '/forums/' in node.url:
                forum_pages += 1
            else:
                other_pages += 1

    logger.info(f"\n📊 Results:")
    logger.info(f"   📚 Fiction pages: {fiction_pages}")
    logger.info(f"   💬 Forum pages: {forum_pages} (should be 0)")
    logger.info(f"   📄 Other pages: {other_pages}")

    return graph


def example_2_ignore_file_types():
    """Приклад 2: Ігнорування типів файлів"""
    logger.info("\n" + "=" * 60)
    logger.info("Example 2: Ignore File Types")
    logger.info("=" * 60)

    # Часто треба ігнорувати файли (PDF, images, videos, тощо)
    url_rules = [
        # Ігнорувати PDF файли
        URLRule(pattern=r".*\.pdf$", should_scan=False),
        # Ігнорувати зображення
        URLRule(pattern=r".*\.(jpg|jpeg|png|gif|svg|webp)$", should_scan=False),
        # Ігнорувати відео
        URLRule(pattern=r".*\.(mp4|avi|mov|wmv)$", should_scan=False),
        # Ігнорувати архіви
        URLRule(pattern=r".*\.(zip|rar|7z|tar|gz)$", should_scan=False),
    ]

    graph = crawl(
        url="https://www.royalroad.com/",
        max_pages=25,
        max_depth=2,
        url_rules=url_rules
    )

    # Перевіряємо що не було файлів
    file_extensions = set()
    for node in graph.nodes.values():
        if hasattr(node, 'url'):
            url = node.url.lower()
            if '.' in url.split('/')[-1]:  # є розширення
                ext = url.split('.')[-1].split('?')[0]  # витягаємо розширення
                file_extensions.add(ext)

    logger.info(f"\nFound file extensions: {sorted(file_extensions)}")
    logger.info("💡 Note: No images/PDFs should be in the list")

    return graph


def example_3_priority_based_crawling():
    """Приклад 3: Пріоритетне сканування"""
    logger.info("\n" + "=" * 60)
    logger.info("Example 3: Priority-based Crawling")
    logger.info("=" * 60)

    # Пріоритет визначає порядок сканування
    url_rules = [
        # Найвищий пріоритет - fiction сторінки
        URLRule(
            pattern=r".*/fiction/\d+/.*",  # /fiction/123/chapter-name
            priority=100,
            should_scan=True
        ),
        # Середній пріоритет - огляди
        URLRule(
            pattern=r".*/reviews/.*",
            priority=50,
            should_scan=True
        ),
        # Низький пріоритет - все інше
        URLRule(
            pattern=r".*",
            priority=1,
            should_scan=True
        ),
    ]

    graph = crawl(
        url="https://www.royalroad.com/",
        max_pages=30,
        max_depth=2,
        url_rules=url_rules
    )

    stats = graph.get_stats()
    logger.info(f"\nScanned {stats['scanned_nodes']} pages")
    logger.info("📌 High-priority pages were scanned first")

    return graph


def example_4_complex_patterns():
    """Приклад 4: Складні URL patterns"""
    logger.info("\n" + "=" * 60)
    logger.info("Example 4: Complex URL Patterns")
    logger.info("=" * 60)

    url_rules = [
        # Тільки англійські fiction
        URLRule(
            pattern=r".*/fiction/\d+/[a-z0-9-]+$",
            should_scan=True,
            priority=90
        ),
        # Ігнорувати сторінки з параметрами (query strings)
        URLRule(
            pattern=r".*\?.*",  # містить ?
            should_scan=False
        ),
        # Ігнорувати anchor links
        URLRule(
            pattern=r".*#.*",  # містить #
            should_scan=False
        ),
        # Тільки HTTPS (безпека)
        URLRule(
            pattern=r"^https://.*",
            should_scan=True
        ),
        URLRule(
            pattern=r"^http://.*",  # HTTP без S
            should_scan=False
        ),
    ]

    graph = crawl(
        url="https://www.royalroad.com/",
        max_pages=20,
        max_depth=2,
        url_rules=url_rules
    )

    # Перевіряємо що всі URL відповідають правилам
    https_count = 0
    with_params = 0

    for node in graph.nodes.values():
        if hasattr(node, 'url'):
            if node.url.startswith('https://'):
                https_count += 1
            if '?' in node.url:
                with_params += 1

    logger.info(f"\nHTTPS URLs: {https_count}")
    logger.info(f"❌ URLs with params: {with_params} (should be 0)")

    return graph


def example_5_whitelist_blacklist():
    """Приклад 5: Whitelist та Blacklist підхід"""
    logger.info("\n" + "=" * 60)
    logger.info("Example 5: Whitelist/Blacklist Approach")
    logger.info("=" * 60)

    # Whitelist підхід - дозволяємо тільки певні URL
    whitelist_rules = [
        URLRule(pattern=r".*/fiction/.*", should_scan=True, priority=10),
        URLRule(pattern=r".*/author/.*", should_scan=True, priority=5),
        URLRule(pattern=r".*", should_scan=False, priority=0),  # Все інше - ні
    ]

    graph_whitelist = crawl(
        url="https://www.royalroad.com/",
        max_pages=20,
        max_depth=2,
        url_rules=whitelist_rules
    )

    logger.info(f"\n🎯 Whitelist approach:")
    logger.info(f"   Scanned: {len(graph_whitelist.nodes)} pages")

    # Blacklist підхід - блокуємо певні URL, решта дозволена
    blacklist_rules = [
        URLRule(pattern=r".*/forums/.*", should_scan=False),
        URLRule(pattern=r".*/user/.*", should_scan=False),
        URLRule(pattern=r".*/private/.*", should_scan=False),
        # Все інше дозволено (немає загального правила з should_scan=True)
    ]

    graph_blacklist = crawl(
        url="https://www.royalroad.com/",
        max_pages=20,
        max_depth=2,
        url_rules=blacklist_rules
    )

    logger.info(f"\n🚫 Blacklist approach:")
    logger.info(f"   Scanned: {len(graph_blacklist.nodes)} pages")

    logger.info("\n💡 When to use:")
    logger.info("   - Whitelist: коли знаєте точно що потрібно")
    logger.info("   - Blacklist: коли знаєте що НЕ потрібно")

    return graph_whitelist, graph_blacklist


if __name__ == "__main__":
    print("\n🚀 Starting URL Pattern Examples\n")

    try:
        example_1_basic_url_rules()
        example_2_ignore_file_types()
        example_3_priority_based_crawling()
        example_4_complex_patterns()
        example_5_whitelist_blacklist()

        print("\n" + "=" * 60)
        print("All URL pattern examples completed!")
        print("=" * 60)

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        raise
