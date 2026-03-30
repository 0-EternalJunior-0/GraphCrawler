"""Command Line Interface для GraphCrawler.

Використання:
    graph-crawler init <project_name>          # Створити новий проект
    graph-crawler crawl <url> [OPTIONS]        # Сканувати сайт
    graph-crawler scan-urls <file> [OPTIONS]   # Сканувати список URL
    graph-crawler list                         # Список збережених графів
    graph-crawler info <name>                  # Інформація про граф
    graph-crawler compare <name1> <name2>      # Порівняти два графи

Приклади:
    graph-crawler init my_project
    graph-crawler crawl https://example.com --max-depth 3
    graph-crawler scan-urls urls.txt --no-follow
    graph-crawler list
"""

import argparse
import sys

from graph_crawler.shared.constants import MAX_DEPTH_DEFAULT, MAX_PAGES_DEFAULT


def main():
    """Головна функція CLI."""
    parser = argparse.ArgumentParser(
        description="GraphCrawler - Бібліотека для побудови графу веб-сайтів",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Приклади:
    graph-crawler init my_project              # Створити проект
    graph-crawler crawl https://example.com    # Сканувати сайт
    graph-crawler scan-urls urls.txt           # Сканувати список URL
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Доступні команди")

    # Команда: init (НОВА!)
    init_parser = subparsers.add_parser(
        "init", help="Створити новий проект (як scrapy startproject)"
    )
    init_parser.add_argument("name", help="Назва проекту")
    init_parser.add_argument(
        "--dir", type=str, default=None, help="Директорія для створення (default: поточна)"
    )

    # Команда: scan-urls (НОВА!)
    scan_urls_parser = subparsers.add_parser("scan-urls", help="Сканувати список URL з файлу")
    scan_urls_parser.add_argument("file", help="Файл зі списком URL")
    scan_urls_parser.add_argument(
        "--no-follow", action="store_true", help="Не переходити за посиланнями"
    )
    scan_urls_parser.add_argument(
        "--output", type=str, default="results.json", help="Файл для результатів"
    )
    scan_urls_parser.add_argument(
        "--settings", type=str, default=None, help="Файл налаштувань (settings.yaml)"
    )

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
    subparsers.add_parser("list", help="Список збережених графів")

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
    if args.command == "init":
        init_command(args)
    elif args.command == "scan-urls":
        scan_urls_command(args)
    elif args.command == "crawl":
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


def init_command(args):
    """Створює новий проект."""
    from graph_crawler.api.project_init import init_project, print_success_message

    try:
        project_dir = init_project(args.name, args.dir)
        print_success_message(project_dir, args.name)
    except FileExistsError as e:
        print(f"❌ Помилка: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Помилка: {e}")
        sys.exit(1)


def scan_urls_command(args):
    """Сканує список URL з файлу."""
    import json

    import graph_crawler as gc

    # Читаємо URL з файлу
    urls = []
    try:
        with open(args.file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    urls.append(line)
    except FileNotFoundError:
        print(f"❌ Файл не знайдено: {args.file}")
        sys.exit(1)

    if not urls:
        print("❌ Файл порожній або не містить URL")
        sys.exit(1)

    print(f"🎯 URL для сканування: {len(urls)}")

    # Завантажуємо налаштування якщо є
    settings_kwargs = {}
    if args.settings:
        try:
            from graph_crawler.domain.value_objects.settings import CrawlerSettings

            settings = CrawlerSettings.from_file(args.settings)
            settings_kwargs = settings.to_crawl_kwargs()
            print(f"📋 Налаштування: {args.settings}")
        except Exception as e:
            print(f"⚠️  Помилка налаштувань: {e}, використовую defaults")

    # Сканування
    follow_links = not args.no_follow
    print(f"🔗 Переходити за посиланнями: {follow_links}")
    print()

    try:
        graph = gc.crawl(
            seed_urls=urls,
            follow_links=follow_links,
            same_domain=False,
            max_depth=1 if not follow_links else 3,
            **settings_kwargs,
        )

        stats = graph.get_stats()
        print()
        print("✅ Сканування завершено!")
        print(f"   📊 Вузлів: {stats['total_nodes']}")
        print(f"   📊 Просканованих: {stats['scanned_nodes']}")
        print(f"   📊 Посилань: {stats['total_edges']}")

        # Експорт
        if args.output:
            results = []
            for node in graph:
                if node.scanned:
                    results.append(
                        {
                            "url": node.url,
                            "title": node.get_title(),
                            "h1": node.get_h1(),
                            "status": node.response_status,
                        }
                    )

            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

            print(f"   💾 Результати: {args.output}")

    except Exception as e:
        print(f"❌ Помилка: {e}")
        sys.exit(1)


def crawl_command(args):
    """Виконує сканування."""
    import graph_crawler as gc

    print(f"  Сканування: {args.url}")
    print(f"   Глибина: {args.max_depth}, Сторінок: {args.max_pages}")
    print(f"   Драйвер: {args.driver}, Storage: {args.storage}")
    print()

    # Маппінг драйверів (sync API підтримує string values)
    driver_map = {
        "http": "http",
        "async": "async",
        "scrapy": "http",  # scrapy не підтримується, використовуємо HTTP
        "playwright": "playwright",
    }

    # Маппінг storage (sync API підтримує string values)
    storage_map = {
        "memory": "memory",
        "json": "json",
        "sqlite": "sqlite",
        "auto": "memory",  # auto -> memory для простоти
    }

    try:
        # Використовуємо sync API
        graph = gc.crawl(
            url=args.url,
            max_depth=args.max_depth,
            max_pages=args.max_pages,
            same_domain=args.same_domain,
            driver=driver_map.get(args.driver, "http"),
            storage=storage_map.get(args.storage, "memory"),
        )

        stats = graph.get_stats()
        print()
        print("Сканування завершено!")
        print(f"   Всього вузлів: {stats['total_nodes']}")
        print(f"   Просканованих: {stats['scanned_nodes']}")
        print(f"   Посилань: {stats['total_edges']}")

        # Збереження
        if args.save:
            gc.save_graph(graph, args.save)
            print(f"   Збережено як: {args.save}")

    except Exception as e:
        print(f" Помилка: {e}")
        sys.exit(1)


def list_command(args):
    """Виводить список збережених графів."""
    print(" Функція list_graphs() ще не реалізована в поточній версії")
    print(" Використовуйте gc.load_graph(filepath) для завантаження конкретного графу")
    sys.exit(0)


def info_command(args):
    """Виводить інформацію про граф."""
    import graph_crawler as gc

    try:
        graph = gc.load_graph(args.name)

        stats = graph.get_stats()
        print(f" Інформація про граф: {args.name}")
        print()
        print("   Статистика:")
        print(f"      Всього вузлів: {stats.get('total_nodes', 0)}")
        print(f"      Просканованих: {stats.get('scanned_nodes', 0)}")
        print(f"      Непросканованих: {stats.get('unscanned_nodes', 0)}")
        print(f"      Всього ребер: {stats.get('total_edges', 0)}")

    except FileNotFoundError:
        print(f" Граф '{args.name}' не знайдено")
        sys.exit(1)
    except Exception as e:
        print(f" Помилка: {e}")
        sys.exit(1)


def compare_command(args):
    """Порівнює два графи."""
    import graph_crawler as gc

    try:
        print(f" Порівняння графів: {args.name1} vs {args.name2}")
        print()

        graph1 = gc.load_graph(args.name1)
        graph2 = gc.load_graph(args.name2)

        if not graph1:
            raise FileNotFoundError(f"Граф '{args.name1}' не знайдено")
        if not graph2:
            raise FileNotFoundError(f"Граф '{args.name2}' не знайдено")

        # Базове порівняння (streaming через iter_nodes)
        nodes1 = {n.url for n in graph1.iter_nodes()}
        nodes2 = {n.url for n in graph2.iter_nodes()}

        added = len(nodes2 - nodes1)
        removed = len(nodes1 - nodes2)
        common = len(nodes1 & nodes2)
        total = len(nodes1 | nodes2)
        similarity = common / total if total > 0 else 0

        print(" Результати порівняння:")
        print(f"   Нових вузлів: {added}")
        print(f"   Видалених вузлів: {removed}")
        print(f"   Схожість: {similarity:.2%}")

    except FileNotFoundError as e:
        print(f" Граф не знайдено: {e}")
        sys.exit(1)
    except Exception as e:
        print(f" Помилка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
