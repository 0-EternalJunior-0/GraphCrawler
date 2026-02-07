# Plugin System

> **Час читання:** 15 хвилин  
> **Рівень:** Середній

Повна документація системи плагінів GraphCrawler.

---

## Огляд

GraphCrawler використовує plugin-based архітектуру для:
- Екстракції даних (метадані, посилання, телефони, ціни, emails)
- Трансформації (векторизація, ML аналіз)
- Фільтрації (динамічні пріоритети, URL фільтрація)

---

## Типи плагінів

```python
from graph_crawler.extensions.plugins.node import NodePluginType

# Доступні типи:
NodePluginType.ON_NODE_CREATED   # При створенні Node
NodePluginType.ON_BEFORE_SCAN    # Перед fetch
NodePluginType.ON_HTML_PARSED    # Після парсингу HTML
NodePluginType.ON_AFTER_SCAN     # Після всіх плагінів
NodePluginType.BEFORE_CRAWL      # Перед початком краулінгу
NodePluginType.AFTER_CRAWL       # Після завершення краулінгу
```

### Життєвий цикл

```
Node створено
    │
    ▼
[ON_NODE_CREATED] ← URL аналіз, пріоритети, should_scan
    │
    ▼ (if should_scan)
[ON_BEFORE_SCAN] ← Перевірки перед fetch
    │
    ▼
    HTTP Fetch + HTML Parse
    │
    ▼
[ON_HTML_PARSED] ← Екстракція даних
    │
    ▼
[ON_AFTER_SCAN] ← Векторизація, ML, аналітика
    │
    ▼
Node завершено
```

---

## Вбудовані плагіни

### MetadataExtractorPlugin

Витягує метадані сторінки:

```python
import graph_crawler as gc
from graph_crawler.extensions.plugins.node import MetadataExtractorPlugin

graph = gc.crawl(
    "https://example.com",
    plugins=[MetadataExtractorPlugin()]
)

for node in graph:
    print(f"Title: {node.get_title()}")
    print(f"H1: {node.get_h1()}")
    print(f"Description: {node.get_description()}")
```

**Витягує:**
- `title` - `<title>` tag
- `h1` - перший `<h1>`
- `description` - meta description
- `keywords` - meta keywords
- `canonical` - canonical URL
- `language` - html lang

### LinkExtractorPlugin

Витягує всі посилання:

```python
from graph_crawler.extensions.plugins.node import LinkExtractorPlugin

graph = gc.crawl(
    "https://example.com",
    plugins=[LinkExtractorPlugin()]
)
```

### TextExtractorPlugin

Витягує текстовий контент:

```python
from graph_crawler.extensions.plugins.node import TextExtractorPlugin

graph = gc.crawl(
    "https://example.com",
    plugins=[TextExtractorPlugin()]
)

for node in graph:
    text = node.user_data.get('text')
    print(f"{node.url}: {len(text)} chars")
```

### PhoneExtractorPlugin

Витягує телефонні номери:

```python
from graph_crawler.extensions.plugins.node.extractors import PhoneExtractorPlugin

graph = gc.crawl(
    "https://example.com",
    plugins=[PhoneExtractorPlugin()]
)

for node in graph:
    phones = node.user_data.get('phones', [])
    phone_count = node.user_data.get('phone_count', 0)
    print(f"{node.url}: {phones}")
```

**Підтримує формати:**
- UA: `+380XXXXXXXXX`, `380XXXXXXXXX`, `0XXXXXXXXX`, `(0XX) XXX-XX-XX`
- RU: `+7XXXXXXXXXX`, `7XXXXXXXXXX`
- US: `+1XXXXXXXXXX`, `(XXX) XXX-XXXX`
- International: `+XXXXXXXXXXXX`
- `tel:` links

### EmailExtractorPlugin

Витягує email адреси:

```python
from graph_crawler.extensions.plugins.node.extractors import EmailExtractorPlugin

graph = gc.crawl(
    "https://example.com",
    plugins=[EmailExtractorPlugin()]
)

for node in graph:
    emails = node.user_data.get('emails', [])
    email_count = node.user_data.get('email_count', 0)
    print(f"{node.url}: {emails}")
```

**Features:**
- RFC 5322 compliant regex
- `mailto:` links parsing
- Фільтрація fake domains (example.com, test.com тощо)
- Автоматична дедуплікація (lowercase)

### PriceExtractorPlugin

Витягує ціни:

```python
from graph_crawler.extensions.plugins.node.extractors import PriceExtractorPlugin

graph = gc.crawl(
    "https://shop.example.com",
    plugins=[PriceExtractorPlugin()]
)

for node in graph:
    prices = node.user_data.get('prices', [])
    for p in prices:
        print(f"{p['value']} {p['currency']} (original: {p['original']})")
```

**Підтримує:**
- USD: `$50`, `$1,000`, `$1.5k`, `$1M`
- EUR: `€50`, `50€`, `50 EUR`
- UAH: `₴50`, `50 грн`, `50 гривень`
- Salary ranges: `$50k - $70k`, `від 30000 грн`

### RealTimeVectorizerPlugin

Векторизує текст в реальному часі:

```python
from graph_crawler.extensions.plugins.node.vectorization import RealTimeVectorizerPlugin

plugin = RealTimeVectorizerPlugin(config={
    'enabled': True,
    'model_name': 'paraphrase-multilingual-MiniLM-L12-v2',
    'vector_size': 512,
    'field_name': 'text',          # Поле з текстом
    'skip_field': 'not_vector',    # Пропустити якщо True
    'vector_key': 'vector_512_realtime'  # Ключ для збереження
})

graph = gc.crawl(
    "https://example.com",
    plugins=[plugin]
)

for node in graph:
    embedding = node.user_data.get('vector_512_realtime')
    if embedding:
        print(f"{node.url}: {len(embedding)} dimensions")
```

**Параметри config:**
- `enabled` - чи увімкнено плагін (True)
- `model_name` - модель sentence-transformers
- `vector_size` - розмір вектору (512)
- `field_name` - поле з текстом ('text')
- `skip_field` - поле-прапорець для пропуску ('not_vector')
- `vector_key` - ключ для збереження вектору

**Важливо:** Плагін є async і виконує векторизацію в ThreadPoolExecutor.

Потребує: `pip install graph-crawler[embeddings]`

---

## Створення кастомного плагіна

### Базовий шаблон

```python
from graph_crawler.extensions.plugins.node import BaseNodePlugin, NodePluginType, NodePluginContext

class MyPlugin(BaseNodePlugin):
    """Опис плагіна."""
    
    @property
    def name(self) -> str:
        return "my_plugin"
    
    @property
    def plugin_type(self) -> NodePluginType:
        return NodePluginType.ON_HTML_PARSED
    
    def execute(self, context: NodePluginContext) -> NodePluginContext:
        # Ваша логіка
        context.user_data['my_data'] = "value"
        return context
    
    def setup(self):
        """Ініціалізація (опціонально)."""
        pass
    
    def teardown(self):
        """Очищення (опціонально)."""
        pass
```

### Async плагін

```python
class MyAsyncPlugin(BaseNodePlugin):
    """Async плагін з CPU-bound операціями."""
    
    @property
    def name(self) -> str:
        return "my_async_plugin"
    
    @property
    def plugin_type(self) -> NodePluginType:
        return NodePluginType.ON_AFTER_SCAN
    
    async def execute(self, context: NodePluginContext) -> NodePluginContext:
        import asyncio
        from concurrent.futures import ThreadPoolExecutor
        
        loop = asyncio.get_event_loop()
        
        # CPU-bound операція в ThreadPoolExecutor
        result = await loop.run_in_executor(
            None,  # default executor
            self._cpu_bound_task,
            context.user_data.get('text', '')
        )
        
        context.user_data['async_result'] = result
        return context
    
    def _cpu_bound_task(self, text: str):
        # Важка обробка
        return len(text)
```

### NodePluginContext

```python
from pydantic import BaseModel

class NodePluginContext(BaseModel):
    """Pydantic BaseModel для контексту плагіна."""
    
    # Завжди доступно
    node: Any                          # Поточна нода
    url: str                           # URL
    depth: int                         # Глибина
    should_scan: bool                  # Сканувати? (можна змінити)
    can_create_edges: bool             # Створювати edges?
    
    # Тільки на HTML етапі
    html: Optional[str] = None          # HTML контент
    html_tree: Optional[Any] = None     # BeautifulSoup/parser об'єкт
    parser: Optional[Any] = None        # Tree adapter/parser instance
    
    # Результати (модифікуються плагінами)
    metadata: Dict[str, Any] = {}       # Метадані
    user_data: Dict[str, Any] = {}      # Користувацькі дані
    extracted_links: List[str] = []     # Посилання
    
    # Флаги
    skip_link_extraction: bool = False
    skip_metadata_extraction: bool = False
    
    # Методи Law of Demeter
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Безпечно отримує значення з metadata."""
        return self.metadata.get(key, default)
    
    def set_metadata(self, key: str, value: Any) -> None:
        """Встановлює значення в metadata."""
        self.metadata[key] = value
    
    def has_metadata(self, key: str) -> bool:
        """Перевіряє наявність ключа в metadata."""
        return key in self.metadata
```

---

## Приклади

### SEO Analyzer

```python
class SEOAnalyzerPlugin(BaseNodePlugin):
    """Аналізує SEO метрики."""
    
    @property
    def name(self) -> str:
        return "seo_analyzer"
    
    @property
    def plugin_type(self) -> NodePluginType:
        return NodePluginType.ON_HTML_PARSED
    
    def execute(self, context: NodePluginContext) -> NodePluginContext:
        tree = context.html_tree
        
        seo = {
            'title_length': len(context.metadata.get('title', '') or ''),
            'h1_count': len(tree.find_all('h1')),
            'h2_count': len(tree.find_all('h2')),
            'img_without_alt': len([i for i in tree.find_all('img') if not i.get('alt')]),
            'has_meta_description': bool(context.metadata.get('description')),
        }
        
        # Оцінка
        score = 0
        if 30 <= seo['title_length'] <= 60:
            score += 25
        if seo['h1_count'] == 1:
            score += 25
        if seo['has_meta_description']:
            score += 25
        if seo['img_without_alt'] == 0:
            score += 25
        
        seo['score'] = score
        context.user_data['seo'] = seo
        
        return context
```

### Social Links Extractor

```python
import re

class SocialLinksPlugin(BaseNodePlugin):
    """Витягує посилання на соцмережі."""
    
    PATTERNS = {
        'facebook': r'facebook\.com/[\w.]+',
        'twitter': r'twitter\.com/[\w]+',
        'instagram': r'instagram\.com/[\w.]+',
        'linkedin': r'linkedin\.com/(in|company)/[\w-]+',
        'youtube': r'youtube\.com/(c|channel)/[\w-]+',
    }
    
    @property
    def name(self) -> str:
        return "social_links"
    
    @property
    def plugin_type(self) -> NodePluginType:
        return NodePluginType.ON_HTML_PARSED
    
    def execute(self, context: NodePluginContext) -> NodePluginContext:
        html = context.html or ''
        social = {}
        
        for platform, pattern in self.PATTERNS.items():
            matches = re.findall(pattern, html, re.IGNORECASE)
            if matches:
                social[platform] = list(set(matches))
        
        context.user_data['social_links'] = social
        return context
```

### Dynamic Priority

```python
class DynamicPriorityPlugin(BaseNodePlugin):
    """Встановлює пріоритет на основі контенту."""
    
    def __init__(self, keywords, config=None):
        super().__init__(config)
        self.keywords = keywords
    
    @property
    def name(self) -> str:
        return "dynamic_priority"
    
    @property
    def plugin_type(self) -> NodePluginType:
        return NodePluginType.ON_AFTER_SCAN
    
    def execute(self, context: NodePluginContext) -> NodePluginContext:
        text = context.user_data.get('text_content', '').lower()
        
        priorities = {}
        for link in context.extracted_links:
            link_lower = link.lower()
            # Високий пріоритет якщо є ключові слова
            if any(kw in link_lower for kw in self.keywords):
                priorities[link] = 10
        
        context.user_data['child_priorities'] = priorities
        return context

# Використання
graph = gc.crawl(
    "https://example.com",
    plugins=[DynamicPriorityPlugin(['product', 'buy', 'price'])]
)
```

---

## Комбінування плагінів

```python
from graph_crawler.extensions.plugins.node import (
    MetadataExtractorPlugin,
    LinkExtractorPlugin,
    TextExtractorPlugin,
)
from graph_crawler.extensions.plugins.node.extractors import (
    PhoneExtractorPlugin,
    EmailExtractorPlugin,
    PriceExtractorPlugin,
)

graph = gc.crawl(
    "https://shop.example.com",
    plugins=[
        MetadataExtractorPlugin(),
        LinkExtractorPlugin(),
        TextExtractorPlugin(),
        PhoneExtractorPlugin(),
        EmailExtractorPlugin(),
        PriceExtractorPlugin(),
        SEOAnalyzerPlugin(),          # Кастомний
        SocialLinksPlugin(),          # Кастомний
    ]
)
```

---

## SmartPageFinderPlugin (ML)

Інтелектуальний пошук потрібних сторінок за допомогою AI (g4f):

```python
from graph_crawler.extensions.plugins.node import (
    SmartPageFinderPlugin, 
    SmartFinderNode,
    RelevanceLevel,
)

# Створюємо плагін з промптом
plugin = SmartPageFinderPlugin(
    search_prompt="Шукаю сторінки з автомобілями BMW X5 2024 року",
    config={
        'min_relevance_score': 0.7,
        'priority_boost': 10,
        'analyze_links': True,
        'analyze_content': True,
        'max_text_length': 4000,
        'model': 'gpt-4o-mini',
        'cache_results': True,
        'strict_mode': False,
    }
)

# Краулінг з ML пошуком
graph = gc.crawl(
    "https://auto-shop.com",
    plugins=[plugin],
    node_class=SmartFinderNode  # Опціонально
)

# Отримання знайдених сторінок
target_pages = [n for n in graph if n.user_data.get('is_target_page')]
for page in target_pages:
    print(f"Found: {page.url}")
    print(f"  Relevance: {page.user_data.get('relevance_score')}")
    print(f"  Level: {page.user_data.get('relevance_level')}")
    print(f"  Reason: {page.user_data.get('relevance_reason')}")
```

**Параметри config:**
- `min_relevance_score` - мінімальний score (0.0-1.0) для target page (0.7)
- `priority_boost` - додатковий пріоритет для релевантних посилань (10)
- `analyze_links` - аналізувати посилання на релевантність (True)
- `analyze_content` - аналізувати контент сторінки (True)
- `max_text_length` - максимальна довжина тексту для аналізу (4000)
- `model` - модель g4f ('gpt-4o-mini')
- `provider` - провайдер g4f (None = автовибір)
- `cache_results` - кешувати результати (True)
- `strict_mode` - тільки високорелевантні (False)

**Результати в user_data:**
- `is_target_page` - чи це шукана сторінка
- `relevance_score` - score релевантності 0.0-1.0
- `relevance_level` - рівень (high/medium/low/irrelevant)
- `relevance_reason` - пояснення оцінки
- `child_priorities` - пріоритети для дочірніх посилань
- `explicit_scan_decisions` - рішення про сканування URL

**RelevanceLevel enum:**
- `HIGH` (0.8-1.0) - точно те, що шукаємо
- `MEDIUM` (0.5-0.8) - можливо релевантна
- `LOW` (0.2-0.5) - малоймовірно
- `IRRELEVANT` (0.0-0.2) - точно не те

---

## BatchVectorizerPlugin

Batch векторизація для великих обсягів:

```python
from graph_crawler.extensions.plugins.node.vectorization import BatchVectorizerPlugin

plugin = BatchVectorizerPlugin(config={
    'text_content': 'text',                    # ОБОВ'ЯЗКОВИЙ!
    'model_name': 'paraphrase-multilingual-MiniLM-L12-v2',
    'vector_size': 512,
    'batch_size': 64,
    'skip_nodes': {'not_vector'},              # Set полів для пропуску
    'vector_key': 'vector_512_batch',
})

graph = gc.crawl("https://docs.example.com", plugins=[plugin])

# Статистика
stats = plugin.get_stats()
print(f"Total: {stats['total_nodes']}")
print(f"Vectorized: {stats['vectorized_nodes']}")
print(f"Skipped: {stats['skipped_nodes']}")
```

**Параметри config:**
- `text_content` - ім'я поля з текстом (ОБОВ'ЯЗКОВИЙ!)
- `model_name` - модель sentence-transformers
- `vector_size` - розмір вектору (512)
- `batch_size` - розмір батчу (64)
- `skip_nodes` - множина полів-прапорців для пропуску
- `vector_key` - ключ для збереження

**Переваги batch підходу:**
- До 10x швидше ніж real-time при великих графах
- Ефективне використання GPU
- Менше overhead на завантаження моделі

Потребує: `pip install graph-crawler[embeddings]`

---

## Утиліти векторизації

```python
from graph_crawler.extensions.plugins.node.vectorization import (
    search,
    cluster,
    compare,
    vectorize_text,
    vectorize_batch,
    cosine_similarity,
    euclidean_distance,
    dot_product,
    SimilarityMetric,
    ClusteringMethod,
    clear_model_cache,
)

# Векторний пошук
results = search(graph, "Python developer", top_k=10)

# Кластеризація
clusters = cluster(graph, method=ClusteringMethod.KMEANS, n_clusters=5)

# Порівняння векторів
similarity = compare(vector1, vector2)  # вектор vs вектор
similarity = compare(vector, "текст")   # вектор vs текст (автовекторизація)

# Пряма векторизація
vector = vectorize_text("Hello world", model_name="all-MiniLM-L6-v2")
vectors = vectorize_batch(["text1", "text2"], batch_size=32)

# Метрики подібності
sim = cosine_similarity(v1, v2)
dist = euclidean_distance(v1, v2)
dot = dot_product(v1, v2)

# Очистити кеш моделей
clear_model_cache()
```

---

## Наступні кроки

- [Structured Data →](structured-data.md)
- [Custom Extractors →](custom-extractors.md)
- [Architecture: Plugin System →](../architecture/PLUGIN_SYSTEM.md)
