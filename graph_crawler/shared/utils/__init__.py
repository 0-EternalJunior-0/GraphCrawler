"""Модуль UTILS - Допоміжні утіліти для роботи з URL та HTML.

Цей модуль містить статичні утіліти для:
"""

from graph_crawler.shared.utils.bloom_filter import BloomFilter, create_bloom_filter

# CAPTCHA Detection: plugins_new/captcha_detector.py (CaptchaDetectorPlugin)
# Для standalone детекції використовуйте graph_crawler.CustomPlugins.engine.captcha_solver
from graph_crawler.shared.utils.captcha import (
    BypassAttempt,
    BypassResult,
    BypassStrategy,
    CaptchaBypassManager,
    SessionInfo,
)
from graph_crawler.shared.utils.fast_json import (
    dumps as fast_json_dumps,
)
from graph_crawler.shared.utils.fast_json import (
    dumps_bytes as fast_json_dumps_bytes,
)
from graph_crawler.shared.utils.fast_json import (
    is_orjson_available,
)
from graph_crawler.shared.utils.fast_json import (
    loads as fast_json_loads,
)
from graph_crawler.shared.utils.fingerprint import (
    FingerprintProfile,
    generate_fingerprint_profile,
    generate_random_geolocation,
    generate_random_timezone,
    generate_random_viewport,
    generate_realistic_headers,
    get_stealth_script,
)
from graph_crawler.shared.utils.html_utils import HTMLUtils
from graph_crawler.shared.utils.proxy_manager import (
    Proxy,
    ProxyPoolManager,
    ProxyStats,
    ProxyType,
    RotationStrategy,
    create_proxy_manager,
)
from graph_crawler.shared.utils.rate_limiter import (
    DomainLimitConfig,
    DomainRateLimiter,
    RateLimiter,
)
from graph_crawler.shared.utils.url_utils import URLUtils
from graph_crawler.shared.utils.user_agent_rotator import (
    UserAgentRotator,
    create_rotator,
)

# Text processing utilities
from graph_crawler.shared.utils.text_utils import (
    STOP_WORDS,
    extract_keywords,
    normalize_text,
)

# URL pattern constants
from graph_crawler.shared.utils.url_patterns import (
    CONTENT_PAGE_PATTERNS,
    IGNORE_PATTERNS,
    NAVIGATION_PATTERNS,
    is_content_url,
    is_navigation_url,
    should_ignore_url,
)


# Backward compatibility - create_captcha_bypass_manager
def create_captcha_bypass_manager(**kwargs) -> CaptchaBypassManager:
    """Factory функція для створення CaptchaBypassManager (backward compatibility)."""
    return CaptchaBypassManager(**kwargs)


# Celery Config
from graph_crawler.shared.utils.celery_config import (
    check_broker_connection,
    check_workers,
    get_backend_url,
    get_broker_url,
    get_celery_app_config,
    get_celery_batch_config,
    validate_distributed_setup,
)

# Celery Helpers
from graph_crawler.shared.utils.celery_helpers import (
    create_driver_from_config,
    import_class,
    import_plugin,
)

# Markdown Generation
from graph_crawler.shared.utils.markdown import (
    MarkdownGenerator,
    MarkdownOptions,
    MarkdownResult,
)
from graph_crawler.shared.utils.memory_optimizer import (
    MemoryEfficientNodeCache,
    MemoryMonitor,
    MemoryProfiler,
    MemoryStats,
    WeakValueGraph,
    estimate_graph_memory,
    get_object_size,
    memory_efficient_node_iterator,
    optimize_graph_memory,
)

__all__ = [
    "URLUtils",
    "HTMLUtils",
    "BloomFilter",
    "create_bloom_filter",
    # Rate Limiting
    "RateLimiter",
    "DomainRateLimiter",  # Backward compatibility alias
    "DomainLimitConfig",
    # User-Agent Rotation
    "UserAgentRotator",
    "create_rotator",
    # Proxy Manager
    "Proxy",
    "ProxyType",
    "ProxyStats",
    "RotationStrategy",
    "ProxyPoolManager",
    "create_proxy_manager",
    # Browser Fingerprinting
    "FingerprintProfile",
    "generate_fingerprint_profile",
    "generate_random_viewport",
    "generate_realistic_headers",
    "generate_random_timezone",
    "generate_random_geolocation",
    "get_stealth_script",
    # CAPTCHA Bypass
    "CaptchaBypassManager",
    "BypassStrategy",
    "BypassResult",
    "BypassAttempt",
    "SessionInfo",
    "create_captcha_bypass_manager",
    # Memory Optimization
    "MemoryProfiler",
    "MemoryStats",
    "MemoryMonitor",
    "WeakValueGraph",
    "get_object_size",
    "optimize_graph_memory",
    "memory_efficient_node_iterator",
    "estimate_graph_memory",
    "MemoryEfficientNodeCache",
    # Celery Config
    "get_broker_url",
    "get_backend_url",
    "get_celery_app_config",
    "get_celery_batch_config",
    "check_broker_connection",
    "check_workers",
    "validate_distributed_setup",
    # Celery Helpers
    "import_plugin",
    "import_class",
    "create_driver_from_config",
    # Fast JSON (orjson-based)
    "fast_json_dumps",
    "fast_json_loads",
    "fast_json_dumps_bytes",
    "is_orjson_available",
    # Markdown Generation
    "MarkdownGenerator",
    "MarkdownOptions",
    "MarkdownResult",
    # Text Processing
    "extract_keywords",
    "normalize_text",
    "STOP_WORDS",
    # URL Patterns
    "CONTENT_PAGE_PATTERNS",
    "NAVIGATION_PATTERNS",
    "IGNORE_PATTERNS",
    "is_content_url",
    "is_navigation_url",
    "should_ignore_url",
]
