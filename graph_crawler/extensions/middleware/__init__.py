"""Middleware система для GraphCrawler.

Middleware pattern дозволяє модифікувати запити та відповіді на різних етапах:
- PRE_REQUEST: перед виконанням запиту
- POST_REQUEST: після отримання відповіді
- ON_ERROR: при виникненні помилки

Приклади middleware:
- LoggingMiddleware - логування
- CacheMiddleware - кешування відповідей
- RetryMiddleware - повтор при помилці
- RobotsTxtMiddleware - robots.txt валідація
"""

from graph_crawler.extensions.middleware.base import (
    BaseMiddleware,
    MiddlewareContext,
    MiddlewareType,
)
from graph_crawler.extensions.middleware.cache_middleware import CacheMiddleware
from graph_crawler.extensions.middleware.chain import MiddlewareChain
from graph_crawler.extensions.middleware.error_recovery_middleware import (
    ErrorRecoveryMiddleware,
)
from graph_crawler.extensions.middleware.logging_middleware import LoggingMiddleware
from graph_crawler.extensions.middleware.proxy_middleware import (
    ProxyInfo,
    ProxyRotationMiddleware,
)
from graph_crawler.extensions.middleware.rate_limit_middleware import (
    RateLimitMiddleware,
    TokenBucket,
)
from graph_crawler.extensions.middleware.request_response_middleware import (
    RequestMiddleware,
    ResponseMiddleware,
)
from graph_crawler.extensions.middleware.retry_middleware import RetryMiddleware
from graph_crawler.extensions.middleware.robots_cache import RobotsCache
from graph_crawler.extensions.middleware.robots_middleware import RobotsTxtMiddleware
from graph_crawler.extensions.middleware.robots_validator import RobotsValidator
from graph_crawler.extensions.middleware.user_agent_middleware import (
    UserAgentMiddleware,
)

__all__ = [
    "BaseMiddleware",
    "MiddlewareContext",
    "MiddlewareType",
    "MiddlewareChain",
    "LoggingMiddleware",
    "CacheMiddleware",
    "RetryMiddleware",
    "RobotsTxtMiddleware",
    "RobotsCache",
    "RobotsValidator",
    "RateLimitMiddleware",
    "TokenBucket",
    "UserAgentMiddleware",
    "ProxyRotationMiddleware",
    "ProxyInfo",
    "RequestMiddleware",
    "ResponseMiddleware",
    "ErrorRecoveryMiddleware",
]
