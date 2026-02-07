# Structured Data Plugin (Плагін мікророзмітки)

> **Версія:** 2.0  
> **Дата:** Лютий 2026  
> **Статус:** ✅ РЕАЛІЗОВАНО  
> **Автор:** GraphCrawler Team

---

## 📋 Зміст

1. [Проблема та мотивація](#проблема-та-мотивація)
2. [Типи мікророзмітки](#типи-мікророзмітки)
3. [Архітектура рішення](#архітектура-рішення)
4. [Інтеграція з існуючим пайплайном](#інтеграція-з-існуючим-пайплайном)
5. [Специфікація API](#специфікація-api)
6. [Production Considerations](#production-considerations)
7. [Приклади використання](#приклади-використання)
8. [Етапи реалізації](#етапи-реалізації)
9. [Тестування](#тестування)

---

## Проблема та мотивація

### Поточна ситуація

Зараз граф містить ноди з базовими метаданими (title, h1, description) і контентом. Але ці дані не дають повного розуміння **типу контенту** сторінки:
- Це стаття чи продукт?
- Це вакансія чи компанія?
- Це рецепт чи відео?

### Рішення через мікророзмітку

Мікророзмітка (Structured Data) — це стандартизований спосіб опису типу та властивостей контенту:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           БЕЗ МІКРОРОЗМІТКИ                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Node A          Node B          Node C          Node D                    │
│   ┌─────┐         ┌─────┐         ┌─────┐         ┌─────┐                   │
│   │ url │         │ url │         │ url │         │ url │                   │
│   │title│         │title│         │title│         │title│                   │
│   │ h1  │         │ h1  │         │ h1  │         │ h1  │                   │
│   └─────┘         └─────┘         └─────┘         └─────┘                   │
│                                                                             │
│   Всі ноди однорідні - незрозуміло що на сторінці                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                           З МІКРОРОЗМІТКОЮ                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Node A          Node B          Node C          Node D                    │
│   ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐               │
│   │ Article │     │ Product │     │JobPosting│    │ Recipe  │               │
│   │─────────│     │─────────│     │─────────│     │─────────│               │
│   │author   │     │price    │     │salary   │     │cookTime │               │
│   │datePubl.│     │currency │     │location │     │calories │               │
│   │wordCount│     │rating   │     │company  │     │rating   │               │
│   └─────────┘     └─────────┘     └─────────┘     └─────────┘               │
│                                                                             │
│   Кожна нода має тип і структуровані дані                                   │
│   Можна фільтрувати: "покажи тільки вакансії з зарплатою > $50k"            │
│   Граф стає семантично багатшим                                             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Цінність для користувача

1. **Класифікація без ML** — тип сторінки визначається автоматично через розмітку
2. **Структуровані дані** — отримуємо готові JSON об'єкти (ціна, рейтинг, дата)
3. **Краще розуміння графа** — ноди мають семантичний тип
4. **Точніші фільтри** — "вакансії в Києві" замість "сторінки з словом вакансія"

---

## Типи мікророзмітки

### 1. JSON-LD (рекомендовано Google)

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "How to make bread",
  "author": {"@type": "Person", "name": "John"}
}
</script>
```

**Переваги:**
- Найпростіший для парсингу (вже JSON!)
- Не залежить від DOM структури
- Може містити декілька об'єктів

**Обмеження:**
- Потребує raw HTML (не тільки DOM tree)

### 2. Microdata (HTML атрибути)

```html
<div itemscope itemtype="https://schema.org/Product">
  <span itemprop="name">Widget</span>
  <span itemprop="price">$19.99</span>
</div>
```

**Переваги:**
- Вбудовано в HTML
- Підтримується старими сайтами

**Обмеження:**
- Залежить від DOM структури
- Складніший парсинг вкладених елементів

### 3. RDFa (семантичний веб)

```html
<div vocab="https://schema.org/" typeof="Product">
  <span property="name">Widget</span>
</div>
```

**Переваги:**
- Стандарт W3C
- Гнучкий синтаксис

**Обмеження:**
- Рідко використовується на практиці
- Потребує більше ресурсів для парсингу

### 4. Open Graph (Facebook)

```html
<meta property="og:type" content="article" />
<meta property="og:title" content="Article Title" />
```

**Переваги:**
- Майже на кожному сайті
- Простий парсинг

**Обмеження:**
- Обмежений набір властивостей
- Не замінює повноцінну schema.org розмітку

### 5. Twitter Cards

```html
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="Title" />
```

**Переваги:**
- Широка підтримка
- Простий формат

---

## Архітектура рішення

### Структура файлів

```
graph_crawler/
└── extensions/
    └── plugins/
        └── node/
            └── structured_data/              # НОВИЙ МОДУЛЬ
                ├── __init__.py               # Публічні експорти
                ├── plugin.py                 # StructuredDataPlugin (ON_HTML_PARSED)
                ├── extractor.py              # StructuredDataExtractor (core logic)
                ├── result.py                 # StructuredDataResult dataclass
                ├── options.py                # StructuredDataOptions
                ├── exceptions.py             # Кастомні винятки
                └── parsers/                  # Парсери для різних форматів
                    ├── __init__.py
                    ├── base.py               # BaseParser Protocol
                    ├── jsonld.py             # JSON-LD парсер
                    ├── microdata.py          # Microdata парсер
                    ├── rdfa.py               # RDFa парсер (опціонально)
                    ├── opengraph.py          # Open Graph парсер
                    └── twitter.py            # Twitter Cards парсер
```

### Діаграма потоку даних

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    STRUCTURED DATA EXTRACTION FLOW                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Node.process_html(html)                                                   │
│         │                                                                   │
│         ▼                                                                   │
│   ┌─────────────────┐                                                       │
│   │ tree_parser.    │  <-- Selectolax/Lxml/BS4 (вже налаштований)           │
│   │ parse(html)     │                                                       │
│   └────────┬────────┘                                                       │
│            │                                                                │
│            ▼                                                                │
│   ┌──────────────────────────────────────────────────────────────────┐     │
│   │              NodePluginContext                                    │     │
│   │  - parser: BaseTreeAdapter                                        │     │
│   │  - html: str (для JSON-LD <script>)                               │     │
│   └────────┬─────────────────────────────────────────────────────────┘     │
│            │                                                                │
│            ▼                                                                │
│   ┌──────────────────────────────────────────────────────────────────┐     │
│   │              StructuredDataPlugin                                 │     │
│   │              (ON_HTML_PARSED)                                     │     │
│   │                                                                   │     │
│   │   1. Витягує JSON-LD з <script type="application/ld+json">        │     │
│   │   2. Витягує Microdata з itemscope/itemprop                       │     │
│   │   3. Витягує Open Graph з <meta property="og:*">                  │     │
│   │   4. Витягує Twitter Cards з <meta name="twitter:*">              │     │
│   │   5. (Опціонально) RDFa                                           │     │
│   │                                                                   │     │
│   │   OUTPUT:                                                         │     │
│   │     context.user_data['structured_data'] = StructuredDataResult   │     │
│   │                                                                   │     │
│   └──────────────────────────────────────────────────────────────────┘     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Взаємодія з іншими плагінами

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        ON_HTML_PARSED PLUGINS                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   NodePluginContext                                                         │
│         │                                                                   │
│         ├──────> MetadataExtractorPlugin                                    │
│         │            └──> context.metadata['title', 'h1', ...]              │
│         │                                                                   │
│         ├──────> LinkExtractorPlugin                                        │
│         │            └──> context.extracted_links                           │
│         │                                                                   │
│         ├──────> StructuredDataPlugin (НОВИЙ)                               │
│         │            └──> context.user_data['structured_data']              │
│         │                                                                   │
│         └──────> MarkdownGeneratorPlugin (якщо підключений)                 │
│                      └──> context.user_data['markdown']                     │
│                                                                             │
│   ВАЖЛИВО: Плагіни незалежні - порядок виконання не впливає на результат    │
│   Кожен плагін працює зі своєю частиною user_data                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Інтеграція з існуючим пайплайном

### Принципи інтеграції

1. **Не модифікувати context.metadata** — це зона відповідальності MetadataExtractorPlugin
2. **Зберігати дані в user_data** — стандартний механізм для плагінів
3. **Ізольована обробка помилок** — помилка в одному парсері не впливає на інші
4. **Сумісність з async** — всі методи повинні бути sync-safe

```python
# Плагін працює НЕЗАЛЕЖНО від:
# 1. Типу парсера (BS4, lxml, selectolax)
# 2. Інших плагінів (metadata, links, markdown)
# 3. Типу драйвера (http, playwright)

# Користувач підключає плагін - все працює автоматично
graph = crawl(
    "https://example.com",
    plugins=[StructuredDataPlugin()]  # <-- Просто додати в список
)
```

### Масштабованість

1. **Модульні парсери** — кожен формат в окремому файлі
2. **Конфігурація** — користувач обирає які формати парсити
3. **Lazy parsing** — парсимо тільки потрібні формати
4. **Graceful degradation** — якщо один парсер впав, інші продовжують

```python
# Налаштування через options
options = StructuredDataOptions(
    parse_jsonld=True,        # Увімкнено
    parse_microdata=True,     # Увімкнено
    parse_opengraph=True,     # Увімкнено
    parse_twitter=True,       # Увімкнено
    parse_rdfa=False,         # Вимкнено (ресурсозатратний)
)

plugin = StructuredDataPlugin(options=options)
```

---

## Специфікація API

### StructuredDataResult (dataclass)

```python
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any
from enum import Enum

class SchemaType(str, Enum):
    """Популярні schema.org типи для type hints."""
    ARTICLE = "Article"
    PRODUCT = "Product"
    JOB_POSTING = "JobPosting"
    RECIPE = "Recipe"
    EVENT = "Event"
    ORGANIZATION = "Organization"
    PERSON = "Person"
    LOCAL_BUSINESS = "LocalBusiness"
    FAQ_PAGE = "FAQPage"
    HOW_TO = "HowTo"
    VIDEO_OBJECT = "VideoObject"
    BREADCRUMB_LIST = "BreadcrumbList"

@dataclass
class StructuredDataResult:
    """
    Результат витягування мікророзмітки.
    
    Attributes:
        primary_type: Основний тип контенту (перший знайдений)
        jsonld: Список JSON-LD об'єктів
        microdata: Список Microdata об'єктів
        opengraph: Open Graph метатеги
        twitter: Twitter Cards метатеги
        rdfa: RDFa об'єкти (якщо увімкнено)
        all_types: Всі знайдені schema.org типи
        has_data: Чи знайдено хоч якісь дані
        errors: Помилки парсингу (для діагностики)
    """
    
    # Основний тип контенту (перший знайдений з JSON-LD або Microdata)
    primary_type: Optional[str] = None
    
    # JSON-LD дані (список, бо може бути декілька блоків)
    jsonld: List[Dict[str, Any]] = field(default_factory=list)
    
    # Microdata (витягнуті itemscope блоки)
    microdata: List[Dict[str, Any]] = field(default_factory=list)
    
    # Open Graph метатеги
    opengraph: Dict[str, str] = field(default_factory=dict)
    
    # Twitter Cards
    twitter: Dict[str, str] = field(default_factory=dict)
    
    # RDFa (опціонально)
    rdfa: List[Dict[str, Any]] = field(default_factory=list)
    
    # Всі знайдені типи
    all_types: Set[str] = field(default_factory=set)
    
    # Чи знайдено хоч щось
    has_data: bool = False
    
    # Помилки парсингу (для діагностики)
    errors: List[str] = field(default_factory=list)
    
    @classmethod
    def empty(cls) -> "StructuredDataResult":
        """Створює порожній результат."""
        return cls()
    
    def get_type(self) -> Optional[str]:
        """
        Повертає primary_type або перший з all_types.
        
        Returns:
            Тип контенту або None
        """
        return self.primary_type or (
            next(iter(self.all_types), None) if self.all_types else None
        )
    
    def get_property(self, prop: str, default: Any = None) -> Optional[Any]:
        """
        Шукає властивість у всіх джерелах.
        
        Порядок пошуку:
        1. JSON-LD (найточніші дані)
        2. Microdata
        3. Open Graph
        4. Twitter Cards
        
        Args:
            prop: Назва властивості (напр. 'price', 'author', 'title')
            default: Значення за замовчуванням
            
        Returns:
            Знайдене значення або default
        """
        # JSON-LD (найвищий пріоритет)
        for item in self.jsonld:
            if prop in item:
                return item[prop]
        
        # Microdata
        for item in self.microdata:
            if prop in item:
                return item[prop]
        
        # Open Graph (маппінг og: -> property)
        og_mapping = {
            'title': 'title',
            'description': 'description',
            'image': 'image',
            'url': 'url',
            'type': 'type',
        }
        if prop in og_mapping and og_mapping[prop] in self.opengraph:
            return self.opengraph[og_mapping[prop]]
        
        # Twitter Cards
        twitter_mapping = {
            'title': 'title',
            'description': 'description',
            'image': 'image',
        }
        if prop in twitter_mapping and twitter_mapping[prop] in self.twitter:
            return self.twitter[twitter_mapping[prop]]
        
        return default
    
    def get_all_of_type(self, schema_type: str) -> List[Dict[str, Any]]:
        """
        Повертає всі об'єкти заданого типу.
        
        Args:
            schema_type: Тип schema.org (напр. 'Product', 'Article')
            
        Returns:
            Список об'єктів заданого типу
        """
        result = []
        
        for item in self.jsonld:
            item_type = item.get('@type')
            if isinstance(item_type, list):
                if schema_type in item_type:
                    result.append(item)
            elif item_type == schema_type:
                result.append(item)
        
        for item in self.microdata:
            if item.get('@type') == schema_type or item.get('type') == schema_type:
                result.append(item)
        
        return result
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Конвертує результат у словник для серіалізації.
        
        Returns:
            Dict з усіма даними
        """
        return {
            'primary_type': self.primary_type,
            'jsonld': self.jsonld,
            'microdata': self.microdata,
            'opengraph': self.opengraph,
            'twitter': self.twitter,
            'rdfa': self.rdfa,
            'all_types': list(self.all_types),
            'has_data': self.has_data,
            'errors': self.errors,
        }
```

### StructuredDataOptions

```python
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class StructuredDataOptions:
    """
    Налаштування витягування мікророзмітки.
    
    Attributes:
        parse_jsonld: Чи парсити JSON-LD блоки
        parse_microdata: Чи парсити Microdata атрибути
        parse_opengraph: Чи парсити Open Graph метатеги
        parse_twitter: Чи парсити Twitter Cards
        parse_rdfa: Чи парсити RDFa (вимкнено за замовчуванням)
        allowed_types: Список дозволених типів (None = всі)
        max_jsonld_blocks: Максимум JSON-LD блоків для обробки
        max_jsonld_size: Максимальний розмір JSON-LD блоку в байтах
        include_nested: Чи включати вкладені об'єкти
        timeout_per_parser: Таймаут на парсер в секундах
        fail_silently: Чи продовжувати при помилках
    """
    
    # Які формати парсити
    parse_jsonld: bool = True
    parse_microdata: bool = True
    parse_opengraph: bool = True
    parse_twitter: bool = True
    parse_rdfa: bool = False  # Вимкнено за замовчуванням
    
    # Фільтрація типів (None = всі)
    allowed_types: Optional[List[str]] = None
    
    # Ліміти для безпеки
    max_jsonld_blocks: int = 10
    max_jsonld_size: int = 100_000  # 100KB на блок
    max_microdata_items: int = 50
    
    # Глибина парсингу
    include_nested: bool = True
    max_nesting_depth: int = 5
    
    # Таймаути та обробка помилок
    timeout_per_parser: float = 2.0  # секунди
    fail_silently: bool = True  # продовжувати при помилках
    
    def __post_init__(self):
        """Валідація налаштувань."""
        if self.max_jsonld_blocks < 1:
            raise ValueError("max_jsonld_blocks must be >= 1")
        if self.max_jsonld_size < 1000:
            raise ValueError("max_jsonld_size must be >= 1000 bytes")
        if self.timeout_per_parser <= 0:
            raise ValueError("timeout_per_parser must be > 0")
```

### BaseParser Protocol

```python
from typing import Protocol, Any, Dict, List, Optional, Union

class BaseParser(Protocol):
    """
    Протокол для парсерів мікророзмітки.
    
    Кожен парсер відповідає за один формат (JSON-LD, Microdata тощо).
    """
    
    @property
    def name(self) -> str:
        """Унікальне ім'я парсера."""
        ...
    
    def parse(
        self, 
        source: Union[str, Any],
        options: Optional["StructuredDataOptions"] = None
    ) -> Union[List[Dict[str, Any]], Dict[str, str]]:
        """
        Парсить джерело та повертає структуровані дані.
        
        Args:
            source: HTML string або tree adapter
            options: Налаштування парсингу
            
        Returns:
            List[Dict] для JSON-LD/Microdata або Dict для OG/Twitter
            
        Raises:
            ParserError: При критичній помилці парсингу
        """
        ...
    
    def can_parse(self, source: Union[str, Any]) -> bool:
        """
        Перевіряє чи парсер може обробити джерело.
        
        Args:
            source: HTML string або tree adapter
            
        Returns:
            True якщо парсер може обробити джерело
        """
        ...
```

### StructuredDataPlugin

```python
import logging
from typing import Optional
from graph_crawler.extensions.plugins.node.base import (
    BaseNodePlugin,
    NodePluginContext,
    NodePluginType,
)

logger = logging.getLogger(__name__)

class StructuredDataPlugin(BaseNodePlugin):
    """
    Плагін для витягування мікророзмітки (Structured Data).
    
    Підтримує:
    - JSON-LD (schema.org) - рекомендовано Google
    - Microdata (itemscope/itemprop)
    - Open Graph (og:*)
    - Twitter Cards (twitter:*)
    - RDFa (опціонально)
    
    Дані зберігаються в context.user_data['structured_data'].
    
    Example:
        >>> plugin = StructuredDataPlugin()
        >>> 
        >>> # З налаштуваннями
        >>> plugin = StructuredDataPlugin(options=StructuredDataOptions(
        ...     parse_rdfa=True,
        ...     allowed_types=['Article', 'Product', 'JobPosting']
        ... ))
        
    Note:
        Плагін НЕ модифікує context.metadata - це зона відповідальності
        MetadataExtractorPlugin. Всі дані зберігаються в user_data.
    """
    
    def __init__(self, options: Optional[StructuredDataOptions] = None):
        super().__init__()
        self.options = options or StructuredDataOptions()
        self._extractor: Optional[StructuredDataExtractor] = None
    
    @property
    def plugin_type(self) -> NodePluginType:
        return NodePluginType.ON_HTML_PARSED
    
    @property
    def name(self) -> str:
        return "StructuredDataPlugin"
    
    def setup(self) -> None:
        """Ініціалізує extractor при реєстрації плагіна."""
        self._extractor = StructuredDataExtractor(self.options)
        logger.debug(f"{self.name} initialized with options: {self.options}")
    
    def teardown(self) -> None:
        """Очищує ресурси."""
        self._extractor = None
    
    def execute(self, context: NodePluginContext) -> NodePluginContext:
        """
        Витягує мікророзмітку з HTML.
        
        Args:
            context: Контекст з HTML та parser
            
        Returns:
            Контекст з доданими structured_data в user_data
        """
        if self._extractor is None:
            self._extractor = StructuredDataExtractor(self.options)
        
        try:
            result = self._extractor.extract(
                html=context.html,
                parser=context.parser
            )
            
            context.user_data['structured_data'] = result
            
            if result.has_data:
                logger.debug(
                    f"Extracted structured data from {context.url}: "
                    f"type={result.primary_type}, "
                    f"jsonld={len(result.jsonld)}, "
                    f"microdata={len(result.microdata)}"
                )
            
        except Exception as e:
            logger.error(f"Error extracting structured data from {context.url}: {e}")
            
            if self.options.fail_silently:
                empty_result = StructuredDataResult.empty()
                empty_result.errors.append(str(e))
                context.user_data['structured_data'] = empty_result
            else:
                raise
        
        return context
```

### StructuredDataExtractor

```python
import json
import re
import logging
from typing import Any, Dict, List, Optional, Set, Union

logger = logging.getLogger(__name__)

class StructuredDataExtractor:
    """
    Core логіка витягування мікророзмітки.
    
    Може використовуватись як:
    1. Всередині плагіна (ON_HTML_PARSED)
    2. Standalone утиліта
    
    Example:
        >>> extractor = StructuredDataExtractor()
        >>> result = extractor.extract(html=html_string)
        >>> print(result.primary_type)
        'Article'
    """
    
    def __init__(self, options: Optional[StructuredDataOptions] = None):
        self.options = options or StructuredDataOptions()
        self._parsers = self._init_parsers()
    
    def _init_parsers(self) -> Dict[str, BaseParser]:
        """Ініціалізує парсери на основі options."""
        parsers = {}
        
        if self.options.parse_jsonld:
            from .parsers.jsonld import JsonLdParser
            parsers['jsonld'] = JsonLdParser()
        
        if self.options.parse_microdata:
            from .parsers.microdata import MicrodataParser
            parsers['microdata'] = MicrodataParser()
        
        if self.options.parse_opengraph:
            from .parsers.opengraph import OpenGraphParser
            parsers['opengraph'] = OpenGraphParser()
        
        if self.options.parse_twitter:
            from .parsers.twitter import TwitterCardsParser
            parsers['twitter'] = TwitterCardsParser()
        
        if self.options.parse_rdfa:
            from .parsers.rdfa import RdfaParser
            parsers['rdfa'] = RdfaParser()
        
        return parsers
    
    def extract(
        self, 
        html: Optional[str] = None,
        parser: Optional[Any] = None
    ) -> StructuredDataResult:
        """
        Витягує мікророзмітку.
        
        Args:
            html: HTML string (для JSON-LD, Microdata)
            parser: BaseTreeAdapter (для Open Graph, Twitter)
            
        Returns:
            StructuredDataResult з усіма знайденими даними
        """
        result = StructuredDataResult()
        
        # JSON-LD (потребує raw HTML)
        if 'jsonld' in self._parsers and html:
            try:
                result.jsonld = self._parsers['jsonld'].parse(
                    html, 
                    self.options
                )[:self.options.max_jsonld_blocks]
                self._extract_types(result.jsonld, result.all_types)
            except Exception as e:
                logger.warning(f"JSON-LD parsing error: {e}")
                result.errors.append(f"jsonld: {e}")
        
        # Open Graph (працює через адаптер)
        if 'opengraph' in self._parsers and parser:
            try:
                result.opengraph = self._parsers['opengraph'].parse(
                    parser, 
                    self.options
                )
                if 'type' in result.opengraph:
                    result.all_types.add(f"og:{result.opengraph['type']}")
            except Exception as e:
                logger.warning(f"Open Graph parsing error: {e}")
                result.errors.append(f"opengraph: {e}")
        
        # Twitter Cards
        if 'twitter' in self._parsers and parser:
            try:
                result.twitter = self._parsers['twitter'].parse(
                    parser, 
                    self.options
                )
            except Exception as e:
                logger.warning(f"Twitter Cards parsing error: {e}")
                result.errors.append(f"twitter: {e}")
        
        # Microdata
        if 'microdata' in self._parsers:
            source = parser if parser else html
            if source:
                try:
                    result.microdata = self._parsers['microdata'].parse(
                        source, 
                        self.options
                    )[:self.options.max_microdata_items]
                    self._extract_types(result.microdata, result.all_types)
                except Exception as e:
                    logger.warning(f"Microdata parsing error: {e}")
                    result.errors.append(f"microdata: {e}")
        
        # RDFa
        if 'rdfa' in self._parsers and html:
            try:
                result.rdfa = self._parsers['rdfa'].parse(html, self.options)
                self._extract_types(result.rdfa, result.all_types)
            except Exception as e:
                logger.warning(f"RDFa parsing error: {e}")
                result.errors.append(f"rdfa: {e}")
        
        # Фільтрація за дозволеними типами
        if self.options.allowed_types:
            result = self._filter_by_types(result, self.options.allowed_types)
        
        # Визначаємо primary_type
        result.primary_type = self._determine_primary_type(result)
        result.has_data = bool(
            result.jsonld or 
            result.microdata or 
            result.opengraph or
            result.twitter
        )
        
        return result
    
    def _extract_types(self, items: List[Dict], types_set: Set[str]) -> None:
        """Витягує типи з списку об'єктів."""
        for item in items:
            item_type = item.get('@type') or item.get('type')
            if item_type:
                if isinstance(item_type, list):
                    types_set.update(item_type)
                else:
                    types_set.add(item_type)
    
    def _determine_primary_type(self, result: StructuredDataResult) -> Optional[str]:
        """
        Визначає основний тип контенту.
        
        Пріоритет: JSON-LD > Microdata > Open Graph
        """
        if result.jsonld:
            first = result.jsonld[0]
            item_type = first.get('@type')
            if isinstance(item_type, str):
                return item_type
            elif isinstance(item_type, list) and item_type:
                return item_type[0]
        
        if result.microdata:
            first = result.microdata[0]
            return first.get('@type') or first.get('type')
        
        if result.opengraph.get('type'):
            return f"og:{result.opengraph['type']}"
        
        return None
    
    def _filter_by_types(
        self, 
        result: StructuredDataResult, 
        allowed: List[str]
    ) -> StructuredDataResult:
        """Фільтрує результати за дозволеними типами."""
        allowed_set = set(allowed)
        
        result.jsonld = [
            item for item in result.jsonld
            if self._type_matches(item.get('@type'), allowed_set)
        ]
        
        result.microdata = [
            item for item in result.microdata
            if self._type_matches(
                item.get('@type') or item.get('type'), 
                allowed_set
            )
        ]
        
        result.all_types = result.all_types & allowed_set
        
        return result
    
    def _type_matches(
        self, 
        item_type: Union[str, List[str], None], 
        allowed: Set[str]
    ) -> bool:
        """Перевіряє чи тип відповідає дозволеним."""
        if item_type is None:
            return False
        if isinstance(item_type, list):
            return bool(set(item_type) & allowed)
        return item_type in allowed
```

---

## Production Considerations

### Безпека

```python
# 1. Ліміти на розмір даних
options = StructuredDataOptions(
    max_jsonld_blocks=10,        # Макс. 10 блоків
    max_jsonld_size=100_000,     # Макс. 100KB на блок
    max_microdata_items=50,      # Макс. 50 microdata елементів
    max_nesting_depth=5,         # Макс. глибина вкладеності
)

# 2. Таймаути
options = StructuredDataOptions(
    timeout_per_parser=2.0,      # 2 секунди на парсер
)

# 3. Валідація JSON
# JsonLdParser внутрішньо використовує json.loads з обмеженнями
```

### Обробка помилок

```python
# Graceful degradation - помилка в одному парсері не зупиняє інші
options = StructuredDataOptions(
    fail_silently=True,  # За замовчуванням
)

# Для дебагу можна увімкнути строгий режим
options = StructuredDataOptions(
    fail_silently=False,  # Кидає виняток при помилці
)

# Помилки завжди логуються та зберігаються в result.errors
result = extractor.extract(html=html)
if result.errors:
    logger.warning(f"Parsing had errors: {result.errors}")
```

### Продуктивність

```python
# 1. Lazy imports - парсери завантажуються тільки якщо потрібні
options = StructuredDataOptions(
    parse_rdfa=False,  # RDFa не завантажується
)

# 2. Ранній вихід - якщо HTML порожній
if not html or len(html) < 100:
    return StructuredDataResult.empty()

# 3. Регулярні вирази компілюються один раз
JSONLD_PATTERN = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE
)
```

### Моніторинг

```python
# Метрики для моніторингу
# - structured_data_extraction_time_seconds
# - structured_data_jsonld_count
# - structured_data_errors_total
# - structured_data_types_found (counter per type)

# Інтеграція з EventBus
event_bus.emit(CrawlerEvent(
    type=EventType.PLUGIN_EXECUTED,
    data={
        'plugin': 'StructuredDataPlugin',
        'url': context.url,
        'primary_type': result.primary_type,
        'has_data': result.has_data,
        'errors': len(result.errors),
    }
))
```

---

## Приклади використання

### Базове використання

```python
from graph_crawler import crawl
from graph_crawler.extensions.plugins.node.structured_data import (
    StructuredDataPlugin,
)

# Підключаємо плагін
graph = crawl(
    "https://example.com",
    plugins=[StructuredDataPlugin()]
)

# Доступ до даних
for node in graph.nodes:
    sd = node.user_data.get('structured_data')
    if sd and sd.has_data:
        print(f"URL: {node.url}")
        print(f"Type: {sd.primary_type}")
        print(f"JSON-LD objects: {len(sd.jsonld)}")
```

### E-commerce: Витягування продуктів

```python
from graph_crawler.extensions.plugins.node.structured_data import (
    StructuredDataPlugin,
    StructuredDataOptions,
)

# Налаштування для e-commerce
options = StructuredDataOptions(
    allowed_types=['Product', 'Offer', 'AggregateOffer'],
    parse_rdfa=False,  # Не потрібно для більшості магазинів
)

graph = crawl(
    "https://shop.example.com",
    plugins=[StructuredDataPlugin(options=options)]
)

# Збираємо продукти
products = []
for node in graph.nodes:
    sd = node.user_data.get('structured_data')
    if sd and sd.primary_type == 'Product':
        for product in sd.jsonld:
            products.append({
                'name': product.get('name'),
                'price': product.get('offers', {}).get('price'),
                'currency': product.get('offers', {}).get('priceCurrency'),
                'availability': product.get('offers', {}).get('availability'),
                'rating': product.get('aggregateRating', {}).get('ratingValue'),
                'reviews_count': product.get('aggregateRating', {}).get('reviewCount'),
                'url': node.url,
            })

# Фільтрація за ціною
affordable = [p for p in products if p.get('price', 0) < 100]
```

### Рекрутинг: Пошук вакансій

```python
# Налаштування для job-сайтів
options = StructuredDataOptions(
    allowed_types=['JobPosting'],
)

graph = crawl(
    "https://jobs.example.com",
    max_pages=500,
    plugins=[StructuredDataPlugin(options=options)]
)

# Витягуємо вакансії
jobs = []
for node in graph.nodes:
    sd = node.user_data.get('structured_data')
    if not sd or not sd.has_data:
        continue
    
    for job in sd.get_all_of_type('JobPosting'):
        salary = job.get('baseSalary', {})
        jobs.append({
            'title': job.get('title'),
            'company': job.get('hiringOrganization', {}).get('name'),
            'location': job.get('jobLocation', {}).get('address', {}).get('addressLocality'),
            'salary_min': salary.get('value', {}).get('minValue') if isinstance(salary.get('value'), dict) else None,
            'salary_max': salary.get('value', {}).get('maxValue') if isinstance(salary.get('value'), dict) else None,
            'salary_currency': salary.get('currency'),
            'employment_type': job.get('employmentType'),
            'date_posted': job.get('datePosted'),
            'url': node.url,
        })

# Фільтруємо за зарплатою (>$50k)
high_paying = [
    j for j in jobs 
    if j.get('salary_min') and j['salary_min'] > 50000
]
```

### Контент-аналітика: Статті та блоги

```python
options = StructuredDataOptions(
    allowed_types=['Article', 'NewsArticle', 'BlogPosting'],
)

graph = crawl(
    "https://blog.example.com",
    plugins=[
        StructuredDataPlugin(options=options),
    ]
)

# Аналізуємо контент
articles = []
for node in graph.nodes:
    sd = node.user_data.get('structured_data')
    if not sd:
        continue
    
    article = next(
        (item for item in sd.jsonld if item.get('@type') in ['Article', 'NewsArticle', 'BlogPosting']),
        None
    )
    
    if article:
        articles.append({
            'headline': article.get('headline'),
            'author': article.get('author', {}).get('name') if isinstance(article.get('author'), dict) else article.get('author'),
            'date_published': article.get('datePublished'),
            'date_modified': article.get('dateModified'),
            'word_count': article.get('wordCount'),
            'section': article.get('articleSection'),
            'url': node.url,
        })

# Сортуємо за датою
articles.sort(key=lambda x: x.get('date_published', ''), reverse=True)
```

### Standalone використання (без плагіна)

```python
from graph_crawler.extensions.plugins.node.structured_data import (
    StructuredDataExtractor,
    StructuredDataOptions,
)

# Створюємо extractor напряму
extractor = StructuredDataExtractor(
    options=StructuredDataOptions(parse_rdfa=False)
)

# Парсимо HTML
html = """
<html>
<head>
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": "Test Article"
    }
    </script>
</head>
<body></body>
</html>
"""

result = extractor.extract(html=html)
print(f"Type: {result.primary_type}")  # Article
print(f"Headline: {result.get_property('headline')}")  # Test Article
```

---

## Етапи реалізації

### Етап 1: Базова структура (2-3 год)

- [ ] Створити директорію `structured_data/`
- [ ] `__init__.py` — публічні експорти
- [ ] `result.py` — StructuredDataResult dataclass
- [ ] `options.py` — StructuredDataOptions з валідацією
- [ ] `exceptions.py` — ParserError, ExtractionError
- [ ] `parsers/base.py` — BaseParser Protocol

### Етап 2: Парсери (4-5 год)

- [ ] `parsers/jsonld.py` — JSON-LD парсер (найважливіший!)
  - Regex для пошуку `<script type="application/ld+json">`
  - json.loads з обробкою помилок
  - Підтримка декількох блоків
  - Ліміти на розмір
- [ ] `parsers/opengraph.py` — Open Graph парсер
  - Пошук `<meta property="og:*">`
  - Маппінг властивостей
- [ ] `parsers/twitter.py` — Twitter Cards парсер
  - Пошук `<meta name="twitter:*">`
- [ ] `parsers/microdata.py` — Microdata парсер
  - Рекурсивний обхід itemscope
  - itemprop витягування
- [ ] `parsers/rdfa.py` — RDFa парсер (низький пріоритет)

### Етап 3: Extractor та Plugin (2 год)

- [ ] `extractor.py` — StructuredDataExtractor
  - Оркестрація парсерів
  - Graceful degradation
  - Визначення primary_type
- [ ] `plugin.py` — StructuredDataPlugin
  - Інтеграція з NodePluginContext
  - setup/teardown lifecycle
  - Логування

### Етап 4: Тести (3-4 год)

- [ ] Unit tests для StructuredDataResult
- [ ] Unit tests для кожного парсера
- [ ] Unit tests для StructuredDataExtractor
- [ ] Integration tests з реальними HTML
- [ ] Test fixtures з різними типами розмітки
- [ ] Performance tests (великі документи)

### Етап 5: Документація та інтеграція (1-2 год)

- [ ] README.md для модуля
- [ ] Приклади використання
- [ ] Оновити INDEX.md
- [ ] Оновити PLUGIN_SYSTEM.md
- [ ] Push на GitLab

**Загальний час:** ~12-16 годин

---

## Тестування

### Unit тести

```python
# tests/unit/plugins/node/structured_data/test_result.py

import pytest
from graph_crawler.extensions.plugins.node.structured_data import (
    StructuredDataResult,
)

class TestStructuredDataResult:
    def test_empty_result(self):
        result = StructuredDataResult.empty()
        assert result.has_data is False
        assert result.primary_type is None
        assert len(result.jsonld) == 0
    
    def test_get_type_from_jsonld(self):
        result = StructuredDataResult(
            jsonld=[{'@type': 'Article', 'headline': 'Test'}]
        )
        result.primary_type = 'Article'
        assert result.get_type() == 'Article'
    
    def test_get_property_priority(self):
        """JSON-LD має вищий пріоритет за Open Graph."""
        result = StructuredDataResult(
            jsonld=[{'title': 'JSON-LD Title'}],
            opengraph={'title': 'OG Title'},
        )
        assert result.get_property('title') == 'JSON-LD Title'
    
    def test_get_all_of_type(self):
        result = StructuredDataResult(
            jsonld=[
                {'@type': 'Product', 'name': 'Product 1'},
                {'@type': 'Article', 'headline': 'Article 1'},
                {'@type': 'Product', 'name': 'Product 2'},
            ]
        )
        products = result.get_all_of_type('Product')
        assert len(products) == 2
    
    def test_to_dict(self):
        result = StructuredDataResult(
            primary_type='Article',
            jsonld=[{'@type': 'Article'}],
            all_types={'Article'},
            has_data=True,
        )
        d = result.to_dict()
        assert d['primary_type'] == 'Article'
        assert 'Article' in d['all_types']
```

### Fixtures

```python
# tests/fixtures/structured_data/jsonld_article.html

<!DOCTYPE html>
<html>
<head>
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": "Test Article",
        "author": {
            "@type": "Person",
            "name": "John Doe"
        },
        "datePublished": "2024-01-15",
        "wordCount": 1500
    }
    </script>
</head>
<body></body>
</html>
```

```python
# tests/fixtures/structured_data/product_with_offer.html

<!DOCTYPE html>
<html>
<head>
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "Test Product",
        "offers": {
            "@type": "Offer",
            "price": "99.99",
            "priceCurrency": "USD",
            "availability": "https://schema.org/InStock"
        },
        "aggregateRating": {
            "@type": "AggregateRating",
            "ratingValue": "4.5",
            "reviewCount": "127"
        }
    }
    </script>
</head>
<body></body>
</html>
```

### Integration тести

```python
# tests/integration/test_structured_data_plugin.py

import pytest
from graph_crawler import crawl
from graph_crawler.extensions.plugins.node.structured_data import (
    StructuredDataPlugin,
    StructuredDataOptions,
)

class TestStructuredDataPluginIntegration:
    def test_crawl_with_plugin(self, mock_server):
        """Тест краулінгу з плагіном."""
        graph = crawl(
            mock_server.url,
            max_pages=5,
            plugins=[StructuredDataPlugin()]
        )
        
        for node in graph.nodes:
            assert 'structured_data' in node.user_data
    
    def test_plugin_does_not_modify_metadata(self, mock_server):
        """Плагін не повинен модифікувати metadata."""
        graph = crawl(
            mock_server.url,
            plugins=[StructuredDataPlugin()]
        )
        
        for node in graph.nodes:
            # schema_type НЕ повинен бути в metadata
            assert 'schema_type' not in node.metadata
            # structured_data повинен бути в user_data
            assert 'structured_data' in node.user_data
    
    def test_graceful_degradation(self, mock_server_with_invalid_jsonld):
        """При помилці парсингу краулінг продовжується."""
        graph = crawl(
            mock_server_with_invalid_jsonld.url,
            plugins=[StructuredDataPlugin()]
        )
        
        # Граф повинен бути побудований
        assert len(graph.nodes) > 0
        
        # Помилки повинні бути залоговані
        for node in graph.nodes:
            sd = node.user_data.get('structured_data')
            if sd and sd.errors:
                assert 'jsonld' in sd.errors[0]
```

---

## Чекліст готовності

### Функціональність

- [ ] JSON-LD парсинг працює
- [ ] Open Graph парсинг працює
- [ ] Twitter Cards парсинг працює
- [ ] Microdata парсинг працює
- [ ] RDFa парсинг працює (опціонально)
- [ ] Фільтрація за типами працює
- [ ] get_property шукає у всіх джерелах

### Архітектура

- [ ] Не модифікує context.metadata
- [ ] Зберігає дані тільки в user_data
- [ ] Працює з будь-яким адаптером (BS4, lxml, selectolax)
- [ ] Сумісний з async режимом
- [ ] Підтримує graceful degradation

### Production

- [ ] Ліміти на розмір даних
- [ ] Таймаути на парсери
- [ ] Обробка помилок для кожного парсера окремо
- [ ] Логування помилок
- [ ] Метрики для моніторингу

### Тестування

- [ ] Unit тести для всіх компонентів
- [ ] Integration тести
- [ ] Performance тести
- [ ] Test fixtures для різних форматів

### Документація

- [ ] README для модуля
- [ ] Приклади використання
- [ ] API документація
- [ ] Оновлений INDEX.md

---

## Посилання

- [Schema.org](https://schema.org/) — стандарт мікророзмітки
- [Google Structured Data](https://developers.google.com/search/docs/appearance/structured-data) — документація Google
- [JSON-LD Playground](https://json-ld.org/playground/) — тестування JSON-LD
- [Rich Results Test](https://search.google.com/test/rich-results) — перевірка розмітки
- [Plugin System](./PLUGIN_SYSTEM.md) — документація плагінів GraphCrawler
- [Architecture Overview](./ARCHITECTURE_OVERVIEW.md) — огляд архітектури
