"""
Тести для value objects - configs.

Очікувана кількість: 30+ тестів
"""

import pytest
from graph_crawler.domain.value_objects.configs import (
    ProxyType,
    SQLitePragmas,
    ProxyConfig,
    BrowserConfig,
    DriverConfig,
    StorageConfig,
    CrawlerConfig,
)


class TestProxyType:
    """Тести для ProxyType enum."""
    
    def test_proxy_type_http(self):
        """HTTP proxy type."""
        assert ProxyType.HTTP.value == "http"
    
    def test_proxy_type_https(self):
        """HTTPS proxy type."""
        assert ProxyType.HTTPS.value == "https"
    
    def test_proxy_type_socks4(self):
        """SOCKS4 proxy type."""
        assert ProxyType.SOCKS4.value == "socks4"
    
    def test_proxy_type_socks5(self):
        """SOCKS5 proxy type."""
        assert ProxyType.SOCKS5.value == "socks5"


class TestSQLitePragmas:
    """Тести для SQLitePragmas."""
    
    def test_default_values(self):
        """Значення за замовчуванням."""
        pragmas = SQLitePragmas()
        
        assert pragmas.journal_mode == "WAL"
        assert pragmas.synchronous == "NORMAL"
        assert pragmas.cache_size == -64000
    
    def test_custom_journal_mode(self):
        """Кастомний journal_mode."""
        pragmas = SQLitePragmas(journal_mode="DELETE")
        assert pragmas.journal_mode == "DELETE"
    
    def test_invalid_journal_mode(self):
        """Невалідний journal_mode."""
        with pytest.raises(ValueError):
            SQLitePragmas(journal_mode="INVALID")
    
    def test_custom_synchronous(self):
        """Кастомний synchronous."""
        pragmas = SQLitePragmas(synchronous="FULL")
        assert pragmas.synchronous == "FULL"
    
    def test_invalid_synchronous(self):
        """Невалідний synchronous."""
        with pytest.raises(ValueError):
            SQLitePragmas(synchronous="INVALID")
    
    def test_to_dict(self):
        """to_dict() повертає словник."""
        pragmas = SQLitePragmas()
        data = pragmas.to_dict()
        
        assert isinstance(data, dict)
        assert "journal_mode" in data
        assert "synchronous" in data
        assert "cache_size" in data


class TestProxyConfig:
    """Тести для ProxyConfig."""
    
    def test_default_disabled(self):
        """Проксі за замовчуванням вимкнено."""
        proxy = ProxyConfig()
        
        assert proxy.enabled is False
        assert proxy.url is None
    
    def test_enabled_with_url(self):
        """Проксі з URL."""
        proxy = ProxyConfig(
            enabled=True,
            url="http://proxy.example.com:8080"
        )
        
        assert proxy.enabled is True
        assert proxy.url == "http://proxy.example.com:8080"
    
    def test_with_credentials(self):
        """Проксі з credentials."""
        proxy = ProxyConfig(
            enabled=True,
            url="http://proxy.example.com:8080",
            username="user",
            password="pass"
        )
        
        assert proxy.username == "user"
        assert proxy.password == "pass"


class TestBrowserConfig:
    """Тести для BrowserConfig."""
    
    def test_default_values(self):
        """Значення за замовчуванням."""
        config = BrowserConfig()
        
        assert config.headless is True
        assert config.viewport_width == 1920
        assert config.viewport_height == 1080
    
    def test_headless_false(self):
        """headless=False."""
        config = BrowserConfig(headless=False)
        assert config.headless is False
    
    def test_custom_viewport(self):
        """Кастомний viewport."""
        config = BrowserConfig(
            viewport_width=1280,
            viewport_height=720
        )
        
        assert config.viewport_width == 1280
        assert config.viewport_height == 720


class TestDriverConfig:
    """Тести для DriverConfig."""
    
    def test_default_values(self):
        """Значення за замовчуванням."""
        config = DriverConfig()
        
        # Використовуємо правильні назви полів
        assert config.request_timeout == 30
        assert config.max_retries == 3
    
    def test_custom_timeout(self):
        """Кастомний request_timeout."""
        config = DriverConfig(request_timeout=60)
        assert config.request_timeout == 60
    
    def test_custom_user_agent(self):
        """Кастомний user_agent."""
        config = DriverConfig(user_agent="MyBot/1.0")
        assert config.user_agent == "MyBot/1.0"


class TestStorageConfig:
    """Тести для StorageConfig."""
    
    def test_default_values(self):
        """Значення за замовчуванням."""
        import tempfile
        import os
        
        config = StorageConfig()
        
        # StorageConfig не має storage_type, але має storage_dir
        expected_dir = os.path.join(tempfile.gettempdir(), "graph_crawler")
        assert config.storage_dir == expected_dir
        assert config.auto_save_enabled is True
    
    def test_json_settings(self):
        """JSON settings."""
        config = StorageConfig(json_indent=4)
        assert config.json_indent == 4
    
    def test_sqlite_pragmas(self):
        """SQLite pragmas."""
        config = StorageConfig()
        assert config.sqlite_pragmas.journal_mode == "WAL"
    
    def test_custom_storage_dir(self):
        """Кастомна директорія."""
        config = StorageConfig(storage_dir="/tmp/crawl")
        assert config.storage_dir == "/tmp/crawl"


class TestCrawlerConfig:
    """Тести для CrawlerConfig."""
    
    def test_creates_with_url(self):
        """Створюється з URL."""
        # Використовуємо правильне поле 'url' замість 'start_url'
        config = CrawlerConfig(url="https://example.com")
        
        assert config.url == "https://example.com"
    
    def test_default_max_depth(self):
        """max_depth за замовчуванням."""
        config = CrawlerConfig(url="https://example.com")
        
        assert config.max_depth >= 0
    
    def test_default_max_pages(self):
        """max_pages за замовчуванням."""
        config = CrawlerConfig(url="https://example.com")
        
        assert config.max_pages >= 0
    
    def test_custom_max_depth(self):
        """Кастомний max_depth."""
        config = CrawlerConfig(
            url="https://example.com",
            max_depth=5
        )
        
        assert config.max_depth == 5
    
    def test_custom_max_pages(self):
        """Кастомний max_pages."""
        config = CrawlerConfig(
            url="https://example.com",
            max_pages=1000
        )
        
        assert config.max_pages == 1000
    
    def test_negative_max_depth_invalid(self):
        """Негативний max_depth невалідний."""
        with pytest.raises(ValueError):
            CrawlerConfig(
                url="https://example.com",
                max_depth=-1
            )
    
    def test_negative_max_pages_invalid(self):
        """Негативний max_pages невалідний."""
        with pytest.raises(ValueError):
            CrawlerConfig(
                url="https://example.com",
                max_pages=-1
            )
    
    def test_nested_configs(self):
        """Вкладені конфігурації."""
        config = CrawlerConfig(
            url="https://example.com",
            driver=DriverConfig(request_timeout=60),
            storage=StorageConfig(storage_dir="/tmp/sqlite")
        )
        
        assert config.driver.request_timeout == 60
        assert config.storage.storage_dir == "/tmp/sqlite"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
