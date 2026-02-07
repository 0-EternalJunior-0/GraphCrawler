# Hooks & Authentication

> **Час читання:** 10 хвилин  
> **Рівень:** Senior

Hooks та авторизація для захищених сайтів.

---

## Огляд Hooks

GraphCrawler підтримує 6 типів hooks:

| Hook | Етап | Опис |
|------|------|------|
| `ON_NODE_CREATED` | URL | При створенні ноди |
| `ON_BEFORE_SCAN` | URL | Перед завантаженням |
| `ON_HTML_PARSED` | HTML | Після парсингу HTML |
| `ON_AFTER_SCAN` | HTML | Після обробки |
| `BEFORE_CRAWL` | Crawl | Перед початком |
| `AFTER_CRAWL` | Crawl | Після завершення |

---

## Basic Auth

```python
import graph_crawler as gc

graph = gc.crawl(
    "https://protected.example.com",
    driver_config={
        "auth": {
            "type": "basic",
            "username": "user",
            "password": "pass",
        }
    }
)
```

---

## Bearer Token

```python
graph = gc.crawl(
    "https://api.example.com",
    driver_config={
        "headers": {
            "Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
        }
    }
)
```

---

## Form Login (Playwright)

### Приклад логіну

```python
from graph_crawler import BaseNodePlugin, NodePluginType

class LoginPlugin(BaseNodePlugin):
    """Плагін для логіну."""
    
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.logged_in = False
    
    @property
    def name(self):
        return "login"
    
    @property
    def plugin_type(self):
        return NodePluginType.ON_BEFORE_SCAN
    
    def execute(self, context):
        if not self.logged_in and '/login' not in context.url:
            # Перенаправити на логін
            context.redirect_url = "https://example.com/login"
        
        return context

# Використання з Playwright
graph = gc.crawl(
    "https://example.com",
    driver="playwright",
    driver_config={
        "before_navigation": """
            async (page) => {
                // Перевірити чи потрібен логін
                if (await page.$('.login-form')) {
                    await page.fill('#username', 'user');
                    await page.fill('#password', 'pass');
                    await page.click('#login-button');
                    await page.waitForNavigation();
                }
            }
        """
    }
)
```

---

## OAuth2

```python
import requests

# Отримати токен
token_response = requests.post(
    "https://auth.example.com/oauth/token",
    data={
        "grant_type": "client_credentials",
        "client_id": "your_client_id",
        "client_secret": "your_client_secret",
    }
)
access_token = token_response.json()["access_token"]

# Використати токен
graph = gc.crawl(
    "https://api.example.com",
    driver_config={
        "headers": {
            "Authorization": f"Bearer {access_token}"
        }
    }
)
```

---

## Custom Hook для Auth

```python
from graph_crawler import BaseNodePlugin, NodePluginType
from graph_crawler.extensions.middleware import BaseMiddleware, MiddlewareType

class AuthMiddleware(BaseMiddleware):
    """Додає авторизацію до запитів."""
    
    def __init__(self, token):
        super().__init__()
        self.token = token
    
    @property
    def name(self):
        return "auth"
    
    @property
    def middleware_type(self):
        return MiddlewareType.PRE_REQUEST
    
    def process(self, context):
        context.headers['Authorization'] = f'Bearer {self.token}'
        return context

# Використання
graph = gc.crawl(
    "https://api.example.com",
    driver_config={
        "middleware": [AuthMiddleware("your_token")]
    }
)
```

---

## Session Persistence

```python
import json

# Зберегти сесію після логіну
graph = gc.crawl(
    "https://example.com",
    driver="playwright",
    driver_config={
        "storage_state": "./auth_state.json",
        "save_state": True,
    }
)

# Потім використати збережену сесію
graph2 = gc.crawl(
    "https://example.com/protected",
    driver="playwright",
    driver_config={
        "storage_state": "./auth_state.json",
    }
)
```

---

## Наступні кроки

- [Session Management →](session-management.md)
- [Plugin System →](../extraction/plugins.md)
