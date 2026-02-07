# Custom Extractors

> **Час читання:** 10 хвилин  
> **Рівень:** Середній - Senior

Створення власних екстракторів даних для GraphCrawler.

---

## Огляд

Custom extractors дозволяють витягувати специфічні дані з HTML сторінок. Всі екстрактори наслідують `BaseNodePlugin` і працюють в lifecycle системі плагінів.

**Типові use cases:**
- CSS селектор екстракція
- XPath екстракція
- Regex екстракція
- Таблиці та JSON дані
- Комбіновані екстрактори

---

## CSS Selector Extractor

```python
from graph_crawler.extensions.plugins.node import BaseNodePlugin, NodePluginType, NodePluginContext

class CSSExtractorPlugin(BaseNodePlugin):
    """Витягує дані за CSS селекторами."""
    
    def __init__(self, selectors: dict, config: dict = None):
        """
        Args:
            selectors: dict з {key: css_selector}
            config: конфігурація плагіна
        """
        super().__init__(config)
        self.selectors = selectors
    
    @property
    def name(self) -> str:
        return "css_extractor"
    
    @property
    def plugin_type(self) -> NodePluginType:
        return NodePluginType.ON_HTML_PARSED
    
    def execute(self, context: NodePluginContext) -> NodePluginContext:
        tree = context.html_tree
        if not tree:
            context.user_data['css_data'] = {}
            return context
        
        extracted = {}
        
        for key, selector in self.selectors.items():
            elements = tree.select(selector)
            if elements:
                if len(elements) == 1:
                    extracted[key] = elements[0].get_text(strip=True)
                else:
                    extracted[key] = [e.get_text(strip=True) for e in elements]
        
        context.user_data['css_data'] = extracted
        return context

# Використання
graph = gc.crawl(
    "https://example.com",
    plugins=[CSSExtractorPlugin({
        'title': 'h1.product-title',
        'price': '.price-current',
        'rating': '.rating-value',
        'reviews': '.review-text',
    })]
)
```

---

## XPath Extractor

```python
from lxml import etree

class XPathExtractorPlugin(BaseNodePlugin):
    """Витягує дані за XPath."""
    
    def __init__(self, paths: dict, config: dict = None):
        super().__init__(config)
        self.paths = paths
    
    @property
    def name(self) -> str:
        return "xpath_extractor"
    
    @property
    def plugin_type(self) -> NodePluginType:
        return NodePluginType.ON_HTML_PARSED
    
    def execute(self, context: NodePluginContext) -> NodePluginContext:
        html = context.html
        if not html:
            context.user_data['xpath_data'] = {}
            return context
        
        tree = etree.HTML(html)
        extracted = {}
        
        for key, xpath in self.paths.items():
            try:
                results = tree.xpath(xpath)
                if results:
                    if len(results) == 1:
                        # Конвертуємо Element в текст якщо потрібно
                        if hasattr(results[0], 'text'):
                            extracted[key] = results[0].text or ''
                        else:
                            extracted[key] = str(results[0])
                    else:
                        extracted[key] = [
                            r.text if hasattr(r, 'text') else str(r) 
                            for r in results
                        ]
            except Exception as e:
                # Log error but continue
                pass
        
        context.user_data['xpath_data'] = extracted
        return context

# Використання
graph = gc.crawl(
    "https://example.com",
    plugins=[XPathExtractorPlugin({
        'title': '//h1[@class="title"]/text()',
        'links': '//a/@href',
        'images': '//img/@src',
    })]
)
```

---

## Regex Extractor

```python
import re
from typing import Dict, Pattern

class RegexExtractorPlugin(BaseNodePlugin):
    """Витягує дані за regex patterns."""
    
    def __init__(self, patterns: Dict[str, str], config: dict = None):
        super().__init__(config)
        self.patterns: Dict[str, Pattern] = {
            key: re.compile(pattern, re.IGNORECASE)
            for key, pattern in patterns.items()
        }
    
    @property
    def name(self) -> str:
        return "regex_extractor"
    
    @property
    def plugin_type(self) -> NodePluginType:
        return NodePluginType.ON_HTML_PARSED
    
    def execute(self, context: NodePluginContext) -> NodePluginContext:
        html = context.html or ''
        extracted = {}
        
        for key, pattern in self.patterns.items():
            matches = pattern.findall(html)
            if matches:
                # Видаляємо дублікати
                extracted[key] = list(set(matches))
        
        context.user_data['regex_data'] = extracted
        return context

# Використання
graph = gc.crawl(
    "https://example.com",
    plugins=[RegexExtractorPlugin({
        'dates': r'\d{1,2}[./]\d{1,2}[./]\d{2,4}',
        'iban': r'[A-Z]{2}\d{2}[A-Z0-9]{4,30}',
        'ip_addresses': r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}',
        'emails': r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b',
    })]
)
```

---

## Table Extractor

```python
import pandas as pd
from io import StringIO
from typing import List, Dict, Any

class TableExtractorPlugin(BaseNodePlugin):
    """Витягує таблиці зі сторінки."""
    
    @property
    def name(self) -> str:
        return "table_extractor"
    
    @property
    def plugin_type(self) -> NodePluginType:
        return NodePluginType.ON_HTML_PARSED
    
    def execute(self, context: NodePluginContext) -> NodePluginContext:
        html = context.html
        if not html:
            context.user_data['tables'] = []
            context.user_data['table_count'] = 0
            return context
        
        tables: List[List[Dict[str, Any]]] = []
        
        try:
            df_tables = pd.read_html(StringIO(html))
            tables = [
                table.to_dict('records') for table in df_tables
            ]
        except ValueError:
            # Немає таблиць на сторінці
            pass
        except Exception as e:
            # Інші помилки парсингу
            pass
        
        context.user_data['tables'] = tables
        context.user_data['table_count'] = len(tables)
        
        return context

# Використання
graph = gc.crawl(
    "https://example.com",
    plugins=[TableExtractorPlugin()]
)

for node in graph:
    tables = node.user_data.get('tables', [])
    print(f"{node.url}: {len(tables)} tables found")
```

---

## JSON API Extractor

```python
import json
from typing import List, Any

class JSONExtractorPlugin(BaseNodePlugin):
    """Витягує JSON дані зі сторінки (JSON-LD, application/json)."""
    
    @property
    def name(self) -> str:
        return "json_extractor"
    
    @property
    def plugin_type(self) -> NodePluginType:
        return NodePluginType.ON_HTML_PARSED
    
    def execute(self, context: NodePluginContext) -> NodePluginContext:
        tree = context.html_tree
        if not tree:
            context.user_data['json_data'] = []
            return context
        
        json_data: List[Any] = []
        
        # Знайти всі <script type="application/json">
        json_scripts = tree.find_all('script', {'type': 'application/json'})
        for script in json_scripts:
            try:
                if script.string:
                    data = json.loads(script.string)
                    json_data.append({
                        'type': 'application/json',
                        'data': data
                    })
            except (json.JSONDecodeError, TypeError):
                pass
        
        # Знайти JSON-LD (schema.org)
        ld_scripts = tree.find_all('script', {'type': 'application/ld+json'})
        for script in ld_scripts:
            try:
                if script.string:
                    data = json.loads(script.string)
                    json_data.append({
                        'type': 'application/ld+json',
                        'data': data
                    })
            except (json.JSONDecodeError, TypeError):
                pass
        
        context.user_data['json_data'] = json_data
        context.user_data['json_count'] = len(json_data)
        
        return context
```

---

## Async Extractor (CPU-bound)

Для важких операцій використовуйте async з ThreadPoolExecutor:

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial

# ThreadPoolExecutor для CPU-bound операцій
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="extractor_")

class HeavyExtractorPlugin(BaseNodePlugin):
    """Async екстрактор для важких операцій."""
    
    @property
    def name(self) -> str:
        return "heavy_extractor"
    
    @property
    def plugin_type(self) -> NodePluginType:
        return NodePluginType.ON_AFTER_SCAN
    
    async def execute(self, context: NodePluginContext) -> NodePluginContext:
        """Async execute - НЕ блокує event loop."""
        
        text = context.user_data.get('text', '')
        if not text:
            return context
        
        loop = asyncio.get_event_loop()
        
        # Виконуємо CPU-bound операцію в окремому потоці
        result = await loop.run_in_executor(
            _executor,
            partial(self._heavy_processing, text)
        )
        
        context.user_data['heavy_result'] = result
        return context
    
    def _heavy_processing(self, text: str) -> dict:
        """CPU-bound обробка (виконується в thread)."""
        # Тут ваша важка логіка
        return {
            'word_count': len(text.split()),
            'char_count': len(text),
            'processed': True
        }
```

---

## Комбінований Product Extractor

```python
import re
from typing import Optional, List, Dict, Any

class ProductExtractorPlugin(BaseNodePlugin):
    """Комплексний екстрактор продуктів."""
    
    @property
    def name(self) -> str:
        return "product_extractor"
    
    @property
    def plugin_type(self) -> NodePluginType:
        return NodePluginType.ON_HTML_PARSED
    
    def execute(self, context: NodePluginContext) -> NodePluginContext:
        tree = context.html_tree
        if not tree:
            context.user_data['product'] = None
            return context
        
        product = {
            'name': self._extract_name(tree),
            'price': self._extract_price(tree),
            'currency': self._extract_currency(tree),
            'description': self._extract_description(tree),
            'images': self._extract_images(tree),
            'attributes': self._extract_attributes(tree),
            'availability': self._extract_availability(tree),
        }
        
        # Видаляємо None значення
        product = {k: v for k, v in product.items() if v is not None}
        
        context.user_data['product'] = product if product else None
        return context
    
    def _extract_name(self, tree) -> Optional[str]:
        """Витягує назву продукту."""
        selectors = [
            'h1.product-title',
            'h1.product-name',
            '[itemprop="name"]',
            '.product h1',
            'h1[data-product-title]',
        ]
        for sel in selectors:
            elem = tree.select_one(sel)
            if elem:
                return elem.get_text(strip=True)
        return None
    
    def _extract_price(self, tree) -> Optional[float]:
        """Витягує ціну продукту."""
        selectors = [
            '[itemprop="price"]',
            '.price-current',
            '.product-price',
            '[data-price]',
            '.price',
        ]
        for sel in selectors:
            elem = tree.select_one(sel)
            if elem:
                text = elem.get_text(strip=True)
                # Парсинг ціни - витягуємо числа
                match = re.search(r'[\d,]+\.?\d*', text.replace(',', ''))
                if match:
                    try:
                        return float(match.group())
                    except ValueError:
                        pass
        return None
    
    def _extract_currency(self, tree) -> Optional[str]:
        """Витягує валюту."""
        elem = tree.select_one('[itemprop="priceCurrency"]')
        if elem:
            return elem.get('content') or elem.get_text(strip=True)
        
        # Шукаємо в тексті ціни
        price_elem = tree.select_one('.price, .product-price')
        if price_elem:
            text = price_elem.get_text()
            if '$' in text:
                return 'USD'
            elif '€' in text:
                return 'EUR'
            elif '₴' in text or 'грн' in text:
                return 'UAH'
        return None
    
    def _extract_description(self, tree) -> Optional[str]:
        """Витягує опис продукту."""
        selectors = [
            '[itemprop="description"]',
            '.product-description',
            '.description',
            '#product-description',
        ]
        for sel in selectors:
            elem = tree.select_one(sel)
            if elem:
                text = elem.get_text(strip=True)
                return text[:1000] if text else None  # Обмежуємо довжину
        return None
    
    def _extract_images(self, tree) -> List[str]:
        """Витягує зображення продукту."""
        images = []
        selectors = [
            '.product-image img',
            '.gallery img',
            '[itemprop="image"]',
            '.product-gallery img',
        ]
        
        for sel in selectors:
            for img in tree.select(sel):
                src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
                if src and src not in images:
                    images.append(src)
        
        return images[:10]  # Максимум 10 зображень
    
    def _extract_attributes(self, tree) -> Dict[str, str]:
        """Витягує атрибути продукту."""
        attrs = {}
        
        # Таблиці характеристик
        for row in tree.select('.product-attributes tr, .specs tr, .specifications tr'):
            cells = row.find_all(['th', 'td'])
            if len(cells) == 2:
                key = cells[0].get_text(strip=True)
                value = cells[1].get_text(strip=True)
                if key and value:
                    attrs[key] = value
        
        # Definition lists
        for dl in tree.select('.product-specs dl, .attributes dl'):
            dts = dl.find_all('dt')
            dds = dl.find_all('dd')
            for dt, dd in zip(dts, dds):
                key = dt.get_text(strip=True)
                value = dd.get_text(strip=True)
                if key and value:
                    attrs[key] = value
        
        return attrs
    
    def _extract_availability(self, tree) -> Optional[str]:
        """Витягує доступність продукту."""
        elem = tree.select_one('[itemprop="availability"]')
        if elem:
            href = elem.get('href', '')
            if 'InStock' in href:
                return 'in_stock'
            elif 'OutOfStock' in href:
                return 'out_of_stock'
            elif 'PreOrder' in href:
                return 'pre_order'
        
        # Перевіряємо текст
        for selector in ['.availability', '.stock-status', '[data-availability]']:
            elem = tree.select_one(selector)
            if elem:
                text = elem.get_text(strip=True).lower()
                if 'в наявності' in text or 'in stock' in text:
                    return 'in_stock'
                elif 'немає' in text or 'out of stock' in text:
                    return 'out_of_stock'
        
        return None
```

---

## Best Practices

### 1. Graceful Degradation

```python
def execute(self, context: NodePluginContext) -> NodePluginContext:
    # Завжди ініціалізуйте default значення
    context.user_data['my_data'] = []
    
    if not context.html_tree:
        return context  # Early return
    
    try:
        # Ваша логіка
        pass
    except Exception as e:
        # Log but don't crash
        import logging
        logging.getLogger(__name__).error(f"Error: {e}")
    
    return context
```

### 2. Type Hints

```python
from typing import Optional, List, Dict, Any

def _extract_name(self, tree) -> Optional[str]:
    """Документуйте return types."""
    pass
```

### 3. Конфігурація через config

```python
def __init__(self, config: dict = None):
    super().__init__(config)
    self.max_items = self.config.get('max_items', 100)
    self.timeout = self.config.get('timeout', 5.0)
```

### 4. Кешування результатів

```python
class CachedExtractor(BaseNodePlugin):
    def __init__(self, config=None):
        super().__init__(config)
        self._cache = {}
    
    def execute(self, context):
        cache_key = context.url
        if cache_key in self._cache:
            context.user_data['cached_data'] = self._cache[cache_key]
            return context
        
        # Обробка...
        result = self._process(context)
        self._cache[cache_key] = result
        context.user_data['cached_data'] = result
        
        return context
```

---

## Наступні кроки

- [Plugin System →](plugins.md)
- [Structured Data →](structured-data.md)
- [API Reference →](../api/API.md)
