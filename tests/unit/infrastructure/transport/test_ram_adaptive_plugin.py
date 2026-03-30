"""Unit-тести для RamAdaptivePlugin."""

import asyncio
from unittest.mock import MagicMock

import pytest

from graph_crawler.infrastructure.transport.playwright.context import BrowserContext
from graph_crawler.infrastructure.transport.playwright.plugins.ram_adaptive import RamAdaptivePlugin
from graph_crawler.infrastructure.transport.playwright.stages import BrowserStage


def _make_plugin(percent=30.0, **kwargs) -> RamAdaptivePlugin:
    """Плагін з мок-psutil що повертає заданий % завантаження RAM."""
    plugin = RamAdaptivePlugin(**kwargs)
    mock_psutil = MagicMock()
    mock_psutil.virtual_memory.return_value.percent = percent
    mock_psutil.virtual_memory.return_value.used = int(percent / 100 * 32 * 1024 ** 3)
    plugin._psutil = mock_psutil
    plugin._lock = asyncio.Lock()
    return plugin


def _ctx(**data) -> BrowserContext:
    return BrowserContext(url="http://example.com", data=dict(data))


# ─── percent_mode (default) ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_no_adaptation_on_first_call():
    plugin = _make_plugin(percent=50.0)
    ctx = await plugin.on_before_fetch_many(_ctx())
    assert "suggested_concurrent" not in ctx.data


@pytest.mark.asyncio
async def test_samples_collected_on_content_ready():
    plugin = _make_plugin(percent=50.0)
    await plugin.on_content_ready(_ctx())
    await plugin.on_content_ready(_ctx())
    assert len(plugin._samples) == 2


@pytest.mark.asyncio
async def test_decrease_when_above_upper_threshold():
    # percent=90 → ratio=0.90 → > upper(0.85) → decrease
    plugin = _make_plugin(percent=90.0, upper_threshold=0.85, max_concurrent=10)
    plugin._current = 10
    await plugin.on_content_ready(_ctx())
    ctx = await plugin.on_before_fetch_many(_ctx())
    assert ctx.data["suggested_concurrent"] == 9
    assert ctx.data["ram_pressure"] == "high"


@pytest.mark.asyncio
async def test_increase_when_below_lower_threshold():
    # percent=50 → ratio=0.50 → < lower(0.70) → increase
    plugin = _make_plugin(percent=50.0, lower_threshold=0.70, max_concurrent=10)
    plugin._current = 5
    await plugin.on_content_ready(_ctx())
    ctx = await plugin.on_before_fetch_many(_ctx())
    assert ctx.data["suggested_concurrent"] == 6
    assert ctx.data["ram_pressure"] == "low"


@pytest.mark.asyncio
async def test_no_change_in_hysteresis_zone():
    # percent=78 → ratio=0.78 → between 0.70 and 0.85 → no change
    plugin = _make_plugin(percent=78.0, upper_threshold=0.85, lower_threshold=0.70)
    plugin._current = 8
    await plugin.on_content_ready(_ctx())
    ctx = await plugin.on_before_fetch_many(_ctx())
    assert ctx.data["suggested_concurrent"] == 8
    assert ctx.data["ram_pressure"] == "ok"


@pytest.mark.asyncio
async def test_high_system_load_does_not_crash_to_one_immediately():
    """Ключовий продакшен-тест: навіть при 95% завантаженні concurrent знижується по 1, не до 1."""
    plugin = _make_plugin(percent=95.0, upper_threshold=0.85, max_concurrent=10)
    plugin._current = 10
    await plugin.on_content_ready(_ctx())
    ctx = await plugin.on_before_fetch_many(_ctx())
    # Має знизитись ЛИШЕ на 1, не до мінімуму
    assert ctx.data["suggested_concurrent"] == 9


@pytest.mark.asyncio
async def test_min_concurrent_floor():
    plugin = _make_plugin(percent=95.0, upper_threshold=0.85, min_concurrent=2)
    plugin._current = 2
    await plugin.on_content_ready(_ctx())
    ctx = await plugin.on_before_fetch_many(_ctx())
    assert ctx.data["suggested_concurrent"] == 2


@pytest.mark.asyncio
async def test_max_concurrent_ceiling():
    plugin = _make_plugin(percent=30.0, lower_threshold=0.70, max_concurrent=5)
    plugin._current = 5
    await plugin.on_content_ready(_ctx())
    ctx = await plugin.on_before_fetch_many(_ctx())
    assert ctx.data["suggested_concurrent"] == 5


@pytest.mark.asyncio
async def test_samples_cleared_after_adaptation():
    plugin = _make_plugin(percent=50.0)
    await plugin.on_content_ready(_ctx())
    await plugin.on_content_ready(_ctx())
    await plugin.on_before_fetch_many(_ctx())
    assert len(plugin._samples) == 0


# ─── percent_mode=False (absolute mode) ───────────────────────────────────────

@pytest.mark.asyncio
async def test_absolute_mode_decrease():
    # used=28GB, limit=30GB → ratio=0.93 → > upper(0.85)
    plugin = RamAdaptivePlugin(
        percent_mode=False, ram_limit_gb=30.0,
        upper_threshold=0.85, max_concurrent=10,
    )
    mock_psutil = MagicMock()
    mock_psutil.virtual_memory.return_value.used = int(28 * 1024 ** 3)
    plugin._psutil = mock_psutil
    plugin._lock = asyncio.Lock()
    plugin._current = 10
    await plugin.on_content_ready(_ctx())
    ctx = await plugin.on_before_fetch_many(_ctx())
    assert ctx.data["suggested_concurrent"] == 9
    assert ctx.data["ram_pressure"] == "high"


# ─── meta ──────────────────────────────────────────────────────────────────────

def test_name():
    assert RamAdaptivePlugin().name == "ram_adaptive"


def test_hooks_registered():
    hooks = RamAdaptivePlugin().get_hooks()
    assert BrowserStage.CONTENT_READY in hooks
    assert BrowserStage.BEFORE_FETCH_MANY in hooks


def test_get_stats_keys():
    plugin = _make_plugin()
    stats = plugin.get_stats()
    for key in ("current_concurrent", "adaptations", "last_pressure_pct",
                "percent_mode", "upper_threshold_pct", "lower_threshold_pct"):
        assert key in stats
