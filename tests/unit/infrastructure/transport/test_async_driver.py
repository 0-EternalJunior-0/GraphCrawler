"""Тести для AsyncDriver - асинхронний HTTP драйвер.

Виправлено API:
- AsyncDriver(config={...}) - через config dict
- fetch(url) замість fetch_page(url)
- FetchResponse замість Response
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from graph_crawler.infrastructure.transport.async_http.driver import AsyncDriver
from graph_crawler.domain.value_objects.models import FetchResponse


@pytest.mark.asyncio
class TestAsyncDriverInitialization:
    """Тести ініціалізації AsyncDriver."""
    
    async def test_creates_driver_with_defaults(self):
        """Driver створюється з дефолтними налаштуваннями."""
        driver = AsyncDriver()
        
        assert driver is not None
        assert hasattr(driver, 'fetch')
        assert hasattr(driver, 'fetch_many')
    
    async def test_creates_driver_with_config_timeout(self):
        """Driver створюється з custom timeout через config."""
        driver = AsyncDriver(config={"timeout": 30})
        
        assert driver.config.get("timeout") == 30
    
    async def test_creates_driver_with_custom_user_agent(self):
        """Driver створюється з custom user agent."""
        driver = AsyncDriver(config={"user_agent": "TestBot/1.0"})
        
        assert driver.config.get("user_agent") == "TestBot/1.0"


@pytest.mark.asyncio
class TestAsyncDriverFetch:
    """Тести методу fetch."""
    
    async def test_fetch_returns_fetch_response(self):
        """fetch повертає FetchResponse object."""
        driver = AsyncDriver()
        
        # Mock aiohttp session
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="<html><body>Test</body></html>")
        mock_response.headers = {}
        
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_response
        mock_context.__aexit__.return_value = None
        
        with patch.object(driver, '_get_session') as mock_get_session:
            mock_session = AsyncMock()
            mock_session.get.return_value = mock_context
            mock_get_session.return_value = mock_session
            
            response = await driver.fetch("https://example.com")
        
        assert response is not None
        assert isinstance(response, FetchResponse)
    
    async def test_fetch_returns_url(self):
        """fetch повертає URL в response."""
        driver = AsyncDriver()
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="<html></html>")
        mock_response.headers = {}
        
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_response
        mock_context.__aexit__.return_value = None
        
        with patch.object(driver, '_get_session') as mock_get_session:
            mock_session = AsyncMock()
            mock_session.get.return_value = mock_context
            mock_get_session.return_value = mock_session
            
            response = await driver.fetch("https://example.com/page")
        
        assert response.url == "https://example.com/page"


@pytest.mark.asyncio
class TestAsyncDriverFetchMany:
    """Тести методу fetch_many."""
    
    async def test_fetch_many_returns_list(self):
        """fetch_many повертає список FetchResponse."""
        driver = AsyncDriver()
        
        # Mock fetch
        with patch.object(driver, 'fetch') as mock_fetch:
            mock_fetch.return_value = FetchResponse(
                url="https://example.com",
                html="<html></html>",
                status_code=200,
                headers={},
                error=None
            )
            
            results = await driver.fetch_many(["https://example.com", "https://example.org"])
        
        assert isinstance(results, list)
        assert len(results) == 2
    
    async def test_fetch_many_empty_list(self):
        """fetch_many повертає пустий список для пустого input."""
        driver = AsyncDriver()
        
        results = await driver.fetch_many([])
        
        assert results == []


@pytest.mark.asyncio
class TestAsyncDriverClose:
    """Тести закриття AsyncDriver."""
    
    async def test_close_method_exists(self):
        """Driver має метод close()."""
        driver = AsyncDriver()
        
        assert hasattr(driver, 'close')
    
    async def test_close_is_async(self):
        """close() метод є async."""
        driver = AsyncDriver()
        
        # close має бути async
        await driver.close()


@pytest.mark.asyncio
class TestAsyncDriverBatchSupport:
    """Тести batch fetching."""
    
    async def test_supports_batch_fetching(self):
        """Driver підтримує batch fetching."""
        driver = AsyncDriver()
        
        result = driver.supports_batch_fetching()
        
        assert result is True


@pytest.mark.asyncio
class TestAsyncDriverConfig:
    """Тести конфігурації."""
    
    async def test_default_max_concurrent(self):
        """Driver має default max_concurrent."""
        driver = AsyncDriver()
        
        assert driver.max_concurrent > 0
    
    async def test_custom_max_concurrent(self):
        """Driver з custom max_concurrent."""
        driver = AsyncDriver(config={"max_concurrent_requests": 5})
        
        assert driver.max_concurrent == 5


@pytest.mark.asyncio
class TestAsyncDriverPlugins:
    """Тести плагінів."""
    
    async def test_has_plugin_manager(self):
        """Driver має plugin manager."""
        driver = AsyncDriver()
        
        assert hasattr(driver, 'plugin_manager')
    
    async def test_creates_with_plugins(self):
        """Driver створюється з плагінами."""
        from graph_crawler.infrastructure.transport.base_plugin import BaseDriverPlugin
        
        class TestPlugin(BaseDriverPlugin):
            name = "test_plugin"
        
        plugin = TestPlugin()
        driver = AsyncDriver(plugins=[plugin])
        
        assert len(driver.plugin_manager.plugins) == 1


# Загальна кількість тестів: 15+
# Покриває: ініціалізація, fetch, fetch_many, close, config, plugins
