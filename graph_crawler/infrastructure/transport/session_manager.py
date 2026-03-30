"""Session Manager - управління сесіями та cookies для різних доменів.

Team 3: Reliability & DevOps
Week 2

ВИПРАВЛЕНО: Замінено requests на httpx для async HTTP запитів.
Додано async методи та підтримку httpx.AsyncClient.
"""

import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Dict, Optional, Union
from urllib.parse import urlparse

try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

try:
    import aiohttp

    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

# Fallback to requests for sync operations
import requests

logger = logging.getLogger(__name__)

# Thread pool для неблокуючих операцій
_session_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="session_mgr_")


class SessionManager:
    """
    Управління сесіями та cookies для HTTP crawling.

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

        logger.info("SessionManager initialized with storage_path=%s", storage_path)

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

        logger.debug("Created new session for domain: %s", domain)
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
            logger.info("New session created for domain: %s", domain)
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
            logger.warning("Session for domain %s does not exist, cannot save", domain)
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

            logger.info("Session saved for domain: %s (%s cookies)", domain, len(cookies_dict))
            return True

        except Exception as e:
            logger.error("Error saving session for %s: %s", domain, e)
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
            logger.debug("Session file not found for domain: %s", domain)
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

            logger.info("Session loaded for domain: %s (%s cookies)", domain, len(cookies))
            return True

        except Exception as e:
            logger.error("Error loading session for %s: %s", domain, e)
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
                logger.info("Session deleted for domain: %s", domain)
                return True
            except Exception as e:
                logger.error("Error deleting session file for %s: %s", domain, e)
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
                        logger.debug("Deleted expired session file: %s", file_path.name)

                except Exception as e:
                    logger.error("Error processing file %s: %s", file_path, e)
                    continue

            if deleted_count > 0:
                logger.info("Cleaned up %s expired session files", deleted_count)

            return deleted_count

        except Exception as e:
            logger.error("Error during session cleanup: %s", e)
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
                logger.debug("Closed session for domain: %s", domain)
            except Exception as e:
                logger.error("Error closing session for %s: %s", domain, e)

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

    async def get_async_client(self, url_or_domain: str) -> "httpx.AsyncClient":
        """
        Отримує або створює async HTTP client (httpx.AsyncClient) для домену.

        Використовує httpx для async HTTP запитів замість requests.

        Args:
            url_or_domain: URL або домен

        Returns:
            httpx.AsyncClient для цього домену

        Raises:
            ImportError: Якщо httpx не встановлено
        """
        if not HTTPX_AVAILABLE:
            raise ImportError(
                "httpx is required for async operations. Install with: pip install httpx"
            )

        domain = self._extract_domain(url_or_domain)

        if not hasattr(self, "_async_clients"):
            self._async_clients: Dict[str, httpx.AsyncClient] = {}

        if domain not in self._async_clients:
            # Створюємо новий async client
            client = httpx.AsyncClient(
                headers=self.default_headers,
                timeout=httpx.Timeout(30.0),
                follow_redirects=True,
            )

            # Завантажуємо cookies якщо є збережені
            if self.has_session(domain):
                await self._load_cookies_to_async_client(client, domain)

            self._async_clients[domain] = client

            if domain not in self.session_metadata:
                self.session_metadata[domain] = {
                    "created_at": datetime.now().isoformat(),
                    "last_used": datetime.now().isoformat(),
                    "request_count": 0,
                    "client_type": "httpx",
                }

            logger.info("New async client (httpx) created for domain: %s", domain)
        else:
            # Оновлюємо метадані
            self.session_metadata[domain]["last_used"] = datetime.now().isoformat()
            self.session_metadata[domain]["request_count"] += 1

        return self._async_clients[domain]

    async def _load_cookies_to_async_client(self, client: "httpx.AsyncClient", domain: str) -> None:
        """Завантажує збережені cookies в async client."""
        file_path = self._get_session_file_path(domain)

        if not file_path.exists():
            return

        try:
            loop = asyncio.get_event_loop()
            session_data = await loop.run_in_executor(
                _session_executor, partial(self._sync_read_json_file, file_path)
            )

            cookies = session_data.get("cookies", {})
            for key, value in cookies.items():
                client.cookies.set(key, value, domain=domain)

            logger.debug("Loaded %s cookies to async client for %s", len(cookies), domain)

        except Exception as e:
            logger.warning("Failed to load cookies for async client: %s", e)

    async def save_async_client_cookies(self, url_or_domain: str) -> bool:
        """
        Зберігає cookies з async client на диск.

        Args:
            url_or_domain: URL або домен

        Returns:
            True якщо успішно збережено
        """
        domain = self._extract_domain(url_or_domain)

        if not hasattr(self, "_async_clients") or domain not in self._async_clients:
            logger.warning("No async client for domain %s", domain)
            return False

        try:
            client = self._async_clients[domain]

            # Конвертуємо cookies в dict
            cookies_dict = dict(client.cookies)

            session_data = {
                "domain": domain,
                "cookies": cookies_dict,
                "headers": dict(client.headers),
                "metadata": self.session_metadata.get(domain, {}),
                "saved_at": datetime.now().isoformat(),
                "client_type": "httpx",
            }

            file_path = self._get_session_file_path(domain)

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                _session_executor, partial(self._sync_write_json_file, file_path, session_data)
            )

            logger.info("Async client cookies saved for domain: %s", domain)
            return True

        except Exception as e:
            logger.error("Error saving async client cookies for %s: %s", domain, e)
            return False

    async def close_async_client(self, url_or_domain: str) -> None:
        """Закриває async client для домену."""
        domain = self._extract_domain(url_or_domain)

        if hasattr(self, "_async_clients") and domain in self._async_clients:
            await self._async_clients[domain].aclose()
            del self._async_clients[domain]
            logger.debug("Closed async client for domain: %s", domain)

    async def close_all_async(self) -> None:
        """Закриває всі async clients."""
        if hasattr(self, "_async_clients"):
            for domain, client in list(self._async_clients.items()):
                try:
                    await client.aclose()
                    logger.debug("Closed async client for domain: %s", domain)
                except Exception as e:
                    logger.error("Error closing async client for %s: %s", domain, e)

            self._async_clients.clear()
            logger.info("All async clients closed")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - закриває всі async clients."""
        await self.close_all_async()
        self.close_all()
        return False

    @staticmethod
    def _sync_read_json_file(file_path: Path) -> Dict:
        """Синхронне читання JSON файлу."""
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _sync_write_json_file(file_path: Path, data: Dict) -> None:
        """Синхронний запис JSON файлу."""
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
