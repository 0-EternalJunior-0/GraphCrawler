"""Integration tests для Infrastructure Layer з DTO."""

import json
import pytest
import tempfile
from datetime import datetime
from pathlib import Path

from graph_crawler.application.dto import (
    GraphDTO,
    NodeDTO,
    EdgeDTO,
    GraphStatsDTO,
)
from graph_crawler.infrastructure.persistence.json_storage import JSONStorage
from graph_crawler.infrastructure.persistence.sqlite_storage import SQLiteStorage
from graph_crawler.infrastructure.persistence.graph_repository import GraphRepository


# ===== Fixtures =====

@pytest.fixture
def sample_graph_dto():
    """Створює тестовий GraphDTO."""
    node1 = NodeDTO(
        node_id="node-1",
        url="https://example.com",
        depth=0,
        should_scan=True,
        can_create_edges=True,
        scanned=True,
        metadata={"title": "Example Domain"},
        user_data={},
        response_status=200,
        content_hash="abc123",
        priority=5,
        created_at=datetime.now(),
        lifecycle_stage="html_stage",
    )

    node2 = NodeDTO(
        node_id="node-2",
        url="https://example.com/page1",
        depth=1,
        should_scan=True,
        can_create_edges=True,
        scanned=False,
        metadata={"title": "Page 1"},
        user_data={},
        response_status=None,
        content_hash=None,
        priority=3,
        created_at=datetime.now(),
        lifecycle_stage="url_stage",
    )

    edge1 = EdgeDTO(
        edge_id="edge-1",
        source_node_id="node-1",
        target_node_id="node-2",
        metadata={"link_type": ["internal"]},
        created_at=datetime.now(),
    )

    stats = GraphStatsDTO(
        total_nodes=2,
        scanned_nodes=1,
        unscanned_nodes=1,
        total_edges=1,
        avg_depth=0.5,
        max_depth=1,
    )

    return GraphDTO(
        nodes=[node1, node2],
        edges=[edge1],
        stats=stats,
    )


@pytest.fixture
def temp_dir():
    """Створює тимчасову директорію для тестів."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


# ===== JSONStorage Tests =====

@pytest.mark.asyncio
async def test_json_storage_save_and_load(sample_graph_dto, temp_dir):
    """Тест збереження та завантаження GraphDTO через JSONStorage."""
    storage = JSONStorage(storage_dir=temp_dir)

    # Збереження
    result = await storage.save_graph(sample_graph_dto)
    assert result is True

    # Завантаження
    loaded_dto = await storage.load_graph()
    assert loaded_dto is not None
    assert len(loaded_dto.nodes) == 2
    assert len(loaded_dto.edges) == 1
    assert loaded_dto.stats.total_nodes == 2
    assert loaded_dto.nodes[0].url == "https://example.com"


@pytest.mark.asyncio
async def test_json_storage_exists(sample_graph_dto, temp_dir):
    """Тест перевірки існування GraphDTO в JSONStorage."""
    storage = JSONStorage(storage_dir=temp_dir)

    # Спочатку не існує
    exists = await storage.exists()
    assert exists is False

    # Зберігаємо
    await storage.save_graph(sample_graph_dto)

    # Тепер існує
    exists = await storage.exists()
    assert exists is True


@pytest.mark.asyncio
async def test_json_storage_clear(sample_graph_dto, temp_dir):
    """Тест очищення GraphDTO в JSONStorage."""
    storage = JSONStorage(storage_dir=temp_dir)

    # Зберігаємо
    await storage.save_graph(sample_graph_dto)
    assert await storage.exists() is True

    # Очищаємо
    result = await storage.clear()
    assert result is True
    assert await storage.exists() is False


@pytest.mark.asyncio
async def test_json_storage_load_nonexistent(temp_dir):
    """Тест завантаження неіснуючого GraphDTO з JSONStorage."""
    storage = JSONStorage(storage_dir=temp_dir)

    loaded_dto = await storage.load_graph()
    assert loaded_dto is None


# ===== SQLiteStorage Tests =====

@pytest.mark.asyncio
async def test_sqlite_storage_save_and_load(sample_graph_dto, temp_dir):
    """Тест збереження та завантаження GraphDTO через SQLiteStorage."""
    storage = SQLiteStorage(storage_dir=temp_dir)

    # Збереження
    result = await storage.save_graph(sample_graph_dto)
    assert result is True

    # Завантаження
    loaded_dto = await storage.load_graph()
    assert loaded_dto is not None
    assert len(loaded_dto.nodes) == 2
    assert len(loaded_dto.edges) == 1
    assert loaded_dto.stats.total_nodes == 2
    assert loaded_dto.nodes[0].url == "https://example.com"

    # Cleanup
    await storage.close()


@pytest.mark.asyncio
async def test_sqlite_storage_exists(sample_graph_dto, temp_dir):
    """Тест перевірки існування GraphDTO в SQLiteStorage."""
    storage = SQLiteStorage(storage_dir=temp_dir)

    # Спочатку не існує
    exists = await storage.exists()
    assert exists is False

    # Зберігаємо
    await storage.save_graph(sample_graph_dto)

    # Тепер існує
    exists = await storage.exists()
    assert exists is True

    # Cleanup
    await storage.close()


@pytest.mark.asyncio
async def test_sqlite_storage_clear(sample_graph_dto, temp_dir):
    """Тест очищення GraphDTO в SQLiteStorage."""
    storage = SQLiteStorage(storage_dir=temp_dir)

    # Зберігаємо
    await storage.save_graph(sample_graph_dto)
    assert await storage.exists() is True

    # Очищаємо
    result = await storage.clear()
    assert result is True
    assert await storage.exists() is False

    # Cleanup
    await storage.close()


# ===== GraphRepository Tests =====

def test_graph_repository_save_and_load(sample_graph_dto, temp_dir):
    """Тест збереження та завантаження GraphDTO через GraphRepository."""
    repo = GraphRepository(storage_dir=temp_dir)

    # Збереження
    full_name = repo.save_graph(
        sample_graph_dto,
        name="test_graph",
        description="Test graph for DTO",
    )
    assert full_name is not None
    assert "test_graph" in full_name

    # Завантаження
    loaded_dto = repo.load_graph("test_graph")
    assert loaded_dto is not None
    assert len(loaded_dto.nodes) == 2
    assert len(loaded_dto.edges) == 1
    assert loaded_dto.nodes[0].url == "https://example.com"


def test_graph_repository_list_graphs(sample_graph_dto, temp_dir):
    """Тест отримання списку GraphDTO в GraphRepository."""
    repo = GraphRepository(storage_dir=temp_dir)

    # Зберігаємо кілька графів
    repo.save_graph(sample_graph_dto, name="graph1", description="First graph")
    repo.save_graph(sample_graph_dto, name="graph2", description="Second graph")

    # Отримуємо список
    graphs = repo.list_graphs()
    assert len(graphs) == 2
    assert all(hasattr(g, "name") for g in graphs)
    assert all(hasattr(g, "stats") for g in graphs)


def test_graph_repository_delete_graph(sample_graph_dto, temp_dir):
    """Тест видалення GraphDTO з GraphRepository."""
    repo = GraphRepository(storage_dir=temp_dir)

    # Зберігаємо
    full_name = repo.save_graph(sample_graph_dto, name="test_graph")
    assert repo.graph_exists(full_name) is True

    # Видаляємо
    result = repo.delete_graph(full_name)
    assert result is True
    assert repo.graph_exists(full_name) is False


def test_graph_repository_get_metadata(sample_graph_dto, temp_dir):
    """Тест отримання метаданих GraphDTO з GraphRepository."""
    repo = GraphRepository(storage_dir=temp_dir)

    # Зберігаємо
    full_name = repo.save_graph(
        sample_graph_dto,
        name="test_graph",
        description="Test metadata",
    )

    # Отримуємо метадані
    metadata = repo.get_metadata(full_name)
    assert metadata is not None
    assert metadata.name == "test_graph"
    assert metadata.description == "Test metadata"
    assert metadata.stats.total_nodes == 2


# ===== Validation Tests =====

@pytest.mark.asyncio
async def test_json_storage_validates_dto(temp_dir):
    """Тест валідації GraphDTO в JSONStorage."""
    storage = JSONStorage(storage_dir=temp_dir)

    # Створюємо невалідний DTO (без обов'язкових полів)
    invalid_data = {
        "nodes": [],
        "edges": [],
        # "stats" відсутній!
    }

    # Записуємо невалідні дані напряму у файл
    graph_file = Path(temp_dir) / "graph.json"
    with open(graph_file, "w") as f:
        json.dump(invalid_data, f)

    # Спроба завантажити повинна викинути помилку валідації
    from graph_crawler.shared.exceptions import LoadError

    with pytest.raises(LoadError):
        await storage.load_graph()


def test_graph_repository_validates_dto(temp_dir):
    """Тест валідації GraphDTO в GraphRepository."""
    repo = GraphRepository(storage_dir=temp_dir)

    # Створюємо невалідний DTO
    invalid_data = {
        "nodes": [],
        "edges": [],
        # "stats" відсутній!
    }

    # Записуємо невалідні дані напряму у файл
    graph_file = repo.graphs_dir / "invalid_graph.json"
    with open(graph_file, "w") as f:
        json.dump(invalid_data, f)

    # Спроба завантажити повинна викинути помилку валідації
    from graph_crawler.shared.exceptions import LoadError

    with pytest.raises(LoadError):
        repo.load_graph("invalid_graph")


# ===== Performance Tests =====

@pytest.mark.asyncio
async def test_json_storage_large_graph_performance(temp_dir):
    """Тест продуктивності JSONStorage з великим GraphDTO."""
    storage = JSONStorage(storage_dir=temp_dir)

    # Створюємо великий граф (100 nodes, 200 edges)
    nodes = []
    for i in range(100):
        node = NodeDTO(
            node_id=f"node-{i}",
            url=f"https://example.com/page{i}",
            depth=i % 5,
            should_scan=True,
            can_create_edges=True,
            scanned=i % 2 == 0,
            metadata={"title": f"Page {i}"},
            user_data={},
            response_status=200 if i % 2 == 0 else None,
            content_hash=f"hash-{i}" if i % 2 == 0 else None,
            priority=5,
            created_at=datetime.now(),
            lifecycle_stage="html_stage" if i % 2 == 0 else "url_stage",
        )
        nodes.append(node)

    edges = []
    for i in range(200):
        edge = EdgeDTO(
            edge_id=f"edge-{i}",
            source_node_id=f"node-{i % 100}",
            target_node_id=f"node-{(i + 1) % 100}",
            metadata={"link_type": ["internal"]},
            created_at=datetime.now(),
        )
        edges.append(edge)

    stats = GraphStatsDTO(
        total_nodes=100,
        scanned_nodes=50,
        unscanned_nodes=50,
        total_edges=200,
        avg_depth=2.0,
        max_depth=4,
    )

    large_graph_dto = GraphDTO(nodes=nodes, edges=edges, stats=stats)

    # Збереження
    import time
    start = time.time()
    result = await storage.save_graph(large_graph_dto)
    save_time = time.time() - start
    assert result is True
    assert save_time < 5.0  # Має зберегти за менш ніж 5 секунд

    # Завантаження
    start = time.time()
    loaded_dto = await storage.load_graph()
    load_time = time.time() - start
    assert loaded_dto is not None
    assert len(loaded_dto.nodes) == 100
    assert len(loaded_dto.edges) == 200
    assert load_time < 5.0  # Має завантажити за менш ніж 5 секунд
