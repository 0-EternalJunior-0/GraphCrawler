"""CaptchaSolverPlugin - основний plugin для розв'язання CAPTCHA.

Інтегрується з різними CAPTCHA solving сервісами.
"""

import logging
from typing import Any, Dict, List, Optional

from graph_crawler.extensions.plugins.base import BasePlugin, PluginContext, PluginType
from graph_crawler.extensions.plugins.engine.captcha.detector import CaptchaDetector
from graph_crawler.extensions.plugins.engine.captcha.models import (
    CaptchaInfo,
    CaptchaService,
    CaptchaSolution,
)
from graph_crawler.extensions.plugins.engine.captcha.services import create_solver

logger = logging.getLogger(__name__)


class CaptchaSolverPlugin(BasePlugin):
    """
    Plugin для розв'язання CAPTCHA через зовнішні сервіси.

    Config:
        service: Назва сервісу ("2captcha", "anticaptcha", "capsolver")
        api_key: API ключ
        auto_detect: Автоматично визначати CAPTCHA (default: True)
        solve_timeout: Таймаут розв'язання (default: 120)
        fallback_services: Список fallback сервісів
        fallback_keys: Словник API ключів для fallback
        track_cost: Відстежувати вартість (default: True)
        min_score: Мінімальний score для reCAPTCHA v3 (default: 0.3)
    """

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.total_solved = 0
        self.total_failed = 0
        self.total_cost = 0.0
        self.solve_times: List[float] = []
        self._solver = None

    @property
    def plugin_type(self) -> PluginType:
        return PluginType.POST_REQUEST

    @property
    def name(self) -> str:
        return "captcha_solver"

    def setup(self):
        """Initialize solver."""
        api_key = self.config.get("api_key")

        if not api_key:
            logger.warning("CAPTCHA Solver: API key not provided - plugin disabled")
            self.enabled = False
            return

        service = self.config.get("service", CaptchaService.TWO_CAPTCHA)

        try:
            self._solver = create_solver(service, api_key, self.config)
            logger.info(f"CAPTCHA Solver initialized: {service}")

            if self.config.get("check_balance", False):
                balance = self._solver.check_balance()
                if balance is not None:
                    logger.info(f"CAPTCHA service balance: ${balance:.2f}")
        except Exception as e:
            logger.error(f"Failed to initialize CAPTCHA solver: {e}")
            self.enabled = False

    def detect_captcha(self, html: str, page_url: str) -> Optional[CaptchaInfo]:
        """Виявляє CAPTCHA на сторінці."""
        return CaptchaDetector.detect(html, page_url)

    def solve_captcha(self, captcha_info: CaptchaInfo) -> Optional[CaptchaSolution]:
        """Розв'язує CAPTCHA."""
        if not self._solver:
            return None

        solution = self._solver.solve(captcha_info)

        if solution:
            self.total_solved += 1
            self.solve_times.append(solution.solve_time)
            if self.config.get("track_cost", True):
                self.total_cost += solution.cost
            logger.info(f"CAPTCHA solved: {solution}")
        else:
            self.total_failed += 1
            solution = self._try_fallback(captcha_info)

        return solution

    def _try_fallback(self, captcha_info: CaptchaInfo) -> Optional[CaptchaSolution]:
        """Спробувати fallback сервіси."""
        fallback_services = self.config.get("fallback_services", [])
        fallback_keys = self.config.get("fallback_keys", {})

        for service in fallback_services:
            api_key = fallback_keys.get(service)
            if not api_key:
                continue

            try:
                solver = create_solver(service, api_key, self.config)
                solution = solver.solve(captcha_info)
                if solution:
                    logger.info(f"Fallback service {service} succeeded")
                    return solution
            except Exception as e:
                logger.warning(f"Fallback {service} failed: {e}")

        return None

    def execute(self, context: PluginContext) -> PluginContext:
        """Виконує автоматичне визначення та розв'язання CAPTCHA."""
        if not self.enabled or not self.config.get("auto_detect", True):
            return context

        html = context.html
        if not html:
            return context

        captcha_info = self.detect_captcha(html, context.url)

        if captcha_info:
            logger.info(f"CAPTCHA detected: {captcha_info}")
            solution = self.solve_captcha(captcha_info)

            if solution:
                context.plugin_data["captcha_solution"] = {
                    "token": solution.token,
                    "captcha_type": solution.captcha_type,
                    "solve_time": solution.solve_time,
                    "cost": solution.cost,
                    "service": solution.service,
                }
            else:
                context.plugin_data["captcha_failed"] = True

        return context

    def get_stats(self) -> Dict[str, Any]:
        """Повертає статистику."""
        avg_solve_time = (
            sum(self.solve_times) / len(self.solve_times) if self.solve_times else 0.0
        )
        total = self.total_solved + self.total_failed

        return {
            "total_solved": self.total_solved,
            "total_failed": self.total_failed,
            "total_cost": self.total_cost,
            "success_rate": self.total_solved / total if total > 0 else 0.0,
            "avg_solve_time": avg_solve_time,
            "service": self.config.get("service"),
            "enabled": self.enabled,
        }

    def reset_stats(self):
        """Скидає статистику."""
        self.total_solved = 0
        self.total_failed = 0
        self.total_cost = 0.0
        self.solve_times = []
