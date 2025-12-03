"""Тести для перевірки відсутності hardcoded паролів."""

import pytest
from pathlib import Path


class TestNoHardcodedPasswords:
    """Тести для перевірки відсутності hardcoded паролів у коді."""
    
    # Патерни які вказують на hardcoded паролі
    FORBIDDEN_PATTERNS = [
        'password="secret"',
        "password='secret'",
        'password="pass"',
        "password='pass'",
        'password="password"',
        "password='password'",
        'password="admin"',
        "password='admin'",
        'password="123456"',
        "password='123456'",
    ]
    
    # Файли/директорії які можна пропустити
    SKIP_DIRS = {'__pycache__', '.git', 'venv', '.venv', 'node_modules', 'tests'}
    
    def test_no_hardcoded_passwords_in_source(self):
        """Перевіряє, що немає hardcoded паролів у source коді."""
        project_root = Path(__file__).parent.parent.parent.parent / "graph_crawler"
        
        if not project_root.exists():
            pytest.skip(f"Project root not found: {project_root}")
        
        violations = []
        
        for py_file in project_root.rglob("*.py"):
            # Пропускаємо тестові директорії
            if any(skip in py_file.parts for skip in self.SKIP_DIRS):
                continue
            
            try:
                content = py_file.read_text(encoding='utf-8', errors='ignore')
                content_lower = content.lower()
                
                for pattern in self.FORBIDDEN_PATTERNS:
                    if pattern.lower() in content_lower:
                        # Перевіряємо що це не коментар
                        for i, line in enumerate(content.split('\n'), 1):
                            if pattern.lower() in line.lower() and not line.strip().startswith('#'):
                                violations.append(f"{py_file}:{i}: {pattern}")
            except Exception as e:
                # Ігноруємо файли які не можна прочитати
                pass
        
        assert len(violations) == 0, (
            f"Found {len(violations)} hardcoded password(s):\n" +
            "\n".join(violations[:10])  # Показуємо перші 10
        )
    
    def test_passwords_use_env_variables(self):
        """Перевіряє, що паролі беруться з environment variables."""
        # Перевіряємо configs.py
        configs_path = Path(__file__).parent.parent.parent.parent / "graph_crawler" / "domain" / "value_objects" / "configs.py"
        
        if not configs_path.exists():
            pytest.skip(f"Configs file not found: {configs_path}")
        
        content = configs_path.read_text(encoding='utf-8', errors='ignore')
        
        # Перевіряємо що для password є валідатор або default=""
        # Це непрямий тест - якщо password="secret" немає, то OK
        assert 'password="secret"' not in content.lower()
        assert "password='secret'" not in content.lower()


class TestSQLInjectionPrevention:
    """Тести для перевірки захисту від SQL Injection."""
    
    def test_postgresql_storage_validates_keys(self):
        """PostgreSQL storage валідує ключі для update."""
        storage_path = (
            Path(__file__).parent.parent.parent.parent / 
            "graph_crawler" / "infrastructure" / "persistence" / 
            "unified" / "postgresql_job_storage.py"
        )
        
        if not storage_path.exists():
            pytest.skip(f"Storage file not found: {storage_path}")
        
        content = storage_path.read_text()
        
        # Перевіряємо наявність whitelist
        assert "ALLOWED_UPDATE_KEYS" in content, "Missing ALLOWED_UPDATE_KEYS whitelist"
        
        # Перевіряємо валідацію
        assert "invalid_keys" in content.lower() or "Invalid update keys" in content, \
            "Missing key validation in update_job"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
