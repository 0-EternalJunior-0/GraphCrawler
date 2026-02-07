"""CaptchaBypassManager - менеджер стратегій обходу CAPTCHA."""

import hashlib
import logging
import pickle
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import requests

from graph_crawler.shared.utils.captcha.base import (
    BypassAttempt,
    BypassResult,
    BypassStrategy,
    SessionInfo,
)

logger = logging.getLogger(__name__)


class CaptchaBypassManager:
    """
    Менеджер для обходу CAPTCHA з різними стратегіями.

    Основні можливості:
    - Cookie persistence (зберігання cookies в файл)
    - Session reuse (переіспользування робочих сесій)
    - Delay strategy (очікування з exponential backoff)
    - Alternative endpoints (пошук API без CAPTCHA)
    - Rotating strategies (автоматична ротація стратегій)

    Example:
        >>> manager = CaptchaBypassManager(
        ...     cookie_storage_path="./cookies",
        ...     max_retry_attempts=3,
        ...     default_delay=5.0
        ... )
        >>> result = manager.try_bypass(url, strategy=BypassStrategy.COOKIE_PERSISTENCE)
    """

    def __init__(
        self,
        cookie_storage_path: Optional[str] = None,
        session_storage_path: Optional[str] = None,
        max_retry_attempts: int = 3,
        default_delay: float = 5.0,
        min_delay: float = 2.0,
        max_delay: float = 60.0,
        delay_multiplier: float = 2.0,
        session_max_age_hours: int = 24,
        captcha_solver_fallback: Optional[Callable] = None,
    ):
        """
        Ініціалізація менеджера обходу CAPTCHA.

        Args:
            cookie_storage_path: Шлях до папки для зберігання cookies
            session_storage_path: Шлях до папки для зберігання сесій
            max_retry_attempts: Максимальна кількість спроб обходу
            default_delay: Початкова затримка між спробами (секунди)
            min_delay: Мінімальна затримка (секунди)
            max_delay: Максимальна затримка (секунди)
            delay_multiplier: Множник для exponential backoff
            session_max_age_hours: Максимальний вік сесії (години)
            captcha_solver_fallback: Функція для розв'язання CAPTCHA
        """
        self.cookie_storage_path = Path(cookie_storage_path or "./cookies")
        self.session_storage_path = Path(session_storage_path or "./sessions")
        self.max_retry_attempts = max_retry_attempts
        self.default_delay = default_delay
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.delay_multiplier = delay_multiplier
        self.session_max_age_hours = session_max_age_hours
        self.captcha_solver_fallback = captcha_solver_fallback

        # Створення папок для зберігання
        self.cookie_storage_path.mkdir(parents=True, exist_ok=True)
        self.session_storage_path.mkdir(parents=True, exist_ok=True)

        # Статистика
        self.attempts: List[BypassAttempt] = []
        self.sessions: Dict[str, SessionInfo] = {}

        # Порядок стратегій для ротації
        self.strategy_order = [
            BypassStrategy.COOKIE_PERSISTENCE,
            BypassStrategy.SESSION_REUSE,
            BypassStrategy.DELAY_STRATEGY,
            BypassStrategy.ALTERNATIVE_ENDPOINTS,
        ]

        logger.info(f"CaptchaBypassManager ініціалізовано")

    def _get_domain_hash(self, url: str) -> str:
        """Створити хеш домену для імені файлу."""
        from urllib.parse import urlparse

        domain = urlparse(url).netloc
        return hashlib.md5(domain.encode()).hexdigest()

    def _get_cookie_file_path(self, url: str) -> Path:
        """Отримати шлях до файлу з cookies для домену."""
        domain_hash = self._get_domain_hash(url)
        return self.cookie_storage_path / f"{domain_hash}.cookies"

    def _get_session_file_path(self, url: str) -> Path:
        """Отримати шлях до файлу з session для домену."""
        domain_hash = self._get_domain_hash(url)
        return self.session_storage_path / f"{domain_hash}.session"

    def save_cookies(self, url: str, cookies: Dict[str, str]) -> None:
        """Зберегти cookies в файл."""
        cookie_file = self._get_cookie_file_path(url)
        try:
            with open(cookie_file, "wb") as f:
                pickle.dump(cookies, f)
            logger.info(f"Cookies збережено: {cookie_file}")
        except Exception as e:
            logger.error(f"Помилка збереження cookies: {e}")

    def load_cookies(self, url: str) -> Optional[Dict[str, str]]:
        """Завантажити cookies з файлу."""
        cookie_file = self._get_cookie_file_path(url)
        if not cookie_file.exists():
            return None
        try:
            with open(cookie_file, "rb") as f:
                return pickle.load(f)
        except Exception as e:
            logger.error(f"Помилка завантаження cookies: {e}")
            return None

    def save_session(self, url: str, session_info: SessionInfo) -> None:
        """Зберегти сесію в файл."""
        session_file = self._get_session_file_path(url)
        try:
            with open(session_file, "wb") as f:
                pickle.dump(session_info, f)
            logger.info(f"Session збережено: {session_file}")
        except Exception as e:
            logger.error(f"Помилка збереження session: {e}")

    def load_session(self, url: str) -> Optional[SessionInfo]:
        """Завантажити сесію з файлу."""
        session_file = self._get_session_file_path(url)
        if not session_file.exists():
            return None
        try:
            with open(session_file, "rb") as f:
                session_info = pickle.load(f)
            if session_info.is_expired(self.session_max_age_hours):
                session_file.unlink()
                return None
            return session_info
        except Exception as e:
            logger.error(f"Помилка завантаження session: {e}")
            return None

    def _detect_captcha_in_response(self, response: requests.Response) -> bool:
        """Виявлення CAPTCHA у відповіді."""
        captcha_indicators = [
            "captcha",
            "recaptcha",
            "hcaptcha",
            "cf-turnstile",
            "challenge-form",
            "g-recaptcha",
            "h-captcha",
        ]
        content = response.text.lower()
        return any(indicator in content for indicator in captcha_indicators)

    def try_bypass(
        self,
        url: str,
        strategy: BypassStrategy = BypassStrategy.ROTATING,
        **request_kwargs,
    ) -> BypassAttempt:
        """
        Спроба обходу CAPTCHA з вказаною стратегією.

        Args:
            url: URL для запиту
            strategy: Стратегія обходу
            **request_kwargs: Додаткові параметри для requests

        Returns:
            BypassAttempt з результатом
        """
        if strategy == BypassStrategy.COOKIE_PERSISTENCE:
            return self._try_cookie_persistence(url, **request_kwargs)
        elif strategy == BypassStrategy.SESSION_REUSE:
            return self._try_session_reuse(url, **request_kwargs)
        elif strategy == BypassStrategy.DELAY_STRATEGY:
            return self._try_delay_strategy(url, **request_kwargs)
        elif strategy == BypassStrategy.ALTERNATIVE_ENDPOINTS:
            return self._try_alternative_endpoints(url, **request_kwargs)
        elif strategy == BypassStrategy.ROTATING:
            return self.try_all_strategies(url, **request_kwargs)
        else:
            return BypassAttempt(
                strategy=strategy,
                result=BypassResult.FAILED,
                error_message=f"Unknown strategy: {strategy}",
            )

    def _try_cookie_persistence(self, url: str, **request_kwargs) -> BypassAttempt:
        """Спроба обходу через збережені cookies."""
        cookies = self.load_cookies(url)
        if not cookies:
            return BypassAttempt(
                strategy=BypassStrategy.COOKIE_PERSISTENCE,
                result=BypassResult.FAILED,
                error_message="No saved cookies found",
            )

        start_time = time.time()
        try:
            response = requests.get(url, cookies=cookies, timeout=30, **request_kwargs)
            response_time = time.time() - start_time

            has_captcha = self._detect_captcha_in_response(response)

            if not has_captcha and response.status_code == 200:
                return BypassAttempt(
                    strategy=BypassStrategy.COOKIE_PERSISTENCE,
                    result=BypassResult.SUCCESS,
                    response_status=response.status_code,
                    response_time=response_time,
                )
            else:
                return BypassAttempt(
                    strategy=BypassStrategy.COOKIE_PERSISTENCE,
                    result=BypassResult.CAPTCHA_STILL_PRESENT,
                    response_status=response.status_code,
                    response_time=response_time,
                )
        except Exception as e:
            return BypassAttempt(
                strategy=BypassStrategy.COOKIE_PERSISTENCE,
                result=BypassResult.FAILED,
                error_message=str(e),
            )

    def _try_session_reuse(self, url: str, **request_kwargs) -> BypassAttempt:
        """Спроба обходу через переіспользування сесії."""
        session_info = self.load_session(url)
        if not session_info:
            return BypassAttempt(
                strategy=BypassStrategy.SESSION_REUSE,
                result=BypassResult.FAILED,
                error_message="No saved session found",
            )

        start_time = time.time()
        try:
            response = requests.get(
                url,
                cookies=session_info.cookies,
                headers=session_info.headers,
                timeout=30,
                **request_kwargs,
            )
            response_time = time.time() - start_time

            has_captcha = self._detect_captcha_in_response(response)

            if not has_captcha and response.status_code == 200:
                session_info.last_used = datetime.now()
                session_info.success_count += 1
                self.save_session(url, session_info)
                return BypassAttempt(
                    strategy=BypassStrategy.SESSION_REUSE,
                    result=BypassResult.SUCCESS,
                    response_status=response.status_code,
                    response_time=response_time,
                )
            else:
                session_info.failure_count += 1
                self.save_session(url, session_info)
                return BypassAttempt(
                    strategy=BypassStrategy.SESSION_REUSE,
                    result=BypassResult.CAPTCHA_STILL_PRESENT,
                    response_status=response.status_code,
                    response_time=response_time,
                )
        except Exception as e:
            return BypassAttempt(
                strategy=BypassStrategy.SESSION_REUSE,
                result=BypassResult.FAILED,
                error_message=str(e),
            )

    def _try_delay_strategy(self, url: str, **request_kwargs) -> BypassAttempt:
        """Спроба обходу через очікування."""
        delay = self.default_delay

        for attempt in range(self.max_retry_attempts):
            time.sleep(delay)

            start_time = time.time()
            try:
                response = requests.get(url, timeout=30, **request_kwargs)
                response_time = time.time() - start_time

                has_captcha = self._detect_captcha_in_response(response)

                if not has_captcha and response.status_code == 200:
                    return BypassAttempt(
                        strategy=BypassStrategy.DELAY_STRATEGY,
                        result=BypassResult.SUCCESS,
                        response_status=response.status_code,
                        response_time=response_time,
                        metadata={"attempts": attempt + 1, "delay": delay},
                    )

                # Exponential backoff
                delay = min(delay * self.delay_multiplier, self.max_delay)

            except Exception as e:
                logger.warning(f"Delay strategy attempt {attempt + 1} failed: {e}")
                delay = min(delay * self.delay_multiplier, self.max_delay)

        return BypassAttempt(
            strategy=BypassStrategy.DELAY_STRATEGY,
            result=BypassResult.FAILED,
            error_message=f"Failed after {self.max_retry_attempts} attempts",
        )

    def _try_alternative_endpoints(self, url: str, **request_kwargs) -> BypassAttempt:
        """Спроба знайти альтернативні endpoints."""
        from urllib.parse import urljoin, urlparse

        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        # Список альтернативних шляхів
        alternative_paths = [
            "/api" + parsed.path,
            "/v1" + parsed.path,
            "/v2" + parsed.path,
            parsed.path + ".json",
            "/mobile" + parsed.path,
        ]

        for path in alternative_paths:
            alt_url = urljoin(base_url, path)
            try:
                response = requests.get(alt_url, timeout=10, **request_kwargs)
                has_captcha = self._detect_captcha_in_response(response)

                if not has_captcha and response.status_code == 200:
                    return BypassAttempt(
                        strategy=BypassStrategy.ALTERNATIVE_ENDPOINTS,
                        result=BypassResult.SUCCESS,
                        response_status=response.status_code,
                        metadata={"alternative_url": alt_url},
                    )
            except Exception:
                continue

        return BypassAttempt(
            strategy=BypassStrategy.ALTERNATIVE_ENDPOINTS,
            result=BypassResult.FAILED,
            error_message="No alternative endpoints found",
        )

    def try_all_strategies(self, url: str, **request_kwargs) -> BypassAttempt:
        """Спробувати всі стратегії по черзі."""
        for strategy in self.strategy_order:
            logger.info(f"Спроба стратегії: {strategy.value}")
            result = self.try_bypass(url, strategy, **request_kwargs)
            self.attempts.append(result)

            if result.result == BypassResult.SUCCESS:
                logger.info(f"Успіх з {strategy.value}!")
                return result

        # Всі стратегії не спрацювали - fallback до CAPTCHA solver
        if self.captcha_solver_fallback:
            logger.info("Використовуємо CAPTCHA solver fallback")
            try:
                self.captcha_solver_fallback(url)
                return BypassAttempt(
                    strategy=BypassStrategy.ROTATING,
                    result=BypassResult.SUCCESS,
                    metadata={"method": "captcha_solver_fallback"},
                )
            except Exception as e:
                logger.error(f"CAPTCHA solver fallback failed: {e}")

        return BypassAttempt(
            strategy=BypassStrategy.ROTATING,
            result=BypassResult.FAILED,
            error_message="All strategies failed",
        )

    def get_summary(self) -> Dict[str, Any]:
        """Отримати статистику спроб обходу."""
        total = len(self.attempts)
        successful = sum(1 for a in self.attempts if a.result == BypassResult.SUCCESS)

        by_strategy = {}
        for strategy in BypassStrategy:
            strategy_attempts = [a for a in self.attempts if a.strategy == strategy]
            if strategy_attempts:
                by_strategy[strategy.value] = {
                    "total": len(strategy_attempts),
                    "successful": sum(
                        1 for a in strategy_attempts if a.result == BypassResult.SUCCESS
                    ),
                }

        return {
            "total_attempts": total,
            "successful": successful,
            "success_rate": (successful / total * 100) if total > 0 else 0,
            "by_strategy": by_strategy,
        }
