"""Тести для санітизації URL."""

import pytest
from graph_crawler.shared.security.url_sanitizer import (
    sanitize_url,
    sanitize_connection_string,
)


class TestSanitizeUrl:
    """Тести для функції sanitize_url()."""
    
    def test_sanitizes_password(self):
        """Маскує пароль в URL."""
        url = "redis://:password123@localhost:6379/0"
        result = sanitize_url(url)
        
        assert "password123" not in result
        assert "***:***@localhost:6379/0" in result
    
    def test_sanitizes_username_and_password(self):
        """Маскує username та password."""
        url = "postgres://user:pass@host:5432/db"
        result = sanitize_url(url)
        
        assert "user" not in result
        assert "pass" not in result
        assert "***:***@host:5432" in result
    
    def test_preserves_url_without_credentials(self):
        """Зберігає URL без credentials."""
        url = "https://example.com/path?query=1"
        result = sanitize_url(url)
        
        assert result == url
    
    def test_preserves_scheme(self):
        """Зберігає схему URL."""
        url = "redis://:secret@localhost:6379/0"
        result = sanitize_url(url)
        
        assert result.startswith("redis://")
    
    def test_preserves_path(self):
        """Зберігає path."""
        url = "postgres://user:pass@host:5432/mydb"
        result = sanitize_url(url)
        
        assert "/mydb" in result
    
    def test_preserves_port(self):
        """Зберігає порт."""
        url = "redis://:secret@localhost:6379/0"
        result = sanitize_url(url)
        
        assert ":6379" in result
    
    def test_handles_url_with_only_password(self):
        """Обробляє URL тільки з паролем (без username)."""
        url = "redis://:mypassword@localhost:6379/0"
        result = sanitize_url(url)
        
        assert "mypassword" not in result
        assert "***:***@" in result
    
    def test_handles_invalid_url(self):
        """Повертає невалідний URL як є."""
        url = "not-a-valid-url"
        result = sanitize_url(url)
        
        assert result == url
    
    def test_custom_mask(self):
        """Використовує custom mask."""
        url = "redis://:secret@localhost:6379/0"
        result = sanitize_url(url, mask="[HIDDEN]")
        
        assert "[HIDDEN]:[HIDDEN]@" in result
        assert "secret" not in result


class TestSanitizeConnectionString:
    """Тести для функції sanitize_connection_string()."""
    
    def test_sanitizes_url_format(self):
        """Санітизує URL формат."""
        conn = "postgres://user:pass@host:5432/db"
        result = sanitize_connection_string(conn)
        
        assert "pass" not in result
        assert "***" in result
    
    def test_sanitizes_key_value_format(self):
        """Санітизує key-value формат."""
        conn = "host=localhost user=admin password=secret123 dbname=mydb"
        result = sanitize_connection_string(conn)
        
        assert "secret123" not in result
        assert "password=***" in result
    
    def test_sanitizes_pwd_keyword(self):
        """Санітизує pwd= ключове слово."""
        conn = "host=localhost user=admin pwd=secret123"
        result = sanitize_connection_string(conn)
        
        assert "secret123" not in result
        assert "pwd=***" in result
    
    def test_case_insensitive(self):
        """Password маскується незалежно від регістру."""
        conn = "host=localhost PASSWORD=Secret123"
        result = sanitize_connection_string(conn)
        
        assert "Secret123" not in result
    
    def test_preserves_other_params(self):
        """Зберігає інші параметри."""
        conn = "host=localhost user=admin password=secret dbname=mydb"
        result = sanitize_connection_string(conn)
        
        assert "host=localhost" in result
        assert "user=admin" in result
        assert "dbname=mydb" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
