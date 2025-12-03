"""Фікстури для тестів GraphCrawler з агресивним async cleanup."""

import pytest
import pytest_asyncio
import asyncio
import tempfile
import shutil
import gc
import warnings
from pathlib import Path
from unittest.mock import AsyncMock, Mock
from graph_crawler.domain.entities.node import Node
from graph_crawler.domain.entities.edge import Edge
from graph_crawler.domain.entities.graph import Graph


# ==========================================
# PYTEST CONFIGURATION
# ==========================================

def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "e2e: mark test as end-to-end test")
    config.addinivalue_line("markers", "distributed: mark test as distributed crawling test")
    config.addinivalue_line("markers", "playwright: mark test as requiring Playwright")

    # Suppress aiohttp warnings
    warnings.filterwarnings("ignore", category=ResourceWarning)
    warnings.filterwarnings("ignore", message="unclosed")
    warnings.filterwarnings("ignore", message="Unclosed")


@pytest.fixture(scope="function")
def event_loop():
    """
    Створює новий event loop для КОЖНОГО тесту.
    
    Це гарантує що:
    1. Кожен тест має чистий event loop
    2. Немає витоків між тестами
    3. Після тесту loop закривається
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop

    # Cleanup після тесту
    try:
        # Cancel всі pending tasks
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()

        # Wait for cancellation
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))

        # Shutdown asyncgens
        loop.run_until_complete(loop.shutdown_asyncgens())

        # Close loop
        loop.close()
    except Exception:
        pass
    finally:
        # Force garbage collection
        gc.collect()


# ==========================================
# ASYNC DRIVER FIXTURES
# ==========================================

@pytest_asyncio.fixture
async def async_driver():
    """Fixture для AsyncDriver з автоматичним cleanup."""
    from graph_crawler.infrastructure.transport.async_http.driver import AsyncDriver

    driver = AsyncDriver()
    yield driver

    # Cleanup
    try:
        await driver.close()
        await asyncio.sleep(0.01)
    except Exception:
        pass


# ==========================================
# STORAGE FIXTURES
# ==========================================

@pytest.fixture
def temp_dir():
    """Створює тимчасову директорію для тестів."""
    tmp_dir = tempfile.mkdtemp()
    yield tmp_dir

    # Cleanup with retry
    import time
    for attempt in range(5):
        try:
            shutil.rmtree(tmp_dir, ignore_errors=False)
            break
        except (PermissionError, OSError):
            if attempt < 4:
                time.sleep(0.2)
            else:
                shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest_asyncio.fixture
async def sqlite_storage(temp_dir):
    """Fixture для SQLiteStorage з автоматичним cleanup."""
    from graph_crawler.infrastructure.persistence import SQLiteStorage

    storage = SQLiteStorage(storage_dir=temp_dir)
    yield storage

    # КРИТИЧНО: Закриваємо з'єднання
    try:
        await storage.close()
        await asyncio.sleep(0.1)
        gc.collect()
    except Exception:
        pass


# ==========================================
# MOCK FIXTURES
# ==========================================

@pytest.fixture
def mock_processor():
    """Mock для LinkProcessor."""
    processor = Mock()
    processor.process_links = Mock(return_value=0)
    processor.process_links_async = AsyncMock(return_value=0)
    return processor


@pytest.fixture
def mock_scanner():
    """Mock для Scanner."""
    scanner = Mock()
    scanner.scan_node = AsyncMock(return_value=[])
    return scanner


@pytest.fixture
def mock_progress_tracker():
    """Mock для ProgressTracker."""
    tracker = Mock()
    tracker.get_pages_crawled = Mock(return_value=0)
    tracker.should_publish_progress = Mock(return_value=False)
    tracker.publish_node_scan_started = Mock()
    tracker.publish_node_scanned = Mock()
    tracker.increment_pages = Mock()
    tracker.publish_progress_event = Mock()
    return tracker


@pytest.fixture
def mock_incremental_strategy():
    """Mock для IncrementalStrategy."""
    strategy = Mock()
    strategy.should_process_node_links = Mock(return_value=True)
    return strategy


# ==========================================
# SAMPLE DATA FIXTURES
# ==========================================

@pytest.fixture
def sample_node():
    """Створює зразкову ноду."""
    return Node(url="https://example.com", depth=0)


@pytest.fixture
def sample_edge(sample_node):
    """Створює зразкове ребро."""
    child_node = Node(url="https://example.com/page", depth=1)
    return Edge(source_node_id=sample_node.node_id, target_node_id=child_node.node_id)


@pytest.fixture
def sample_graph():
    """Створює зразковий граф."""
    graph = Graph()

    root = Node(url="https://example.com", depth=0)
    page1 = Node(url="https://example.com/page1", depth=1)
    page2 = Node(url="https://example.com/page2", depth=1)

    graph.add_node(root)
    graph.add_node(page1)
    graph.add_node(page2)

    edge1 = Edge(source_node_id=root.node_id, target_node_id=page1.node_id)
    edge2 = Edge(source_node_id=root.node_id, target_node_id=page2.node_id)

    graph.add_edge(edge1)
    graph.add_edge(edge2)

    return graph


@pytest.fixture
def sample_html():
    """Зразковий HTML для тестів."""
    return '''
    <html>
    <head>
        <title>Test Page</title>
        <meta name="description" content="Test description">
        <meta name="keywords" content="test, example">
    </head>
    <body>
        <h1>Test Heading</h1>
        <a href="/page1">Page 1</a>
        <a href="/page2">Page 2</a>
        <a href="https://external.com">External</a>
    </body>
    </html>
    '''


@pytest.fixture(scope="session")
def html_fixtures_dir():
    """Шлях до HTML фікстур."""
    return Path(__file__).parent / "fixtures" / "html"


@pytest.fixture(scope="session")
def graphs_fixtures_dir():
    """Шлях до graph фікстур."""
    return Path(__file__).parent / "fixtures" / "graphs"


@pytest.fixture
def load_html_fixture(html_fixtures_dir):
    """Завантажує HTML фікстуру за назвою."""
    def _load(filename):
        filepath = html_fixtures_dir / filename
        if not filepath.exists():
            raise FileNotFoundError(f"Fixture not found: {filename}")
        return filepath.read_text()
    return _load
