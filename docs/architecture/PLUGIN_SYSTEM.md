# 5. Plugin System Documentation (Система плагінів)

## 📋 Зміст

1. [Архітектура плагінів](#архітектура-плагінів)
2. [Node Plugins](#node-plugins)
3. [Middleware](#middleware)
4. [Реєстрація та життєвий цикл](#реєстрація-та-життєвий-цикл)
5. [Вбудовані плагіни](#вбудовані-плагіни)
6. [Приклади кастомних плагінів](#приклади-кастомних-плагінів)

---

## Архітектура плагінів

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PLUGIN ARCHITECTURE                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │                      NODE PLUGINS                                   │     │
│  │                                                                     │     │
│  │   Node Creation              HTML Processing                        │     │
│  │   ┌─────────────┐           ┌─────────────────────────────────┐    │     │
│  │   │ON_NODE_     │           │ON_BEFORE_ │ON_HTML_  │ON_AFTER_ │    │     │
│  │   │CREATED      │    ───▶   │SCAN       │PARSED    │SCAN      │    │     │
│  │   └─────────────┘           └─────────────────────────────────┘    │     │
│  │                                                                     │     │
│  │   URL_STAGE                 HTML_STAGE                              │     │
│  │   (url, depth)              (html, tree, metadata, links)           │     │
│  │                                                                     │     │
│  │   Use Cases:                Use Cases:                              │     │
│  │   • URL filtering           • Metadata extraction                   │     │
│  │   • Priority setting        • Link extraction                       │     │
│  │   • should_scan control     • Phone/Email extraction                │     │
│  │                             • ML analysis                           │     │
│  │                             • Vectorization                         │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                             │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │                        MIDDLEWARE                                   │     │
│  │                                                                     │     │
│  │   Request Flow:                                                     │     │
│  │   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    │     │
│  │   │RateLimit │───▶│  Proxy   │───▶│UserAgent │───▶│  Driver  │    │     │
│  │   └──────────┘    └──────────┘    └──────────┘    └────┬─────┘    │     │
│  │                                                        │          │     │
│  │   Response Flow:                                       │          │     │
│  │   ┌──────────┐    ┌──────────┐    ┌──────────┐        │          │     │
│  │   │  Cache   │◀───│  Retry   │◀───│  Error   │◀───────┘          │     │
│  │   └──────────┘    └──────────┘    └──────────┘                    │     │
│  │                                                                     │     │
│  │   Use Cases:                                                        │     │
│  │   • Rate limiting          • Proxy rotation                         │     │
│  │   • Retry logic            • Caching                                │     │
│  │   • Error recovery         • robots.txt                             │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Node Plugins

### Базовий клас

```python
from abc import ABC, abstractmethod
from graph_crawler.extensions.plugins.node import NodePluginType

class BaseNodePlugin(ABC):
    """Базовий клас для Node плагінів."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Унікальне ім'я плагіна."""
        pass
    
    @property
    @abstractmethod
    def plugin_type(self) -> NodePluginType:
        """Тип/етап виконання плагіна."""
        pass
    
    @abstractmethod
    def execute(self, context: NodePluginContext) -> NodePluginContext:
        """Виконує логіку плагіна."""
        pass
    
    def setup(self):
        """Ініціалізація (опціонально)."""
        pass
    
    def teardown(self):
        """Очищення ресурсів (опціонально)."""
        pass
```

### Типи плагінів (NodePluginType)

```python
class NodePluginType(str, Enum):
    ON_NODE_CREATED = "on_node_created"  # При створенні Node
    ON_BEFORE_SCAN = "on_before_scan"    # Перед fetch
    ON_HTML_PARSED = "on_html_parsed"    # Після парсингу HTML
    ON_AFTER_SCAN = "on_after_scan"      # Після всіх плагінів
```

### NodePluginContext

```python
@dataclass
class NodePluginContext:
    """Контекст для Node плагінів."""
    
    # Завжди доступно
    node: Node                          # Поточна нода
    url: str                            # URL сторінки
    depth: int                          # Глибина
    should_scan: bool                   # Чи сканувати (можна змінити)
    can_create_edges: bool              # Чи створювати edges (можна змінити)
    
    # Доступно на HTML_STAGE
    html: Optional[str] = None          # HTML контент
    html_tree: Optional[Any] = None     # BeautifulSoup/lxml дерево
    parser: Optional[BaseAdapter] = None # Tree adapter
    
    # Результати (модифікуються плагінами)
    metadata: Dict[str, Any] = field(default_factory=dict)
    user_data: Dict[str, Any] = field(default_factory=dict)
    extracted_links: List[str] = field(default_factory=list)
```

### Порядок виконання

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      NODE PLUGIN EXECUTION ORDER                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. Node(url="...") створюється                                             │
│     │                                                                       │
│     ▼                                                                       │
│  ┌─────────────────────────────────────────┐                                │
│  │ ON_NODE_CREATED plugins                 │  URL_STAGE                     │
│  │                                         │                                │
│  │ Доступно: url, depth                    │                                │
│  │ Можна змінити: should_scan,             │                                │
│  │                can_create_edges         │                                │
│  │                                         │                                │
│  │ Use cases:                              │                                │
│  │ • Аналіз URL на ключові слова           │                                │
│  │ • Встановлення пріоритету               │                                │
│  │ • Рішення чи сканувати                  │                                │
│  └─────────────────────────────────────────┘                                │
│     │                                                                       │
│     │ if should_scan == True                                                │
│     ▼                                                                       │
│  ┌─────────────────────────────────────────┐                                │
│  │ ON_BEFORE_SCAN plugins                  │  HTML_STAGE start              │
│  │                                         │                                │
│  │ Доступно: url, depth, should_scan       │                                │
│  │ Можна: останнє рішення перед fetch      │                                │
│  │                                         │                                │
│  │ Use cases:                              │                                │
│  │ • Перевірка robots.txt                  │                                │
│  │ • Rate limit check                      │                                │
│  └─────────────────────────────────────────┘                                │
│     │                                                                       │
│     │ Driver.fetch(url) → html                                              │
│     │ Parser.parse(html) → html_tree                                        │
│     ▼                                                                       │
│  ┌─────────────────────────────────────────┐                                │
│  │ ON_HTML_PARSED plugins                  │  HTML_STAGE                    │
│  │                                         │                                │
│  │ Доступно: html, html_tree, parser       │                                │
│  │                                         │                                │
│  │ Заповнюють:                             │                                │
│  │ • metadata (title, h1, description)     │                                │
│  │ • extracted_links (посилання)           │                                │
│  │ • user_data (phones, emails, тощо)      │                                │
│  │                                         │                                │
│  │ Use cases:                              │                                │
│  │ • MetadataExtractor                     │                                │
│  │ • LinkExtractor                         │                                │
│  │ • PhoneExtractor                        │                                │
│  │ • EmailExtractor                        │                                │
│  │ • PriceExtractor                        │                                │
│  └─────────────────────────────────────────┘                                │
│     │                                                                       │
│     │ _update_from_context() - metadata → node                              │
│     ▼                                                                       │
│  ┌─────────────────────────────────────────┐                                │
│  │ ON_AFTER_SCAN plugins                   │  HTML_STAGE end                │
│  │                                         │                                │
│  │ Доступно: все + заповнені metadata      │                                │
│  │                                         │                                │
│  │ Use cases:                              │                                │
│  │ • Vectorization (embeddings)            │                                │
│  │ • ML analysis                           │                                │
│  │ • Link filtering                        │                                │
│  │ • Dynamic priorities                    │                                │
│  │ • Explicit filter override              │                                │
│  │ • Stats export                          │                                │
│  └─────────────────────────────────────────┘                                │
│     │                                                                       │
│     ▼                                                                       │
│  content_hash обчислюється                                                  │
│  HTML видаляється з пам'яті                                                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Middleware

### Базовий клас

```python
from abc import ABC, abstractmethod
from graph_crawler.extensions.middleware import MiddlewareType

class BaseMiddleware(ABC):
    """Базовий клас для Middleware."""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.enabled = True
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Унікальне ім'я middleware."""
        pass
    
    @property
    @abstractmethod
    def middleware_type(self) -> MiddlewareType:
        """Тип middleware (коли виконується)."""
        pass
    
    @abstractmethod
    def process(self, context: MiddlewareContext) -> MiddlewareContext:
        """Обробляє контекст (sync або async)."""
        pass
    
    def setup(self):
        """Ініціалізація."""
        pass
    
    def teardown(self):
        """Очищення."""
        pass
```

### Типи middleware (MiddlewareType)

```python
class MiddlewareType(str, Enum):
    PRE_REQUEST = "pre_request"    # Перед HTTP запитом
    POST_REQUEST = "post_request"  # Після HTTP запиту
    POST_RESPONSE = "post_response" # Після обробки response
```

### MiddlewareContext

```python
@dataclass
class MiddlewareContext:
    """Контекст для Middleware."""
    
    # Request
    url: str
    headers: Dict[str, str] = field(default_factory=dict)
    cookies: Dict[str, str] = field(default_factory=dict)
    proxy: Optional[str] = None
    timeout: int = 30
    
    # Response (після fetch)
    response: Optional[FetchResponse] = None
    error: Optional[Exception] = None
    
    # Control
    skip_request: bool = False      # True = пропустити fetch (cache hit)
    retry_count: int = 0
    max_retries: int = 3
```

### MiddlewareChain

```python
from graph_crawler.extensions.middleware import MiddlewareChain

chain = MiddlewareChain()

# Додавання middleware (порядок важливий!)
chain.add(RateLimitMiddleware(requests_per_second=10))
chain.add(ProxyMiddleware(proxies=[...]))
chain.add(UserAgentMiddleware(agents=[...]))
chain.add(CacheMiddleware(ttl=3600))
chain.add(RetryMiddleware(max_retries=3))

# Виконання
context = MiddlewareContext(url="https://example.com")
context = await chain.execute(MiddlewareType.PRE_REQUEST, context)

# Після fetch
context.response = response
context = await chain.execute(MiddlewareType.POST_REQUEST, context)

# Статистика
stats = chain.get_stats()
# {'pre_request': ['rate_limit', 'proxy', 'user_agent', 'cache'],
#  'post_request': ['retry']}
```

---

## Реєстрація та життєвий цикл

### NodePluginManager

```python
from graph_crawler.extensions.plugins.node import NodePluginManager

pm = NodePluginManager(event_bus=event_bus)

# Реєстрація
pm.register(MetadataExtractorPlugin())
pm.register(LinkExtractorPlugin())
pm.register(MyCustomPlugin())

# Виконання (викликається автоматично в Node.process_html)
context = await pm.execute(NodePluginType.ON_HTML_PARSED, context)

# Sync виконання (для ON_NODE_CREATED)
context = pm.execute_sync(NodePluginType.ON_NODE_CREATED, context)
```

### Дефолтні плагіни

```python
from graph_crawler.extensions.plugins.node import get_default_node_plugins

default_plugins = get_default_node_plugins()
# [MetadataExtractorPlugin, LinkExtractorPlugin, TextExtractorPlugin]

# Використання з кастомними
all_plugins = default_plugins + [MyPlugin()]
graph = crawl(url, plugins=all_plugins)
```

### Життєвий цикл

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        PLUGIN LIFECYCLE                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. CREATION                                                                │
│     plugin = MyPlugin(config={...})                                         │
│                                                                             │
│  2. REGISTRATION                                                            │
│     plugin_manager.register(plugin)                                         │
│     │                                                                       │
│     └──▶ plugin.setup() викликається                                        │
│                                                                             │
│  3. EXECUTION (для кожної Node)                                             │
│     context = plugin.execute(context)                                       │
│                                                                             │
│  4. TEARDOWN (при завершенні Spider)                                        │
│     plugin.teardown()                                                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Вбудовані плагіни

### MetadataExtractorPlugin

```python
# Автоматично витягує:
# metadata['title']       - <title> tag
# metadata['h1']          - перший <h1>
# metadata['description'] - meta description
# metadata['keywords']    - meta keywords
# metadata['canonical']   - canonical URL
# metadata['language']    - html lang attribute
```

### LinkExtractorPlugin

```python
# Витягує всі <a href> посилання
# context.extracted_links = ['https://...', ...]
```

### PhoneExtractorPlugin

```python
# Витягує телефони:
# user_data['phones'] = ['380501234567', ...]

# Підтримує формати:
# UA: +380XXXXXXXXX, 0XXXXXXXXX, (0XX) XXX-XX-XX
# RU: +7XXXXXXXXXX
# US: +1XXXXXXXXXX, (XXX) XXX-XXXX
# tel: links
```

### EmailExtractorPlugin

```python
# Витягує email адреси:
# user_data['emails'] = ['info@example.com', ...]

# RFC 5322 compliant regex
# mailto: links parsing
# Фільтрація fake domains
```

### PriceExtractorPlugin

```python
# Витягує ціни:
# user_data['prices'] = [
#     {'value': 1000, 'currency': 'USD', 'original': '$1,000'},
#     ...
# ]

# Підтримує:
# USD: $50, $1,000, $1.5k, $1M
# EUR: €50, 50€, 50 EUR
# UAH: ₴50, 50 грн, 50 гривень
# Salary ranges: $50k - $70k
```

### RealTimeVectorizerPlugin

```python
# Векторизує текст сторінки:
# user_data['embedding'] = [0.1, 0.2, ...]

# Потребує: pip install -e ".[embeddings]"
```

---

## Приклади кастомних плагінів

### Приклад 1: SEO Analyzer

```python
class SEOAnalyzerPlugin(BaseNodePlugin):
    """Аналізує SEO метрики сторінки."""
    
    @property
    def name(self):
        return "seo_analyzer"
    
    @property
    def plugin_type(self):
        return NodePluginType.ON_HTML_PARSED
    
    def execute(self, context):
        tree = context.html_tree
        parser = context.parser
        
        seo_data = {
            'title_length': len(context.metadata.get('title', '') or ''),
            'h1_count': len(tree.find_all('h1')),
            'h2_count': len(tree.find_all('h2')),
            'img_without_alt': len([img for img in tree.find_all('img') if not img.get('alt')]),
            'has_meta_description': bool(context.metadata.get('description')),
            'internal_links': 0,
            'external_links': 0,
        }
        
        # Classify links
        base_domain = urlparse(context.url).netloc
        for link in context.extracted_links:
            if urlparse(link).netloc == base_domain:
                seo_data['internal_links'] += 1
            else:
                seo_data['external_links'] += 1
        
        # SEO score
        score = 0
        if 30 <= seo_data['title_length'] <= 60:
            score += 20
        if seo_data['h1_count'] == 1:
            score += 20
        if seo_data['has_meta_description']:
            score += 20
        if seo_data['img_without_alt'] == 0:
            score += 20
        if seo_data['internal_links'] > 0:
            score += 20
        
        seo_data['score'] = score
        context.user_data['seo'] = seo_data
        
        return context
```

### Приклад 2: ML Decision Plugin

```python
class MLDecisionPlugin(BaseNodePlugin):
    """
    ML плагін для інтелектуального вибору посилань.
    
    Демонструє 3 механізми гнучкого ядра:
    1. Dynamic Priority - встановлює пріоритети для child нод
    2. Explicit Filter Override - перебиває domain/path фільтри
    3. Link Filtering - фільтрує посилання на основі ML
    """
    
    def __init__(self, target_keywords: List[str] = None):
        super().__init__()
        self.target_keywords = target_keywords or ['job', 'vacancy', 'career']
    
    @property
    def name(self):
        return "ml_decision"
    
    @property
    def plugin_type(self):
        return NodePluginType.ON_AFTER_SCAN
    
    def execute(self, context):
        # ML аналіз контенту
        text = context.user_data.get('text_content', '')
        relevance_score = self._calculate_relevance(text)
        
        context.user_data['ml_score'] = relevance_score
        
        # Низька релевантність - пропускаємо всі посилання
        if relevance_score < 0.3:
            context.extracted_links = []
            return context
        
        # Аналізуємо посилання
        selected_links = []
        priorities = {}
        explicit_decisions = {}
        
        for link in context.extracted_links:
            link_score = self._score_link(link)
            
            if link_score > 0.5:
                selected_links.append(link)
                
                # МЕХАНІЗМ 1: Dynamic Priority
                if link_score > 0.8:
                    priorities[link] = 10  # Високий пріоритет
                elif link_score > 0.6:
                    priorities[link] = 7
                else:
                    priorities[link] = 5
                
                # МЕХАНІЗМ 2: Explicit Filter Override
                # Дозволяємо зовнішні домени якщо дуже релевантні
                if link_score > 0.9:
                    explicit_decisions[link] = True  # Перебиває domain filter!
        
        context.extracted_links = selected_links
        context.user_data['child_priorities'] = priorities
        context.user_data['explicit_scan_decisions'] = explicit_decisions
        
        return context
    
    def _calculate_relevance(self, text: str) -> float:
        text_lower = text.lower()
        matches = sum(1 for kw in self.target_keywords if kw in text_lower)
        return min(matches / len(self.target_keywords), 1.0)
    
    def _score_link(self, link: str) -> float:
        link_lower = link.lower()
        if any(kw in link_lower for kw in self.target_keywords):
            return 0.9
        return 0.3
```

### Приклад 3: Custom Middleware

```python
class AuthMiddleware(BaseMiddleware):
    """Додає авторизацію до запитів."""
    
    def __init__(self, token: str):
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


class MetricsMiddleware(BaseMiddleware):
    """Збирає метрики запитів."""
    
    def __init__(self):
        super().__init__()
        self.requests_count = 0
        self.errors_count = 0
        self.total_time = 0
    
    @property
    def name(self):
        return "metrics"
    
    @property
    def middleware_type(self):
        return MiddlewareType.POST_REQUEST
    
    def process(self, context):
        self.requests_count += 1
        
        if context.error:
            self.errors_count += 1
        
        if context.response:
            # Припускаємо що час збережено в metadata
            self.total_time += context.response.headers.get('x-fetch-time', 0)
        
        return context
    
    def get_stats(self):
        return {
            'requests': self.requests_count,
            'errors': self.errors_count,
            'avg_time': self.total_time / max(self.requests_count, 1)
        }
```
