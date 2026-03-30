# tests/unit/test_autothrottle.py
"""
Unit тести для AsyncAutoThrottlePlugin.

Покриття:
- Валідація конфігурації
- Поведінка основного алгоритму
- Обчислення затримки
- Захист від помилок
- Дотримання меж
- Безпека при паралельному доступі
"""

import asyncio
import time

import pytest

from graph_crawler.infrastructure.transport.async_http.context import AsyncHTTPContext
from graph_crawler.infrastructure.transport.async_http.plugins.autothrottle import (
    AsyncAutoThrottlePlugin,
    AutoThrottleConfig,
    DomainSlot,
)


# =============================================================================
# Тести конфігурації
# =============================================================================

class TestAutoThrottleConfig:
    """Тести для AutoThrottleConfig dataclass."""
    
    def test_default_config(self):
        """Тест значень за замовчуванням."""
        config = AutoThrottleConfig()
        
        assert config.start_delay == 5.0
        assert config.max_delay == 60.0
        assert config.min_delay == 0.0
        assert config.target_concurrency == 1.0
        assert config.debug is False
        assert config.error_backoff_factor == 1.5
    
    def test_conservative_profile(self):
        """Тест консервативного профілю конфігурації."""
        config = AutoThrottleConfig.conservative()
        
        assert config.start_delay == 10.0
        assert config.max_delay == 120.0
        assert config.min_delay == 5.0
        assert config.target_concurrency == 0.5
    
    def test_balanced_profile(self):
        """Тест збалансованого профілю конфігурації."""
        config = AutoThrottleConfig.balanced()
        
        assert config.start_delay == 5.0
        assert config.max_delay == 60.0
        assert config.min_delay == 0.5
        assert config.target_concurrency == 1.0
    
    def test_aggressive_profile(self):
        """Тест агресивного профілю конфігурації."""
        config = AutoThrottleConfig.aggressive()
        
        assert config.start_delay == 1.0
        assert config.max_delay == 30.0
        assert config.min_delay == 0.0
        assert config.target_concurrency == 4.0
    
    def test_invalid_target_concurrency(self):
        """Тест що невалідний target_concurrency викликає помилку."""
        with pytest.raises(ValueError, match="target_concurrency must be > 0"):
            AutoThrottleConfig(target_concurrency=0)
        
        with pytest.raises(ValueError, match="target_concurrency must be > 0"):
            AutoThrottleConfig(target_concurrency=-1.0)
    
    def test_invalid_delay_bounds(self):
        """Тест що min_delay > max_delay викликає помилку."""
        with pytest.raises(ValueError, match="min_delay .* > max_delay"):
            AutoThrottleConfig(min_delay=10.0, max_delay=5.0)
    
    def test_invalid_start_delay(self):
        """Тест що start_delay поза межами викликає помилку."""
        with pytest.raises(ValueError, match="start_delay .* must be in"):
            AutoThrottleConfig(start_delay=100.0, max_delay=60.0)
        
        with pytest.raises(ValueError, match="start_delay .* must be in"):
            AutoThrottleConfig(start_delay=0.0, min_delay=1.0)
    
    def test_config_is_frozen(self):
        """Тест що конфігурація незмінна."""
        config = AutoThrottleConfig()
        
        with pytest.raises(Exception):  # FrozenInstanceError
            config.start_delay = 10.0


# =============================================================================
# Тести DomainSlot
# =============================================================================

class TestDomainSlot:
    """Тести для DomainSlot dataclass."""
    
    def test_default_values(self):
        """Тест значень слота за замовчуванням."""
        slot = DomainSlot(domain="example.com")
        
        assert slot.domain == "example.com"
        assert slot.delay == 5.0
        assert slot.active_requests == 0
        assert slot.total_requests == 0
        assert slot.total_latency == 0.0
        assert slot.error_count == 0
        assert slot.success_count == 0
    
    def test_avg_latency_calculation(self):
        """Тест обчислення середньої затримки."""
        slot = DomainSlot(domain="example.com")
        
        # Немає запитів - має повернути 0
        assert slot.avg_latency == 0.0
        
        # З запитами
        slot.total_requests = 10
        slot.total_latency = 5.0  # 5s загалом
        
        assert slot.avg_latency == 0.5  # 500ms середнє
    
    def test_error_rate_calculation(self):
        """Тест обчислення рівня помилок."""
        slot = DomainSlot(domain="example.com")
        
        # Немає запитів - має повернути 0
        assert slot.error_rate == 0.0
        
        # З помилками
        slot.total_requests = 100
        slot.error_count = 10
        
        assert slot.error_rate == 0.1  # 10%
    
    def test_effective_throughput(self):
        """Тест обчислення пропускної здатності."""
        slot = DomainSlot(domain="example.com")
        
        # Затримка 5s за замовчуванням -> 0.2 rps
        assert slot.effective_throughput == 0.2
        
        # Затримка 1s -> 1 rps
        slot.delay = 1.0
        assert slot.effective_throughput == 1.0
        
        # Затримка 0.1s -> 10 rps
        slot.delay = 0.1
        assert slot.effective_throughput == 10.0
    
    def test_to_dict(self):
        """Тест експорту в словник."""
        slot = DomainSlot(domain="example.com", delay=2.5)
        slot.total_requests = 100
        slot.total_latency = 50.0
        slot.error_count = 5
        slot.min_latency_observed = 0.1
        slot.max_latency_observed = 2.0
        
        data = slot.to_dict()
        
        assert data["domain"] == "example.com"
        assert data["delay_ms"] == 2500.0
        assert data["total_requests"] == 100
        assert data["avg_latency_ms"] == 500.0
        assert data["min_latency_ms"] == 100.0
        assert data["max_latency_ms"] == 2000.0
        assert data["error_count"] == 5
        assert data["error_rate"] == 5.0


# =============================================================================
# Тести алгоритму
# =============================================================================

class TestAutoThrottleAlgorithm:
    """Unit тести для основного алгоритму throttling."""
    
    def test_target_delay_calculation(self):
        """Цільова затримка = latency / target_concurrency."""
        plugin = AsyncAutoThrottlePlugin(AutoThrottleConfig(
            start_delay=5.0,
            target_concurrency=2.0
        ))
        slot = DomainSlot(domain="test.com", delay=5.0)
        
        # latency=1.0, concurrency=2.0 → target=0.5
        new_delay, _ = plugin._calculate_new_delay(slot, latency=1.0, status_code=200)
        
        # Smoothed: (5.0 + 0.5) / 2 = 2.75
        # max(0.5, 2.75) = 2.75
        assert new_delay == 2.75
    
    def test_asymmetric_slowdown(self):
        """Сповільнення має бути негайним при зростанні latency."""
        plugin = AsyncAutoThrottlePlugin(AutoThrottleConfig(
            start_delay=1.0,
            target_concurrency=1.0,
            max_delay=100.0
        ))
        slot = DomainSlot(domain="test.com", delay=1.0)
        
        # High latency should cause immediate increase
        new_delay, _ = plugin._calculate_new_delay(slot, latency=10.0, status_code=200)
        
        # target = 10.0, smoothed = (1.0 + 10.0)/2 = 5.5
        # max(10.0, 5.5) = 10.0 (immediate jump to target)
        assert new_delay == 10.0
    
    def test_gradual_speedup(self):
        """Speedup should be gradual (smoothed)."""
        plugin = AsyncAutoThrottlePlugin(AutoThrottleConfig(
            start_delay=10.0,
            target_concurrency=1.0,
            min_delay=0.0
        ))
        slot = DomainSlot(domain="test.com", delay=10.0)
        
        # Low latency should cause gradual decrease
        new_delay, _ = plugin._calculate_new_delay(slot, latency=1.0, status_code=200)
        
        # target = 1.0, smoothed = (10.0 + 1.0)/2 = 5.5
        # max(1.0, 5.5) = 5.5 (gradual, not immediate)
        assert new_delay == 5.5
    
    def test_error_protection(self):
        """Non-2xx should not decrease delay."""
        plugin = AsyncAutoThrottlePlugin(AutoThrottleConfig(
            start_delay=5.0,
            target_concurrency=1.0
        ))
        slot = DomainSlot(domain="test.com", delay=5.0)
        
        # Fast error response should not speed up
        new_delay, should_update = plugin._calculate_new_delay(
            slot, latency=0.1, status_code=500
        )
        
        assert not should_update
        assert new_delay == 5.0  # Preserved
    
    def test_error_can_increase_delay(self):
        """Errors with high latency can still increase delay."""
        plugin = AsyncAutoThrottlePlugin(AutoThrottleConfig(
            start_delay=5.0,
            target_concurrency=1.0,
            max_delay=100.0
        ))
        slot = DomainSlot(domain="test.com", delay=5.0)
        
        # Slow error response can increase delay
        new_delay, should_update = plugin._calculate_new_delay(
            slot, latency=20.0, status_code=503
        )
        
        assert should_update
        assert new_delay == 20.0  # Increased
    
    def test_bounds_enforcement_max(self):
        """Delay should not exceed max_delay."""
        plugin = AsyncAutoThrottlePlugin(AutoThrottleConfig(
            start_delay=5.0,
            max_delay=10.0,
            target_concurrency=1.0
        ))
        slot = DomainSlot(domain="test.com", delay=5.0)
        
        # Very high latency
        new_delay, _ = plugin._calculate_new_delay(slot, latency=100.0, status_code=200)
        
        assert new_delay == 10.0  # Capped at max
    
    def test_bounds_enforcement_min(self):
        """Delay should not go below min_delay."""
        plugin = AsyncAutoThrottlePlugin(AutoThrottleConfig(
            start_delay=5.0,
            min_delay=1.0,
            target_concurrency=100.0  # High concurrency for very low target delay
        ))
        slot = DomainSlot(domain="test.com", delay=5.0)
        
        # Very low latency with high concurrency
        new_delay, _ = plugin._calculate_new_delay(slot, latency=0.01, status_code=200)
        
        assert new_delay >= 1.0  # At or above min


# =============================================================================
# Plugin Integration Tests
# =============================================================================

class TestAsyncAutoThrottlePlugin:
    """Integration tests for the plugin."""
    
    def test_plugin_initialization(self):
        """Test plugin initialization."""
        plugin = AsyncAutoThrottlePlugin()
        
        assert plugin.name == "async_autothrottle"
        assert plugin._throttle_config.start_delay == 5.0
        assert len(plugin._slots) == 0
    
    def test_plugin_with_config_dict(self):
        """Test initialization with dict config."""
        plugin = AsyncAutoThrottlePlugin(config={
            "start_delay": 2.0,
            "target_concurrency": 3.0
        })
        
        assert plugin._throttle_config.start_delay == 2.0
        assert plugin._throttle_config.target_concurrency == 3.0
    
    def test_plugin_with_config_object(self):
        """Test initialization with AutoThrottleConfig."""
        config = AutoThrottleConfig.aggressive()
        plugin = AsyncAutoThrottlePlugin(config=config)
        
        assert plugin._throttle_config.start_delay == 1.0
        assert plugin._throttle_config.target_concurrency == 4.0
    
    def test_hooks_registration(self):
        """Test that correct hooks are registered."""
        plugin = AsyncAutoThrottlePlugin()
        hooks = plugin.get_hooks()
        
        assert "preparing_request" in hooks
        assert "response_received" in hooks
        assert "request_failed" in hooks
    
    def test_domain_extraction(self):
        """Test domain extraction from URLs."""
        plugin = AsyncAutoThrottlePlugin()
        
        assert plugin._extract_domain("https://example.com/page") == "example.com"
        assert plugin._extract_domain("http://api.test.io:8080/v1") == "api.test.io:8080"
        assert plugin._extract_domain("https://sub.domain.co.uk/path") == "sub.domain.co.uk"
    
    @pytest.mark.asyncio
    async def test_slot_creation(self):
        """Test lazy slot creation."""
        plugin = AsyncAutoThrottlePlugin(AutoThrottleConfig(start_delay=3.0))
        
        slot = await plugin._get_or_create_slot("example.com")
        
        assert slot.domain == "example.com"
        assert slot.delay == 3.0
        assert "example.com" in plugin._slots
    
    @pytest.mark.asyncio
    async def test_slot_reuse(self):
        """Test that same slot is reused for domain."""
        plugin = AsyncAutoThrottlePlugin()
        
        slot1 = await plugin._get_or_create_slot("example.com")
        slot2 = await plugin._get_or_create_slot("example.com")
        
        assert slot1 is slot2
    
    def test_get_stats(self):
        """Test statistics retrieval."""
        plugin = AsyncAutoThrottlePlugin()
        plugin._slots["test.com"] = DomainSlot(
            domain="test.com",
            delay=2.5,
            total_requests=50,
            error_count=5
        )
        
        stats = plugin.get_stats()
        
        assert "test.com" in stats
        assert stats["test.com"]["delay_ms"] == 2500.0
        assert stats["test.com"]["total_requests"] == 50
    
    @pytest.mark.asyncio
    async def test_reset_single_domain(self):
        """Test resetting a single domain."""
        plugin = AsyncAutoThrottlePlugin(AutoThrottleConfig(start_delay=5.0))
        
        # Create slots
        await plugin._get_or_create_slot("domain1.com")
        await plugin._get_or_create_slot("domain2.com")
        
        # Modify one
        plugin._slots["domain1.com"].delay = 20.0
        
        # Reset single domain
        await plugin.reset("domain1.com")
        
        assert plugin._slots["domain1.com"].delay == 5.0  # Reset
        assert "domain2.com" in plugin._slots  # Not affected
    
    @pytest.mark.asyncio
    async def test_reset_all_domains(self):
        """Test resetting all domains."""
        plugin = AsyncAutoThrottlePlugin()
        
        # Create slots
        await plugin._get_or_create_slot("domain1.com")
        await plugin._get_or_create_slot("domain2.com")
        
        # Reset all
        await plugin.reset()
        
        assert len(plugin._slots) == 0


# =============================================================================
# Concurrency Tests
# =============================================================================

class TestAutoThrottleConcurrency:
    """Tests for thread safety and concurrent access."""
    
    @pytest.mark.asyncio
    async def test_concurrent_slot_creation(self):
        """Multiple coroutines creating same slot should not race."""
        plugin = AsyncAutoThrottlePlugin(AutoThrottleConfig())
        
        async def create_slot():
            return await plugin._get_or_create_slot("test.com")
        
        # 100 concurrent creations
        slots = await asyncio.gather(*[create_slot() for _ in range(100)])
        
        # All should return same slot instance
        assert all(s is slots[0] for s in slots)
        assert len(plugin._slots) == 1
    
    @pytest.mark.asyncio
    async def test_multiple_domains_isolation(self):
        """Different domains should have independent slots."""
        plugin = AsyncAutoThrottlePlugin(AutoThrottleConfig(start_delay=5.0))
        
        domains = [f"domain{i}.com" for i in range(10)]
        
        async def create_and_modify(domain: str, delay: float):
            slot = await plugin._get_or_create_slot(domain)
            async with plugin._lock:
                slot.delay = delay
            return slot
        
        # Create slots with different delays
        tasks = [create_and_modify(d, float(i)) for i, d in enumerate(domains)]
        await asyncio.gather(*tasks)
        
        # Each domain should have its own delay
        for i, domain in enumerate(domains):
            assert plugin._slots[domain].delay == float(i)


# =============================================================================
# Lifecycle Hook Tests
# =============================================================================

class TestLifecycleHooks:
    """Tests for lifecycle hooks."""
    
    @pytest.mark.asyncio
    async def test_on_preparing_request(self):
        """Test preparing request hook."""
        plugin = AsyncAutoThrottlePlugin(AutoThrottleConfig(
            start_delay=0.0  # No delay for test
        ))
        
        ctx = AsyncHTTPContext(url="https://example.com/page")
        ctx.data = {}
        
        result = await plugin.on_preparing_request(ctx)
        
        # Should add metadata
        assert AsyncAutoThrottlePlugin.CTX_START_TIME in result.data
        assert result.data[AsyncAutoThrottlePlugin.CTX_DOMAIN] == "example.com"
        
        # Should increment active requests
        slot = plugin._slots["example.com"]
        assert slot.active_requests == 1
    
    @pytest.mark.asyncio
    async def test_on_response_received(self):
        """Test response received hook."""
        plugin = AsyncAutoThrottlePlugin(AutoThrottleConfig(
            start_delay=5.0,
            target_concurrency=1.0
        ))
        
        # Setup context with metadata
        ctx = AsyncHTTPContext(url="https://example.com/page")
        ctx.data = {
            AsyncAutoThrottlePlugin.CTX_START_TIME: time.time() - 1.0,  # 1s latency
            AsyncAutoThrottlePlugin.CTX_DOMAIN: "example.com"
        }
        ctx.status_code = 200
        
        # Pre-create slot with active request
        slot = await plugin._get_or_create_slot("example.com")
        slot.active_requests = 1
        
        result = await plugin.on_response_received(ctx)
        
        # Should update metrics
        assert slot.total_requests == 1
        assert slot.success_count == 1
        assert slot.active_requests == 0
        assert slot.total_latency > 0
    
    @pytest.mark.asyncio
    async def test_on_request_failed(self):
        """Test request failed hook."""
        plugin = AsyncAutoThrottlePlugin(AutoThrottleConfig(
            start_delay=5.0,
            error_backoff_factor=2.0
        ))
        
        # Setup context
        ctx = AsyncHTTPContext(url="https://example.com/page")
        ctx.data = {
            AsyncAutoThrottlePlugin.CTX_DOMAIN: "example.com"
        }
        
        # Pre-create slot
        slot = await plugin._get_or_create_slot("example.com")
        slot.active_requests = 1
        
        result = await plugin.on_request_failed(ctx)
        
        # Should increase delay by backoff factor
        assert slot.delay == 10.0  # 5.0 * 2.0
        assert slot.error_count == 1
        assert slot.active_requests == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
