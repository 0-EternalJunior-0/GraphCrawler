# Distributed Crawling

> **Час читання:** 12 хвилин  
> **Рівень:** Senior

Розподілений краулінг для масштабованих задач.

---

## Огляд

GraphCrawler підтримує розподілений краулінг через Celery:

```
┌────────────────────────────────────────────────────────┐
│                 DISTRIBUTED ARCHITECTURE                    │
├────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────┐          ┌───────────────────┐          │
│  │ Coordinator │─────────▶│  Redis/RabbitMQ  │          │
│  │  (Master)   │          │ (Message Broker)│          │
│  └─────────────┘          └─────────┬─────────┘          │
│                                    │                        │
│              ┌─────────────────┼─────────────────┐       │
│              │                 │                 │       │
│              ▼                 ▼                 ▼       │
│     ┌────────────┐  ┌────────────┐  ┌────────────┐     │
│     │  Worker 1  │  │  Worker 2  │  │  Worker N  │     │
│     │  (Celery)  │  │  (Celery)  │  │  (Celery)  │     │
│     └───────┬────┘  └──────┬─────┘  └──────┬─────┘     │
│            │             │             │             │
│            └─────────────┼─────────────┘             │
│                          │                           │
│                          ▼                           │
│                 ┌─────────────────┐                  │
│                 │MongoDB/PostgreSQL│                 │
│                 │ (Result Storage) │                  │
│                 └─────────────────┘                  │
│                                                              │
└────────────────────────────────────────────────────────┘
```

---

## Вимоги

### Інфраструктура

- **Message Broker:** Redis або RabbitMQ
- **Result Storage:** MongoDB або PostgreSQL
- **Workers:** Python 3.11+ з GraphCrawler

### Встановлення

```bash
pip install graph-crawler[distributed]
```

---

## Базове використання

### Конфігурація

```python
import graph_crawler as gc

config = {
    "broker": {
        "type": "redis",
        "host": "redis.example.com",
        "port": 6379,
        "password": "secret",
    },
    "database": {
        "type": "mongodb",
        "host": "mongo.example.com",
        "port": 27017,
        "database": "crawler",
    }
}

graph = gc.crawl(
    "https://large-site.com",
    max_pages=1000000,  # 1 мільйон сторінок
    wrapper=config,
)
```

### Запуск Workers

```bash
# Worker 1
celery -A graph_crawler.distributed worker --loglevel=info -n worker1@%h

# Worker 2
celery -A graph_crawler.distributed worker --loglevel=info -n worker2@%h

# Worker N
celery -A graph_crawler.distributed worker --loglevel=info -n workerN@%h
```

---

## Docker Compose Setup

```yaml
# docker-compose.distributed.yml
version: '3.8'

services:
  # Message Broker
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes

  # Database
  mongodb:
    image: mongo:7
    ports:
      - "27017:27017"
    volumes:
      - mongo_data:/data/db
    environment:
      MONGO_INITDB_ROOT_USERNAME: root
      MONGO_INITDB_ROOT_PASSWORD: secret

  # Coordinator
  coordinator:
    build: .
    command: python -m graph_crawler.distributed.coordinator
    environment:
      - REDIS_HOST=redis
      - MONGO_HOST=mongodb
    depends_on:
      - redis
      - mongodb

  # Workers
  worker:
    build: .
    command: celery -A graph_crawler.distributed worker --loglevel=info
    environment:
      - REDIS_HOST=redis
      - MONGO_HOST=mongodb
      - PYTHON_GIL=0  # Free-threading
    depends_on:
      - redis
      - mongodb
    deploy:
      replicas: 4  # 4 воркери

  # Flower (Monitoring)
  flower:
    build: .
    command: celery -A graph_crawler.distributed flower --port=5555
    ports:
      - "5555:5555"
    depends_on:
      - redis

volumes:
  redis_data:
  mongo_data:
```

### Запуск

```bash
docker-compose -f docker-compose.distributed.yml up -d --scale worker=8
```

---

## Конфігурація

### Redis Broker

```python
config = {
    "broker": {
        "type": "redis",
        "host": "localhost",
        "port": 6379,
        "db": 0,
        "password": None,
    }
}
```

### RabbitMQ Broker

```python
config = {
    "broker": {
        "type": "rabbitmq",
        "host": "localhost",
        "port": 5672,
        "user": "guest",
        "password": "guest",
        "vhost": "/",
    }
}
```

### MongoDB Database

```python
config = {
    "database": {
        "type": "mongodb",
        "host": "localhost",
        "port": 27017,
        "database": "crawler",
        "collection": "crawl_results",
        "user": None,
        "password": None,
    }
}
```

### PostgreSQL Database

```python
config = {
    "database": {
        "type": "postgresql",
        "host": "localhost",
        "port": 5432,
        "database": "crawler",
        "user": "crawler",
        "password": "secret",
    }
}
```

---

## Моніторинг

### Flower Dashboard

```bash
celery -A graph_crawler.distributed flower --port=5555
```

Доступ: http://localhost:5555

### Programmatic Monitoring

```python
from graph_crawler.distributed import DistributedCrawler

crawler = DistributedCrawler(config)

# Статус завдань
status = crawler.get_status()
print(f"Pending tasks: {status['pending']}")
print(f"Active tasks: {status['active']}")
print(f"Completed: {status['completed']}")

# Статистика воркерів
workers = crawler.get_workers()
for worker in workers:
    print(f"{worker['name']}: {worker['tasks_completed']} tasks")
```

---

## Приклад: Краулінг 1M+ сторінок

```python
import graph_crawler as gc
from graph_crawler import URLRule

# Конфігурація для великого краулінгу
config = {
    "broker": {
        "type": "redis",
        "host": "redis-cluster.example.com",
        "port": 6379,
    },
    "database": {
        "type": "mongodb",
        "host": "mongo-cluster.example.com",
        "port": 27017,
        "database": "large_crawl",
    },
    "workers": {
        "concurrency": 100,  # 100 паралельних запитів на воркер
        "prefetch_multiplier": 4,
    }
}

# URL правила
rules = [
    URLRule(pattern=r"/product/", priority=10),
    URLRule(pattern=r"\.pdf$", should_scan=False),
    URLRule(pattern=r"/admin/", should_scan=False),
]

# Запуск
graph = gc.crawl(
    "https://mega-shop.com",
    max_depth=10,
    max_pages=5000000,  # 5 мільйонів
    url_rules=rules,
    request_delay=0.05,
    wrapper=config,
)

print(f"Crawled {len(graph.nodes)} pages")
```

---

## EasyDistributedCrawler

Спрощений API для розподіленого краулінгу:

```python
from graph_crawler.distributed import EasyDistributedCrawler

crawler = EasyDistributedCrawler(
    redis_url="redis://localhost:6379/0",
    mongo_url="mongodb://localhost:27017/crawler",
)

# Запуск краулінгу
job_id = crawler.start("https://example.com", max_pages=100000)

# Перевірка статусу
while not crawler.is_completed(job_id):
    status = crawler.get_status(job_id)
    print(f"Progress: {status['completed']}/{status['total']}")
    time.sleep(10)

# Отримання результату
graph = crawler.get_result(job_id)
```

---

## Наступні кроки

- [Proxy & Security →](proxy-security.md)
- [Session Management →](session-management.md)
- [Architecture Overview →](../architecture/ARCHITECTURE_OVERVIEW.md)
