"""Тести для SSRF валідації URL."""

import pytest
from graph_crawler.shared.security.url_validator import (
    validate_url_security,
    is_url_safe,
    SSRFError,
    BLOCKED_HOSTS,
    BLOCKED_PORTS,
)


class TestBlockedHosts:
    """Тести для блокування небезпечних хостів."""
    
    def test_blocks_localhost(self):
        """Блокує localhost."""
        with pytest.raises(SSRFError, match="Blocked hostname"):
            validate_url_security("http://localhost/admin")
    
    def test_blocks_127_0_0_1(self):
        """Блокує 127.0.0.1."""
        with pytest.raises(SSRFError, match="Blocked hostname"):
            validate_url_security("http://127.0.0.1/admin")
    
    def test_blocks_0_0_0_0(self):
        """Блокує 0.0.0.0."""
        with pytest.raises(SSRFError, match="Blocked hostname"):
            validate_url_security("http://0.0.0.0/admin")
    
    def test_blocks_aws_metadata(self):
        """Блокує AWS metadata endpoint."""
        with pytest.raises(SSRFError, match="Blocked hostname"):
            validate_url_security("http://169.254.169.254/latest/meta-data/")
    
    def test_blocks_ipv6_localhost(self):
        """Блокує IPv6 localhost."""
        with pytest.raises(SSRFError, match="Blocked hostname"):
            validate_url_security("http://[::1]/admin")


class TestPrivateIPs:
    """Тести для блокування приватних IP адрес."""
    
    def test_blocks_private_192_168(self):
        """Блокує 192.168.x.x."""
        with pytest.raises(SSRFError, match="Private/reserved IP"):
            validate_url_security("http://192.168.1.1/admin")
    
    def test_blocks_private_10_x(self):
        """Блокує 10.x.x.x."""
        with pytest.raises(SSRFError, match="Private/reserved IP"):
            validate_url_security("http://10.0.0.1/")
    
    def test_blocks_private_172_16(self):
        """Блокує 172.16-31.x.x."""
        with pytest.raises(SSRFError, match="Private/reserved IP"):
            validate_url_security("http://172.16.0.1/")
    
    def test_allows_private_ip_when_allowed(self):
        """Дозволяє приватні IP якщо allow_internal=True."""
        # Не має викидати exception
        result = validate_url_security("http://192.168.1.1/", allow_internal=True)
        assert result is True


class TestBlockedPorts:
    """Тести для блокування небезпечних портів."""
    
    def test_blocks_ssh_port(self):
        """Блокує SSH порт 22."""
        with pytest.raises(SSRFError, match="Blocked port: 22"):
            validate_url_security("http://example.com:22/")
    
    def test_blocks_mysql_port(self):
        """Блокує MySQL порт 3306."""
        with pytest.raises(SSRFError, match="Blocked port: 3306"):
            validate_url_security("http://example.com:3306/")
    
    def test_blocks_postgresql_port(self):
        """Блокує PostgreSQL порт 5432."""
        with pytest.raises(SSRFError, match="Blocked port: 5432"):
            validate_url_security("http://example.com:5432/")
    
    def test_blocks_redis_port(self):
        """Блокує Redis порт 6379."""
        with pytest.raises(SSRFError, match="Blocked port: 6379"):
            validate_url_security("http://example.com:6379/")
    
    def test_blocks_mongodb_port(self):
        """Блокує MongoDB порт 27017."""
        with pytest.raises(SSRFError, match="Blocked port: 27017"):
            validate_url_security("http://example.com:27017/")


class TestProtocols:
    """Тести для валідації протоколів."""
    
    def test_allows_http(self):
        """Дозволяє HTTP."""
        assert validate_url_security("http://example.com/") is True
    
    def test_allows_https(self):
        """Дозволяє HTTPS."""
        assert validate_url_security("https://example.com/") is True
    
    def test_blocks_ftp(self):
        """Блокує FTP."""
        with pytest.raises(SSRFError, match="Unsupported protocol"):
            validate_url_security("ftp://example.com/")
    
    def test_blocks_file(self):
        """Блокує file://."""
        with pytest.raises(SSRFError, match="Unsupported protocol"):
            validate_url_security("file:///etc/passwd")
    
    def test_blocks_javascript(self):
        """Блокує javascript:."""
        with pytest.raises(SSRFError, match="Unsupported protocol"):
            validate_url_security("javascript:alert(1)")


class TestValidURLs:
    """Тести для валідних URL."""
    
    def test_allows_public_url(self):
        """Дозволяє публічні URL."""
        assert validate_url_security("https://example.com/") is True
    
    def test_allows_url_with_path(self):
        """Дозволяє URL з path."""
        assert validate_url_security("https://example.com/page/1") is True
    
    def test_allows_url_with_query(self):
        """Дозволяє URL з query параметрами."""
        assert validate_url_security("https://example.com/search?q=test") is True
    
    def test_allows_url_with_safe_port(self):
        """Дозволяє URL з безпечним портом."""
        assert validate_url_security("https://example.com:8080/") is True
    
    def test_allows_subdomain(self):
        """Дозволяє субдомени."""
        assert validate_url_security("https://api.example.com/") is True


class TestIsUrlSafe:
    """Тести для функції is_url_safe()."""
    
    def test_returns_true_for_safe_url(self):
        """Повертає True для безпечного URL."""
        assert is_url_safe("https://example.com") is True
    
    def test_returns_false_for_localhost(self):
        """Повертає False для localhost."""
        assert is_url_safe("http://localhost/admin") is False
    
    def test_returns_false_for_private_ip(self):
        """Повертає False для приватного IP."""
        assert is_url_safe("http://192.168.1.1/") is False
    
    def test_returns_false_for_blocked_port(self):
        """Повертає False для заблокованого порту."""
        assert is_url_safe("http://example.com:22/") is False


class TestEdgeCases:
    """Тести для граничних випадків."""
    
    def test_rejects_missing_hostname(self):
        """Відхиляє URL без hostname."""
        with pytest.raises(SSRFError, match="Missing hostname"):
            validate_url_security("http:///path")
    
    def test_rejects_invalid_url(self):
        """Відхиляє невалідний URL."""
        with pytest.raises(SSRFError):
            validate_url_security("not-a-url")
    
    def test_case_insensitive_hostname(self):
        """Hostname перевіряється case-insensitive."""
        with pytest.raises(SSRFError, match="Blocked hostname"):
            validate_url_security("http://LOCALHOST/admin")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
