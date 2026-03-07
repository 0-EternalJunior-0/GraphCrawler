# Structured Data Extraction

> **Час читання:** 12 хвилин  
> **Рівень:** Середній

Витягування структурованих даних (JSON-LD, Open Graph, Microdata, Twitter Cards, RDFa).

---

## Огляд

StructuredDataPlugin витягує машиночитані дані з HTML сторінок:

| Формат            | Опис                               | Пріоритет |
| ----------------- | ---------------------------------- | --------- |
| **JSON-LD**       | schema.org (рекомендований Google) | Високий   |
| **Open Graph**    | Facebook/LinkedIn метатеги (og:\*) | Середній  |
| **Twitter Cards** | Twitter метатеги (twitter:\*)      | Середній  |
| **Microdata**     | HTML атрибути (itemscope/itemprop) | Низький   |
| **RDFa**          | Семантичний веб (опціонально)      | Низький   |

**Бізнес-цінність:**

- **E-commerce**: структуровані Product/Offer замість regex
- **Job aggregation**: JobPosting з salary, location
- **News**: Article з author, datePublished
- **SEO audit**: автоматична валідація schema

---

## Базове використання

```python
import graph_crawler as gc
from graph_crawler.extensions.plugins.node.structured_data import StructuredDataPlugin

graph = gc.crawl(
    "https://example.com",
    plugins=[StructuredDataPlugin()]
)

for node in graph:
    sd = node.user_data.get('structured_data')
    if sd and sd.has_data:
        print(f"\n{node.url}:")
        print(f"  Type: {sd.get_type()}")
        print(f"  Name: {sd.get_property('name')}")
        print(f"  Parse time: {sd.parse_time_ms:.1f}ms")
```

---

## Налаштування

```python
from graph_crawler.extensions.plugins.node.structured_data import (
    StructuredDataPlugin,
    StructuredDataOptions,
)

options = StructuredDataOptions(
    # Формати для парсингу
    parse_jsonld=True,           # JSON-LD (schema.org)
    parse_opengraph=True,        # Open Graph (og:*)
    parse_twitter=True,          # Twitter Cards
    parse_microdata=True,        # Microdata (itemscope)
    parse_rdfa=False,            # RDFa (вимкнено для швидкості)

    # Фільтрація типів (None = всі)
    allowed_types=['Product', 'Offer', 'Organization'],

    # Ліміти безпеки
    max_jsonld_blocks=10,        # Макс. JSON-LD блоків
    max_jsonld_size=100_000,     # Макс. розмір JSON-LD (bytes)
    max_microdata_items=50,      # Макс. microdata items
    max_nesting_depth=5,         # Макс. глибина вкладеності

    # Таймаути
    timeout_per_parser=2.0,      # Секунд на парсер

    # Обробка помилок
    fail_silently=True,          # Не падати при помилках

    # Опції парсингу
    include_nested=True,         # Включати вкладені об'єкти
    normalize_types=True,        # "schema.org/Product" -> "Product"
)

graph = gc.crawl(
    "https://shop.example.com",
    plugins=[StructuredDataPlugin(options)]
)
```

---

## Робота з даними

### StructuredDataResult

```python
sd = node.user_data.get('structured_data')

# Перевірка наявності даних
if sd.has_data:
    # Основний тип (з найвищим пріоритетом)
    print(sd.get_type())        # "Product"
    print(sd.primary_type)      # Аліас

    # Отримати властивість (шукає в усіх джерелах)
    print(sd.get_property('name'))
    print(sd.get_property('description'))
    print(sd.get_property('price'))

    # Всі об'єкти певного типу
    products = sd.get_all_of_type('Product')
    for product in products:
        print(product.get('name'))
        print(product.get('offers', {}).get('price'))

# Статистика
print(f"JSON-LD blocks: {sd.jsonld_count}")
print(f"Microdata items: {sd.microdata_count}")
print(f"Parse time: {sd.parse_time_ms}ms")

# Помилки (якщо були)
if sd.has_errors:
    print(f"Errors: {sd.errors}")
```

### JSON-LD

```python
# Прямий доступ до JSON-LD
json_ld = sd.json_ld  # List[dict]

for item in json_ld:
    print(f"@type: {item.get('@type')}")
    print(f"@context: {item.get('@context')}")
    print(f"name: {item.get('name')}")

    # Вкладені об'єкти
    if 'offers' in item:
        offer = item['offers']
        print(f"price: {offer.get('price')}")
        print(f"priceCurrency: {offer.get('priceCurrency')}")
```

### Open Graph

```python
# Open Graph дані (dict)
og = sd.open_graph

print(f"og:title: {og.get('og:title')}")
print(f"og:description: {og.get('og:description')}")
print(f"og:image: {og.get('og:image')}")
print(f"og:url: {og.get('og:url')}")
print(f"og:type: {og.get('og:type')}")
print(f"og:site_name: {og.get('og:site_name')}")
```

### Twitter Cards

```python
# Twitter Cards (dict)
twitter = sd.twitter_cards

print(f"twitter:card: {twitter.get('twitter:card')}")
print(f"twitter:title: {twitter.get('twitter:title')}")
print(f"twitter:description: {twitter.get('twitter:description')}")
print(f"twitter:image: {twitter.get('twitter:image')}")
print(f"twitter:site: {twitter.get('twitter:site')}")
```

### Microdata

```python
# Microdata items (List[dict])
microdata = sd.microdata

for item in microdata:
    print(f"type: {item.get('type')}")
    print(f"properties: {item.get('properties')}")
```

### RDFa

```python
# RDFa (якщо увімкнено)
rdfa = sd.rdfa  # List[dict]
```

---

## Приклади

### E-commerce: Продукти

```python
from graph_crawler.extensions.plugins.node.structured_data import (
    StructuredDataPlugin,
    StructuredDataOptions,
)

options = StructuredDataOptions(
    allowed_types=['Product', 'Offer', 'AggregateOffer', 'AggregateRating'],
)

graph = gc.crawl(
    "https://shop.example.com",
    plugins=[StructuredDataPlugin(options)]
)

products = []
for node in graph:
    sd = node.user_data.get('structured_data')
    if sd:
        for product in sd.get_all_of_type('Product'):
            offers = product.get('offers', {})

            # Обробка AggregateOffer
            if isinstance(offers, list):
                prices = [o.get('price') for o in offers if o.get('price')]
                price = min(prices) if prices else None
            else:
                price = offers.get('price')

            products.append({
                'url': node.url,
                'name': product.get('name'),
                'brand': product.get('brand', {}).get('name'),
                'price': price,
                'currency': offers.get('priceCurrency') if isinstance(offers, dict) else None,
                'availability': offers.get('availability') if isinstance(offers, dict) else None,
                'rating': product.get('aggregateRating', {}).get('ratingValue'),
                'review_count': product.get('aggregateRating', {}).get('reviewCount'),
            })

print(f"Found {len(products)} products")

# Експорт
import pandas as pd
df = pd.DataFrame(products)
df.to_csv('products.csv', index=False)
```

### Новинні статті

```python
options = StructuredDataOptions(
    allowed_types=['Article', 'NewsArticle', 'BlogPosting', 'WebPage'],
)

graph = gc.crawl(
    "https://news.example.com",
    plugins=[StructuredDataPlugin(options)]
)

articles = []
for node in graph:
    sd = node.user_data.get('structured_data')
    if sd:
        for article in sd.get_all_of_type('Article'):
            # Author може бути string або object
            author = article.get('author', {})
            if isinstance(author, dict):
                author_name = author.get('name')
            elif isinstance(author, list):
                author_name = author[0].get('name') if author else None
            else:
                author_name = str(author)

            articles.append({
                'url': node.url,
                'headline': article.get('headline'),
                'author': author_name,
                'datePublished': article.get('datePublished'),
                'dateModified': article.get('dateModified'),
                'image': article.get('image'),
                'publisher': article.get('publisher', {}).get('name'),
            })

print(f"Found {len(articles)} articles")
```

### Job Postings

```python
options = StructuredDataOptions(
    allowed_types=['JobPosting'],
)

graph = gc.crawl(
    "https://jobs.example.com",
    plugins=[StructuredDataPlugin(options)]
)

jobs = []
for node in graph:
    sd = node.user_data.get('structured_data')
    if sd:
        for job in sd.get_all_of_type('JobPosting'):
            salary = job.get('baseSalary', {})

            jobs.append({
                'url': node.url,
                'title': job.get('title'),
                'company': job.get('hiringOrganization', {}).get('name'),
                'location': job.get('jobLocation', {}).get('address', {}).get('addressLocality'),
                'salary_min': salary.get('value', {}).get('minValue') if isinstance(salary.get('value'), dict) else None,
                'salary_max': salary.get('value', {}).get('maxValue') if isinstance(salary.get('value'), dict) else None,
                'salary_currency': salary.get('currency'),
                'employment_type': job.get('employmentType'),
                'date_posted': job.get('datePosted'),
                'valid_through': job.get('validThrough'),
            })

print(f"Found {len(jobs)} job postings")
```

### Social Media Preview

```python
graph = gc.crawl(
    "https://example.com",
    plugins=[StructuredDataPlugin()]
)

for node in graph:
    sd = node.user_data.get('structured_data')
    if sd:
        og = sd.open_graph
        twitter = sd.twitter_cards

        # Fallback chain: OG -> Twitter -> JSON-LD
        title = (
            og.get('og:title') or
            twitter.get('twitter:title') or
            sd.get_property('name')
        )
        description = (
            og.get('og:description') or
            twitter.get('twitter:description') or
            sd.get_property('description')
        )
        image = (
            og.get('og:image') or
            twitter.get('twitter:image') or
            sd.get_property('image')
        )

        print(f"\n{node.url}:")
        print(f"  Title: {title}")
        print(f"  Description: {description[:100] if description else None}...")
        print(f"  Image: {image}")
```

### SEO Audit

```python
def audit_structured_data(node):
    """Аудит структурованих даних для SEO."""
    sd = node.user_data.get('structured_data')
    issues = []

    if not sd or not sd.has_data:
        issues.append("No structured data found")
        return issues

    # JSON-LD check
    if not sd.json_ld:
        issues.append("No JSON-LD found (recommended by Google)")

    # Open Graph check
    og = sd.open_graph
    if not og.get('og:title'):
        issues.append("Missing og:title")
    if not og.get('og:description'):
        issues.append("Missing og:description")
    if not og.get('og:image'):
        issues.append("Missing og:image")

    # Twitter Cards check
    twitter = sd.twitter_cards
    if not twitter.get('twitter:card'):
        issues.append("Missing twitter:card")

    return issues

graph = gc.crawl(
    "https://example.com",
    plugins=[StructuredDataPlugin()]
)

for node in graph:
    issues = audit_structured_data(node)
    if issues:
        print(f"\n{node.url}:")
        for issue in issues:
            print(f"  ⚠️ {issue}")
```

---

## Парсери

GraphCrawler включає окремі парсери для кожного формату:

```python
from graph_crawler.extensions.plugins.node.structured_data import (
    JsonLdParser,
    OpenGraphParser,
    TwitterCardsParser,
    MicrodataParser,
    RdfaParser,
)

# Standalone використання
parser = JsonLdParser()
json_ld_data = parser.parse(html_content)

og_parser = OpenGraphParser()
og_data = og_parser.parse(html_content)
```

---

## SchemaType Enum

```python
from graph_crawler.extensions.plugins.node.structured_data import SchemaType

# Типові schema.org типи
SchemaType.PRODUCT
SchemaType.OFFER
SchemaType.ARTICLE
SchemaType.ORGANIZATION
SchemaType.PERSON
SchemaType.EVENT
SchemaType.JOB_POSTING
# ... та інші
```

---

## Обробка помилок

```python
options = StructuredDataOptions(
    fail_silently=True,  # За замовчуванням
)

graph = gc.crawl(url, plugins=[StructuredDataPlugin(options)])

for node in graph:
    sd = node.user_data.get('structured_data')

    # Перевірка на помилки
    if sd.has_errors:
        print(f"Errors on {node.url}:")
        for error in sd.errors:
            print(f"  - {error}")

    # Перевірка чи результат порожній через помилку
    if sd.is_error_result:
        print(f"Failed to parse: {sd.error_message}")
```

---

## Performance Tips

1. **Вимкніть непотрібні парсери:**

   ```python
   options = StructuredDataOptions(
       parse_rdfa=False,      # RDFa повільний
       parse_microdata=False, # Якщо не потрібен
   )
   ```

2. **Обмежте типи:**

   ```python
   options = StructuredDataOptions(
       allowed_types=['Product'],  # Тільки Product
   )
   ```

3. **Встановіть ліміти:**
   ```python
   options = StructuredDataOptions(
       max_jsonld_blocks=5,
       max_microdata_items=20,
       timeout_per_parser=1.0,
   )
   ```

---

## Наступні кроки

- [Custom Extractors →](custom-extractors.md)
- [Plugin System →](plugins.md)
