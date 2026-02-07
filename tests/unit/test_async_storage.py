"""Async tests for storage (v3.0)."""

import pytest
import asyncio


@pytest.mark.asyncio
async def test_json_storage_async(temp_dir, sample_graph):
    """Test that JSONStorage async methods work correctly."""
    from graph_crawler.infrastructure.persistence import JSONStorage
    
    storage = JSONStorage(storage_dir=temp_dir)
    
    # Test save_graph
    result = await storage.save_graph(sample_graph)
    assert result is True
    
    # Test load_graph
    loaded_graph = await storage.load_graph()
    assert loaded_graph is not None
    assert len(loaded_graph.nodes) == len(sample_graph.nodes)


@pytest.mark.asyncio
async def test_memory_storage_async(sample_graph):
    """Test that MemoryStorage async methods work correctly."""
    from graph_crawler.infrastructure.persistence import MemoryStorage
    
    storage = MemoryStorage()
    
    # Test save_graph
    result = await storage.save_graph(sample_graph)
    assert result is True
    
    # Test load_graph
    loaded_graph = await storage.load_graph()
    assert loaded_graph is not None
    assert len(loaded_graph.nodes) == len(sample_graph.nodes)


@pytest.mark.asyncio
async def test_sqlite_storage_async(temp_dir, sample_graph):
    """Test that SQLiteStorage async methods work correctly."""
    from graph_crawler.infrastructure.persistence import SQLiteStorage
    
    storage = SQLiteStorage(storage_dir=temp_dir)
    
    # Test save_graph
    result = await storage.save_graph(sample_graph)
    assert result is True
    
    # Test load_graph
    loaded_graph = await storage.load_graph()
    assert loaded_graph is not None
    assert len(loaded_graph.nodes) == len(sample_graph.nodes)
