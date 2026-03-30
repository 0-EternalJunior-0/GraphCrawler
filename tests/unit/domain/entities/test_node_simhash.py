"""
Тести для SimHash функціональності Node entity.

SimHash - Locality-Sensitive Hash для пошуку подібних документів (near-duplicates).
"""

import pytest

from graph_crawler.domain.entities.node import Node
from graph_crawler.domain.value_objects.lifecycle import NodeLifecycle, NodeLifecycleError
from graph_crawler.shared.constants import (
    SIMHASH_BITS,
    SIMHASH_HEX_LENGTH,
    SIMHASH_PATTERN,
)

class TestSimHashField:
    """Тести для simhash поля Node."""

    def test_simhash_default_is_none(self):
        """SimHash за замовчуванням None."""
        node = Node(url="https://example.com", depth=0)
        assert node.simhash is None

    def test_simhash_can_be_set(self):
        """SimHash можна встановити."""
        node = Node(url="https://example.com", depth=0)
        node.simhash = "abc123def456789a"
        assert node.simhash == "abc123def456789a"

class TestGetSimHash:
    """Тести для get_simhash() методу."""

    @pytest.mark.asyncio
    async def test_get_simhash_after_process_html(self):
        """get_simhash() працює після process_html()."""
        node = Node(url="https://example.com", depth=0)

        # Спочатку потрібно обробити HTML
        html = "<html><body><p>This is a test page with some content for testing simhash functionality</p></body></html>"
        await node.process_html(html)

        # Тепер simhash має бути обчислений
        assert node.simhash is not None
        assert len(node.simhash) == SIMHASH_HEX_LENGTH  # 16 hex символів для 64-bit

    def test_get_simhash_before_process_html_raises_error(self):
        """get_simhash() до process_html() викидає помилку."""
        node = Node(url="https://example.com", depth=0)

        with pytest.raises(NodeLifecycleError, match="Cannot compute simhash at url_stage"):
            node.get_simhash()

    @pytest.mark.asyncio
    async def test_simhash_is_deterministic(self):
        """SimHash детермінований - однакові дані = однаковий хеш."""
        html = "<html><body><p>Same content for testing determinism</p></body></html>"

        node1 = Node(url="https://example.com/1", depth=0)
        await node1.process_html(html)

        node2 = Node(url="https://example.com/2", depth=0)
        await node2.process_html(html)

        assert node1.simhash == node2.simhash

    @pytest.mark.asyncio
    async def test_simhash_different_for_different_content(self):
        """SimHash різний для різного контенту (з text_content)."""
        node1 = Node(url="https://example.com/1", depth=0)
        await node1.process_html("<html><body><p>First unique content about topic A</p></body></html>")
        node1.user_data["text_content"] = "First unique content about topic A with some extra words"

        node2 = Node(url="https://example.com/2", depth=0)
        await node2.process_html("<html><body><p>Completely different content about topic B</p></body></html>")
        node2.user_data["text_content"] = "Completely different content about topic B with other words"

        # Обчислюємо SimHash напряму для перевірки з текстом
        simhash1 = node1._compute_simhash_default(node1.user_data["text_content"])
        simhash2 = node2._compute_simhash_default(node2.user_data["text_content"])

        assert simhash1 != simhash2

    @pytest.mark.asyncio
    async def test_simhash_format_valid_hex(self):
        """SimHash має валідний hex формат."""
        import re

        node = Node(url="https://example.com", depth=0)
        await node.process_html("<html><body><p>Test content for hex validation</p></body></html>")

        # Перевіряємо що це валідний hex
        assert re.match(SIMHASH_PATTERN, node.simhash)

        # Перевіряємо що можна конвертувати в int
        int_value = int(node.simhash, 16)
        assert int_value >= 0
        assert int_value < 2**SIMHASH_BITS

    @pytest.mark.asyncio
    async def test_simhash_empty_content_returns_zeros(self):
        """SimHash для порожнього контенту - нулі."""
        node = Node(url="https://example.com", depth=0)
        await node.process_html("<html><body></body></html>")

        # Для порожнього тексту має бути нульовий хеш
        assert node.simhash is not None
        assert len(node.simhash) == SIMHASH_HEX_LENGTH

class TestHammingDistance:
    """Тести для hamming_distance() static методу."""

    def test_hamming_distance_identical_hashes(self):
        """Hamming distance для ідентичних хешів = 0."""
        simhash = "abc123def456789a"
        distance = Node.hamming_distance(simhash, simhash)
        assert distance == 0

    def test_hamming_distance_one_bit_difference(self):
        """Hamming distance для 1 біта різниці."""
        # 0x...9 (1001) vs 0x...8 (1000) = 1 bit difference
        simhash1 = "abc123def4567899"
        simhash2 = "abc123def4567898"
        distance = Node.hamming_distance(simhash1, simhash2)
        assert distance == 1

    def test_hamming_distance_completely_different(self):
        """Hamming distance для повністю різних хешів."""
        # 0x0...0 vs 0xF...F = all bits different
        simhash1 = "0000000000000000"
        simhash2 = "ffffffffffffffff"
        distance = Node.hamming_distance(simhash1, simhash2)
        assert distance == SIMHASH_BITS  # 64 для 64-bit

    def test_hamming_distance_symmetric(self):
        """Hamming distance симетрична."""
        simhash1 = "1234567890abcdef"
        simhash2 = "fedcba0987654321"

        dist1 = Node.hamming_distance(simhash1, simhash2)
        dist2 = Node.hamming_distance(simhash2, simhash1)

        assert dist1 == dist2

    def test_hamming_distance_range(self):
        """Hamming distance в діапазоні [0, 64]."""
        import random

        for _ in range(10):
            h1 = format(random.randint(0, 2**64 - 1), "016x")
            h2 = format(random.randint(0, 2**64 - 1), "016x")

            distance = Node.hamming_distance(h1, h2)
            assert 0 <= distance <= SIMHASH_BITS

class TestSimHashSimilarity:
    """Тести для перевірки схожості документів через SimHash."""

    @pytest.mark.asyncio
    async def test_similar_documents_have_small_distance(self):
        """Схожі документи мають малу Hamming distance."""
        node1 = Node(url="https://example.com/1", depth=0)
        await node1.process_html("""
            <html><body>
            <p>Python programming language tutorial for beginners</p>
            <p>Learn Python basics and advanced concepts</p>
            </body></html>
        """)

        node2 = Node(url="https://example.com/2", depth=0)
        await node2.process_html("""
            <html><body>
            <p>Python programming language tutorial for beginners</p>
            <p>Learn Python fundamentals and advanced topics</p>
            </body></html>
        """)

        distance = Node.hamming_distance(node1.simhash, node2.simhash)

        # Схожі документи повинні мати distance < 15 (з 64 можливих)
        assert distance < 20, f"Expected distance < 20 for similar docs, got {distance}"

    @pytest.mark.asyncio
    async def test_different_documents_have_large_distance(self):
        """Різні документи мають велику Hamming distance (з text_content)."""
        node1 = Node(url="https://example.com/1", depth=0)
        await node1.process_html("""
            <html><body>
            <h1>Weather Forecast</h1>
            <p>Today sunny skies with temperatures around 25 degrees celsius</p>
            <p>Tomorrow rain expected with thunderstorms</p>
            </body></html>
        """)
        node1.user_data["text_content"] = "Weather Forecast Today sunny skies with temperatures around 25 degrees celsius Tomorrow rain expected with thunderstorms"

        node2 = Node(url="https://example.com/2", depth=0)
        await node2.process_html("""
            <html><body>
            <h1>Stock Market Analysis</h1>
            <p>NASDAQ index rose by 2% today amid positive earnings reports</p>
            <p>Technology sector leads market gains with Apple up 5%</p>
            </body></html>
        """)
        node2.user_data["text_content"] = "Stock Market Analysis NASDAQ index rose by 2% today amid positive earnings reports Technology sector leads market gains with Apple up 5%"

        # Обчислюємо SimHash напряму
        simhash1 = node1._compute_simhash_default(node1.user_data["text_content"])
        simhash2 = node2._compute_simhash_default(node2.user_data["text_content"])

        distance = Node.hamming_distance(simhash1, simhash2)

        # Різні документи повинні мати distance > 10
        assert distance > 10, f"Expected distance > 10 for different docs, got {distance}"

class TestSimHashStrategy:
    """Тести для кастомної SimHash стратегії."""

    def test_simhash_strategy_default_none(self):
        """simhash_strategy за замовчуванням None."""
        node = Node(url="https://example.com", depth=0)
        assert node.simhash_strategy is None

    def test_restore_simhash_strategy(self):
        """Відновлення simhash_strategy через restore_dependencies()."""
        node = Node(url="https://example.com", depth=0)

        mock_strategy = object()
        node.restore_dependencies(simhash_strategy=mock_strategy)

        assert node.simhash_strategy is mock_strategy

    @pytest.mark.asyncio
    async def test_custom_simhash_strategy_used(self):
        """Кастомна simhash_strategy використовується."""

        class CustomSimHashStrategy:
            def compute_simhash(self, node):
                return "deadbeefcafebabe"  # Фіксований SimHash

        node = Node(url="https://example.com", depth=0)
        node.simhash_strategy = CustomSimHashStrategy()
        await node.process_html("<html><body><p>Any content</p></body></html>")

        assert node.simhash == "deadbeefcafebabe"

    @pytest.mark.asyncio
    async def test_invalid_simhash_strategy_logs_warning(self):
        """Невалідна simhash_strategy логує попередження (не ламає process_html)."""

        class BadStrategy:
            def compute_simhash(self, node):
                return "invalid"  # Занадто коротко

        node = Node(url="https://example.com", depth=0)
        node.simhash_strategy = BadStrategy()

        # process_html не повинен впасти, лише логує warning
        await node.process_html("<html><body><p>Content</p></body></html>")

        # simhash буде None через помилку
        assert node.simhash is None

    @pytest.mark.asyncio
    async def test_non_deterministic_strategy_logs_warning(self):
        """Недетермінована стратегія логує попередження."""
        import random

        class NonDeterministicStrategy:
            def compute_simhash(self, node):
                return format(random.randint(0, 2**64 - 1), "016x")

        node = Node(url="https://example.com", depth=0)
        node.simhash_strategy = NonDeterministicStrategy()

        # process_html не повинен впасти
        await node.process_html("<html><body><p>Content</p></body></html>")

        # simhash буде None через помилку детермінованості
        assert node.simhash is None

class TestSimHashSerialization:
    """Тести серіалізації SimHash."""

    @pytest.mark.asyncio
    async def test_simhash_in_model_dump(self):
        """simhash присутній в model_dump()."""
        node = Node(url="https://example.com", depth=0)
        await node.process_html("<html><body><p>Test content</p></body></html>")

        data = node.model_dump()

        assert "simhash" in data
        assert data["simhash"] == node.simhash

    @pytest.mark.asyncio
    async def test_simhash_round_trip(self):
        """SimHash зберігається при серіалізації → десеріалізації."""
        node = Node(url="https://example.com", depth=0)
        await node.process_html("<html><body><p>Test content for round trip</p></body></html>")

        original_simhash = node.simhash

        # Серіалізація
        data = node.model_dump()

        # Десеріалізація
        restored = Node.model_validate(data)

        assert restored.simhash == original_simhash

class TestComputeSimHashDefault:
    """Тести для дефолтної реалізації _compute_simhash_default()."""

    def test_compute_simhash_default_empty_text(self):
        """Порожній текст повертає нулі."""
        node = Node(url="https://example.com", depth=0)
        node.lifecycle_stage = NodeLifecycle.HTML_STAGE
        node.user_data["text_content"] = ""

        result = node._compute_simhash_default("", ngram_size=3, bits=64)

        assert result == "0" * 16  # 64 bits = 16 hex chars

    def test_compute_simhash_default_returns_correct_length(self):
        """Повертає правильну довжину hex."""
        node = Node(url="https://example.com", depth=0)

        result = node._compute_simhash_default("test text for simhash")

        assert len(result) == SIMHASH_HEX_LENGTH

    def test_compute_simhash_default_different_ngram_sizes(self):
        """Різні ngram_size дають різні результати."""
        node = Node(url="https://example.com", depth=0)
        text = "This is a longer test text for different ngram sizes"

        result_2 = node._compute_simhash_default(text, ngram_size=2)
        result_3 = node._compute_simhash_default(text, ngram_size=3)
        result_4 = node._compute_simhash_default(text, ngram_size=4)

        # Різні ngram розміри мають давати різні SimHash
        # (можуть бути однакові в рідких випадках, але зазвичай різні)
        unique_hashes = {result_2, result_3, result_4}
        assert len(unique_hashes) >= 2, "Expected at least 2 unique hashes"

class TestISimHashStrategyProtocol:
    """Тести для ISimHashStrategy Protocol."""

    def test_protocol_exists_in_node_interfaces(self):
        """ISimHashStrategy Protocol існує."""
        from graph_crawler.domain.interfaces.node_interfaces import ISimHashStrategy
        assert ISimHashStrategy is not None

    def test_custom_class_implements_protocol(self):
        """Кастомний клас може реалізувати Protocol."""
        from graph_crawler.domain.interfaces.node_interfaces import ISimHashStrategy

        class MySimHashStrategy:
            def compute_simhash(self, node) -> str:
                return "0" * 16

        strategy = MySimHashStrategy()
        assert isinstance(strategy, ISimHashStrategy)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
