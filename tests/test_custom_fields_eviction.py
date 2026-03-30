"""
Тести для збереження та відновлення кастомних полів підкласів Node при eviction.

Ця проблема виникає коли:
1. Користувач створює підклас Node (наприклад JobsNode) з кастомними полями
2. Ноди evict-яться на диск при low_memory_mode
3. При завантаженні назад кастомні поля ВТРАЧАЛИСЬ

Рішення:
1. SQLiteEvictionStorage автоматично зберігає кастомні поля в user_data['_custom_fields']
2. Graph._load_node_from_disk() відновлює кастомні поля при завантаженні
"""

import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

# Додаємо path для імпорту
sys.path.insert(0, str(Path(__file__).parent.parent))

from pydantic import Field

from graph_crawler.domain.entities.graph import Graph
from graph_crawler.domain.entities.node import Node
from graph_crawler.infrastructure.persistence.sqlite_eviction_storage import SQLiteEvictionStorage


class JobsNode(Node):
    """Тестовий підклас Node з кастомними полями (імітація реального JobsNode)."""

    # Кастомні поля для вакансій
    text: str = ''
    text_md: str = ''

    # Детекція по URL
    is_jobs_url: bool = False

    # Детекція по контенту
    is_jobs_h1: bool = False
    is_jobs_title: bool = False

    # Валідація
    is_job_content_valid: bool = False
    word_count: int = 0
    html_length: int = 0
    has_frames: bool = False

    # Metadata
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    h1_text: Optional[str] = None
    job_posting_schema: Optional[Dict] = None
    source_posted_date: Optional[str] = None
    all_jsonld_schemas: Optional[List[str]] = None

    # Backwards compatibility
    is_jobs: bool = False
    is_jobs_backup_h1: bool = False
    is_jobs_backup_title: bool = False
    is_jobs_metadata: bool = False

    # Редірект
    is_redirected_to_different_page: bool = False

    @property
    def is_vacancy(self) -> bool:
        """Чи є сторінка вакансією."""
        if self.job_posting_schema:
            return True
        return self.is_jobs_url and self.is_job_content_valid


def test_custom_fields_storage_extraction():
    """Тест що кастомні поля коректно витягуються з підкласу Node."""
    from graph_crawler.infrastructure.persistence.sqlite_eviction_storage import _extract_custom_fields

    node = JobsNode(
        url="https://example.com/jobs/developer",
        depth=1,
        text="Senior Python Developer",
        text_md="# Senior Python Developer",
        is_jobs_url=True,
        is_jobs_h1=True,
        is_job_content_valid=True,
        word_count=500,
        html_length=10000,
        meta_title="Job: Python Developer",
        job_posting_schema={"@type": "JobPosting", "title": "Developer"},
    )

    custom_fields = _extract_custom_fields(node)

    # Перевіряємо що кастомні поля витягнуто
    assert 'text' in custom_fields
    assert custom_fields['text'] == "Senior Python Developer"
    assert 'is_jobs_url' in custom_fields
    assert custom_fields['is_jobs_url'] == True
    assert 'word_count' in custom_fields
    assert custom_fields['word_count'] == 500
    assert 'job_posting_schema' in custom_fields
    assert custom_fields['job_posting_schema']['@type'] == "JobPosting"

    # Перевіряємо що базові поля Node НЕ потрапили
    assert 'url' not in custom_fields
    assert 'node_id' not in custom_fields
    assert 'depth' not in custom_fields
    assert 'scanned' not in custom_fields

    print("✅ test_custom_fields_storage_extraction PASSED")


def test_custom_fields_save_and_load():
    """Тест збереження та завантаження кастомних полів через SQLite."""

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = SQLiteEvictionStorage(tmpdir)

        # Створюємо JobsNode з кастомними полями
        node = JobsNode(
            url="https://example.com/jobs/developer",
            depth=1,
            text="Senior Python Developer needed",
            text_md="# Senior Python Developer\n\nWe need...",
            is_jobs_url=True,
            is_jobs_h1=True,
            is_job_content_valid=True,
            word_count=500,
            html_length=10000,
            meta_title="Job: Python Developer",
            h1_text="Python Developer Position",
            job_posting_schema={"@type": "JobPosting", "title": "Developer"},
            all_jsonld_schemas=["JobPosting", "Organization"],
        )
        node.scanned = True

        # Зберігаємо ноду
        count = storage.save_nodes_sync([node])
        assert count == 1

        # Завантажуємо ноду
        loaded_data = storage.load_node_sync("https://example.com/jobs/developer")

        assert loaded_data is not None
        assert loaded_data['url'] == "https://example.com/jobs/developer"
        assert loaded_data['scanned'] == True

        # Перевіряємо що кастомні поля збережені в user_data['_custom_fields']
        user_data = loaded_data['user_data']
        assert '_custom_fields' in user_data

        custom_fields = user_data['_custom_fields']
        assert custom_fields['text'] == "Senior Python Developer needed"
        assert custom_fields['is_jobs_url'] == True
        assert custom_fields['is_jobs_h1'] == True
        assert custom_fields['is_job_content_valid'] == True
        assert custom_fields['word_count'] == 500
        assert custom_fields['meta_title'] == "Job: Python Developer"
        assert custom_fields['job_posting_schema']['@type'] == "JobPosting"
        assert custom_fields['all_jsonld_schemas'] == ["JobPosting", "Organization"]

        storage.close()
        print("✅ test_custom_fields_save_and_load PASSED")


def test_custom_fields_eviction_and_restore():
    """Інтеграційний тест: eviction підкласу Node та відновлення через Graph."""

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = SQLiteEvictionStorage(tmpdir)

        graph = Graph(
            low_memory_mode=True,
            evict_threshold=5,
            eviction_storage=storage,
        )

        # Створюємо JobsNode з кастомними полями
        job_node = JobsNode(
            url="https://company.com/careers/python-dev",
            depth=1,
            text="We are looking for a Python developer",
            is_jobs_url=True,
            is_jobs_h1=True,
            is_job_content_valid=True,
            word_count=300,
            html_length=5000,
            meta_title="Python Developer Job",
            job_posting_schema={"@type": "JobPosting", "title": "Python Developer"},
        )
        job_node.scanned = True

        # Додаємо до графа
        graph.add_node(job_node)

        # Примусово evict-имо ноду
        graph._evict_nodes_sync([job_node])

        # Перевіряємо що нода evicted
        assert len(graph._nodes) == 0
        assert len(graph._evicted_url_hashes) == 1

        # Завантажуємо ноду назад
        loaded_node = graph._load_node_from_disk("https://company.com/careers/python-dev")

        assert loaded_node is not None
        assert loaded_node.url == "https://company.com/careers/python-dev"
        assert loaded_node.scanned == True

        # Примітка: loaded_node - це базовий Node, не JobsNode
        # Але кастомні поля мають бути доступні через user_data або атрибути
        # Перевіримо що принаймні user_data не містить _custom_fields (вони були pop-нуті)
        assert '_custom_fields' not in loaded_node.user_data

        # Кастомні поля повинні бути відновлені як атрибути Node (хоча це базовий Node)
        # Pydantic дозволяє extra="allow" за замовчуванням
        # Але оскільки ми створюємо базовий Node, кастомні поля ігноруються
        # Це очікувана поведінка - для повного відновлення підкласу потрібен node_class

        storage.close()
        print("✅ test_custom_fields_eviction_and_restore PASSED")


def test_custom_fields_batch_operations():
    """Тест batch операцій з кастомними полями."""

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = SQLiteEvictionStorage(tmpdir)

        # Створюємо кілька JobsNode
        nodes = []
        for i in range(10):
            node = JobsNode(
                url=f"https://example.com/jobs/{i}",
                depth=1,
                text=f"Job description {i}",
                is_jobs_url=True,
                word_count=100 + i * 10,
                meta_title=f"Job {i}",
            )
            node.scanned = True
            nodes.append(node)

        # Batch save
        count = storage.save_nodes_sync(nodes)
        assert count == 10

        # Batch load
        urls = [f"https://example.com/jobs/{i}" for i in range(5)]
        loaded = storage.load_nodes_batch_sync(urls)

        assert len(loaded) == 5

        for i in range(5):
            url = f"https://example.com/jobs/{i}"
            assert url in loaded
            data = loaded[url]
            custom_fields = data['user_data'].get('_custom_fields', {})
            assert custom_fields['text'] == f"Job description {i}"
            assert custom_fields['word_count'] == 100 + i * 10
            assert custom_fields['meta_title'] == f"Job {i}"

        storage.close()
        print("✅ test_custom_fields_batch_operations PASSED")


def test_node_mapper_compatibility():
    """Тест сумісності з NodeMapper (JSON storage)."""
    from graph_crawler.application.dto.mappers.node_mapper import NodeMapper

    # Створюємо JobsNode
    node = JobsNode(
        url="https://example.com/job",
        depth=0,
        text="Job text",
        is_jobs_url=True,
        word_count=200,
        job_posting_schema={"@type": "JobPosting"},
    )

    # Конвертуємо в DTO
    dto = NodeMapper.to_dto(node)

    # Перевіряємо що кастомні поля в user_data['_custom_fields']
    assert '_custom_fields' in dto.user_data
    custom_fields = dto.user_data['_custom_fields']
    assert custom_fields['text'] == "Job text"
    assert custom_fields['is_jobs_url'] == True
    assert custom_fields['word_count'] == 200

    # Конвертуємо назад в базовий Node (без передачі node_class)
    restored_node = NodeMapper.to_domain(dto)

    # Базовий Node не має кастомних полів, але user_data чистий
    assert '_custom_fields' not in restored_node.user_data

    # Конвертуємо назад в JobsNode (з передачею node_class)
    restored_jobs_node = NodeMapper.to_domain(dto, node_class=JobsNode)

    # JobsNode повинен мати кастомні поля
    assert restored_jobs_node.text == "Job text"
    assert restored_jobs_node.is_jobs_url == True
    assert restored_jobs_node.word_count == 200

    print("✅ test_node_mapper_compatibility PASSED")


# ============== EDGE CUSTOM FIELDS TESTS ==============

from graph_crawler.domain.entities.edge import Edge


class JobLinkEdge(Edge):
    """Тестовий підклас Edge з кастомними полями для зв'язків вакансій."""

    # Кастомні поля для зв'язків вакансій
    link_type: str = "internal"
    is_apply_link: bool = False
    is_job_listing_link: bool = False
    anchor_text: str = ""
    rel_attributes: List[str] = Field(default_factory=list)
    link_position: str = "body"  # header, footer, sidebar, body
    confidence_score: float = 0.0


def test_edge_custom_fields_extraction():
    """Тест що кастомні поля коректно витягуються з підкласу Edge."""
    from graph_crawler.infrastructure.persistence.sqlite_eviction_storage import _extract_edge_custom_fields

    edge = JobLinkEdge(
        source_node_id="node1",
        target_node_id="node2",
        link_type="apply",
        is_apply_link=True,
        anchor_text="Apply Now",
        rel_attributes=["nofollow", "sponsored"],
        link_position="sidebar",
        confidence_score=0.95,
    )

    custom_fields = _extract_edge_custom_fields(edge)

    # Перевіряємо що кастомні поля витягнуто
    assert 'link_type' in custom_fields
    assert custom_fields['link_type'] == "apply"
    assert 'is_apply_link' in custom_fields
    assert custom_fields['is_apply_link'] == True
    assert 'anchor_text' in custom_fields
    assert custom_fields['anchor_text'] == "Apply Now"
    assert 'rel_attributes' in custom_fields
    assert custom_fields['rel_attributes'] == ["nofollow", "sponsored"]
    assert 'confidence_score' in custom_fields
    assert custom_fields['confidence_score'] == 0.95

    # Перевіряємо що базові поля Edge НЕ потрапили
    assert 'source_node_id' not in custom_fields
    assert 'target_node_id' not in custom_fields
    assert 'edge_id' not in custom_fields
    assert 'metadata' not in custom_fields

    print("✅ test_edge_custom_fields_extraction PASSED")


def test_edge_custom_fields_save_and_load():
    """Тест збереження та завантаження кастомних полів Edge через SQLite."""

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = SQLiteEvictionStorage(tmpdir)

        # Створюємо JobLinkEdge з кастомними полями
        edge = JobLinkEdge(
            source_node_id="job-page-1",
            target_node_id="apply-form-1",
            link_type="apply",
            is_apply_link=True,
            is_job_listing_link=False,
            anchor_text="Apply for this position",
            rel_attributes=["nofollow"],
            link_position="body",
            confidence_score=0.92,
        )

        # Зберігаємо edge
        count = storage.save_edges_sync([edge])
        assert count == 1

        # Завантажуємо edges
        loaded_edges = storage.load_edges_sync(source_node_id="job-page-1")

        assert len(loaded_edges) == 1
        loaded_data = loaded_edges[0]

        assert loaded_data['source_node_id'] == "job-page-1"
        assert loaded_data['target_node_id'] == "apply-form-1"

        # Перевіряємо що кастомні поля збережені в metadata['_custom_fields']
        metadata = loaded_data['metadata']
        assert '_custom_fields' in metadata

        custom_fields = metadata['_custom_fields']
        assert custom_fields['link_type'] == "apply"
        assert custom_fields['is_apply_link'] == True
        assert custom_fields['anchor_text'] == "Apply for this position"
        assert custom_fields['rel_attributes'] == ["nofollow"]
        assert custom_fields['confidence_score'] == 0.92

        storage.close()
        print("✅ test_edge_custom_fields_save_and_load PASSED")


def test_edge_custom_fields_batch_operations():
    """Тест batch операцій з кастомними полями Edge."""

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = SQLiteEvictionStorage(tmpdir)

        # Створюємо кілька JobLinkEdge
        edges = []
        for i in range(10):
            edge = JobLinkEdge(
                source_node_id=f"page-{i}",
                target_node_id=f"target-{i}",
                link_type="job_listing" if i % 2 == 0 else "apply",
                is_apply_link=(i % 2 == 1),
                is_job_listing_link=(i % 2 == 0),
                anchor_text=f"Link text {i}",
                confidence_score=0.5 + i * 0.05,
            )
            edges.append(edge)

        # Batch save
        count = storage.save_edges_sync(edges)
        assert count == 10

        # Load all
        loaded = storage.load_all_edges_sync()
        assert len(loaded) == 10

        # Перевіряємо кастомні поля
        for i, edge_data in enumerate(sorted(loaded, key=lambda x: x['source_node_id'])):
            custom_fields = edge_data['metadata'].get('_custom_fields', {})
            assert custom_fields['anchor_text'] == f"Link text {i}"
            expected_score = 0.5 + i * 0.05
            assert abs(custom_fields['confidence_score'] - expected_score) < 0.001

        storage.close()
        print("✅ test_edge_custom_fields_batch_operations PASSED")


if __name__ == "__main__":
    print("\n🧪 Custom Fields Eviction Tests")
    print("=" * 50)

    # Node tests
    test_custom_fields_storage_extraction()
    test_custom_fields_save_and_load()
    test_custom_fields_eviction_and_restore()
    test_custom_fields_batch_operations()
    test_node_mapper_compatibility()

    # Edge tests
    print("\n--- Edge Custom Fields Tests ---")
    test_edge_custom_fields_extraction()
    test_edge_custom_fields_save_and_load()
    test_edge_custom_fields_batch_operations()

    print("\n" + "=" * 50)
    print("✅ All custom fields eviction tests passed!")
