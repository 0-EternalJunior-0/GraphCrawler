"""
Тест для перевірки фіксу race condition в парсері.

Проблема: get_default_parser() повертав singleton, і при паралельному
парсингу кілька нод перезаписували self._tree один одному.

Фікс: create_parser_instance() створює НОВИЙ instance для кожного виклику.
"""

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

class TestRaceConditionFix:
    """Тести для перевірки фіксу race condition."""

    def test_create_parser_instance_returns_new_instances(self):
        """Перевіряє що create_parser_instance() повертає різні instance."""
        from graph_crawler.infrastructure.adapters import create_parser_instance

        parser1 = create_parser_instance()
        parser2 = create_parser_instance()
        parser3 = create_parser_instance()

        # Повинні бути РІЗНІ об'єкти
        assert parser1 is not parser2
        assert parser2 is not parser3
        assert parser1 is not parser3

        print("✅ create_parser_instance() повертає різні instance")

    def test_get_default_parser_returns_same_instance(self):
        """Перевіряє що get_default_parser() повертає той самий singleton."""
        from graph_crawler.infrastructure.adapters import get_default_parser

        parser1 = get_default_parser()
        parser2 = get_default_parser()
        parser3 = get_default_parser()

        # Повинні бути ОДНАКОВІ об'єкти (singleton)
        assert parser1 is parser2
        assert parser2 is parser3

        print("✅ get_default_parser() повертає той самий singleton")

    def test_parallel_parsing_no_race_condition(self):
        """
        Тест на відсутність race condition при паралельному парсингу.

        Симулює ситуацію коли кілька threads парсять різний HTML одночасно.
        Кожен thread повинен отримати свій canonical URL, а не чужий.
        """
        from graph_crawler.infrastructure.adapters import create_parser_instance

        # Різні HTML з різними canonical URL
        html_templates = [
            '<html><head><link rel="canonical" href="https://example.com/page{i}"></head><body>Page {i}</body></html>'
            for i in range(10)
        ]

        results = {}
        errors = []

        def parse_html(index: int) -> None:
            """Парсить HTML і зберігає canonical."""
            html = html_templates[index].format(i=index)
            expected_canonical = f"https://example.com/page{index}"

            # Використовуємо create_parser_instance() для thread-safe парсингу
            parser = create_parser_instance()
            parser.parse(html)

            # Шукаємо canonical
            canonical_elem = parser.find('link[rel="canonical"]')
            if canonical_elem:
                actual_canonical = canonical_elem.get_attribute("href")
                results[index] = actual_canonical

                # Перевіряємо що canonical правильний
                if actual_canonical != expected_canonical:
                    errors.append(
                        f"Thread {index}: expected '{expected_canonical}', "
                        f"got '{actual_canonical}'"
                    )

        # Запускаємо паралельно
        with ThreadPoolExecutor(max_workers=10) as executor:
            executor.map(parse_html, range(10))

        # Перевіряємо результати
        assert len(errors) == 0, "Race condition detected:\n" + "\n".join(errors)
        assert len(results) == 10, f"Not all threads completed: {len(results)}/10"

        for i in range(10):
            assert results[i] == f"https://example.com/page{i}", \
                f"Wrong canonical for thread {i}: {results[i]}"

        print("✅ Паралельний парсинг працює без race condition")

    def test_singleton_race_condition_exists(self):
        """
        Демонструє що singleton МАЄ race condition при паралельному використанні.

        Цей тест може бути flaky через природу race condition,
        але він демонструє проблему.
        """
        from graph_crawler.infrastructure.adapters import get_default_parser

        # Різні HTML
        htmls = [
            '<html><head><title>Title A</title></head></html>',
            '<html><head><title>Title B</title></head></html>',
        ]

        results = {"A": [], "B": []}

        # Singleton parser
        parser = get_default_parser()

        def parse_a():
            for _ in range(50):
                parser.parse(htmls[0])
                title = parser.find("title")
                if title:
                    results["A"].append(title.text())

        def parse_b():
            for _ in range(50):
                parser.parse(htmls[1])
                title = parser.find("title")
                if title:
                    results["B"].append(title.text())

        # Запускаємо паралельно (з великою ймовірністю race condition)
        threads = [
            threading.Thread(target=parse_a),
            threading.Thread(target=parse_b),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Перевіряємо чи є "чужі" результати
        wrong_a = [t for t in results["A"] if t != "Title A"]
        wrong_b = [t for t in results["B"] if t != "Title B"]

        print(f"Thread A results: {len(results['A'])} total, {len(wrong_a)} wrong")
        print(f"Thread B results: {len(results['B'])} total, {len(wrong_b)} wrong")

        # Якщо є хоча б один неправильний результат - race condition є
        if wrong_a or wrong_b:
            print("⚠️ Race condition detected with singleton (expected!)")
        else:
            print("ℹ️ Race condition not detected in this run (timing dependent)")

class TestNodeParsingFix:
    """Тести для перевірки фіксу в Node._parse_html_sync."""

    @pytest.mark.asyncio
    async def test_node_process_html_parallel(self):
        """
        Тест паралельної обробки HTML кількома нодами.

        Кожна нода повинна отримати свої метадані, а не чужі.
        """
        from graph_crawler.domain.entities.node import Node
        from graph_crawler.extensions.plugins.node import (
            NodePluginManager,
            get_default_node_plugins,
        )

        # Створюємо plugin manager
        plugin_manager = NodePluginManager()
        for plugin in get_default_node_plugins():
            plugin_manager.register(plugin)

        # Створюємо 5 нод з різним контентом
        nodes = []
        for i in range(5):
            node = Node(
                url=f"https://example.com/page{i}",
                plugin_manager=plugin_manager,
            )
            nodes.append(node)

        # Різний HTML для кожної ноди
        htmls = [
            f'''<html>
            <head>
                <title>Title {i}</title>
                <link rel="canonical" href="https://example.com/canonical{i}">
            </head>
            <body><h1>Heading {i}</h1></body>
            </html>'''
            for i in range(5)
        ]

        # Паралельно обробляємо HTML
        tasks = [node.process_html(htmls[i]) for i, node in enumerate(nodes)]
        await asyncio.gather(*tasks)

        # Перевіряємо результати
        for i, node in enumerate(nodes):
            expected_title = f"Title {i}"
            expected_canonical = f"https://example.com/canonical{i}"
            expected_h1 = f"Heading {i}"

            actual_title = node.get_title()
            actual_canonical = node.get_canonical_url()
            actual_h1 = node.get_h1()

            assert actual_title == expected_title, \
                f"Node {i}: expected title '{expected_title}', got '{actual_title}'"

            assert actual_canonical == expected_canonical, \
                f"Node {i}: expected canonical '{expected_canonical}', got '{actual_canonical}'"

            assert actual_h1 == expected_h1, \
                f"Node {i}: expected h1 '{expected_h1}', got '{actual_h1}'"

        print("✅ Паралельна обробка HTML нодами працює без race condition")

if __name__ == "__main__":
    # Запуск тестів
    test = TestRaceConditionFix()
    test.test_create_parser_instance_returns_new_instances()
    test.test_get_default_parser_returns_same_instance()
    test.test_parallel_parsing_no_race_condition()
    test.test_singleton_race_condition_exists()

    print("\n--- Node tests ---")
    import asyncio
    node_test = TestNodeParsingFix()
    asyncio.run(node_test.test_node_process_html_parallel())
