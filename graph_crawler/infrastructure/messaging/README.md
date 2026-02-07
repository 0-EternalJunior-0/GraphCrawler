# Distributed Crawling Guide 🚀

Простий спосіб запустити розподілений краулінг через YAML конфіг для GraphCrawler.

---

## 📋 Quick Start

### 1. Створити config.yaml

```yaml
broker:
  type: redis
  host: server11.example.com
  port: 6379

database:
  type: mongodb
  host: server12.example.com
  port: 27017
  database: crawler_results

crawl_task:
  urls:
    - https://example.com
  max_depth: 3
  max_pages: 1000
  extractors:
    - phones
    - emails
    - prices
```

### 2. Запустити Redis (Server 11)

```bash
docker run -d -p 6379:6379 redis:latest
```

### 3. Запустити MongoDB (Server 12)

```bash
docker run -d -p 27017:27017 mongo:latest
```

### 4. Запустити Celery Workers (Servers 1-10)

На кожному сервері:
```bash
# Clone repo
git clone https://github.com/0-EternalJunior-0/GraphCrawler.git
cd web_graf

# Install
pip install -e .

# Start worker
celery -A graph_crawler worker --loglevel=info --concurrency=4
```

### 5. Запустити Coordinator (Local)

```python
from graph_crawler.distributed import EasyDistributedCrawler

crawler = EasyDistributedCrawler.from_yaml("config.yaml")
results = crawler.crawl()

# Отримати результати
stats = results.get_stats()
print(f"Знайдено: {stats['total_nodes']} сторінок")
print(f"Посилань: {stats['total_edges']}")

# Extractors результати
for node in results.nodes.values():
    phones = node.user_data.get('phones', [])
    emails = node.user_data.get('emails', [])
    prices = node.user_data.get('prices', [])
    
    if phones or emails or prices:
        print(f"\n{node.url}:")
        if phones:
            print(f"  Телефони: {phones}")
        if emails:
            print(f"  Emails: {emails}")
        if prices:
            print(f"  Ціни: {prices}")
```

---

## 🏗️ Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                    DISTRIBUTED ARCHITECTURE                     │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  LOCAL (Master)                                                 │
│  ┌──────────────┐                                               │
│  │ Coordinator  │                                               │
│  │ (EasyDist...) │                                              │
│  └──────┬───────┘                                               │
│         │                                                        │
│         │ 1. Push tasks                                         │
│         ▼                                                        │
│  ┌─────────────────────────────────────┐                        │
│  │  REDIS BROKER (Server 11)           │                        │
│  │  - Task queue: graph_crawler        │                        │
│  │  - Results backend                  │                        │
│  └────────┬────────────────────────────┘                        │
│           │                                                      │
│           │ 2. Workers pull tasks                               │
│           ▼                                                      │
│  ┌────────────────────────────────────────────────┐             │
│  │         CELERY WORKERS (Servers 1-10)          │             │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐     │             │
│  │  │ Worker 1 │  │ Worker 2 │  │ Worker N │     │             │
│  │  │ + Driver │  │ + Driver │  │ + Driver │     │             │
│  │  │ +Plugins │  │ +Plugins │  │ +Plugins │     │             │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘     │             │
│  │       │             │             │            │             │
│  │       │ 3. Scan pages & extract data           │             │
│  │       ▼             ▼             ▼            │             │
│  └────────────────────────────────────────────────┘             │
│           │                                                      │
│           │ 4. Save results                                     │
│           ▼                                                      │
│  ┌─────────────────────────────────────┐                        │
│  │  MONGODB (Server 12)                │                        │
│  │  - Collection: nodes                │                        │
│  │  - Collection: edges                │                        │
│  │  - user_data: phones, emails, etc.  │                        │
│  └─────────────────────────────────────┘                        │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

---

## ⚙️ Configuration Options

### Broker Configuration

```yaml
broker:
  type: redis          # або rabbitmq
  host: localhost      # адреса брокера
  port: 6379          # порт брокера
  db: 0               # номер БД (тільки для Redis)
  password: null      # пароль (опціонально)
```

### Database Configuration

```yaml
database:
  type: mongodb        # або postgresql
  host: localhost      # адреса БД
  port: 27017         # порт БД
  database: package_crawler   # назва БД
  username: null      # ім'я користувача (опціонально)
  password: null      # пароль (опціонально)
```

### Proxy Configuration (Optional)

```yaml
proxy:
  enabled: true
  type: file          # або api
  source: ./proxies.txt  # шлях до файлу або API URL
```

### Crawl Task Configuration

```yaml
crawl_task:
  urls:
    - https://example1.com
    - https://example2.com
  max_depth: 3        # максимальна глибина
  max_pages: 1000     # максимум сторінок
  extractors:
    - phones          # витягувати телефони
    - emails          # витягувати emails
    - prices          # витягувати ціни
  custom_plugins: []  # custom плагіни (import paths)
```

### Workers Configuration

```yaml
workers: 10                      # кількість воркерів
task_time_limit: 600             # ліміт часу задачі (сек)
worker_prefetch_multiplier: 4    # префетч множник
```

---

## 🔌 Extractors

### Phone Extractor

Витягує телефонні номери з різних форматів:

- **UA**: +380XXXXXXXXX, 0XXXXXXXXX, (0XX) XXX-XX-XX
- **RU**: +7XXXXXXXXXX
- **US**: +1XXXXXXXXXX, (XXX) XXX-XXXX
- **International**: +XXXXXXXXXXXX
- **tel: links**: `<a href="tel:+380...">`

```python
phones = node.user_data.get('phones', [])
# ['380501234567', '380441234567']
```

### Email Extractor

Витягує email адреси:

- **RFC 5322 compliant** regex
- **mailto: links** parsing
- **Фільтрація** fake domains (example.com, test.com)
- **Deduplication** (lowercase)

```python
emails = node.user_data.get('emails', [])
# ['info@example.com', 'support@example.com']
```

### Price Extractor

Витягує ціни та зарплати:

- **USD**: $50, $1,000, $1.5k, $1M
- **EUR**: €50, 50€, 50 EUR
- **UAH**: ₴50, 50 грн, 50 гривень
- **Salary ranges**: $50k - $70k, від 30000 грн

```python
prices = node.user_data.get('prices', [])
# [{'value': '$1000', 'currency': 'USD', 'original': '$1,000'}]
```

---

## 🔧 Advanced Usage

### Custom Plugins

Додайте власні плагіни для витягування даних:

```python
# myapp/CustomPlugins.py
from graph_crawler.plugins.node.base import BaseNodePlugin, NodePluginType, NodePluginContext

class CustomExtractorPlugin(BaseNodePlugin):
    @property
    def name(self):
        return "CustomExtractor"
    
    @property
    def plugin_type(self):
        return NodePluginType.ON_HTML_PARSED
    
    def execute(self, context: NodePluginContext):
        # Ваша логіка витягування даних
        context.user_data['custom_data'] = "value"
        return context
```

У config.yaml:

```yaml
crawl_task:
  custom_plugins:
    - "myapp.CustomPlugins.CustomExtractorPlugin"
```

### Programmatic Configuration

```python
from graph_crawler.distributed import EasyDistributedCrawler

config = {
    "broker": {
        "type": "redis",
        "host": "localhost",
        "port": 6379
    },
    "database": {
        "type": "mongodb",
        "host": "localhost",
        "port": 27017,
        "database": "test"
    },
    "crawl_task": {
        "urls": ["https://example.com"],
        "max_depth": 3,
        "extractors": ["phones", "emails"]
    }
}

crawler = EasyDistributedCrawler.from_dict(config)
results = crawler.crawl()
```

---

## METRICS Statistics

```python
stats = crawler.get_stats()

print(f"Pages crawled: {stats['pages_crawled']}")
print(f"Total nodes: {stats['total_nodes']}")
print(f"Total edges: {stats['total_edges']}")
print(f"Celery workers: {stats['celery_workers']}")
```

---

## 🐛 Troubleshooting

### Workers не підключаються до Redis

```bash
# Перевірити чи працює Redis
redis-cli ping
# Має повернути: PONG

# Перевірити чи worker бачить Redis
celery -A graph_crawler inspect active
```

### MongoDB connection failed

```bash
# Перевірити чи працює MongoDB
mongosh --eval "db.adminCommand('ping')"

# Перевірити connection string
python -c "from pymongo import MongoClient; print(MongoClient('mongodb://localhost:27017/').server_info())"
```

### Tasks не виконуються

```bash
# Перевірити черги
celery -A graph_crawler inspect reserved

# Перевірити логи workers
celery -A graph_crawler worker --loglevel=debug
```

---

## 📚 References

- [CelerySpider Source](../crawler/celery_spider.py)
- [Config Schema](config.py)
- [Extractors](../plugins/node/extractors/)
- [Example Config](../../examples/distributed/config.yaml)

---

## 🎯 Best Practices

1. **Start small**: Почніть з 2-3 workers і збільшуйте поступово
2. **Monitor workers**: Використовуйте `celery flower` для моніторингу
3. **Rate limiting**: Додайте затримки між запитами (`request_delay`)
4. **Error handling**: Workers автоматично retry при помилках (3 спроби)
5. **Storage**: Для >100k сторінок використовуйте PostgreSQL замість MongoDB

---

**Готово!** 🎉

Тепер ви маєте повністю налаштовану систему розподіленого краулінгу з автоматичним витягуванням телефонів, emails та цін!
