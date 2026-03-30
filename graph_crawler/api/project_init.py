"""
Ініціалізація нового проекту GraphCrawler.

Команда: gc init <project_name>

Створює структуру:
    my_project/
    ├── settings.yaml          # Конфігурація
    ├── nodes.py               # Кастомні Node класи
    ├── plugins.py             # Кастомні плагіни
    ├── scanners/              # Кастомні сканери
    │   ├── __init__.py
    │   └── custom_scanner.py
    ├── pipelines/             # Обробка даних
    │   ├── __init__.py
    │   └── data_pipeline.py
    ├── run.py                 # Точка входу
    └── urls.txt               # Список URL (опціонально)
"""

from pathlib import Path
from typing import Optional

SETTINGS_YAML_TEMPLATE = """# GraphCrawler Settings
# Документація: https://github.com/0-EternalJunior-0/GraphCrawler
project_name: "{project_name}"
"""

NODES_PY_TEMPLATE = '''"""
Кастомні Node класи для проекту {project_name}.

        Args:
            html: HTML контент сторінки
        Returns:
            Список знайдених посилань
        """
        # Викликаємо базову обробку (витягує посилання, metadata)
        links = await super().process_html(html)
        # Приклад: визначення цільової сторінки
        if self._is_target_page():
            self.is_target_page = True
            self._extract_custom_data()
'''

PLUGINS_PY_TEMPLATE = '''"""
Кастомні плагіни для проекту {project_name}.

        Args:
            context: Контекст з даними про сторінку
                - context.node: Node об'єкт
                - context.html: сирий HTML
                - context.html_tree: BeautifulSoup об'єкт
                - context.metadata: словник метаданих
                - context.extracted_links: знайдені посилання
                - context.user_data: словник для ваших даних
        Returns:
            Модифікований context
        """
        if context.html_tree is None:
            return context
'''

CUSTOM_SCANNER_TEMPLATE = '''"""
Кастомні сканери для проекту {project_name}.

        Args:
            url: URL для завантаження
        Returns:
            FetchResponse з HTML контентом або помилкою
        """
        import aiohttp
'''

DATA_PIPELINE_TEMPLATE = '''"""
Пайплайни обробки даних для проекту {project_name}.

        Args:
            graph: Граф з результатами сканування
        Returns:
            Результат обробки (залежить від пайплайну)
        """
        raise NotImplementedError
'''

RUN_PY_TEMPLATE = '''#!/usr/bin/env python3
"""
Точка входу для проекту {project_name}.
'''

URLS_TXT_TEMPLATE = """# Список URL для сканування
# Рядки що починаються з # - коментарі

# Приклад:
# https://example.com/page1
# https://example.com/page2
# https://another-site.com/page

"""

INIT_PY_TEMPLATE = '''"""
{module_name} модуль для проекту {project_name}.
"""
'''


def init_project(project_name: str, target_dir: Optional[str] = None) -> Path:
    """
    Створює новий проект GraphCrawler.

    Args:
        project_name: Назва проекту
        target_dir: Директорія для створення (default: поточна)

    Returns:
        Path до створеного проекту
    """
    # Визначаємо директорію
    if target_dir:
        base_dir = Path(target_dir)
    else:
        base_dir = Path.cwd()

    project_dir = base_dir / project_name
    if project_dir.exists():
        raise FileExistsError(f"Directory already exists: {project_dir}")
    project_dir.mkdir(parents=True)
    scanners_dir = project_dir / "scanners"
    scanners_dir.mkdir()

    pipelines_dir = project_dir / "pipelines"
    pipelines_dir.mkdir()
    files_to_create = [
        ("settings.yaml", SETTINGS_YAML_TEMPLATE.format(project_name=project_name)),
        ("nodes.py", NODES_PY_TEMPLATE.format(project_name=project_name)),
        ("plugins.py", PLUGINS_PY_TEMPLATE.format(project_name=project_name)),
        ("run.py", RUN_PY_TEMPLATE.format(project_name=project_name)),
        ("urls.txt", URLS_TXT_TEMPLATE),
        (
            "scanners/__init__.py",
            INIT_PY_TEMPLATE.format(module_name="Scanners", project_name=project_name),
        ),
        ("scanners/custom_scanner.py", CUSTOM_SCANNER_TEMPLATE.format(project_name=project_name)),
        (
            "pipelines/__init__.py",
            INIT_PY_TEMPLATE.format(module_name="Pipelines", project_name=project_name),
        ),
        ("pipelines/data_pipeline.py", DATA_PIPELINE_TEMPLATE.format(project_name=project_name)),
    ]

    for filename, content in files_to_create:
        filepath = project_dir / filename
        filepath.write_text(content, encoding="utf-8")

    # Робимо run.py виконуваним
    run_py = project_dir / "run.py"
    run_py.chmod(run_py.stat().st_mode | 0o111)

    return project_dir


def print_success_message(project_dir: Path, project_name: str) -> None:
    """Виводить повідомлення про успішне створення."""
    print(f"""
✅ Проект '{project_name}' успішно створено!

""")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python project_init.py <project_name> [target_dir]")
        sys.exit(1)

    name = sys.argv[1]
    target = sys.argv[2] if len(sys.argv) > 2 else None

    try:
        path = init_project(name, target)
        print_success_message(path, name)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
