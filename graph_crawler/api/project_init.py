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

# ==================== TEMPLATES ====================

SETTINGS_YAML_TEMPLATE = '''# GraphCrawler Settings
# Документація: https://github.com/0-EternalJunior-0/GraphCrawler

# === Базові налаштування ===
project_name: "{project_name}"
max_depth: 3
max_pages: 100
request_delay: 0.5
timeout: 300

# === Контроль доменів ===
same_domain: true
follow_links: true
allowed_domains: []
blocked_domains: []
blocked_paths:
  - /admin
  - /login
  - /logout
  - /wp-admin

# === Драйвер ===
driver:
  type: http  # http, playwright, stealth
  user_agent: null  # null = автоматичний
  headers: {{}}
  # Playwright specific
  headless: true
  browser_type: chromium
  viewport_width: 1920
  viewport_height: 1080
  block_resources:
    - image
    - media
    - font

# === Storage ===
storage:
  type: memory  # memory, json, sqlite, postgresql, mongodb
  path: null

# === Retry ===
retry:
  max_retries: 3
  retry_delay: 1.0
  backoff_factor: 2.0

# === Паралелізм ===
concurrency:
  max_concurrent_requests: 200
  connector_limit: 500
  connector_limit_per_host: 200

# === Фічі ===
respect_robots_txt: true
extract_metadata: true
calculate_content_hash: true
edge_strategy: all  # all, new_only, max_in_degree, deeper_only

# === Логування ===
log_level: INFO

# === Кастомні компоненти ===
node_class: nodes.CustomNode  # або null для стандартного
plugins:
  - plugins.MetadataEnricherPlugin
  # - plugins.ContentFilterPlugin

# === URL Rules ===
url_rules:
  - pattern: ".*\\\\.pdf$"
    should_scan: false
  - pattern: "/products/"
    priority: 10
  # - pattern: "/archive/"
  #   should_scan: true
  #   should_follow_links: false
'''

NODES_PY_TEMPLATE = '''"""
Кастомні Node класи для проекту {project_name}.

Тут визначаються ваші власні атрибути та логіка обробки сторінок.
Node викликається після парсингу HTML і може додавати власні поля.

Приклад:
    - JobNode для парсингу вакансій
    - ProductNode для e-commerce
    - ArticleNode для новин/блогів
"""

from typing import Any, Dict, List, Optional
from graph_crawler.domain.entities.node import Node


class CustomNode(Node):
    """
    Кастомний Node з додатковими полями.

    Розширює базовий Node додатковими атрибутами які ви визначаєте
    для вашого конкретного use case.

    Attributes:
        custom_field: Ваше кастомне поле
        extracted_data: Словник з витягнутими даними
    """

    # Додаткові поля (Pydantic автоматично їх валідує)
    custom_field: Optional[str] = None
    extracted_data: Dict[str, Any] = {{}}
    is_target_page: bool = False

    async def process_html(self, html: str) -> List[str]:
        """
        Обробка HTML сторінки.

        Викликається після завантаження сторінки.
        Тут ви можете:
        - Витягнути кастомні дані
        - Модифікувати metadata
        - Визначити чи це цільова сторінка

        Args:
            html: HTML контент сторінки

        Returns:
            Список знайдених посилань
        """
        # Викликаємо базову обробку (витягує посилання, metadata)
        links = await super().process_html(html)

        # === ВАША КАСТОМНА ЛОГІКА ТУТ ===

        # Приклад: визначення цільової сторінки
        if self._is_target_page():
            self.is_target_page = True
            self._extract_custom_data()

        return links

    def _is_target_page(self) -> bool:
        """
        Визначає чи це цільова сторінка для парсингу.

        Змініть логіку під ваш use case.
        """
        # Приклад: сторінка вакансії
        url_patterns = ['/job/', '/vacancy/', '/career/']
        return any(pattern in self.url.lower() for pattern in url_patterns)

    def _extract_custom_data(self) -> None:
        """
        Витягує кастомні дані зі сторінки.

        Використовує self.metadata який вже заповнений базовим парсером.
        """
        self.extracted_data = {{
            "title": self.get_title(),
            "h1": self.get_h1(),
            "description": self.get_description(),
            # Додайте свої поля
        }}


class JobNode(CustomNode):
    """
    Node для парсингу сторінок вакансій.

    Приклад спеціалізованого Node.
    """

    job_title: Optional[str] = None
    company: Optional[str] = None
    salary: Optional[str] = None
    location: Optional[str] = None

    def _is_target_page(self) -> bool:
        """Визначає чи це сторінка вакансії."""
        job_indicators = ['/job/', '/vacancy/', '/career/', '/jobs/']
        return any(ind in self.url.lower() for ind in job_indicators)

    def _extract_custom_data(self) -> None:
        """Витягує дані вакансії."""
        super()._extract_custom_data()

        # Тут можна додати спеціфічну логіку для витягування
        # salary, company, location з HTML
        self.job_title = self.get_h1()

        # Зберігаємо в extracted_data для експорту
        self.extracted_data.update({{
            "job_title": self.job_title,
            "company": self.company,
            "salary": self.salary,
            "location": self.location,
        }})


class ProductNode(CustomNode):
    """
    Node для парсингу e-commerce продуктів.

    Приклад для інтернет-магазинів.
    """

    product_name: Optional[str] = None
    price: Optional[str] = None
    sku: Optional[str] = None
    in_stock: bool = True

    def _is_target_page(self) -> bool:
        """Визначає чи це сторінка продукту."""
        return '/product/' in self.url.lower() or '/item/' in self.url.lower()
'''

PLUGINS_PY_TEMPLATE = '''"""
Кастомні плагіни для проекту {project_name}.

Плагіни дозволяють розширювати функціонал краулера на різних етапах:
- ON_NODE_CREATED: після створення Node (ще до сканування)
- ON_BEFORE_SCAN: перед скануванням сторінки
- ON_HTML_PARSED: після парсингу HTML (основне місце для логіки)
- ON_AFTER_SCAN: після завершення сканування сторінки
- BEFORE_CRAWL: перед початком краулінгу
- AFTER_CRAWL: після завершення краулінгу
"""

from typing import Any, Dict, List, Optional
from graph_crawler.extensions.plugins.node import BaseNodePlugin, NodePluginType, NodePluginContext


class MetadataEnricherPlugin(BaseNodePlugin):
    """
    Плагін для збагачення метаданих.

    Додає додаткові поля до metadata після парсингу HTML.
    """

    @property
    def name(self) -> str:
        return "metadata_enricher"

    @property
    def plugin_type(self) -> NodePluginType:
        return NodePluginType.ON_HTML_PARSED

    def execute(self, context: NodePluginContext) -> NodePluginContext:
        """
        Виконується після парсингу HTML.

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

        # Приклад: підрахунок зображень
        images = context.html_tree.find_all('img')
        context.user_data['image_count'] = len(images)

        # Приклад: витягування всіх заголовків
        headings = []
        for tag in ['h1', 'h2', 'h3']:
            for heading in context.html_tree.find_all(tag):
                headings.append({{
                    'tag': tag,
                    'text': heading.get_text(strip=True)[:100]
                }})
        context.user_data['headings'] = headings

        # Приклад: перевірка на цільову сторінку
        context.user_data['is_job_page'] = self._is_job_page(context.url)

        return context

    def _is_job_page(self, url: str) -> bool:
        """Визначає чи URL є сторінкою вакансії."""
        job_patterns = ['/job/', '/vacancy/', '/career/', '/jobs/']
        return any(p in url.lower() for p in job_patterns)


class ContentFilterPlugin(BaseNodePlugin):
    """
    Плагін для фільтрації контенту.

    Може пропустити сканування або модифікувати поведінку.
    """

    @property
    def name(self) -> str:
        return "content_filter"

    @property
    def plugin_type(self) -> NodePluginType:
        return NodePluginType.ON_BEFORE_SCAN

    def execute(self, context: NodePluginContext) -> NodePluginContext:
        """
        Виконується ПЕРЕД скануванням.

        Можна:
        - Пропустити сканування (context.should_scan = False)
        - Заборонити створення edges (context.can_create_edges = False)
        """
        # Приклад: пропустити PDF файли
        if context.url.lower().endswith('.pdf'):
            context.should_scan = False
            return context

        # Приклад: не слідувати за посиланнями з архіву
        if '/archive/' in context.url:
            context.can_create_edges = False

        return context


class DataExportPlugin(BaseNodePlugin):
    """
    Плагін для експорту даних після краулінгу.
    """

    @property
    def name(self) -> str:
        return "data_export"

    @property
    def plugin_type(self) -> NodePluginType:
        return NodePluginType.AFTER_CRAWL

    def __init__(self, output_path: str = "crawl_results.json"):
        self.output_path = output_path
        self.collected_data: List[Dict] = []

    def execute(self, context: NodePluginContext) -> NodePluginContext:
        """Експортує зібрані дані у файл."""
        import json

        # Збираємо дані з всіх нод
        if hasattr(context, 'graph'):
            for node in context.graph:
                if node.user_data.get('is_job_page'):
                    self.collected_data.append({{
                        'url': node.url,
                        'title': node.get_title(),
                        'data': node.user_data,
                    }})

            # Зберігаємо у файл
            with open(self.output_path, 'w', encoding='utf-8') as f:
                json.dump(self.collected_data, f, ensure_ascii=False, indent=2)

        return context
'''

CUSTOM_SCANNER_TEMPLATE = '''"""
Кастомні сканери для проекту {project_name}.

Сканери відповідають за отримання HTML контенту зі сторінок.
Використовуйте для:
- Обходу anti-bot захисту
- Роботи з JavaScript-rendered контентом
- Специфічних headers/cookies
"""

from typing import Optional, Dict, Any
from graph_crawler.domain.interfaces.driver import IDriver
from graph_crawler.domain.value_objects.models import FetchResponse


class CustomScanner(IDriver):
    """
    Кастомний сканер з вашою логікою.

    Implements IDriver interface для інтеграції з краулером.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {{}}
        self._closed = False

    async def fetch(self, url: str) -> FetchResponse:
        """
        Завантажує сторінку.

        Args:
            url: URL для завантаження

        Returns:
            FetchResponse з HTML контентом або помилкою
        """
        import aiohttp

        try:
            # Ваша кастомна логіка тут
            headers = self._get_headers()

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=30) as response:
                    html = await response.text()

                    return FetchResponse(
                        url=url,
                        html=html,
                        status_code=response.status,
                        headers=dict(response.headers),
                        final_url=str(response.url),
                    )

        except Exception as e:
            return FetchResponse(
                url=url,
                error=str(e),
            )

    def _get_headers(self) -> Dict[str, str]:
        """Повертає headers для запиту."""
        return {{
            "User-Agent": self.config.get(
                "user_agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            # Додайте свої headers
        }}

    async def close(self) -> None:
        """Закриває ресурси."""
        self._closed = True

    @property
    def is_closed(self) -> bool:
        return self._closed


class BrowserScanner(IDriver):
    """
    Сканер з використанням браузера (Playwright).

    Для JavaScript-rendered сторінок.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {{}}
        self._browser = None
        self._playwright = None

    async def _ensure_browser(self):
        """Ініціалізує браузер якщо потрібно."""
        if self._browser is None:
            from playwright.async_api import async_playwright

            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self.config.get("headless", True)
            )

    async def fetch(self, url: str) -> FetchResponse:
        """Завантажує сторінку через браузер."""
        try:
            await self._ensure_browser()

            page = await self._browser.new_page()

            try:
                response = await page.goto(url, wait_until="domcontentloaded")
                html = await page.content()

                return FetchResponse(
                    url=url,
                    html=html,
                    status_code=response.status if response else None,
                    final_url=page.url,
                )
            finally:
                await page.close()

        except Exception as e:
            return FetchResponse(url=url, error=str(e))

    async def close(self) -> None:
        """Закриває браузер."""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    @property
    def is_closed(self) -> bool:
        return self._browser is None
'''

DATA_PIPELINE_TEMPLATE = '''"""
Пайплайни обробки даних для проекту {project_name}.

Пайплайни обробляють дані ПІСЛЯ сканування.
Використовуйте для:
- Трансформації даних
- Збереження в базу даних
- Експорту в різні формати
- Валідації та очищення
"""

from typing import Any, Dict, List, Optional
from graph_crawler.domain.entities.graph import Graph
from graph_crawler.domain.entities.node import Node


class DataPipeline:
    """
    Базовий клас для пайплайнів обробки даних.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {{}}

    def process(self, graph: Graph) -> Any:
        """
        Обробляє граф після краулінгу.

        Args:
            graph: Граф з результатами сканування

        Returns:
            Результат обробки (залежить від пайплайну)
        """
        raise NotImplementedError


class JsonExportPipeline(DataPipeline):
    """
    Експортує результати в JSON.
    """

    def __init__(self, output_path: str = "results.json", **kwargs):
        super().__init__(**kwargs)
        self.output_path = output_path

    def process(self, graph: Graph) -> str:
        """Експортує граф в JSON файл."""
        import json

        data = []
        for node in graph:
            if node.scanned:
                data.append({{
                    "url": node.url,
                    "title": node.get_title(),
                    "h1": node.get_h1(),
                    "description": node.get_description(),
                    "status_code": node.response_status,
                    "depth": node.depth,
                    "metadata": node.metadata,
                    "user_data": node.user_data,
                }})

        with open(self.output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return self.output_path


class CsvExportPipeline(DataPipeline):
    """
    Експортує результати в CSV.
    """

    def __init__(self, output_path: str = "results.csv", **kwargs):
        super().__init__(**kwargs)
        self.output_path = output_path

    def process(self, graph: Graph) -> str:
        """Експортує граф в CSV файл."""
        import csv

        fieldnames = ['url', 'title', 'h1', 'status_code', 'depth']

        with open(self.output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for node in graph:
                if node.scanned:
                    writer.writerow({{
                        'url': node.url,
                        'title': node.get_title() or '',
                        'h1': node.get_h1() or '',
                        'status_code': node.response_status,
                        'depth': node.depth,
                    }})

        return self.output_path


class FilterPipeline(DataPipeline):
    """
    Фільтрує ноди за критеріями.
    """

    def __init__(self, filter_func=None, **kwargs):
        super().__init__(**kwargs)
        self.filter_func = filter_func or (lambda n: n.scanned)

    def process(self, graph: Graph) -> List[Node]:
        """Повертає відфільтровані ноди."""
        return [node for node in graph if self.filter_func(node)]


class TargetPagesPipeline(DataPipeline):
    """
    Витягує тільки цільові сторінки (вакансії, продукти, etc).
    """

    def __init__(self, url_patterns: List[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.url_patterns = url_patterns or ['/job/', '/vacancy/', '/product/']

    def process(self, graph: Graph) -> List[Dict[str, Any]]:
        """Повертає дані з цільових сторінок."""
        results = []

        for node in graph:
            if not node.scanned:
                continue

            # Перевіряємо чи URL відповідає патернам
            if any(p in node.url.lower() for p in self.url_patterns):
                results.append({{
                    'url': node.url,
                    'title': node.get_title(),
                    'h1': node.get_h1(),
                    'metadata': node.metadata,
                    'user_data': node.user_data,
                }})

        return results
'''

RUN_PY_TEMPLATE = '''#!/usr/bin/env python3
"""
Точка входу для проекту {project_name}.

Використання:
    python run.py                    # Сканування з settings.yaml
    python run.py --url URL          # Сканування конкретного URL
    python run.py --urls urls.txt    # Сканування списку URL
    python run.py --help             # Допомога
"""

import argparse
import sys
from pathlib import Path

# Пакет має бути встановлений через pip

import graph_crawler as gc
from graph_crawler.domain.value_objects.settings import CrawlerSettings


def load_urls_from_file(filepath: str) -> list:
    """Завантажує URL з файлу."""
    urls = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                urls.append(line)
    return urls


def main():
    parser = argparse.ArgumentParser(
        description="{project_name} - GraphCrawler Project",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Приклади:
    python run.py                           # Використовує settings.yaml
    python run.py --url https://example.com # Один URL
    python run.py --urls urls.txt           # Список URL з файлу
    python run.py --settings custom.yaml    # Інший файл налаштувань
        """
    )

    parser.add_argument(
        '--url',
        type=str,
        help='URL для сканування'
    )
    parser.add_argument(
        '--urls',
        type=str,
        help='Файл зі списком URL'
    )
    parser.add_argument(
        '--settings',
        type=str,
        default='settings.yaml',
        help='Файл налаштувань (default: settings.yaml)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='results.json',
        help='Файл для результатів (default: results.json)'
    )
    parser.add_argument(
        '--no-follow',
        action='store_true',
        help='Не переходити за посиланнями (тільки вказані URL)'
    )

    args = parser.parse_args()

    # Завантажуємо налаштування
    settings_path = Path(args.settings)
    if settings_path.exists():
        print(f"📋 Завантаження налаштувань: {{args.settings}}")
        settings = CrawlerSettings.from_file(settings_path)
    else:
        print(f"⚠️  Файл налаштувань не знайдено, використовую defaults")
        settings = CrawlerSettings()

    # Визначаємо URL для сканування
    urls = []
    if args.url:
        urls = [args.url]
    elif args.urls:
        urls = load_urls_from_file(args.urls)

    if not urls:
        print("❌ Не вказано URL для сканування!")
        print("   Використовуйте: --url URL або --urls файл.txt")
        sys.exit(1)

    print(f"🎯 URL для сканування: {{len(urls)}}")

    # Налаштовуємо параметри
    follow_links = not args.no_follow and settings.follow_links

    # Завантажуємо кастомні компоненти
    node_class = settings.get_node_class()
    plugins = settings.get_plugins()

    if node_class:
        print(f"📦 Використовую Node клас: {{node_class.__name__}}")
    if plugins:
        print(f"🔌 Завантажено плагінів: {{len(plugins)}}")

    # Виконуємо сканування
    print(f"🚀 Початок сканування...")
    print(f"   max_depth: {{settings.max_depth}}")
    print(f"   max_pages: {{settings.max_pages}}")
    print(f"   follow_links: {{follow_links}}")
    print()

    try:
        if len(urls) == 1:
            graph = gc.crawl(
                url=urls[0],
                **settings.to_crawl_kwargs(),
                node_class=node_class,
                plugins=plugins,
                follow_links=follow_links,
            )
        else:
            graph = gc.crawl(
                seed_urls=urls,
                **settings.to_crawl_kwargs(),
                node_class=node_class,
                plugins=plugins,
                follow_links=follow_links,
                same_domain=False,  # Дозволяємо різні домени для списку URL
            )

        # Статистика
        stats = graph.get_stats()
        print()
        print("✅ Сканування завершено!")
        print(f"   📊 Всього вузлів: {{stats['total_nodes']}}")
        print(f"   📊 Просканованих: {{stats['scanned_nodes']}}")
        print(f"   📊 Посилань: {{stats['total_edges']}}")

        # Експорт результатів
        if args.output:
            from pipelines.data_pipeline import JsonExportPipeline

            pipeline = JsonExportPipeline(output_path=args.output)
            output_file = pipeline.process(graph)
            print(f"   💾 Результати збережено: {{output_file}}")

        return graph

    except KeyboardInterrupt:
        print("\\n⚠️  Сканування перервано користувачем")
        sys.exit(0)
    except Exception as e:
        print(f"\\n❌ Помилка: {{e}}")
        sys.exit(1)


if __name__ == "__main__":
    main()
'''

URLS_TXT_TEMPLATE = '''# Список URL для сканування
# Рядки що починаються з # - коментарі

# Приклад:
# https://example.com/page1
# https://example.com/page2
# https://another-site.com/page

'''

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

    # Перевіряємо чи не існує
    if project_dir.exists():
        raise FileExistsError(f"Directory already exists: {project_dir}")

    # Створюємо структуру
    project_dir.mkdir(parents=True)

    # Створюємо піддиректорії
    scanners_dir = project_dir / "scanners"
    scanners_dir.mkdir()

    pipelines_dir = project_dir / "pipelines"
    pipelines_dir.mkdir()

    # Створюємо файли
    files_to_create = [
        ("settings.yaml", SETTINGS_YAML_TEMPLATE.format(project_name=project_name)),
        ("nodes.py", NODES_PY_TEMPLATE.format(project_name=project_name)),
        ("plugins.py", PLUGINS_PY_TEMPLATE.format(project_name=project_name)),
        ("run.py", RUN_PY_TEMPLATE.format(project_name=project_name)),
        ("urls.txt", URLS_TXT_TEMPLATE),
        ("scanners/__init__.py", INIT_PY_TEMPLATE.format(module_name="Scanners", project_name=project_name)),
        ("scanners/custom_scanner.py", CUSTOM_SCANNER_TEMPLATE.format(project_name=project_name)),
        ("pipelines/__init__.py", INIT_PY_TEMPLATE.format(module_name="Pipelines", project_name=project_name)),
        ("pipelines/data_pipeline.py", DATA_PIPELINE_TEMPLATE.format(project_name=project_name)),
    ]

    for filename, content in files_to_create:
        filepath = project_dir / filename
        filepath.write_text(content, encoding='utf-8')

    # Робимо run.py виконуваним
    run_py = project_dir / "run.py"
    run_py.chmod(run_py.stat().st_mode | 0o111)

    return project_dir


def print_success_message(project_dir: Path, project_name: str) -> None:
    """Виводить повідомлення про успішне створення."""
    print(f"""
✅ Проект '{project_name}' успішно створено!

📁 Структура проекту:
    {project_name}/
    ├── settings.yaml          # Конфігурація (як settings.py в Scrapy)
    ├── nodes.py               # Кастомні Node класи
    ├── plugins.py             # Кастомні плагіни
    ├── scanners/              # Кастомні сканери
    │   └── custom_scanner.py
    ├── pipelines/             # Обробка даних
    │   └── data_pipeline.py
    ├── run.py                 # Точка входу
    └── urls.txt               # Список URL (опціонально)

🚀 Швидкий старт:
    cd {project_name}
    python run.py --url https://example.com

    # Або список URL:
    python run.py --urls urls.txt --no-follow

📖 Документація: https://github.com/0-EternalJunior-0/GraphCrawler
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
