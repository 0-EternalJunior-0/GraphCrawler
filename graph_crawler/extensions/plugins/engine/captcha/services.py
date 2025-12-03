"""CAPTCHA Solving Services - інтеграція з сервісами.

Підтримується:
- 2captcha.com API
- AntiCaptcha.com API
- CapSolver API
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import requests

from graph_crawler.extensions.plugins.engine.captcha.models import (
    CaptchaInfo,
    CaptchaService,
    CaptchaSolution,
    CaptchaType,
)

logger = logging.getLogger(__name__)


class BaseCaptchaSolver(ABC):
    """Базовий клас для CAPTCHA solvers."""

    def __init__(self, api_key: str, config: Dict[str, Any] = None):
        self.api_key = api_key
        self.config = config or {}
        self.solve_timeout = self.config.get("solve_timeout", 120)
        self.min_score = self.config.get("min_score", 0.3)

    @abstractmethod
    def solve(self, captcha_info: CaptchaInfo) -> Optional[CaptchaSolution]:
        """Розв'язує CAPTCHA."""
        pass

    @abstractmethod
    def check_balance(self) -> Optional[float]:
        """Перевіряє баланс."""
        pass


class TwoCaptchaSolver(BaseCaptchaSolver):
    """2captcha.com solver."""

    BASE_URL = "http://2captcha.com"
    SERVICE_NAME = "2captcha"

    def solve(self, captcha_info: CaptchaInfo) -> Optional[CaptchaSolution]:
        params = {"key": self.api_key, "json": 1}

        if captcha_info.captcha_type == CaptchaType.RECAPTCHA_V2:
            params.update(
                {
                    "method": "userrecaptcha",
                    "googlekey": captcha_info.site_key,
                    "pageurl": captcha_info.page_url,
                }
            )
            if captcha_info.data_s:
                params["data-s"] = captcha_info.data_s

        elif captcha_info.captcha_type == CaptchaType.RECAPTCHA_V3:
            params.update(
                {
                    "method": "userrecaptcha",
                    "version": "v3",
                    "googlekey": captcha_info.site_key,
                    "pageurl": captcha_info.page_url,
                    "action": captcha_info.action or "submit",
                    "min_score": self.min_score,
                }
            )

        elif captcha_info.captcha_type == CaptchaType.HCAPTCHA:
            params.update(
                {
                    "method": "hcaptcha",
                    "sitekey": captcha_info.site_key,
                    "pageurl": captcha_info.page_url,
                }
            )
        else:
            logger.warning(f"Unsupported CAPTCHA type: {captcha_info.captcha_type}")
            return None

        try:
            response = requests.post(f"{self.BASE_URL}/in.php", data=params, timeout=30)
            result = response.json()

            if result.get("status") != 1:
                logger.error(f"2captcha error: {result.get('request')}")
                return None

            captcha_id = result.get("request")
            elapsed = 0

            while elapsed < self.solve_timeout:
                time.sleep(5)
                elapsed += 5

                check_response = requests.get(
                    f"{self.BASE_URL}/res.php",
                    params={
                        "key": self.api_key,
                        "action": "get",
                        "id": captcha_id,
                        "json": 1,
                    },
                    timeout=30,
                )
                check_result = check_response.json()

                if check_result.get("status") == 1:
                    token = check_result.get("request")
                    cost = (
                        0.003
                        if captcha_info.captcha_type
                        in [CaptchaType.RECAPTCHA_V2, CaptchaType.RECAPTCHA_V3]
                        else 0.002
                    )

                    return CaptchaSolution(
                        token=token,
                        captcha_type=captcha_info.captcha_type,
                        solve_time=elapsed,
                        cost=cost,
                        service=self.SERVICE_NAME,
                    )
                elif check_result.get("request") != "CAPCHA_NOT_READY":
                    logger.error(f"2captcha error: {check_result.get('request')}")
                    return None

            return None
        except Exception as e:
            logger.error(f"2captcha API error: {e}")
            return None

    def check_balance(self) -> Optional[float]:
        try:
            response = requests.get(
                f"{self.BASE_URL}/res.php?key={self.api_key}&action=getbalance",
                timeout=10,
            )
            return float(response.text)
        except Exception:
            return None


class AntiCaptchaSolver(BaseCaptchaSolver):
    """anticaptcha.com solver."""

    BASE_URL = "https://api.anti-captcha.com"
    SERVICE_NAME = "anticaptcha"

    def solve(self, captcha_info: CaptchaInfo) -> Optional[CaptchaSolution]:
        task = {}

        if captcha_info.captcha_type == CaptchaType.RECAPTCHA_V2:
            task = {
                "type": "RecaptchaV2TaskProxyless",
                "websiteURL": captcha_info.page_url,
                "websiteKey": captcha_info.site_key,
            }
            if captcha_info.data_s:
                task["recaptchaDataSValue"] = captcha_info.data_s

        elif captcha_info.captcha_type == CaptchaType.RECAPTCHA_V3:
            task = {
                "type": "RecaptchaV3TaskProxyless",
                "websiteURL": captcha_info.page_url,
                "websiteKey": captcha_info.site_key,
                "pageAction": captcha_info.action or "submit",
                "minScore": self.min_score,
            }

        elif captcha_info.captcha_type == CaptchaType.HCAPTCHA:
            task = {
                "type": "HCaptchaTaskProxyless",
                "websiteURL": captcha_info.page_url,
                "websiteKey": captcha_info.site_key,
            }
        else:
            return None

        try:
            response = requests.post(
                f"{self.BASE_URL}/createTask",
                json={"clientKey": self.api_key, "task": task},
                timeout=30,
            )
            result = response.json()

            if result.get("errorId", 0) != 0:
                logger.error(f"AntiCaptcha error: {result.get('errorDescription')}")
                return None

            task_id = result.get("taskId")
            elapsed = 0

            while elapsed < self.solve_timeout:
                time.sleep(5)
                elapsed += 5

                check_response = requests.post(
                    f"{self.BASE_URL}/getTaskResult",
                    json={"clientKey": self.api_key, "taskId": task_id},
                    timeout=30,
                )
                check_result = check_response.json()

                if check_result.get("status") == "ready":
                    solution = check_result.get("solution", {})
                    token = solution.get("gRecaptchaResponse") or solution.get("token")
                    cost = 0.002

                    return CaptchaSolution(
                        token=token,
                        captcha_type=captcha_info.captcha_type,
                        solve_time=elapsed,
                        cost=cost,
                        service=self.SERVICE_NAME,
                    )
                elif check_result.get("errorId", 0) != 0:
                    return None

            return None
        except Exception as e:
            logger.error(f"AntiCaptcha API error: {e}")
            return None

    def check_balance(self) -> Optional[float]:
        try:
            response = requests.post(
                f"{self.BASE_URL}/getBalance",
                json={"clientKey": self.api_key},
                timeout=10,
            )
            return response.json().get("balance", 0.0)
        except Exception:
            return None


class CapSolverSolver(BaseCaptchaSolver):
    """capsolver.com solver."""

    BASE_URL = "https://api.capsolver.com"
    SERVICE_NAME = "capsolver"

    def solve(self, captcha_info: CaptchaInfo) -> Optional[CaptchaSolution]:
        task = {
            "websiteURL": captcha_info.page_url,
            "websiteKey": captcha_info.site_key,
        }

        if captcha_info.captcha_type == CaptchaType.RECAPTCHA_V2:
            task["type"] = "ReCaptchaV2TaskProxyLess"
        elif captcha_info.captcha_type == CaptchaType.RECAPTCHA_V3:
            task["type"] = "ReCaptchaV3TaskProxyLess"
            task["pageAction"] = captcha_info.action or "submit"
        elif captcha_info.captcha_type == CaptchaType.HCAPTCHA:
            task["type"] = "HCaptchaTaskProxyLess"
        else:
            return None

        try:
            response = requests.post(
                f"{self.BASE_URL}/createTask",
                json={"clientKey": self.api_key, "task": task},
                timeout=30,
            )
            result = response.json()

            if result.get("errorId", 0) != 0:
                return None

            task_id = result.get("taskId")
            elapsed = 0

            while elapsed < self.solve_timeout:
                time.sleep(5)
                elapsed += 5

                check_response = requests.post(
                    f"{self.BASE_URL}/getTaskResult",
                    json={"clientKey": self.api_key, "taskId": task_id},
                    timeout=30,
                )
                check_result = check_response.json()

                if check_result.get("status") == "ready":
                    solution = check_result.get("solution", {})
                    token = solution.get("gRecaptchaResponse") or solution.get("token")

                    return CaptchaSolution(
                        token=token,
                        captcha_type=captcha_info.captcha_type,
                        solve_time=elapsed,
                        cost=0.0025,
                        service=self.SERVICE_NAME,
                    )

            return None
        except Exception as e:
            logger.error(f"CapSolver API error: {e}")
            return None

    def check_balance(self) -> Optional[float]:
        try:
            response = requests.post(
                f"{self.BASE_URL}/getBalance",
                json={"clientKey": self.api_key},
                timeout=10,
            )
            return response.json().get("balance", 0.0)
        except Exception:
            return None


def create_solver(
    service: str, api_key: str, config: Dict[str, Any] = None
) -> BaseCaptchaSolver:
    """Створює solver за назвою сервісу."""
    solvers = {
        CaptchaService.TWO_CAPTCHA: TwoCaptchaSolver,
        CaptchaService.ANTI_CAPTCHA: AntiCaptchaSolver,
        CaptchaService.CAPSOLVER: CapSolverSolver,
        "2captcha": TwoCaptchaSolver,
        "anticaptcha": AntiCaptchaSolver,
        "capsolver": CapSolverSolver,
    }

    solver_class = solvers.get(service)
    if not solver_class:
        raise ValueError(f"Unknown service: {service}")

    return solver_class(api_key, config)
