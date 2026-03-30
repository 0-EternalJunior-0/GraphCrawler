#!/usr/bin/env python3
"""
Comprehensive Data Flow Test - graph_crawler

Тестуємо весь data flow:
1. Конструктор (Graph, Node, Edge) - створення та ініціалізація
2. Scheduler - пріоритети, черга, URL rules
3. Фільтри (DomainFilter, PathFilter) - каскадна фільтрація
4. LinkProcessor - обробка посилань, edge creation
5. Custom Node - кастомні класи нод
6. Backend delegation - MemoryBackend, SQLiteBackend
7. Eviction flow - low-memory mode
8. Edge strategies - різні стратегії створення edges

Перевіряємо що ніде немає помилок при проходженні даних.
"""

import asyncio
import logging
import traceback
import sys
from typing import List, Optional, Dict, Any

# Налаштування логування
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s | %(levelname)-7s | %(name)s | %(message)s',
    datefmt='%H:%M:%S'
)

# Статистика тестів
test_results = {
    'passed': 0,
    'failed': 0,
    'errors': []
}

def test(name: str):
    """Decorator для тестів з автоматичним error handling."""
    def decorator(func):
        async def wrapper():
            try:
                print(f"\n{'='*60}")
                print(f"🧪 TEST: {name}")
                print(f"{'='*60}")

                if asyncio.iscoroutinefunction(func):
                    result = await func()
                else:
                    result = func()

                if result is True or result is None:
                    test_results['passed'] += 1
                    print(f"✅ PASSED: {name}")
                    return True
                else:
                    test_results['failed'] += 1
                    test_results['errors'].append(f"{name}: {result}")
                    print(f"❌ FAILED: {name}")
                    print(f"   Reason: {result}")
                    return False

            except Exception as e:
                test_results['failed'] += 1
                error_msg = f"{name}: {type(e).__name__}: {e}"
                test_results['errors'].append(error_msg)
                print(f"❌ ERROR: {name}")
                print(f"   {type(e).__name__}: {e}")
                traceback.print_exc()
                return False
        return wrapper
    return decorator


# ============================================================
# TEST 1: Constructor Tests (Graph, Node, Edge)
# ============================================================

@test("1.1 Node Constructor - Basic")
def test_node_constructor_basic():
    from graph_crawler.domain.entities.node import Node

    # Basic node creation
    node = Node(url="https://example.com/page1")
    assert node.url == "https://example.com/page1", f"URL mismatch: {node.url}"
    assert node.node_id is not None, "node_id should be generated"
    assert node.depth == 0, f"Default depth should be 0, got {node.depth}"
    assert node.scanned == False, "Default scanned should be False"
    assert node.should_scan == True, "Default should_scan should be True"
    assert node.can_create_edges == True, "Default can_create_edges should be True"

    return True

@test("1.2 Node Constructor - With Parameters")
def test_node_constructor_params():
    from graph_crawler.domain.entities.node import Node

    node = Node(
        url="https://example.com/page2",
        depth=3,
        scanned=True,
        should_scan=False,
        can_create_edges=False,
    )

    assert node.depth == 3, f"Depth mismatch: {node.depth}"
    assert node.scanned == True, "scanned should be True"
    assert node.should_scan == False, "should_scan should be False"
    assert node.can_create_edges == False, "can_create_edges should be False"

    return True

@test("1.3 Node - Metadata and User Data")
def test_node_metadata():
    from graph_crawler.domain.entities.node import Node

    node = Node(url="https://example.com/meta")

    # Test metadata
    node.metadata = {"title": "Test Page", "description": "Test description"}
    assert node.metadata["title"] == "Test Page"

    # Test user_data
    node.user_data = {"custom_field": "custom_value", "priority": 5}
    assert node.user_data["custom_field"] == "custom_value"

    return True

@test("1.4 Edge Constructor")
def test_edge_constructor():
    from graph_crawler.domain.entities.edge import Edge

    edge = Edge(source_node_id="node1", target_node_id="node2")

    assert edge.source_node_id == "node1"
    assert edge.target_node_id == "node2"
    assert edge.metadata is not None or edge.metadata == {}

    # Test metadata
    edge.add_metadata("link_text", "Click here")
    assert edge.metadata.get("link_text") == "Click here"

    return True

@test("1.5 Graph Constructor - Basic")
def test_graph_constructor_basic():
    from graph_crawler.domain.entities.graph import Graph

    graph = Graph()

    assert len(graph.nodes) == 0, f"Empty graph should have 0 nodes, got {len(graph.nodes)}"
    assert len(graph.edges) == 0, f"Empty graph should have 0 edges, got {len(graph.edges)}"
    assert graph.default_merge_strategy == "last", "Default merge strategy should be 'last'"

    return True


# ============================================================
# TEST 2: Scheduler Tests
# ============================================================

@test("2.1 Scheduler - Basic Add/Get")
def test_scheduler_basic():
    from graph_crawler.application.use_cases.crawling.scheduler import CrawlScheduler
    from graph_crawler.domain.entities.node import Node

    scheduler = CrawlScheduler()

    node1 = Node(url="https://example.com/page1")
    node2 = Node(url="https://example.com/page2")

    # Add nodes
    assert scheduler.add_node(node1) == True, "First add should succeed"
    assert scheduler.add_node(node2) == True, "Second add should succeed"
    assert scheduler.add_node(node1) == False, "Duplicate add should fail"

    # Check queue
    assert scheduler.size() == 2, f"Queue size should be 2, got {scheduler.size()}"
    assert scheduler.is_empty() == False, "Queue should not be empty"

    # Get nodes
    next_node = scheduler.get_next()
    assert next_node is not None, "get_next should return a node"
    assert scheduler.size() == 1, f"Queue size should be 1 after get_next, got {scheduler.size()}"

    return True

@test("2.2 Scheduler - URL Rules Priority")
def test_scheduler_url_rules():
    from graph_crawler.application.use_cases.crawling.scheduler import CrawlScheduler
    from graph_crawler.domain.entities.node import Node
    from graph_crawler.domain.value_objects.models import URLRule

    # Create rules with different priorities
    rules = [
        URLRule(pattern=r"/products/", priority=10),  # High priority
        URLRule(pattern=r"/blog/", priority=3),       # Low priority
        URLRule(pattern=r"/about/", priority=5),      # Medium priority
    ]

    scheduler = CrawlScheduler(url_rules=rules)

    # Add nodes (in reverse priority order)
    node_blog = Node(url="https://example.com/blog/post1")
    node_about = Node(url="https://example.com/about/us")
    node_products = Node(url="https://example.com/products/item1")

    scheduler.add_node(node_blog)
    scheduler.add_node(node_about)
    scheduler.add_node(node_products)

    # High priority should come first
    first = scheduler.get_next()
    assert "/products/" in first.url, f"High priority node should come first, got {first.url}"

    second = scheduler.get_next()
    assert "/about/" in second.url, f"Medium priority node should come second, got {second.url}"

    third = scheduler.get_next()
    assert "/blog/" in third.url, f"Low priority node should come third, got {third.url}"

    return True

@test("2.3 Scheduler - should_scan=False Exclusion")
def test_scheduler_exclusion():
    from graph_crawler.application.use_cases.crawling.scheduler import CrawlScheduler
    from graph_crawler.domain.entities.node import Node
    from graph_crawler.domain.value_objects.models import URLRule

    rules = [
        URLRule(pattern=r"\.pdf$", should_scan=False),
        URLRule(pattern=r"/admin/", should_scan=False),
    ]

    scheduler = CrawlScheduler(url_rules=rules)

    # These should be excluded
    pdf_node = Node(url="https://example.com/doc.pdf")
    admin_node = Node(url="https://example.com/admin/dashboard")

    # This should be added
    normal_node = Node(url="https://example.com/page")

    assert scheduler.add_node(pdf_node) == False, "PDF should be excluded"
    assert scheduler.add_node(admin_node) == False, "Admin should be excluded"
    assert scheduler.add_node(normal_node) == True, "Normal page should be added"

    assert scheduler.size() == 1, f"Only 1 node should be in queue, got {scheduler.size()}"

    return True


# ============================================================
# TEST 3: Filter Tests
# ============================================================

@test("3.1 DomainFilter - Basic")
def test_domain_filter_basic():
    from graph_crawler.application.use_cases.crawling.filters.domain_filter import DomainFilter
    from graph_crawler.domain.value_objects.models import DomainFilterConfig

    config = DomainFilterConfig(
        base_domain="example.com",
        allowed_domains=["domain+subdomains"]  # Default
    )

    filter = DomainFilter(config)

    # Same domain - allowed
    assert filter.is_allowed("https://example.com/page") == True

    # Subdomain - allowed
    assert filter.is_allowed("https://blog.example.com/post") == True

    # Different domain - NOT allowed
    assert filter.is_allowed("https://other-site.com/page") == False

    return True

@test("3.2 DomainFilter - Wildcard Mode")
def test_domain_filter_wildcard():
    from graph_crawler.application.use_cases.crawling.filters.domain_filter import DomainFilter
    from graph_crawler.domain.value_objects.models import DomainFilterConfig

    config = DomainFilterConfig(
        base_domain="example.com",
        allowed_domains=["*"]  # Wildcard - allow everything
    )

    filter = DomainFilter(config)

    # Everything should be allowed
    assert filter.is_allowed("https://example.com/page") == True
    assert filter.is_allowed("https://other-site.com/page") == True
    assert filter.is_allowed("https://any-domain.org/any-path") == True

    return True

@test("3.3 DomainFilter - Blocked Domains")
def test_domain_filter_blocked():
    from graph_crawler.application.use_cases.crawling.filters.domain_filter import DomainFilter
    from graph_crawler.domain.value_objects.models import DomainFilterConfig

    config = DomainFilterConfig(
        base_domain="example.com",
        allowed_domains=["*"],  # Allow everything
        blocked_domains=["facebook.com", "twitter.com"]  # Except these
    )

    filter = DomainFilter(config)

    # Blocked domains should NOT be allowed
    assert filter.is_allowed("https://facebook.com/page") == False
    assert filter.is_allowed("https://twitter.com/user") == False

    # Other domains should be allowed
    assert filter.is_allowed("https://example.com/page") == True
    assert filter.is_allowed("https://linkedin.com/profile") == True

    return True

@test("3.4 PathFilter - Excluded Patterns")
def test_path_filter_excluded():
    from graph_crawler.application.use_cases.crawling.filters.path_filter import PathFilter
    from graph_crawler.domain.value_objects.models import PathFilterConfig

    config = PathFilterConfig(
        excluded_patterns=[r"/admin/", r"\.pdf$", r"/api/"]
    )

    filter = PathFilter(config)

    # Excluded paths should NOT be allowed
    assert filter.is_allowed("https://example.com/admin/dashboard") == False
    assert filter.is_allowed("https://example.com/doc.pdf") == False
    assert filter.is_allowed("https://example.com/api/v1/users") == False

    # Other paths should be allowed
    assert filter.is_allowed("https://example.com/products/item") == True
    assert filter.is_allowed("https://example.com/about") == True

    return True

@test("3.5 PathFilter - Included Patterns")
def test_path_filter_included():
    from graph_crawler.application.use_cases.crawling.filters.path_filter import PathFilter
    from graph_crawler.domain.value_objects.models import PathFilterConfig

    config = PathFilterConfig(
        included_patterns=[r"/products/", r"/blog/"]  # Only these allowed
    )

    filter = PathFilter(config)

    # Only included paths should be allowed
    assert filter.is_allowed("https://example.com/products/item") == True
    assert filter.is_allowed("https://example.com/blog/post1") == True

    # Other paths should NOT be allowed
    assert filter.is_allowed("https://example.com/about") == False
    assert filter.is_allowed("https://example.com/contact") == False

    return True


# ============================================================
# TEST 4: LinkProcessor Tests
# ============================================================

@test("4.1 LinkProcessor - Basic Link Processing")
def test_link_processor_basic():
    from graph_crawler.domain.entities.graph import Graph
    from graph_crawler.domain.entities.node import Node
    from graph_crawler.application.use_cases.crawling.scheduler import CrawlScheduler
    from graph_crawler.application.use_cases.crawling.link_processor import LinkProcessor
    from graph_crawler.application.use_cases.crawling.filters.domain_filter import DomainFilter
    from graph_crawler.application.use_cases.crawling.filters.path_filter import PathFilter
    from graph_crawler.domain.value_objects.models import DomainFilterConfig, PathFilterConfig

    # Setup
    graph = Graph()
    scheduler = CrawlScheduler()

    domain_config = DomainFilterConfig(base_domain="example.com")
    path_config = PathFilterConfig()

    domain_filter = DomainFilter(domain_config)
    path_filter = PathFilter(path_config)

    link_processor = LinkProcessor(
        graph=graph,
        scheduler=scheduler,
        domain_filter=domain_filter,
        path_filter=path_filter,
    )

    # Create source node
    source_node = Node(url="https://example.com/page1")
    source_node.can_create_edges = True
    graph.add_node(source_node)

    # Process links
    links = [
        "https://example.com/page2",
        "https://example.com/page3",
        "https://external.com/page",  # Different domain - should be filtered
    ]

    new_count = link_processor.process_links(source_node, links)

    # 2 new nodes should be created (external filtered out)
    assert new_count == 2, f"Expected 2 new nodes, got {new_count}"

    # Check graph
    assert len(graph.nodes) == 3, "Graph should have 3 nodes (source + 2 new)"
    assert len(graph.edges) == 2, "Graph should have 2 edges"

    return True

@test("4.2 LinkProcessor - Edge Creation Strategy")
def test_link_processor_edge_strategy():
    from graph_crawler.domain.entities.graph import Graph
    from graph_crawler.domain.entities.node import Node
    from graph_crawler.application.use_cases.crawling.scheduler import CrawlScheduler
    from graph_crawler.application.use_cases.crawling.link_processor import LinkProcessor
    from graph_crawler.application.use_cases.crawling.filters.domain_filter import DomainFilter
    from graph_crawler.application.use_cases.crawling.filters.path_filter import PathFilter
    from graph_crawler.domain.value_objects.models import DomainFilterConfig, PathFilterConfig

    # Setup with NEW_ONLY edge strategy
    graph = Graph()
    scheduler = CrawlScheduler()

    domain_config = DomainFilterConfig(base_domain="example.com")
    path_config = PathFilterConfig()

    link_processor = LinkProcessor(
        graph=graph,
        scheduler=scheduler,
        domain_filter=DomainFilter(domain_config),
        path_filter=PathFilter(path_config),
        edge_strategy="new_only",  # Only create edge when node is new
    )

    # Create source nodes
    source1 = Node(url="https://example.com/page1")
    source1.can_create_edges = True
    source2 = Node(url="https://example.com/page2")
    source2.can_create_edges = True

    graph.add_node(source1)
    graph.add_node(source2)

    # Both sources link to same target
    target_url = "https://example.com/shared-target"

    link_processor.process_links(source1, [target_url])
    link_processor.process_links(source2, [target_url])

    # With NEW_ONLY strategy, only 1 edge should be created
    edges_to_target = [e for e in graph.edges if "shared-target" in graph.get_node_by_id(e.target_node_id).url]

    assert len(edges_to_target) == 1, f"NEW_ONLY should create only 1 edge, got {len(edges_to_target)}"

    return True


# ============================================================
# TEST 5: Custom Node Tests
# ============================================================

@test("5.1 Custom Node Class")
def test_custom_node_class():
    from graph_crawler.domain.entities.node import Node
    from graph_crawler.domain.entities.graph import Graph

    # Define custom node class
    class SEONode(Node):
        """Custom node with SEO fields."""

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.user_data['seo_score'] = 0
            self.user_data['keywords'] = []

        def set_seo_score(self, score: int):
            self.user_data['seo_score'] = score

        def add_keyword(self, keyword: str):
            self.user_data['keywords'].append(keyword)

    # Create custom node
    seo_node = SEONode(url="https://example.com/seo-page")
    seo_node.set_seo_score(85)
    seo_node.add_keyword("python")
    seo_node.add_keyword("web crawler")

    assert seo_node.user_data['seo_score'] == 85
    assert len(seo_node.user_data['keywords']) == 2
    assert "python" in seo_node.user_data['keywords']

    # Custom node should work with Graph
    graph = Graph()
    graph.add_node(seo_node)

    retrieved = graph.get_node_by_url("https://example.com/seo-page")
    assert retrieved is not None
    assert retrieved.user_data['seo_score'] == 85

    return True


# ============================================================
# TEST 6: Backend Delegation Tests
# ============================================================

@test("6.1 MemoryBackend - Basic Operations")
async def test_memory_backend_basic():
    from graph_crawler.data.backends.memory import MemoryBackend
    from graph_crawler.domain.entities.node import Node
    from graph_crawler.domain.entities.edge import Edge

    backend = MemoryBackend()
    await backend.open()

    # Insert node
    node = Node(url="https://example.com/page1")
    result = await backend.insert_node(node)
    assert result.url == node.url

    # Get node by URL
    found = await backend.get_node_by_url("https://example.com/page1")
    assert found is not None
    assert found.node_id == node.node_id

    # Count
    count = await backend.count_nodes()
    assert count == 1

    # Insert edge
    node2 = Node(url="https://example.com/page2")
    await backend.insert_node(node2)

    edge = Edge(source_node_id=node.node_id, target_node_id=node2.node_id)
    await backend.insert_edge(edge)

    edge_count = await backend.count_edges()
    assert edge_count == 1

    await backend.close()
    return True

@test("6.2 SQLiteBackend - Basic Operations")
async def test_sqlite_backend_basic():
    import os
    from graph_crawler.data.backends.sqlite import SQLiteBackend
    from graph_crawler.domain.entities.node import Node
    from graph_crawler.domain.entities.edge import Edge

    db_path = "/tmp/test_sqlite_backend.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    backend = SQLiteBackend(db_path)
    await backend.open()

    # Insert node
    node = Node(url="https://example.com/sqlite-page1")
    result = await backend.insert_node(node)
    assert result.url == node.url

    # Get node
    found = await backend.get_node_by_url("https://example.com/sqlite-page1")
    assert found is not None

    # Stats
    stats = await backend.get_stats()
    assert stats['total_nodes'] == 1
    assert stats['backend_type'] == 'sqlite'

    await backend.close()

    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)

    return True

@test("6.3 Graph with Backend Delegation")
async def test_graph_with_backend():
    from graph_crawler.data.backends.memory import MemoryBackend
    from graph_crawler.domain.entities.graph import Graph
    from graph_crawler.domain.entities.node import Node

    backend = MemoryBackend()
    await backend.open()

    graph = Graph(backend=backend)

    # Add node through Graph
    node = Node(url="https://example.com/backend-test")
    graph.add_node(node)

    # Node should be in backend
    backend_count = await backend.count_nodes()
    assert backend_count == 1, f"Backend should have 1 node, got {backend_count}"

    # Get through Graph
    found = graph.get_node_by_url("https://example.com/backend-test")
    assert found is not None

    await backend.close()
    return True


# ============================================================
# TEST 7: Eviction Flow Tests
# ============================================================

@test("7.1 Low-Memory Mode - Eviction")
async def test_low_memory_eviction():
    from graph_crawler.domain.entities.graph import Graph
    from graph_crawler.domain.entities.node import Node
    from graph_crawler.infrastructure.persistence.eviction import SQLiteEvictionStorage
    import os
    import shutil

    eviction_path = "/tmp/test_eviction"
    if os.path.exists(eviction_path):
        shutil.rmtree(eviction_path)
    os.makedirs(eviction_path)

    eviction_storage = SQLiteEvictionStorage(eviction_path)

    graph = Graph(
        low_memory_mode=True,
        evict_threshold=10,  # Small threshold for testing
        eviction_strategy="balanced",
        eviction_storage=eviction_storage,
    )

    # Add many nodes
    for i in range(25):
        node = Node(url=f"https://example.com/page{i}")
        node.scanned = True  # Mark as scanned so they can be evicted
        graph.add_node(node)

    # Trigger eviction
    graph._maybe_evict()

    # Some nodes should be evicted
    assert len(graph._evicted_url_hashes) > 0, "Some nodes should be evicted"

    # Total count should still be 25
    total = graph.get_total_nodes_count()
    assert total == 25, f"Total nodes should be 25, got {total}"

    # Cleanup
    if os.path.exists(eviction_path):
        shutil.rmtree(eviction_path)

    return True


# ============================================================
# TEST 8: SmartURLRule Tests
# ============================================================

@test("8.1 SmartURLRule - Scope Matching")
def test_smart_url_rule_scope():
    from graph_crawler.domain.value_objects.models import SmartURLRule, RuleScope

    # Domain scope
    domain_rule = SmartURLRule(
        pattern="example.com",
        scope=RuleScope.DOMAIN,
        is_regex=False,
        priority=5,
    )

    assert domain_rule.matches("https://example.com/page") == True
    assert domain_rule.matches("https://sub.example.com/page") == True
    assert domain_rule.matches("https://other.com/page") == False

    # Path scope
    path_rule = SmartURLRule(
        pattern=r"^/products/",
        scope=RuleScope.PATH,
        is_regex=True,
        priority=8,
    )

    assert path_rule.matches("https://example.com/products/item1") == True
    assert path_rule.matches("https://example.com/blog/post") == False

    # Subdomain scope
    subdomain_rule = SmartURLRule(
        pattern="blog.example.com",
        scope=RuleScope.SUBDOMAIN,
        is_regex=False,
        priority=6,
    )

    assert subdomain_rule.matches("https://blog.example.com/post") == True
    assert subdomain_rule.matches("https://example.com/blog") == False

    return True


# ============================================================
# TEST 9: EdgeRule Tests
# ============================================================

@test("9.1 EdgeRule - Pattern Matching")
def test_edge_rule():
    from graph_crawler.domain.value_objects.models import EdgeRule

    # Skip edges to login page
    skip_login = EdgeRule(
        target_pattern=r".*/login.*",
        action="skip",
    )

    result = skip_login.should_create_edge(
        source_url="https://example.com/page",
        target_url="https://example.com/login",
        source_depth=1,
        target_depth=2,
    )
    assert result == False, "Edge to login should be skipped"

    result = skip_login.should_create_edge(
        source_url="https://example.com/page",
        target_url="https://example.com/products",
        source_depth=1,
        target_depth=2,
    )
    assert result is None, "Rule should not apply to non-login URLs"

    # Max depth diff rule
    depth_rule = EdgeRule(
        max_depth_diff=2,
        action="skip",
    )

    result = depth_rule.should_create_edge(
        source_url="https://example.com/a",
        target_url="https://example.com/b",
        source_depth=1,
        target_depth=5,  # diff = 4 > 2
    )
    assert result == False, "Edge with depth diff > 2 should be skipped"

    return True


# ============================================================
# TEST 10: ContentType Detection
# ============================================================

@test("10.1 ContentType Detection")
def test_content_type_detection():
    from graph_crawler.domain.value_objects.models import ContentType

    # From header
    assert ContentType.from_content_type_header("text/html; charset=utf-8") == ContentType.HTML
    assert ContentType.from_content_type_header("application/json") == ContentType.JSON
    assert ContentType.from_content_type_header("image/png") == ContentType.IMAGE

    # From URL
    assert ContentType.from_url("https://example.com/doc.pdf") == ContentType.PDF
    assert ContentType.from_url("https://example.com/image.jpg") == ContentType.IMAGE
    assert ContentType.from_url("https://example.com/page.html") == ContentType.HTML

    # Detection with status codes
    assert ContentType.detect(status_code=404) == ContentType.ERROR
    assert ContentType.detect(status_code=500) == ContentType.ERROR
    assert ContentType.detect(content="") == ContentType.EMPTY

    return True


# ============================================================
# Main Runner
# ============================================================

async def run_all_tests():
    """Run all tests."""
    print("\n" + "="*70)
    print("🚀 COMPREHENSIVE DATA FLOW TEST SUITE")
    print("="*70)

    tests = [
        # 1. Constructor tests
        test_node_constructor_basic,
        test_node_constructor_params,
        test_node_metadata,
        test_edge_constructor,
        test_graph_constructor_basic,

        # 2. Scheduler tests
        test_scheduler_basic,
        test_scheduler_url_rules,
        test_scheduler_exclusion,

        # 3. Filter tests
        test_domain_filter_basic,
        test_domain_filter_wildcard,
        test_domain_filter_blocked,
        test_path_filter_excluded,
        test_path_filter_included,

        # 4. LinkProcessor tests
        test_link_processor_basic,
        test_link_processor_edge_strategy,

        # 5. Custom Node tests
        test_custom_node_class,

        # 6. Backend tests
        test_memory_backend_basic,
        test_sqlite_backend_basic,
        test_graph_with_backend,

        # 7. Eviction tests
        test_low_memory_eviction,

        # 8. SmartURLRule tests
        test_smart_url_rule_scope,

        # 9. EdgeRule tests
        test_edge_rule,

        # 10. ContentType tests
        test_content_type_detection,
    ]

    for test_func in tests:
        await test_func()

    # Final summary
    print("\n" + "="*70)
    print("📊 TEST SUMMARY")
    print("="*70)

    total = test_results['passed'] + test_results['failed']
    print(f"\n   Total tests: {total}")
    print(f"   ✅ Passed: {test_results['passed']}")
    print(f"   ❌ Failed: {test_results['failed']}")

    if test_results['errors']:
        print("\n   Errors:")
        for error in test_results['errors']:
            print(f"   - {error}")

    print("\n" + "="*70)

    if test_results['failed'] == 0:
        print("✅ ALL TESTS PASSED! Data flow працює коректно.")
    else:
        print(f"⚠️ {test_results['failed']} TESTS FAILED!")

    print("="*70 + "\n")

    return test_results['failed'] == 0


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
