"""Інтеграційний тест RamAdaptivePlugin з реальним psutil та DriverPluginManager."""

import asyncio

import psutil
import pytest

from graph_crawler.infrastructure.transport.playwright.context import BrowserContext
from graph_crawler.infrastructure.transport.playwright.plugins.ram_adaptive import RamAdaptivePlugin
from graph_crawler.infrastructure.transport.playwright.stages import BrowserStage
from graph_crawler.infrastructure.transport.plugin_manager import DriverPluginManager


def _ctx(**data) -> BrowserContext:
    return BrowserContext(url="http://example.com", data=dict(data))


# ─── базові перевірки реального psutil ────────────────────────────────────────

@pytest.mark.asyncio
async def test_psutil_percent_is_real():
    plugin = RamAdaptivePlugin()
    plugin.setup()
    assert plugin.enabled

    ratio = plugin._measure_ratio()
    system_pct = psutil.virtual_memory().percent / 100.0

    assert 0.0 < ratio < 1.5, f"ratio поза розумними межами: {ratio}"
    assert abs(ratio - system_pct) < 0.02, (
        f"Plugin={ratio:.3f} vs psutil={system_pct:.3f} — розходження > 2%"
    )


@pytest.mark.asyncio
async def test_samples_store_ratios_not_gb():
    plugin = RamAdaptivePlugin()
    plugin.setup()

    for _ in range(5):
        await plugin.on_content_ready(_ctx())

    assert len(plugin._samples) == 5
    # У percent_mode samples мають бути в діапазоні 0.0–1.0 (не гігабайти)
    assert all(0.0 < s <= 1.0 for s in plugin._samples), (
        f"Samples виглядають як GB, а не ratio: {plugin._samples}"
    )


# ─── ключовий продакшен-тест: система з 30% RAM не роняє concurrent ───────────

@pytest.mark.asyncio
async def test_production_scenario_stable_system():
    """
    На системі де RAM завантажена < 70% — concurrent НЕ повинен зменшуватись.
    Це фіксує регресію: старий код з ram_limit_gb=3.0 тут падав до 1.
    """
    mem = psutil.virtual_memory()
    system_pct = mem.percent

    plugin = RamAdaptivePlugin(
        upper_threshold=0.85,
        lower_threshold=0.70,
        max_concurrent=10,
    )
    plugin.setup()
    plugin._current = 10

    # Один батч вимірювань
    for _ in range(5):
        await plugin.on_content_ready(_ctx())
    ctx = await plugin.on_before_fetch_many(_ctx())

    if system_pct < 70:
        # Система ненавантажена → concurrent не має падати нижче max
        assert ctx.data["suggested_concurrent"] == 10, (
            f"При system_pct={system_pct:.1f}% (<70%) concurrent впав до "
            f"{ctx.data['suggested_concurrent']} — це баг старого коду"
        )
        assert ctx.data["ram_pressure"] in ("low", "ok")
    elif system_pct < 85:
        assert ctx.data["ram_pressure"] == "ok"
    else:
        assert ctx.data["ram_pressure"] == "high"


@pytest.mark.asyncio
async def test_old_bug_reproduced_then_fixed():
    """
    Демонструє що старий баг (ram_limit_gb=3.0, absolute mode) призводив
    до ratio >> 1 на реальній машині, і плагін падав до min.
    Новий percent_mode цього не робить.
    """
    actual_used_gb = psutil.virtual_memory().used / (1024 ** 3)

    # СТАРИЙ КОД: absolute mode, limit=3GB → ratio = actual_used / 3.0
    old_plugin = RamAdaptivePlugin(
        percent_mode=False, ram_limit_gb=3.0,
        upper_threshold=0.90, lower_threshold=0.75,
        max_concurrent=10, min_concurrent=1,
    )
    old_plugin.setup()
    old_plugin._current = 10

    for _ in range(3):
        await old_plugin.on_content_ready(_ctx())
    old_ctx = await old_plugin.on_before_fetch_many(_ctx())

    old_ratio = actual_used_gb / 3.0
    if old_ratio > 0.90:
        # Стара поведінка: concurrent ЗМЕНШИВСЯ через хибний ratio
        assert old_ctx.data["suggested_concurrent"] < 10, (
            "Очікували зменшення concurrent у старому коді"
        )

    # НОВИЙ КОД: percent_mode → ratio = system%
    new_plugin = RamAdaptivePlugin(
        percent_mode=True,
        upper_threshold=0.85, lower_threshold=0.70,
        max_concurrent=10, min_concurrent=1,
    )
    new_plugin.setup()
    new_plugin._current = 10

    for _ in range(3):
        await new_plugin.on_content_ready(_ctx())
    new_ctx = await new_plugin.on_before_fetch_many(_ctx())

    system_pct = psutil.virtual_memory().percent
    if system_pct < 85:
        # Нова поведінка: при нормальному завантаженні concurrent НЕ падає
        assert new_ctx.data["suggested_concurrent"] >= old_ctx.data["suggested_concurrent"], (
            f"Новий код має бути не гіршим за старий: "
            f"new={new_ctx.data['suggested_concurrent']} old={old_ctx.data['suggested_concurrent']}"
        )


# ─── інтеграція з DriverPluginManager ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_full_lifecycle_via_plugin_manager():
    plugin = RamAdaptivePlugin(max_concurrent=12)
    manager = DriverPluginManager(is_async=True)
    manager.register(plugin)

    assert BrowserStage.CONTENT_READY.value in manager.hook_plugins
    assert BrowserStage.BEFORE_FETCH_MANY.value in manager.hook_plugins

    for _ in range(3):
        await manager.execute_hook_async(BrowserStage.CONTENT_READY, _ctx())

    assert len(plugin._samples) == 3

    batch_ctx = _ctx(total_urls=10)
    batch_ctx = await manager.execute_hook_async(BrowserStage.BEFORE_FETCH_MANY, batch_ctx)

    assert "suggested_concurrent" in batch_ctx.data
    assert "ram_ratio" in batch_ctx.data
    assert len(plugin._samples) == 0


@pytest.mark.asyncio
async def test_race_condition_safety():
    plugin = RamAdaptivePlugin()
    plugin.setup()
    await asyncio.gather(*[plugin.on_content_ready(_ctx()) for _ in range(20)])
    assert len(plugin._samples) == 20


@pytest.mark.asyncio
async def test_gradual_change_not_cliff():
    """concurrent змінюється по 1, а не обвалюється одразу."""
    plugin = RamAdaptivePlugin(upper_threshold=0.01, max_concurrent=10, min_concurrent=1)
    plugin.setup()
    plugin._current = 10

    history = []
    for _ in range(10):
        await plugin.on_content_ready(_ctx())
        ctx = await plugin.on_before_fetch_many(_ctx())
        history.append(ctx.data["suggested_concurrent"])

    # Кожен крок — не більше ніж -1
    for i in range(1, len(history)):
        assert history[i] >= history[i - 1] - 1, (
            f"Стрибок більше ніж 1: {history[i-1]} → {history[i]}, history={history}"
        )


@pytest.mark.asyncio
async def test_get_stats_reflects_real_state():
    plugin = RamAdaptivePlugin()
    plugin.setup()

    for _ in range(2):
        await plugin.on_content_ready(_ctx())
    await plugin.on_before_fetch_many(_ctx())

    stats = plugin.get_stats()
    assert stats["last_pressure_pct"] > 0
    assert stats["percent_mode"] is True
    assert stats["upper_threshold_pct"] == pytest.approx(85.0)


@pytest.mark.asyncio
async def test_teardown_cleans_state():
    plugin = RamAdaptivePlugin()
    plugin.setup()
    for _ in range(3):
        await plugin.on_content_ready(_ctx())
    plugin.teardown()
    assert len(plugin._samples) == 0
    assert plugin._psutil is None
