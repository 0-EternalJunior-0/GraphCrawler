"""
CAPTCHA Bypass Strategies.

Цей модуль надає різні стратегії для спроби обійти CAPTCHA без використання
платних сервісів розв'язання. Якщо всі стратегії не спрацювали, можна
використовувати fallback на CAPTCHA solver.

Strategies:
1. Cookie Persistence - зберігання cookies між запитами
2. Session Reuse - переіспользування сесій
3. Delay Strategy - очікування перед повторною спробою
4. Alternative Endpoints - пошук API endpoints без CAPTCHA
5. Rotating Strategies - спроба різних підходів по черзі
"""

import hashlib
import json
import logging
import pickle
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class BypassStrategy(str, Enum):
    """Стратегії обходу CAPTCHA."""

    COOKIE_PERSISTENCE = "cookie_persistence"  # Зберігання cookies
    SESSION_REUSE = "session_reuse"  # Переіспользування сесій
    DELAY_STRATEGY = "delay_strategy"  # Очікування
    ALTERNATIVE_ENDPOINTS = "alternative_endpoints"  # Альтернативні endpoints
    ROTATING = "rotating"  # Ротація різних стратегій


class BypassResult(str, Enum):
    """Результати спроби обходу."""

    SUCCESS = "success"  # Успішно обійшли
    FAILED = "failed"  # Не вдалося обійти
    CAPTCHA_STILL_PRESENT = "captcha_still_present"  # CAPTCHA все ще є
    RETRY_NEEDED = "retry_needed"  # Потрібна повторна спроба


@dataclass
class BypassAttempt:
    """Результат спроби обходу CAPTCHA."""

    strategy: BypassStrategy
    result: BypassResult
    timestamp: datetime = field(default_factory=datetime.now)
    response_status: Optional[int] = None
    response_time: Optional[float] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionInfo:
    """Інформація про збережену сесію."""

    url: str
    cookies: Dict[str, str]
    headers: Dict[str, str]
    created_at: datetime
    last_used: datetime
    success_count: int = 0
    failure_count: int = 0

    def is_expired(self, max_age_hours: int = 24) -> bool:
        """Перевірка чи сесія прострочена."""
        age = datetime.now() - self.created_at
        return age > timedelta(hours=max_age_hours)

    @property
    def success_rate(self) -> float:
        """Відсоток успішних запитів."""
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.0
        return (self.success_count / total) * 100


class CaptchaBypassManager:
    """
    Менеджер для обходу CAPTCHA з різними стратегіями.

    Основні можливості:
    - Cookie persistence (зберігання cookies в файл)
    - Session reuse (переіспользування робочих сесій)
    - Delay strategy (очікування з exponential backoff)
    - Alternative endpoints (пошук API без CAPTCHA)
    - Rotating strategies (автоматична ротація стратегій)

    Приклад використання:
        ```python
        from graph_crawler.shared.utils import CaptchaBypassManager, BypassStrategy

        # Ініціалізація
        bypass_manager = CaptchaBypassManager(
            cookie_storage_path="./cookies",
            max_retry_attempts=3,
            default_delay=5.0
        )

        # Спроба обійти CAPTCHA
        url = "https://example.com/page"
        result = bypass_manager.try_bypass(
            url=url,
            strategy=BypassStrategy.COOKIE_PERSISTENCE
        )

        if result.result == BypassResult.SUCCESS:
            print("CAPTCHA обійдена!")
        else:
            print(" Потрібен CAPTCHA solver")

        # Ротація стратегій (автоматичний вибір)
        result = bypass_manager.try_all_strategies(url)

        # Статистика
        print(bypass_manager.get_summary())
        ```
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
            captcha_solver_fallback: Функція для розв'язання CAPTCHA якщо bypass не вдався
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

        logger.info(
            f"CaptchaBypassManager ініціалізовано: cookie_path={self.cookie_storage_path}, session_path={self.session_storage_path}"
        )

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
        """
        Зберегти cookies в файл.

        Args:
            url: URL домену
            cookies: Dictionary з cookies
        """
        cookie_file = self._get_cookie_file_path(url)
        try:
            with open(cookie_file, "wb") as f:
                pickle.dump(cookies, f)
            logger.info(f" Cookies збережено: {cookie_file}")
        except Exception as e:
            logger.error(f" Помилка збереження cookies: {e}")

    def load_cookies(self, url: str) -> Optional[Dict[str, str]]:
        """
        Завантажити cookies з файлу.

        Args:
            url: URL домену

        Returns:
            Dictionary з cookies або None якщо файл не існує
        """
        cookie_file = self._get_cookie_file_path(url)
        if not cookie_file.exists():
            logger.debug(f" Cookies не знайдено: {cookie_file}")
            return None

        try:
            with open(cookie_file, "rb") as f:
                cookies = pickle.load(f)
            logger.info(f" Cookies завантажено: {cookie_file} ({len(cookies)} items)")
            return cookies
        except Exception as e:
            logger.error(f" Помилка завантаження cookies: {e}")
            return None

    def save_session(self, url: str, session_info: SessionInfo) -> None:
        """
        Зберегти сесію в файл.

        Args:
            url: URL домену
            session_info: Інформація про сесію
        """
        session_file = self._get_session_file_path(url)
        try:
            with open(session_file, "wb") as f:
                pickle.dump(session_info, f)
            logger.info(f" Session збережено: {session_file}")
        except Exception as e:
            logger.error(f" Помилка збереження session: {e}")

    def load_session(self, url: str) -> Optional[SessionInfo]:
        """
        Завантажити сесію з файлу.

        Args:
            url: URL домену

        Returns:
            SessionInfo або None якщо файл не існує або сесія прострочена
        """
        session_file = self._get_session_file_path(url)
        if not session_file.exists():
            logger.debug(f" Session не знайдено: {session_file}")
            return None

        try:
            with open(session_file, "rb") as f:
                session_info = pickle.load(f)

            # Перевірка чи не прострочена сесія
            if session_info.is_expired(self.session_max_age_hours):
                logger.warning(f"⏰ Session прострочена: {session_file}")
                session_file.unlink()  # Видалити прострочену сесію
                return None

            logger.info(
                f" Session завантажено: {session_file} (success_rate={session_info.success_rate:.1f}%)"
            )
            return session_info
        except Exception as e:
            logger.error(f" Помилка завантаження session: {e}")
            return None

    def try_cookie_persistence(self, url: str, **request_kwargs) -> BypassAttempt:
        """
        Спроба обходу через збережені cookies.

        Args:
            url: URL для запиту
            **request_kwargs: Додаткові параметри для requests

        Returns:
            BypassAttempt з результатом
        """
        logger.info(f" Спроба обходу через Cookie Persistence: {url}")

        # Завантажити збережені cookies
        cookies = self.load_cookies(url)
        if not cookies:
            return BypassAttempt(
                strategy=BypassStrategy.COOKIE_PERSISTENCE,
                result=BypassResult.FAILED,
                error_message="No saved cookies found",
            )

        # Спроба запиту з cookies
        start_time = time.time()
        try:
            response = requests.get(url, cookies=cookies, timeout=30, **request_kwargs)
            response_time = time.time() - start_time

            # Перевірка чи є CAPTCHA в response
            has_captcha = self._detect_captcha_in_response(response)

            if not has_captcha and response.status_code == 200:
                logger.info(f"Cookie Persistence успішно: {url}")
                return BypassAttempt(
                    strategy=BypassStrategy.COOKIE_PERSISTENCE,
                    result=BypassResult.SUCCESS,
                    response_status=response.status_code,
                    response_time=response_time,
                    metadata={"cookies_count": len(cookies)},
                )
            else:
                logger.warning(f" CAPTCHA все ще присутня після Cookie Persistence")
                return BypassAttempt(
                    strategy=BypassStrategy.COOKIE_PERSISTENCE,
                    result=BypassResult.CAPTCHA_STILL_PRESENT,
                    response_status=response.status_code,
                    response_time=response_time,
                )

        except Exception as e:
            logger.error(f" Помилка Cookie Persistence: {e}")
            return BypassAttempt(
                strategy=BypassStrategy.COOKIE_PERSISTENCE,
                result=BypassResult.FAILED,
                error_message=str(e),
            )

    def try_session_reuse(self, url: str, **request_kwargs) -> BypassAttempt:
        """
        Спроба обходу через переіспользування сесії.

        Args:
            url: URL для запиту
            **request_kwargs: Додаткові параметри для requests

        Returns:
            BypassAttempt з результатом
        """
        logger.info(f" Спроба обходу через Session Reuse: {url}")

        # Завантажити збережену сесію
        session_info = self.load_session(url)
        if not session_info:
            return BypassAttempt(
                strategy=BypassStrategy.SESSION_REUSE,
                result=BypassResult.FAILED,
                error_message="No saved session found or session expired",
            )

        # Спроба запиту з session headers та cookies
        start_time = time.time()
        try:
            headers = {**session_info.headers, **request_kwargs.get("headers", {})}
            response = requests.get(
                url,
                cookies=session_info.cookies,
                headers=headers,
                timeout=30,
                **{k: v for k, v in request_kwargs.items() if k != "headers"},
            )
            response_time = time.time() - start_time

            # Перевірка чи є CAPTCHA
            has_captcha = self._detect_captcha_in_response(response)

            if not has_captcha and response.status_code == 200:
                logger.info(f"Session Reuse успішно: {url}")
                # Оновити статистику сесії
                session_info.last_used = datetime.now()
                session_info.success_count += 1
                self.save_session(url, session_info)

                return BypassAttempt(
                    strategy=BypassStrategy.SESSION_REUSE,
                    result=BypassResult.SUCCESS,
                    response_status=response.status_code,
                    response_time=response_time,
                    metadata={"session_success_rate": session_info.success_rate},
                )
            else:
                logger.warning(f" CAPTCHA все ще присутня після Session Reuse")
                # Оновити статистику
                session_info.failure_count += 1
                self.save_session(url, session_info)

                return BypassAttempt(
                    strategy=BypassStrategy.SESSION_REUSE,
                    result=BypassResult.CAPTCHA_STILL_PRESENT,
                    response_status=response.status_code,
                    response_time=response_time,
                )

        except Exception as e:
            logger.error(f" Помилка Session Reuse: {e}")
            return BypassAttempt(
                strategy=BypassStrategy.SESSION_REUSE,
                result=BypassResult.FAILED,
                error_message=str(e),
            )

    def try_delay_strategy(
        self, url: str, retry_count: int = 0, **request_kwargs
    ) -> BypassAttempt:
        """
        Спроба обходу через очікування (delay with exponential backoff).

        Іноді CAPTCHA автоматично зникає після очікування.

        Args:
            url: URL для запиту
            retry_count: Номер поточної спроби (для backoff)
            **request_kwargs: Додаткові параметри для requests

        Returns:
            BypassAttempt з результатом
        """
        # Розрахувати затримку (exponential backoff)
        delay = min(
            self.default_delay * (self.delay_multiplier**retry_count), self.max_delay
        )
        delay = max(delay, self.min_delay)

        logger.info(
            f"⏰ Спроба обходу через Delay Strategy: {url} (delay={delay:.1f}s, attempt={retry_count + 1})"
        )

        # Очікування
        time.sleep(delay)

        # Спроба запиту після затримки
        start_time = time.time()
        try:
            response = requests.get(url, timeout=30, **request_kwargs)
            response_time = time.time() - start_time

            # Перевірка чи є CAPTCHA
            has_captcha = self._detect_captcha_in_response(response)

            if not has_captcha and response.status_code == 200:
                logger.info(f"Delay Strategy успішно після {delay:.1f}s очікування")
                return BypassAttempt(
                    strategy=BypassStrategy.DELAY_STRATEGY,
                    result=BypassResult.SUCCESS,
                    response_status=response.status_code,
                    response_time=response_time,
                    metadata={"delay_seconds": delay, "retry_count": retry_count},
                )
            else:
                logger.warning(
                    f" CAPTCHA все ще присутня після {delay:.1f}s очікування"
                )

                # Перевірити чи потрібна повторна спроба
                if retry_count < self.max_retry_attempts - 1:
                    return BypassAttempt(
                        strategy=BypassStrategy.DELAY_STRATEGY,
                        result=BypassResult.RETRY_NEEDED,
                        response_status=response.status_code,
                        response_time=response_time,
                        metadata={"delay_seconds": delay, "retry_count": retry_count},
                    )
                else:
                    return BypassAttempt(
                        strategy=BypassStrategy.DELAY_STRATEGY,
                        result=BypassResult.CAPTCHA_STILL_PRESENT,
                        response_status=response.status_code,
                        response_time=response_time,
                        metadata={"delay_seconds": delay, "retry_count": retry_count},
                    )

        except Exception as e:
            logger.error(f" Помилка Delay Strategy: {e}")
            return BypassAttempt(
                strategy=BypassStrategy.DELAY_STRATEGY,
                result=BypassResult.FAILED,
                error_message=str(e),
                metadata={"delay_seconds": delay, "retry_count": retry_count},
            )

    def try_alternative_endpoints(
        self, url: str, alternative_urls: Optional[List[str]] = None, **request_kwargs
    ) -> BypassAttempt:
        """
        Спроба обходу через альтернативні endpoints (API без CAPTCHA).

        Деякі сайти мають API endpoints які не захищені CAPTCHA.

        Args:
            url: Основний URL
            alternative_urls: Список альтернативних URL для спроби
            **request_kwargs: Додаткові параметри для requests

        Returns:
            BypassAttempt з результатом
        """
        logger.info(f" Спроба обходу через Alternative Endpoints: {url}")

        # Якщо не надано альтернативи, спробуємо згенерувати
        if not alternative_urls:
            alternative_urls = self._generate_alternative_urls(url)

        if not alternative_urls:
            return BypassAttempt(
                strategy=BypassStrategy.ALTERNATIVE_ENDPOINTS,
                result=BypassResult.FAILED,
                error_message="No alternative endpoints found",
            )

        # Спроба кожного альтернативного URL
        for alt_url in alternative_urls:
            logger.info(f" Спроба альтернативного endpoint: {alt_url}")
            start_time = time.time()

            try:
                response = requests.get(alt_url, timeout=30, **request_kwargs)
                response_time = time.time() - start_time

                # Перевірка чи є CAPTCHA
                has_captcha = self._detect_captcha_in_response(response)

                if not has_captcha and response.status_code == 200:
                    logger.info(f"Alternative Endpoint успішно: {alt_url}")
                    return BypassAttempt(
                        strategy=BypassStrategy.ALTERNATIVE_ENDPOINTS,
                        result=BypassResult.SUCCESS,
                        response_status=response.status_code,
                        response_time=response_time,
                        metadata={
                            "alternative_url": alt_url,
                            "tried_urls": alternative_urls,
                        },
                    )

            except Exception as e:
                logger.debug(f" Альтернативний endpoint не спрацював: {alt_url} - {e}")
                continue

        logger.warning(f" Жоден альтернативний endpoint не спрацював")
        return BypassAttempt(
            strategy=BypassStrategy.ALTERNATIVE_ENDPOINTS,
            result=BypassResult.FAILED,
            error_message="All alternative endpoints failed",
            metadata={"tried_urls": alternative_urls},
        )

    def try_bypass(
        self,
        url: str,
        strategy: BypassStrategy = BypassStrategy.COOKIE_PERSISTENCE,
        **request_kwargs,
    ) -> BypassAttempt:
        """
        Спроба обходу CAPTCHA використовуючи вказану стратегію.

        Args:
            url: URL для запиту
            strategy: Стратегія обходу
            **request_kwargs: Додаткові параметри для requests

        Returns:
            BypassAttempt з результатом
        """
        attempt = None

        if strategy == BypassStrategy.COOKIE_PERSISTENCE:
            attempt = self.try_cookie_persistence(url, **request_kwargs)
        elif strategy == BypassStrategy.SESSION_REUSE:
            attempt = self.try_session_reuse(url, **request_kwargs)
        elif strategy == BypassStrategy.DELAY_STRATEGY:
            attempt = self.try_delay_strategy(url, **request_kwargs)
        elif strategy == BypassStrategy.ALTERNATIVE_ENDPOINTS:
            attempt = self.try_alternative_endpoints(url, **request_kwargs)
        else:
            logger.error(f" Невідома стратегія: {strategy}")
            attempt = BypassAttempt(
                strategy=strategy,
                result=BypassResult.FAILED,
                error_message=f"Unknown strategy: {strategy}",
            )

        # Зберегти спробу в історію
        self.attempts.append(attempt)

        return attempt

    def try_all_strategies(
        self,
        url: str,
        strategies: Optional[List[BypassStrategy]] = None,
        **request_kwargs,
    ) -> BypassAttempt:
        """
        Спроба обходу CAPTCHA використовуючи всі доступні стратегії по черзі.

        Args:
            url: URL для запиту
            strategies: Список стратегій (за замовчуванням використовує всі)
            **request_kwargs: Додаткові параметри для requests

        Returns:
            BypassAttempt з результатом першої успішної стратегії або останньої невдалої
        """
        logger.info(f" Спроба всіх стратегій обходу для: {url}")

        strategies = strategies or self.strategy_order
        last_attempt = None

        for strategy in strategies:
            attempt = self.try_bypass(url, strategy=strategy, **request_kwargs)
            last_attempt = attempt

            # Якщо успішно - повертаємо результат
            if attempt.result == BypassResult.SUCCESS:
                logger.info(f"Успішний bypass через {strategy}")
                return attempt

            # Якщо потрібна повторна спроба (Delay Strategy)
            if attempt.result == BypassResult.RETRY_NEEDED:
                for retry in range(1, self.max_retry_attempts):
                    attempt = self.try_delay_strategy(
                        url, retry_count=retry, **request_kwargs
                    )
                    last_attempt = attempt
                    self.attempts.append(attempt)

                    if attempt.result == BypassResult.SUCCESS:
                        logger.info(
                            f"Успішний bypass через Delay Strategy після {retry + 1} спроб"
                        )
                        return attempt

        # Якщо жодна стратегія не спрацювала
        logger.warning(f" Всі стратегії обходу не спрацювали для {url}")

        # Fallback на CAPTCHA solver якщо є
        if self.captcha_solver_fallback:
            logger.info(f" Використовую CAPTCHA solver fallback")
            try:
                solver_result = self.captcha_solver_fallback(url, **request_kwargs)
                return BypassAttempt(
                    strategy=BypassStrategy.ROTATING,
                    result=(
                        BypassResult.SUCCESS if solver_result else BypassResult.FAILED
                    ),
                    metadata={"used_solver": True, "solver_result": solver_result},
                )
            except Exception as e:
                logger.error(f" CAPTCHA solver fallback помилка: {e}")

        return last_attempt or BypassAttempt(
            strategy=BypassStrategy.ROTATING,
            result=BypassResult.FAILED,
            error_message="All strategies failed",
        )

    def _detect_captcha_in_response(self, response: requests.Response) -> bool:
        """
        Простий детектор CAPTCHA в response.

        Шукає ключові слова: captcha, recaptcha, hcaptcha

        Args:
            response: requests.Response об'єкт

        Returns:
            True якщо CAPTCHA виявлена, False інакше
        """
        content = response.text.lower()

        # Ключові слова CAPTCHA
        captcha_keywords = [
            "captcha",
            "recaptcha",
            "hcaptcha",
            "g-recaptcha",
            "h-captcha",
            "cf-captcha",  # Cloudflare
            "challenge-form",
        ]

        for keyword in captcha_keywords:
            if keyword in content:
                logger.debug(f" CAPTCHA виявлено: keyword='{keyword}'")
                return True

        # Перевірка специфічних status codes
        if response.status_code in [403, 429, 503]:
            logger.debug(f" CAPTCHA можлива: status_code={response.status_code}")
            # Додаткова перевірка в тексті
            if any(
                kw in content
                for kw in ["blocked", "access denied", "too many requests"]
            ):
                return True

        return False

    def _generate_alternative_urls(self, url: str) -> List[str]:
        """
        Згенерувати альтернативні URLs (API endpoints) для спроби.

        Args:
            url: Основний URL

        Returns:
            Список альтернативних URLs
        """
        from urllib.parse import urlparse, urlunparse

        parsed = urlparse(url)
        alternatives = []

        # Спроба додати /api/ prefix
        if "/api/" not in parsed.path:
            new_path = "/api" + parsed.path
            alt_url = urlunparse((parsed.scheme, parsed.netloc, new_path, "", "", ""))
            alternatives.append(alt_url)

        # Спроба змінити розширення на .json
        if not parsed.path.endswith(".json"):
            new_path = parsed.path.rstrip("/") + ".json"
            alt_url = urlunparse((parsed.scheme, parsed.netloc, new_path, "", "", ""))
            alternatives.append(alt_url)

        # Спроба додати /v1/ або /v2/
        for version in ["v1", "v2", "v3"]:
            if f"/{version}/" not in parsed.path:
                new_path = f"/{version}" + parsed.path
                alt_url = urlunparse(
                    (parsed.scheme, parsed.netloc, new_path, "", "", "")
                )
                alternatives.append(alt_url)

        logger.debug(f" Згенеровано {len(alternatives)} альтернативних URLs")
        return alternatives

    def get_statistics(self) -> Dict[str, Any]:
        """
        Отримати статистику спроб обходу.

        Returns:
            Dictionary зі статистикою
        """
        if not self.attempts:
            return {
                "total_attempts": 0,
                "success_count": 0,
                "failed_count": 0,
                "success_rate": 0.0,
                "by_strategy": {},
            }

        total = len(self.attempts)
        success_count = sum(
            1 for a in self.attempts if a.result == BypassResult.SUCCESS
        )
        failed_count = sum(1 for a in self.attempts if a.result == BypassResult.FAILED)

        # Статистика по стратегіях
        by_strategy = {}
        for strategy in BypassStrategy:
            strategy_attempts = [a for a in self.attempts if a.strategy == strategy]
            if strategy_attempts:
                strategy_success = sum(
                    1 for a in strategy_attempts if a.result == BypassResult.SUCCESS
                )
                by_strategy[strategy.value] = {
                    "total": len(strategy_attempts),
                    "success": strategy_success,
                    "failed": len(strategy_attempts) - strategy_success,
                    "success_rate": (strategy_success / len(strategy_attempts)) * 100,
                }

        return {
            "total_attempts": total,
            "success_count": success_count,
            "failed_count": failed_count,
            "success_rate": (success_count / total) * 100 if total > 0 else 0.0,
            "by_strategy": by_strategy,
        }

    def get_summary(self) -> str:
        """
        Отримати текстовий звіт про роботу bypass manager.

        Returns:
            Відформатований текстовий звіт
        """
        stats = self.get_statistics()

        summary = [
            "\n" + "=" * 60,
            " CAPTCHA Bypass Manager - Статистика",
            "=" * 60,
            f" Загальна кількість спроб: {stats['total_attempts']}",
            f"Успішних обходів: {stats['success_count']}",
            f" Невдалих спроб: {stats['failed_count']}",
            f" Success Rate: {stats['success_rate']:.1f}%",
            "\n" + "-" * 60,
            " Статистика по стратегіях:",
            "-" * 60,
        ]

        for strategy, strategy_stats in stats["by_strategy"].items():
            summary.append(
                f"  • {strategy}:\n"
                f"    - Спроб: {strategy_stats['total']}\n"
                f"    - Успішних: {strategy_stats['success']}\n"
                f"    - Невдалих: {strategy_stats['failed']}\n"
                f"    - Success Rate: {strategy_stats['success_rate']:.1f}%"
            )

        summary.append("=" * 60)

        return "\n".join(summary)


def create_captcha_bypass_manager(
    cookie_storage_path: Optional[str] = None,
    session_storage_path: Optional[str] = None,
    max_retry_attempts: int = 3,
    captcha_solver_fallback: Optional[Callable] = None,
) -> CaptchaBypassManager:
    """
    Factory функція для швидкого створення CaptchaBypassManager.

    Args:
        cookie_storage_path: Шлях до папки для cookies
        session_storage_path: Шлях до папки для sessions
        max_retry_attempts: Максимальна кількість спроб
        captcha_solver_fallback: Функція для CAPTCHA solver

    Returns:
        Налаштований CaptchaBypassManager

    Example:
        ```python
        from graph_crawler.shared.utils import create_captcha_bypass_manager

        bypass_manager = create_captcha_bypass_manager(
            cookie_storage_path="./cookies",
            max_retry_attempts=5
        )

        result = bypass_manager.try_all_strategies("https://example.com")
        print(result.result)
        ```
    """
    return CaptchaBypassManager(
        cookie_storage_path=cookie_storage_path,
        session_storage_path=session_storage_path,
        max_retry_attempts=max_retry_attempts,
        captcha_solver_fallback=captcha_solver_fallback,
    )
