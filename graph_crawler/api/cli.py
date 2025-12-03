"""Command Line Interface для GraphCrawler.

Використання:
    graph-crawler crawl <url> [OPTIONS]
    graph-crawler list
    graph-crawler info <name>
    graph-crawler compare <name1> <name2>

Приклади:
    graph-crawler crawl https://example.com --max-depth 3
    graph-crawler list
    graph-crawler info mysite_scan
"""

import argparse
import sys
from typing import Optional

from graph_crawler import GraphCrawlerClient
from graph_crawler.infrastructure.persistence.base import StorageType
from graph_crawler.infrastructure.transport.base import DriverType
from graph_crawler.shared.constants import MAX_DEPTH_DEFAULT, MAX_PAGES_DEFAULT


def main():
    """Головна функція CLI."""
    parser = argparse.ArgumentParser(
        description="GraphCrawler - Бібліотека для побудови графу веб-сайтів",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Доступні команди")

    # Команда: crawl
    crawl_parser = subparsers.add_parser("crawl", help="Сканування веб-сайту")
    crawl_parser.add_argument("url", help="URL для сканування")
    crawl_parser.add_argument(
        "--max-depth",
        type=int,
        default=MAX_DEPTH_DEFAULT,
        help=f"Максимальна глибина (default: {MAX_DEPTH_DEFAULT})",
    )
    crawl_parser.add_argument(
        "--max-pages",
        type=int,
        default=MAX_PAGES_DEFAULT,
        help=f"Максимум сторінок (default: {MAX_PAGES_DEFAULT})",
    )
    crawl_parser.add_argument(
        "--driver",
        choices=["http", "async", "scrapy", "playwright"],
        default="http",
        help="Тип драйвера (default: http)",
    )
    crawl_parser.add_argument(
        "--storage",
        choices=["memory", "json", "sqlite", "auto"],
        default="auto",
        help="Тип storage (default: auto)",
    )
    crawl_parser.add_argument("--save", type=str, help="Зберегти граф з іменем")
    crawl_parser.add_argument(
        "--same-domain",
        action="store_true",
        default=True,
        help="Сканувати тільки поточний домен",
    )
    crawl_parser.add_argument(
        "--workers", type=int, default=1, help="Кількість воркерів (multiprocessing)"
    )
    crawl_parser.add_argument(
        "--mode",
        choices=["sequential", "multiprocessing", "celery"],
        default="sequential",
        help="Режим обробки",
    )

    # Команда: list
    list_parser = subparsers.add_parser("list", help="Список збережених графів")

    # Команда: info
    info_parser = subparsers.add_parser("info", help="Інформація про граф")
    info_parser.add_argument("name", help="Ім'я графа")

    # Команда: compare
    compare_parser = subparsers.add_parser("compare", help="Порівняти два графи")
    compare_parser.add_argument("name1", help="Ім'я першого графа")
    compare_parser.add_argument("name2", help="Ім'я другого графа")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Виконання команд
    if args.command == "crawl":
        crawl_command(args)
    elif args.command == "list":
        list_command(args)
    elif args.command == "info":
        info_command(args)
    elif args.command == "compare":
        compare_command(args)
    else:
        parser.print_help()
        sys.exit(1)


def crawl_command(args):
    """Виконує сканування."""
    print(f"  Сканування: {args.url}")
    print(f"   Глибина: {args.max_depth}, Сторінок: {args.max_pages}")
    print(f"   Драйвер: {args.driver}, Storage: {args.storage}")
    print()

    # Конвертуємо driver
    driver_map = {
        "http": DriverType.HTTP,
        "async": DriverType.ASYNC,
        "scrapy": DriverType.SCRAPY,
        "playwright": DriverType.PLAYWRIGHT,
    }

    # Конвертуємо storage
    storage_map = {
        "memory": StorageType.MEMORY,
        "json": StorageType.JSON,
        "sqlite": StorageType.SQLITE,
        "auto": StorageType.AUTO,
    }

    client = GraphCrawlerClient()

    try:
        graph = client.crawl(
            url=args.url,
            max_depth=args.max_depth,
            max_pages=args.max_pages,
            same_domain_only=args.same_domain,
            driver_type=driver_map[args.driver],
            storage_type=storage_map[args.storage],
            workers=args.workers,
            mode=args.mode,
        )

        stats = graph.get_stats()
        print()
        print("Сканування завершено!")
        print(f"   Всього вузлів: {stats['total_nodes']}")
        print(f"   Просканованих: {stats['scanned_nodes']}")
        print(f"   Посилань: {stats['total_edges']}")

        # Збереження
        if args.save:
            full_name = client.save_graph(args.save, description=f"Скан {args.url}")
            print(f"   Збережено як: {full_name}")

    except Exception as e:
        print(f" Помилка: {e}")
        sys.exit(1)
    finally:
        client.close()


def list_command(args):
    """Виводить список збережених графів."""
    client = GraphCrawlerClient()

    try:
        graphs = client.list_graphs()

        if not graphs:
            print(" Немає збережених графів")
            return

        print(f" Збережені графи ({len(graphs)}):")
        print()

        for i, meta in enumerate(graphs, 1):
            print(f"{i}. {meta.name}")
            print(f"   Повне ім'я: {meta.full_name}")
            print(f"   Створено: {meta.created_at}")
            print(
                f"   Вузлів: {meta.stats.total_nodes}, Ребер: {meta.stats.total_edges}"
            )
            if meta.description:
                print(f"   Опис: {meta.description}")
            print()

    except Exception as e:
        print(f" Помилка: {e}")
        sys.exit(1)
    finally:
        client.close()


def info_command(args):
    """Виводить інформацію про граф."""
    client = GraphCrawlerClient()

    try:
        meta = client.get_graph_metadata(args.name)

        if not meta:
            print(f" Граф '{args.name}' не знайдено")
            sys.exit(1)

        print(f" Інформація про граф: {meta.name}")
        print(f"   Повне ім'я: {meta.full_name}")
        print(f"   Створено: {meta.created_at}")
        print(f"   Опис: {meta.description or 'N/A'}")
        print()
        print("   Статистика:")
        print(f"      Всього вузлів: {meta.stats.total_nodes}")
        print(f"      Просканованих: {meta.stats.scanned_nodes}")
        print(f"      Непросканованих: {meta.stats.unscanned_nodes}")
        print(f"      Всього ребер: {meta.stats.total_edges}")

        if meta.metadata:
            print()
            print("   Додаткові метадані:")
            for key, value in meta.metadata.items():
                print(f"      {key}: {value}")

    except Exception as e:
        print(f" Помилка: {e}")
        sys.exit(1)
    finally:
        client.close()


def compare_command(args):
    """Порівнює два графи."""
    client = GraphCrawlerClient()

    try:
        print(f" Порівняння графів: {args.name1} vs {args.name2}")
        print()

        result = client.compare_graphs(args.name1, args.name2)

        print(" Результати порівняння:")
        print(f"   Нових вузлів: {result.added_nodes}")
        print(f"   Видалених вузлів: {result.removed_nodes}")
        print(f"   Нових ребер: {result.added_edges}")
        print(f"   Видалених ребер: {result.removed_edges}")
        print(f"   Схожість: {result.similarity:.2%}")

    except Exception as e:
        print(f" Помилка: {e}")
        sys.exit(1)
    finally:
        client.close()


if __name__ == "__main__":
    main()
