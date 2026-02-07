"""Session Manager - управління сесіями та cookies для різних доменів.

Team 3: Reliability & DevOps
Task 3.2: Session & Cookie Management (P0)
Week 2
"""

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)


class SessionManager:
    """
    Управління сесіями та cookies для HTTP crawling.

    Функціонал:
    - Збереження cookies між запитами
    - Automatic cookie refresh (перезавантаження застарілих cookies)
    - Session persistence (save/load на диск)
    - Multi-domain cookies (окрема сесія для кожного домену)
    - Session expiration handling

    Використання:
        manager = SessionManager(storage_path="./sessions")

        # Отримати сесію для домену
        session = manager.get_session("example.com")

        # Зберегти cookies після логіну
        manager.save_session("example.com")

        # Завантажити збережені cookies
        manager.load_session("example.com")

        # Очистити застарілі сесії
        manager.cleanup_expired_sessions(max_age_days=7)
    """

    def __init__(
        self,
        storage_path: str = "./sessions",
        default_headers: Optional[Dict[str, str]] = None,
        session_timeout_hours: int = 24,
    ):
        """
        Ініціалізує SessionManager.

        Args:
            storage_path: Шлях до директорії для збереження cookies
            default_headers: Дефолтні headers для всіх сесій
            session_timeout_hours: Час життя сесії в годинах (default: 24)
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.sessions: Dict[str, requests.Session] = {}  # domain → session
        self.session_metadata: Dict[str, dict] = {}  # domain → metadata
        self.default_headers = default_headers or {}
        self.session_timeout_hours = session_timeout_hours

        logger.info(f"SessionManager initialized with storage_path={storage_path}")

    def _extract_domain(self, url: str) -> str:
        """
        Витягує домен з URL.

        Args:
            url: URL або домен

        Returns:
            Домен (наприклад, "example.com")
        """
        if not url.startswith(("http://", "https://")):
            # Вже домен
            return url

        parsed = urlparse(url)
        return parsed.netloc

    def _create_session(self, domain: str) -> requests.Session:
        """
        Створює нову requests.Session для домену.

        Args:
            domain: Домен для якого створюється сесія

        Returns:
            Налаштована requests.Session
        """
        session = requests.Session()

        # Додаємо дефолтні headers
        session.headers.update(self.default_headers)

        logger.debug(f"Created new session for domain: {domain}")
        return session

    def get_session(self, url_or_domain: str) -> requests.Session:
        """
        Отримує або створює сесію для домену.

        Якщо сесія ще не існує - створює нову.
        Якщо існує - повертає існуючу (з збереженими cookies).

        Args:
            url_or_domain: URL або домен

        Returns:
            requests.Session для цього домену
        """
        domain = self._extract_domain(url_or_domain)

        if domain not in self.sessions:
            session = self._create_session(domain)
            self.sessions[domain] = session
            self.session_metadata[domain] = {
                "created_at": datetime.now().isoformat(),
                "last_used": datetime.now().isoformat(),
                "request_count": 0,
            }
            logger.info(f"New session created for domain: {domain}")
        else:
            # Оновлюємо метадані
            self.session_metadata[domain]["last_used"] = datetime.now().isoformat()
            self.session_metadata[domain]["request_count"] += 1

        return self.sessions[domain]

    def _get_session_file_path(self, domain: str) -> Path:
        """Повертає шлях до файлу сесії для домену."""
        # Замінюємо небезпечні символи в назві файлу
        safe_domain = domain.replace(":", "_").replace("/", "_")
        return self.storage_path / f"{safe_domain}.json"

    def save_session(self, url_or_domain: str) -> bool:
        """
        Зберігає cookies та метадані сесії на диск.

        Args:
            url_or_domain: URL або домен

        Returns:
            True якщо успішно збережено, False якщо помилка
        """
        domain = self._extract_domain(url_or_domain)

        if domain not in self.sessions:
            logger.warning(f"Session for domain {domain} does not exist, cannot save")
            return False

        try:
            session = self.sessions[domain]

            # Конвертуємо cookies в dict
            cookies_dict = dict(session.cookies)

            # Збираємо всі дані для збереження
            session_data = {
                "domain": domain,
                "cookies": cookies_dict,
                "headers": dict(session.headers),
                "metadata": self.session_metadata.get(domain, {}),
                "saved_at": datetime.now().isoformat(),
            }

            # Зберігаємо в JSON файл
            file_path = self._get_session_file_path(domain)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)

            logger.info(
                f"Session saved for domain: {domain} ({len(cookies_dict)} cookies)"
            )
            return True

        except Exception as e:
            logger.error(f"Error saving session for {domain}: {e}")
            return False

    def load_session(self, url_or_domain: str) -> bool:
        """
        Завантажує cookies та метадані сесії з диску.

        Args:
            url_or_domain: URL або домен

        Returns:
            True якщо успішно завантажено, False якщо файл не знайдено або помилка
        """
        domain = self._extract_domain(url_or_domain)
        file_path = self._get_session_file_path(domain)

        if not file_path.exists():
            logger.debug(f"Session file not found for domain: {domain}")
            return False

        try:
            # Завантажуємо дані з файлу
            with open(file_path, "r", encoding="utf-8") as f:
                session_data = json.load(f)

            # Перевіряємо чи не застаріла сесія
            saved_at = datetime.fromisoformat(session_data["saved_at"])
            age_hours = (datetime.now() - saved_at).total_seconds() / 3600

            if age_hours > self.session_timeout_hours:
                logger.warning(
                    f"Session for {domain} is expired "
                    f"(age: {age_hours:.1f}h, max: {self.session_timeout_hours}h)"
                )
                return False

            # Отримуємо або створюємо сесію
            session = self.get_session(domain)

            # Завантажуємо cookies
            cookies = session_data.get("cookies", {})
            for key, value in cookies.items():
                session.cookies.set(key, value)

            # Завантажуємо headers (крім дефолтних)
            headers = session_data.get("headers", {})
            session.headers.update(headers)

            # Завантажуємо метадані
            self.session_metadata[domain] = session_data.get("metadata", {})

            logger.info(f"Session loaded for domain: {domain} ({len(cookies)} cookies)")
            return True

        except Exception as e:
            logger.error(f"Error loading session for {domain}: {e}")
            return False

    def has_session(self, url_or_domain: str) -> bool:
        """
        Перевіряє чи існує сесія для домену.

        Args:
            url_or_domain: URL або домен

        Returns:
            True якщо сесія існує (в пам'яті або на диску)
        """
        domain = self._extract_domain(url_or_domain)

        # Перевіряємо в пам'яті
        if domain in self.sessions:
            return True

        # Перевіряємо на диску
        file_path = self._get_session_file_path(domain)
        return file_path.exists()

    def delete_session(self, url_or_domain: str) -> bool:
        """
        Видаляє сесію з пам'яті та диску.

        Args:
            url_or_domain: URL або домен

        Returns:
            True якщо успішно видалено
        """
        domain = self._extract_domain(url_or_domain)

        # Видаляємо з пам'яті
        if domain in self.sessions:
            self.sessions[domain].close()
            del self.sessions[domain]

        if domain in self.session_metadata:
            del self.session_metadata[domain]

        # Видаляємо файл
        file_path = self._get_session_file_path(domain)
        if file_path.exists():
            try:
                file_path.unlink()
                logger.info(f"Session deleted for domain: {domain}")
                return True
            except Exception as e:
                logger.error(f"Error deleting session file for {domain}: {e}")
                return False

        return True

    def cleanup_expired_sessions(self, max_age_days: int = 7) -> int:
        """
        Видаляє застарілі файли сесій з диску.

        Args:
            max_age_days: Максимальний вік файлу в днях

        Returns:
            Кількість видалених файлів
        """
        deleted_count = 0
        cutoff_time = datetime.now() - timedelta(days=max_age_days)

        try:
            for file_path in self.storage_path.glob("*.json"):
                try:
                    # Перевіряємо вік файлу
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)

                    if mtime < cutoff_time:
                        file_path.unlink()
                        deleted_count += 1
                        logger.debug(f"Deleted expired session file: {file_path.name}")

                except Exception as e:
                    logger.error(f"Error processing file {file_path}: {e}")
                    continue

            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} expired session files")

            return deleted_count

        except Exception as e:
            logger.error(f"Error during session cleanup: {e}")
            return deleted_count

    def get_all_domains(self) -> list:
        """
        Повертає список всіх доменів з активними сесіями.

        Returns:
            Список доменів
        """
        return list(self.sessions.keys())

    def get_session_info(self, url_or_domain: str) -> Optional[dict]:
        """
        Повертає інформацію про сесію.

        Args:
            url_or_domain: URL або домен

        Returns:
            Словник з інформацією про сесію або None
        """
        domain = self._extract_domain(url_or_domain)

        if domain not in self.sessions:
            return None

        session = self.sessions[domain]
        metadata = self.session_metadata.get(domain, {})

        return {
            "domain": domain,
            "cookies_count": len(session.cookies),
            "headers": dict(session.headers),
            "metadata": metadata,
        }

    def close_all(self):
        """Закриває всі активні сесії."""
        for domain, session in self.sessions.items():
            try:
                session.close()
                logger.debug(f"Closed session for domain: {domain}")
            except Exception as e:
                logger.error(f"Error closing session for {domain}: {e}")

        self.sessions.clear()
        self.session_metadata.clear()
        logger.info("All sessions closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - закриває всі сесії."""
        self.close_all()
        return False
