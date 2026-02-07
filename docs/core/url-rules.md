# URL Rules

> **Час читання:** 12 хвилин  
> **Рівень:** Середній

Фільтрація та пріоритизація URL за допомогою правил.

---

## Огляд

GraphCrawler надає два типи правил для контролю краулінгу:

| Модель | Призначення |
|--------|-------------|
| `URLRule` | Контроль URL: фільтрація, пріоритизація, поведінка сканування |
| `EdgeRule` | Контроль edges: умови створення ребер між вузлами |

### URLRule дозволяє:
- Фільтрувати URL (дозволяти/забороняти)
- Встановлювати пріоритети
- Контролювати створення ребер
- Керувати поведінкою сканування (`should_scan`, `should_follow_links`)

---

## Базове використання

```python
import graph_crawler as gc
from graph_crawler import URLRule

rules = [
    URLRule(pattern=r"/products/", priority=10),      # Високий пріоритет
    URLRule(pattern=r"/blog/", priority=5),           # Середній пріоритет
    URLRule(pattern=r"/admin/", should_scan=False),   # Ігнорувати
    URLRule(pattern=r"\.pdf$", should_scan=False),    # Ігнорувати PDF
]

graph = gc.crawl("https://example.com", url_rules=rules)
```

---

## Параметри URLRule

```python
class URLRule(BaseModel):
    pattern: str                              # Regex патерн
    priority: int = 5                         # 1-10 (default: 5)
    should_scan: Optional[bool] = None        # Сканувати URL?
    should_follow_links: Optional[bool] = None # Слідувати посиланням?
    create_edge: Optional[bool] = None        # Створювати ребро?
```

### pattern

Regex патерн для співставлення з URL:

```python
# Точне співпадіння
URLRule(pattern=r"/about$")

# Будь-який текст
URLRule(pattern=r"/products/.*")

# Розширення файлу
URLRule(pattern=r"\.pdf$")

# Домен
URLRule(pattern=r"cdn\.example\.com")

# Параметри запиту
URLRule(pattern=r"\?page=")
```

### priority

Пріоритет сканування (1-10, default: 5):

```python
rules = [
    URLRule(pattern=r"/product/", priority=10),   # Найвищий
    URLRule(pattern=r"/category/", priority=8),
    URLRule(pattern=r"/blog/", priority=5),       # Середній
    URLRule(pattern=r"/faq/", priority=3),
    URLRule(pattern=r"/archive/", priority=1),    # Найнижчий
]
```

### should_scan

Чи сканувати URL:

```python
rules = [
    # Заборонити сканування
    URLRule(pattern=r"/admin/", should_scan=False),
    URLRule(pattern=r"/private/", should_scan=False),
    
    # Явно дозволити (перебиває фільтри)
    URLRule(pattern=r"/api/public/", should_scan=True),
]
```

### should_follow_links

Чи переходити за посиланнями зі сторінки (перебиває глобальний `follow_links`):

```python
rules = [
    # Сканувати, але не переходити далі (dead-end)
    URLRule(pattern=r"/dead-end/", should_follow_links=False),
    
    # Дозволити перехід за посиланнями з hub-сторінок
    URLRule(pattern=r"/hub/", should_follow_links=True),
    
    # Сканувати work.ua але не йти далі (перебиває фільтри!)
    URLRule(
        pattern=r'work\.ua',
        should_scan=True,           # Дозволити сканування
        should_follow_links=False   # Не переходити за посиланнями
    ),
    
    # Сканувати зовнішній сайт для отримання даних
    URLRule(
        pattern=r'api\.partner\.com',
        should_scan=True,
        should_follow_links=False   # Не індексувати партнерський сайт
    ),
]
```

**Важливо:** `should_follow_links` має **ВИЩИЙ ПРІОРИТЕТ** за `allowed_domains` та глобальний параметр `follow_links`. Це дозволяє:
- Сканувати зовнішні домени без переходу за їх посиланнями
- Створювати "dead-end" точки в графі
- Контролювати поведінку для окремих URL патернів

### create_edge

Чи створювати ребро в графі:

```python
rules = [
    # Сканувати, але не створювати ребра
    URLRule(pattern=r"/utility/", create_edge=False),
]
```

---

## Приклади для різних сценаріїв

### E-commerce

```python
ecommerce_rules = [
    # Високий пріоритет для товарів
    URLRule(pattern=r"/product/", priority=10),
    URLRule(pattern=r"/item/", priority=10),
    
    # Середній для категорій
    URLRule(pattern=r"/category/", priority=8),
    URLRule(pattern=r"/catalog/", priority=8),
    
    # Ігнорувати
    URLRule(pattern=r"/cart", should_scan=False),
    URLRule(pattern=r"/checkout", should_scan=False),
    URLRule(pattern=r"/account", should_scan=False),
    URLRule(pattern=r"/login", should_scan=False),
    URLRule(pattern=r"/register", should_scan=False),
    URLRule(pattern=r"/wishlist", should_scan=False),
    
    # Ігнорувати файли
    URLRule(pattern=r"\.pdf$", should_scan=False),
    URLRule(pattern=r"\.zip$", should_scan=False),
    URLRule(pattern=r"\.exe$", should_scan=False),
]

graph = gc.crawl(
    "https://shop.example.com",
    url_rules=ecommerce_rules,
    max_pages=10000
)
```

### Документація

```python
docs_rules = [
    # Пріоритет для конкретних секцій
    URLRule(pattern=r"/api/", priority=10),
    URLRule(pattern=r"/guides/", priority=9),
    URLRule(pattern=r"/tutorials/", priority=8),
    
    # Низький пріоритет для старих версій
    URLRule(pattern=r"/v1/", priority=2),
    URLRule(pattern=r"/v2/", priority=3),
    URLRule(pattern=r"/latest/", priority=10),
    
    # Ігнорувати
    URLRule(pattern=r"/changelog", priority=1),
    URLRule(pattern=r"/search", should_scan=False),
]

graph = gc.crawl(
    "https://docs.example.com",
    url_rules=docs_rules,
)
```

### Новинний сайт

```python
news_rules = [
    # Статті - високий пріоритет
    URLRule(pattern=r"/article/", priority=10),
    URLRule(pattern=r"/news/", priority=9),
    URLRule(pattern=r"/story/", priority=9),
    
    # Автори та теги - середній
    URLRule(pattern=r"/author/", priority=6),
    URLRule(pattern=r"/tag/", priority=5),
    URLRule(pattern=r"/topic/", priority=5),
    
    # Архіви - низький
    URLRule(pattern=r"/archive/", priority=2),
    URLRule(pattern=r"/\d{4}/\d{2}/", priority=3),  # Дати
    
    # Ігнорувати
    URLRule(pattern=r"/ads", should_scan=False),
    URLRule(pattern=r"/subscribe", should_scan=False),
    URLRule(pattern=r"/print/", should_scan=False),
]
```

### SEO Аудит

```python
seo_rules = [
    # Сканувати все крім...
    URLRule(pattern=r"/cdn/", should_scan=False),
    URLRule(pattern=r"/static/", should_scan=False),
    URLRule(pattern=r"/assets/", should_scan=False),
    
    # Ігнорувати зображення та файли
    URLRule(pattern=r"\.(jpg|jpeg|png|gif|svg|ico)$", should_scan=False),
    URLRule(pattern=r"\.(css|js|woff|woff2|ttf)$", should_scan=False),
    URLRule(pattern=r"\.(pdf|doc|docx|xls|xlsx)$", should_scan=False),
    
    # Ігнорувати tracking
    URLRule(pattern=r"utm_", should_scan=False),
    URLRule(pattern=r"\?ref=", should_scan=False),
    URLRule(pattern=r"\?source=", should_scan=False),
]
```

---

## Порядок застосування правил

Правила застосовуються в порядку оголошення. Перше правило, що співпало, визначає поведінку:

```python
rules = [
    # Спочатку конкретні
    URLRule(pattern=r"/products/special/", priority=10),
    
    # Потім загальні
    URLRule(pattern=r"/products/", priority=5),
    
    # Найзагальніші в кінці
    URLRule(pattern=r".*", priority=1),
]
```

---

## Комбінація з плагінами

Плагіни можуть динамічно змінювати правила:

```python
from graph_crawler import BaseNodePlugin, NodePluginType

class DynamicPriorityPlugin(BaseNodePlugin):
    """Динамічно встановлює пріоритет на основі контенту."""
    
    @property
    def name(self):
        return "dynamic_priority"
    
    @property
    def plugin_type(self):
        return NodePluginType.ON_AFTER_SCAN
    
    def execute(self, context):
        # Високий пріоритет для посилань на продукти
        keywords = ['buy', 'price', 'order']
        text = context.user_data.get('text_content', '').lower()
        
        priorities = {}
        for link in context.extracted_links:
            if any(kw in text for kw in keywords):
                priorities[link] = 10
        
        context.user_data['child_priorities'] = priorities
        return context
```

---

## Налагодження правил

```python
def debug_rules(rules, test_urls):
    """Перевірка правил на тестових URL."""
    import re
    
    for url in test_urls:
        print(f"\n{url}:")
        matched = False
        for rule in rules:
            if re.search(rule.pattern, url):
                print(f"  Matched: {rule.pattern}")
                print(f"    Priority: {rule.priority}")
                print(f"    Should scan: {rule.should_scan}")
                matched = True
                break
        
        if not matched:
            print("  No rule matched (default behavior)")

# Тест
test_urls = [
    "https://example.com/products/item-1",
    "https://example.com/admin/users",
    "https://example.com/document.pdf",
    "https://example.com/about",
]

debug_rules(ecommerce_rules, test_urls)
```

---

## EdgeRule - Контроль створення ребер

`EdgeRule` дозволяє задавати складні умови для створення або пропуску edges між вузлами. Перевіряється після фільтрації URL, але перед створенням edge в LinkProcessor.

### Параметри EdgeRule

```python
from graph_crawler import EdgeRule

class EdgeRule(BaseModel):
    source_pattern: Optional[str] = None   # Regex для source URL
    target_pattern: Optional[str] = None   # Regex для target URL
    max_depth_diff: Optional[int] = None   # Макс. різниця глибини
    action: str                             # 'create' або 'skip'
```

### Базове використання

```python
import graph_crawler as gc
from graph_crawler import EdgeRule

edge_rules = [
    # Не створювати edges якщо різниця глибини > 2
    EdgeRule(max_depth_diff=2, action='skip'),
    
    # Не створювати edges з blog на products
    EdgeRule(
        source_pattern=r'.*/blog/.*',
        target_pattern=r'.*/products/.*',
        action='skip'
    ),
    
    # Створювати edges тільки в межах розділів docs
    EdgeRule(
        source_pattern=r'.*/docs/.*',
        target_pattern=r'.*/docs/.*',
        action='create'
    ),
    
    # Не створювати edges назад на головну сторінку
    EdgeRule(
        target_pattern=r'^https://site\.com/$',
        action='skip'
    ),
]

graph = gc.crawl(
    "https://example.com",
    edge_rules=edge_rules  # Передаємо правила
)
```

### Приклади для різних сценаріїв

#### Обмеження "популярних" сторінок

```python
# Проблема: header/footer посилання створюють багато edges на одні й ті ж сторінки
edge_rules = [
    # Не створювати edges на головну та контактну сторінки
    EdgeRule(target_pattern=r'/(|contact|about)$', action='skip'),
    
    # Не створювати edges на login/register
    EdgeRule(target_pattern=r'/(login|register|signup)$', action='skip'),
]
```

#### Контроль глибини

```python
edge_rules = [
    # Edges тільки на сусідні рівні глибини
    EdgeRule(max_depth_diff=1, action='create'),
    
    # Все інше - пропустити
    EdgeRule(action='skip'),
]
```

#### Ізоляція розділів сайту

```python
edge_rules = [
    # Blog -> Blog OK
    EdgeRule(
        source_pattern=r'.*/blog/.*',
        target_pattern=r'.*/blog/.*',
        action='create'
    ),
    # Docs -> Docs OK
    EdgeRule(
        source_pattern=r'.*/docs/.*',
        target_pattern=r'.*/docs/.*',
        action='create'
    ),
    # Blog -> Docs або Docs -> Blog - skip
    EdgeRule(
        source_pattern=r'.*/blog/.*',
        target_pattern=r'.*/docs/.*',
        action='skip'
    ),
    EdgeRule(
        source_pattern=r'.*/docs/.*',
        target_pattern=r'.*/blog/.*',
        action='skip'
    ),
]
```

### Метод matches()

```python
rule = EdgeRule(
    source_pattern=r'.*/blog/.*',
    target_pattern=r'.*/products/.*',
    action='skip'
)

# Перевірка чи правило застосовується
matches = rule.matches(
    source_url="https://site.com/blog/post-1",
    target_url="https://site.com/products/item",
    source_depth=2,
    target_depth=3
)
print(f"Rule matches: {matches}")  # True

# Визначення дії
should_create = rule.should_create_edge(
    source_url="https://site.com/blog/post-1",
    target_url="https://site.com/products/item",
    source_depth=2,
    target_depth=3
)
print(f"Should create edge: {should_create}")  # False (action='skip')
```

### Порядок застосування EdgeRule

1. Правила перевіряються в порядку оголошення
2. Перше правило, що matches, визначає поведінку
3. Якщо жодне правило не matches - використовується default поведінка (create)

```python
edge_rules = [
    # Спочатку конкретні правила
    EdgeRule(source_pattern=r'.*/special/.*', action='create'),
    
    # Потім загальні
    EdgeRule(max_depth_diff=3, action='skip'),
    
    # Default fallback (optional)
    EdgeRule(action='create'),
]
```

---

## Комбінація URLRule та EdgeRule

```python
import graph_crawler as gc
from graph_crawler import URLRule, EdgeRule

# URL правила - ЩО сканувати
url_rules = [
    URLRule(pattern=r"/products/", priority=10),
    URLRule(pattern=r"/admin/", should_scan=False),
    URLRule(pattern=r"\.pdf$", should_scan=False),
]

# Edge правила - ЯКІ зв'язки створювати
edge_rules = [
    EdgeRule(target_pattern=r'/(login|cart)$', action='skip'),
    EdgeRule(max_depth_diff=2, action='skip'),
]

graph = gc.crawl(
    "https://shop.example.com",
    url_rules=url_rules,
    edge_rules=edge_rules,
)
```

---

## Наступні кроки

- [Cache Modes →](cache-modes.md)
- [Plugin System →](../extraction/plugins.md)
- [API Reference →](../api/API.md)
