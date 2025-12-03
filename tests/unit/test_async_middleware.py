"""Async tests for middleware (v3.0)."""

import pytest
import asyncio
from graph_crawler.extensions.middleware.base import MiddlewareContext


@pytest.mark.asyncio
async def test_rate_limit_middleware_async():
    """Test that RateLimitMiddleware.process() is async."""
    from graph_crawler.extensions.middleware.rate_limit_middleware import RateLimitMiddleware
    
    middleware = RateLimitMiddleware({
        "requests_per_second": 10.0,
        "burst_size": 20
    })
    
    context = MiddlewareContext(url="https://example.com")
    result = await middleware.process(context)
    
    assert result is not None
    assert result.url == "https://example.com"
    assert "rate_limit" in result.metadata


@pytest.mark.asyncio
async def test_retry_middleware_async():
    """Test that RetryMiddleware.process() is async."""
    from graph_crawler.extensions.middleware.retry_middleware import RetryMiddleware
    
    middleware = RetryMiddleware({
        "max_retries": 3,
        "retry_delay": 0.01  # Fast for testing
    })
    
    context = MiddlewareContext(url="https://example.com")
    result = await middleware.process(context)
    
    assert result is not None
    assert result.url == "https://example.com"


@pytest.mark.asyncio
async def test_cache_middleware_async(temp_dir):
    """Test that CacheMiddleware.process() is async."""
    from graph_crawler.extensions.middleware.cache_middleware import CacheMiddleware
    
    middleware = CacheMiddleware({
        "cache_dir": temp_dir,
        "ttl": 3600,
        "enabled": True
    })
    
    context = MiddlewareContext(url="https://example.com")
    result = await middleware.process(context)
    
    assert result is not None
    # Перевіряємо що кеш не був hit (перший запит)
    if hasattr(result, 'middleware_data') and "cache" in result.middleware_data:
        assert result.middleware_data["cache"]["hit"] == False


@pytest.mark.asyncio
async def test_error_recovery_middleware_async():
    """Test that ErrorRecoveryMiddleware.process() is async."""
    from graph_crawler.extensions.middleware.error_recovery_middleware import ErrorRecoveryMiddleware
    
    middleware = ErrorRecoveryMiddleware({
        "log_errors": True,
        "continue_on_error": True
    })
    
    context = MiddlewareContext(url="https://example.com")
    result = await middleware.process(context)
    
    assert result is not None
    assert result.url == "https://example.com"


@pytest.mark.asyncio
async def test_proxy_middleware_async():
    """Test that ProxyRotationMiddleware.process() is async."""
    from graph_crawler.extensions.middleware.proxy_middleware import ProxyRotationMiddleware
    
    middleware = ProxyRotationMiddleware({
        "proxy_list": ["http://proxy1:8080"],
        "check_health": False  # Skip health checks for testing
    })
    
    context = MiddlewareContext(url="https://example.com")
    result = await middleware.process(context)
    
    assert result is not None
    assert result.url == "https://example.com"
