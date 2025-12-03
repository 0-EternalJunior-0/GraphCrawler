"""Basic Example 5: Graph Operations v2.0

Цей приклад показує базові операції з графами з новим API v2.0:
- Створення графу через gc.crawl()
- Об'єднання графів (union)
- Різниця між графами (difference)
- Пошук вузлів
- Статистика графу

Сайт для тестування: https://www.royalroad.com/
"""

import logging
import graph_crawler as gc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def example_1_simple_crawl():
    """Приклад 1: Найпростіший краулінг з gc.crawl()"""
    logger.info("=" * 60)
    logger.info("Example 1: Simple Crawl with gc.crawl()")
    logger.info("=" * 60)

    # Одна функція!
    graph = gc.crawl(
        "https://www.royalroad.com/",
        max_pages=10,
        max_depth=2
    )

    stats = graph.get_stats()
    logger.info(f"\nРезультат:")
    logger.info(f"   📄 Вузлів: {stats['total_nodes']}")
    logger.info(f"   🔗 Ребер: {stats['total_edges']}")

    return graph


def example_2_manual_graph_building():
    """Приклад 2: Створення графу вручну"""
    logger.info("\n" + "=" * 60)
    logger.info("Example 2: Manual Graph Building")
    logger.info("=" * 60)

    # Створюємо порожній граф
    graph = gc.Graph()

    # Створюємо вузли вручну
    node1 = gc.Node(
        url="https://www.royalroad.com/fictions/best-rated",
        title="Best Rated Fictions",
        depth=0
    )

    node2 = gc.Node(
        url="https://www.royalroad.com/fictions/best-rated?page=2",
        title="Best Rated Page 2",
        depth=1
    )

    node3 = gc.Node(
        url="https://www.royalroad.com/fictions/best-rated?page=3",
        title="Best Rated Page 3",
        depth=1
    )

    # Додаємо вузли
    graph.add_node(node1)
    graph.add_node(node2)
    graph.add_node(node3)

    # Створюємо ребра
    edge1 = gc.Edge(
        source_node_id=node1.url,
        target_node_id=node2.url
    )
    edge2 = gc.Edge(
        source_node_id=node1.url,
        target_node_id=node3.url
    )

    graph.add_edge(edge1)
    graph.add_edge(edge2)

    stats = graph.get_stats()
    logger.info(f"\nСтворено граф вручну:")
    logger.info(f"   📄 Вузлів: {stats['total_nodes']}")
    logger.info(f"   🔗 Ребер: {stats['total_edges']}")

    return graph


def example_3_graph_union():
    """Приклад 3: Об'єднання графів"""
    logger.info("\n" + "=" * 60)
    logger.info("Example 3: Graph Union")
    logger.info("=" * 60)

    # Краулимо два різні розділи
    graph1 = gc.crawl(
        url="https://www.royalroad.com/fictions/best-rated",
        max_pages=10,
        max_depth=1
    )

    graph2 = gc.crawl(
        url="https://www.royalroad.com/fictions/trending",
        max_pages=10,
        max_depth=1
    )

    stats1 = graph1.get_stats()
    stats2 = graph2.get_stats()

    logger.info(f"\n📊 До об'єднання:")
    logger.info(f"   Graph 1: {stats1['total_nodes']} вузлів")
    logger.info(f"   Graph 2: {stats2['total_nodes']} вузлів")

    # Об'єднуємо
    from graph_crawler.core.graph_operations import GraphOperations

    combined = GraphOperations.union(graph1, graph2)
    stats_combined = combined.get_stats()

    logger.info(f"\nПісля об'єднання:")
    logger.info(f"   Combined: {stats_combined['total_nodes']} вузлів")
    logger.info(f"   (може бути менше якщо були дублікати)")

    return combined


def example_4_graph_difference():
    """Приклад 4: Різниця між графами (зміни на сайті)"""
    logger.info("\n" + "=" * 60)
    logger.info("Example 4: Graph Difference (Зміни)")
    logger.info("=" * 60)

    logger.info("\n🕐 Перший скан...")
    graph_old = gc.crawl(
        url="https://www.royalroad.com/",
        max_pages=10,
        max_depth=2
    )

    logger.info("\n🕑 Другий скан...")
    graph_new = gc.crawl(
        url="https://www.royalroad.com/",
        max_pages=15,  # Більше сторінок
        max_depth=2
    )

    # Знаходимо різницю
    from graph_crawler.core.graph_operations import GraphOperations

    diff = GraphOperations.difference(graph_new, graph_old)

    stats_old = graph_old.get_stats()
    stats_new = graph_new.get_stats()
    stats_diff = diff.get_stats()

    logger.info(f"\n📊 Порівняння:")
    logger.info(f"   Старий: {stats_old['total_nodes']} вузлів")
    logger.info(f"   Новий: {stats_new['total_nodes']} вузлів")
    logger.info(f"   Нові сторінки: {stats_diff['total_nodes']} вузлів")

    # Показуємо нові URL
    if stats_diff['total_nodes'] > 0:
        logger.info("\nНові URL (перші 5):")
        for i, url in enumerate(list(diff.nodes.keys())[:5]):
            logger.info(f"   {i+1}. {url[:60]}...")

    return diff


def example_5_node_search():
    """Приклад 5: Пошук вузлів"""
    logger.info("\n" + "=" * 60)
    logger.info("Example 5: Node Search")
    logger.info("=" * 60)

    graph = gc.crawl(
        url="https://www.royalroad.com/",
        max_pages=25,
        max_depth=2
    )

    # Пошук за URL
    logger.info("\n🔍 Пошук за URL pattern '/fiction/'...")
    fiction_nodes = [node for url, node in graph.nodes.items() if '/fiction/' in url]
    logger.info(f"   Знайдено {len(fiction_nodes)} fiction сторінок")

    # Пошук за глибиною
    logger.info("\n🔍 Пошук за глибиною (depth=1)...")
    depth_1 = [node for url, node in graph.nodes.items()
               if hasattr(node, 'depth') and node.depth == 1]
    logger.info(f"   Знайдено {len(depth_1)} вузлів на глибині 1")

    # Пошук відсканованих
    logger.info("\n🔍 Пошук відсканованих...")
    scanned = [node for url, node in graph.nodes.items()
               if hasattr(node, 'scanned') and node.scanned]
    logger.info(f"   Знайдено {len(scanned)} відсканованих")

    return graph


def example_6_graph_statistics():
    """Приклад 6: Детальна статистика графу"""
    logger.info("\n" + "=" * 60)
    logger.info("Example 6: Detailed Graph Statistics")
    logger.info("=" * 60)

    graph = gc.crawl(
        url="https://www.royalroad.com/",
        max_pages=25,
        max_depth=2
    )

    stats = graph.get_stats()

    logger.info("\n📊 Детальна статистика:")
    logger.info(f"\n🌐 Вузли (Nodes):")
    logger.info(f"   Всього: {stats['total_nodes']}")
    logger.info(f"   Відскановані: {stats['scanned_nodes']}")
    logger.info(f"   Очікують: {stats['pending_nodes']}")

    logger.info(f"\n🔗 Ребра (Edges):")
    logger.info(f"   Всього: {stats['total_edges']}")

    # Розподіл за глибиною
    logger.info(f"\n📈 Розподіл за глибиною:")
    depth_dist = {}
    for url, node in graph.nodes.items():
        if hasattr(node, 'depth'):
            depth = node.depth
            depth_dist[depth] = depth_dist.get(depth, 0) + 1

    for depth in sorted(depth_dist.keys()):
        logger.info(f"   Depth {depth}: {depth_dist[depth]} вузлів")

    # Домени
    logger.info(f"\n🌍 Домени:")
    from urllib.parse import urlparse
    domains = {}
    for url, node in graph.nodes.items():
        domain = urlparse(url).netloc
        domains[domain] = domains.get(domain, 0) + 1

    for domain, count in sorted(domains.items(), key=lambda x: x[1], reverse=True)[:5]:
        logger.info(f"   {domain}: {count} сторінок")

    return graph


if __name__ == "__main__":
    print("\n🚀 GraphCrawler v2.0 Graph Operations Examples\n")

    try:
        graph1 = example_1_simple_crawl()
        graph2 = example_2_manual_graph_building()
        graph3 = example_3_graph_union()
        graph4 = example_4_graph_difference()
        graph5 = example_5_node_search()
        graph6 = example_6_graph_statistics()

        print("\n" + "=" * 60)
        print("All graph operations examples completed!")
        print("=" * 60)

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        raise
