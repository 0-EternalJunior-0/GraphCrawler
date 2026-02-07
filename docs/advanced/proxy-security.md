# Proxy & Security

> **Час читання:** 10 хвилин  
> **Рівень:** Senior

Налаштування проксі та захист від антибот систем.

---

## Проксі

### Один проксі

```python
import graph_crawler as gc

graph = gc.crawl(
    "https://example.com",
    driver_config={
        "proxy": "http://user:pass@proxy.example.com:8080"
    }
)
```

### Ротація проксі

```python
from graph_crawler.extensions.middleware import ProxyMiddleware

proxies = [
    "http://proxy1.example.com:8080",
    "http://proxy2.example.com:8080",
    "http://proxy3.example.com:8080",
]

proxy_middleware = ProxyMiddleware(
    proxies=proxies,
    rotation="round_robin",  # або "random"
)

graph = gc.crawl(
    "https://example.com",
    driver_config={
        "middleware": [proxy_middleware]
    }
)
```

### SOCKS5 проксі

```python
graph = gc.crawl(
    "https://example.com",
    driver_config={
        "proxy": "socks5://user:pass@proxy.example.com:1080"
    }
)
```

---

## User-Agent ротація

### Вбудована ротація

```python
from graph_crawler.extensions.middleware import UserAgentMiddleware

ua_middleware = UserAgentMiddleware(
    rotation="random",
    browser_types=["chrome", "firefox", "safari"],
)

graph = gc.crawl(
    "https://example.com",
    driver_config={
        "middleware": [ua_middleware]
    }
)
```

### Кастомні User-Agents

```python
ua_middleware = UserAgentMiddleware(
    user_agents=[
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) Firefox/120.0",
    ]
)
```

---

## Stealth Mode

### Stealth Driver

```python
graph = gc.crawl(
    "https://protected-site.com",
    driver="stealth",
    driver_config={
        "fingerprint": "random",
        "headless": True,
    }
)
```

### Fingerprint конфігурація

```python
graph = gc.crawl(
    "https://protected-site.com",
    driver="stealth",
    driver_config={
        "fingerprint": {
            "platform": "Win32",
            "vendor": "Google Inc.",
            "renderer": "ANGLE (Intel, Intel(R) UHD Graphics 620)",
            "webgl_vendor": "Intel Inc.",
            "timezone": "Europe/Kiev",
            "language": "uk-UA",
        }
    }
)
```

---

## Rate Limiting

### Базове

```python
graph = gc.crawl(
    "https://example.com",
    request_delay=0.5,  # 0.5 секунди між запитами
)
```

### Middleware

```python
from graph_crawler.extensions.middleware import RateLimitMiddleware

rate_limiter = RateLimitMiddleware(
    requests_per_second=10,
    per_domain=True,  # Обмеження на домен
)

graph = gc.crawl(
    "https://example.com",
    driver_config={
        "middleware": [rate_limiter]
    }
)
```

### Розподілений Rate Limiter

```python
from graph_crawler.shared.utils import DistributedRateLimiter

rate_limiter = DistributedRateLimiter(
    redis_url="redis://localhost:6379",
    requests_per_second=100,
)
```

---

## Robots.txt

### Автоматичне дотримання

```python
from graph_crawler.extensions.middleware import RobotsMiddleware

robots_middleware = RobotsMiddleware(
    respect_robots=True,
    cache_ttl=3600,
)

graph = gc.crawl(
    "https://example.com",
    driver_config={
        "middleware": [robots_middleware]
    }
)
```

### Ігнорування

```python
robots_middleware = RobotsMiddleware(
    respect_robots=False,
)
```

---

## SSL/TLS

### Відключення перевірки

```python
graph = gc.crawl(
    "https://self-signed.example.com",
    driver_config={
        "ssl_verify": False,
    }
)
```

### Кастомний сертифікат

```python
graph = gc.crawl(
    "https://example.com",
    driver_config={
        "ssl_cert": "/path/to/cert.pem",
    }
)
```

---

## Retry логіка

```python
from graph_crawler.extensions.middleware import RetryMiddleware

retry_middleware = RetryMiddleware(
    max_retries=3,
    retry_on_status=[500, 502, 503, 504],
    backoff_factor=2,  # Експоненційний бекоф
)

graph = gc.crawl(
    "https://example.com",
    driver_config={
        "middleware": [retry_middleware]
    }
)
```

---

## Приклад: Повна конфігурація

```python
import graph_crawler as gc
from graph_crawler.extensions.middleware import (
    ProxyMiddleware,
    UserAgentMiddleware,
    RateLimitMiddleware,
    RetryMiddleware,
    RobotsMiddleware,
)

# Мідлвери
middleware = [
    RobotsMiddleware(respect_robots=True),
    RateLimitMiddleware(requests_per_second=5),
    ProxyMiddleware(proxies=[...], rotation="random"),
    UserAgentMiddleware(rotation="random"),
    RetryMiddleware(max_retries=3),
]

graph = gc.crawl(
    "https://protected-site.com",
    driver="stealth",
    driver_config={
        "middleware": middleware,
        "headless": True,
        "timeout": 30,
    },
    request_delay=0.5,
    max_pages=1000,
)
```

---

## Наступні кроки

- [Session Management →](session-management.md)
- [Hooks & Auth →](hooks-auth.md)
