# Конфігурації GraphCrawler

> **Принцип:** Один конфіг для всіх масштабів  
> **Версія:** 3.2.0

---

## Базова структура конфігу

```python
config = {
    "broker": {
        "type": "redis",      # або "rabbitmq"
        "host": "hostname",
        "port": 6379,
        # Опціонально:
        "db": 0,
        "password": None
    },
    "database": {
        "type": "mongodb",    # або "postgresql", "memory"
        "host": "hostname",
        "port": 27017,
        "database": "db_name",
        # Опціонально:
        "username": None,
        "password": None
    }
}
```

---

## Конфігурації по сценаріям

### 1. Локальна розробка (без distributed)

```python
import graph_crawler as gc

# Без wrapper - все локально
graph = gc.crawl("https://example.com")
```

**Що використовується:**
- Driver: HTTP (in-process)
- Storage: Memory (max 1000 nodes)
- Scheduler: Local with Bloom Filter

**Коли використовувати:**
- Розробка та тестування
- < 10 сайтів
- < 1000 сторінок

---

### 2. Мінімальна distributed (Redis + Memory)

```python
config = {
    "broker": {
        "type": "redis",
        "host": "localhost",
        "port": 6379
    },
    "database": {
        "type": "memory"  # Ліміт 1000 nodes!
    }
}

graph = gc.crawl("https://example.com", wrapper=config)
```

**Що використовується:**
- Broker: Redis (черга задач)
- Storage: Memory (workers)
- Workers: Distributed

**Обмеження:**
- ⚠️ MAX 1000 сторінок (жорстке обмеження коду)
- ⚠️ Втрата даних при перезапуску

**Коли використовувати:**
- Тестування distributed режиму
- Короткі краулінги
- Прототипування

---

### 3. Стандартна (Redis + MongoDB)

```python
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
        "database": "crawler_results"
    }
}

graph = gc.crawl("https://example.com", wrapper=config)
```

**Що використовується:**
- Broker: Redis
- Storage: MongoDB
- Workers: Distributed

**Переваги:**
- ✅ Необмежена кількість сторінок
- ✅ Persistent storage
- ✅ Масштабується

**Коли використовувати:**
- 10 - 100,000 сайтів
- Production краулінги
- Довготривалі задачі

---

### 4. З автентифікацією (MongoDB + Auth)

```python
config = {
    "broker": {
        "type": "redis",
        "host": "redis-server.com",
        "port": 6379,
        "password": "redis_secret"
    },
    "database": {
        "type": "mongodb",
        "host": "mongo-server.com",
        "port": 27017,
        "database": "crawler_db",
        "username": "crawler_user",
        "password": "mongo_secret"
    }
}

graph = gc.crawl("https://example.com", wrapper=config)
```

**Коли використовувати:**
- Production середовища
- Хмарні сервіси (AWS, GCP, Azure)
- Спільні сервери

---

### 5. PostgreSQL замість MongoDB

```python
config = {
    "broker": {
        "type": "redis",
        "host": "localhost",
        "port": 6379
    },
    "database": {
        "type": "postgresql",
        "host": "localhost",
        "port": 5432,
        "database": "crawler_db",
        "username": "postgres",
        "password": "pg_secret"
    }
}

graph = gc.crawl("https://example.com", wrapper=config)
```

**Переваги PostgreSQL:**
- ✅ ACID транзакції
- ✅ SQL запити
- ✅ Краща консистентність

**Коли використовувати:**
- Потрібні складні запити
- Інтеграція з існуючою PostgreSQL інфраструктурою
- Потрібна сувора консистентність

---

### 6. RabbitMQ замість Redis

```python
config = {
    "broker": {
        "type": "rabbitmq",
        "host": "localhost",
        "port": 5672,
        "username": "guest",
        "password": "guest"
    },
    "database": {
        "type": "mongodb",
        "host": "localhost",
        "port": 27017
    }
}

graph = gc.crawl("https://example.com", wrapper=config)
```

**Переваги RabbitMQ:**
- ✅ Надійність (durability)
- ✅ Складні routing patterns
- ✅ Гарантована доставка

**Коли використовувати:**
- Критична надійність
- Складні workflow
- Існуюча RabbitMQ інфраструктура

---

## Інфраструктурні параметри (НЕ в коді!)

Ці параметри налаштовуються в Docker Compose або Kubernetes, **НЕ в Python коді!**

### Docker Compose

```yaml
services:
  redis:
    image: redis:7-alpine
    command: redis-server --maxmemory 2gb --maxmemory-policy allkeys-lru
    # maxmemory: скільки Redis може використати RAM
    # allkeys-lru: політика видалення при переповненні

  worker:
    replicas: 10  # Кількість workers
    deploy:
      resources:
        limits:
          memory: 2G    # RAM на worker
          cpus: '2'     # CPU cores
        reservations:
          memory: 512M  # Мінімум RAM

  mongodb:
    image: mongo:7
    command: mongod --wiredTigerCacheSizeGB 4
    # wiredTigerCacheSizeGB: скільки RAM для кешу MongoDB
```

### Kubernetes

```yaml
spec:
  replicas: 50  # Кількість workers
  
  resources:
    limits:
      memory: 2Gi
      cpu: 2000m
    requests:
      memory: 512Mi
      cpu: 500m
  
  autoscaling:
    enabled: true
    minReplicas: 10
    maxReplicas: 200
    targetCPUUtilizationPercentage: 70
```

---

## Масштабування конфігу

### Мінімальна конфігурація (1-10 сайтів)

```yaml
# docker-compose.yml
redis:
  command: redis-server --maxmemory 1gb

worker:
  replicas: 2
  deploy:
    resources:
      limits:
        memory: 1G

mongodb:
  # За замовчуванням
```

**Python конфіг (ОДНАКОВИЙ!):**
```python
config = {
    "broker": {"type": "redis", "host": "localhost"},
    "database": {"type": "mongodb", "host": "localhost"}
}
```

---

### Середня конфігурація (10-100 сайтів)

```yaml
# docker-compose.yml
redis:
  command: redis-server --maxmemory 4gb

worker:
  replicas: 20
  deploy:
    resources:
      limits:
        memory: 2G

mongodb:
  command: mongod --wiredTigerCacheSizeGB 4
```

**Python конфіг (ОДНАКОВИЙ!):**
```python
config = {
    "broker": {"type": "redis", "host": "localhost"},
    "database": {"type": "mongodb", "host": "localhost"}
}
```

---

### Велика конфігурація (100-1000 сайтів)

```yaml
# Kubernetes deployment
redis:
  replicas: 3  # Redis Cluster
  resources:
    limits:
      memory: 16Gi

worker:
  replicas: 100
  autoscaling:
    maxReplicas: 200
  resources:
    limits:
      memory: 2Gi

mongodb:
  replicas: 3  # Replica Set
  resources:
    limits:
      memory: 32Gi
```

**Python конфіг (ОДНАКОВИЙ!):**
```python
config = {
    "broker": {"type": "redis", "host": "redis-cluster"},
    "database": {"type": "mongodb", "host": "mongo-replica-set"}
}
```

---

### Enterprise конфігурація (10M+ сайтів)

```yaml
# Kubernetes production
redis:
  type: RedisCluster  # Sharded
  shards: 10
  replicas: 3
  resources:
    limits:
      memory: 32Gi

worker:
  replicas: 500
  autoscaling:
    minReplicas: 100
    maxReplicas: 1000
  resources:
    limits:
      memory: 4Gi

mongodb:
  type: ShardedCluster
  shards: 10
  replicas: 3
  resources:
    limits:
      memory: 128Gi
```

**Python конфіг (ОДНАКОВИЙ!):**
```python
config = {
    "broker": {"type": "redis", "host": "redis-cluster.production"},
    "database": {"type": "mongodb", "host": "mongo-sharded.production"}
}
```

---

## Playwright конфігурація

### Для JavaScript сайтів

**Код (ОДНАКОВИЙ):**
```python
from graph_crawler.drivers.playwright import PlaywrightDriver

# Той самий wrapper конфіг
config = {
    "broker": {"type": "redis", "host": "localhost"},
    "database": {"type": "mongodb", "host": "localhost"}
}

# Тільки driver змінюється
graph = gc.crawl(
    "https://spa-site.com",
    driver=PlaywrightDriver,  # <-- Playwright замість HTTP
    wrapper=config
)
```

**Інфраструктура (Docker Compose):**
```yaml
worker:
  build:
    context: .
    dockerfile: Dockerfile.playwright  # Інший Dockerfile!
  replicas: 5
  deploy:
    resources:
      limits:
        memory: 4G    # Більше RAM для браузерів
        cpus: '2'
  shm_size: '2gb'     # Обов'язково для браузерів!
```

**Dockerfile.playwright:**
```dockerfile
FROM python:3.11-slim

# Playwright залежності
RUN apt-get update && apt-get install -y \
    wget gnupg libnss3 libnspr4 libatk1.0-0 \
    libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libasound2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Встановити Playwright
RUN pip install playwright
RUN playwright install chromium

COPY . .
RUN pip install -e .

CMD ["celery", "-A", "graph_crawler.infrastructure.messaging.celery_unified", "worker", "--loglevel=info", "-Q", "graph_crawler"]
```

---

## Змінні середовища

### В коді Python (НЕ рекомендується)

```python
# ❌ Погано - хардкод
config = {
    "broker": {"host": "localhost", "port": 6379},
    "database": {"host": "localhost", "port": 27017}
}
```

### Через змінні середовища (✅ Рекомендується)

```python
import os

# ✅ Добре - використання env vars
config = {
    "broker": {
        "type": "redis",
        "host": os.getenv("REDIS_HOST", "localhost"),
        "port": int(os.getenv("REDIS_PORT", 6379)),
        "password": os.getenv("REDIS_PASSWORD")
    },
    "database": {
        "type": "mongodb",
        "host": os.getenv("MONGO_HOST", "localhost"),
        "port": int(os.getenv("MONGO_PORT", 27017)),
        "database": os.getenv("MONGO_DB", "crawler_results"),
        "username": os.getenv("MONGO_USER"),
        "password": os.getenv("MONGO_PASSWORD")
    }
}

graph = gc.crawl("https://example.com", wrapper=config)
```

**Docker Compose:**
```yaml
worker:
  environment:
    - REDIS_HOST=redis
    - REDIS_PORT=6379
    - MONGO_HOST=mongodb
    - MONGO_PORT=27017
    - MONGO_DB=crawler_results
```

**Kubernetes ConfigMap:**
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: crawler-config
data:
  REDIS_HOST: "redis-service"
  REDIS_PORT: "6379"
  MONGO_HOST: "mongo-service"
  MONGO_PORT: "27017"
  MONGO_DB: "crawler_results"
```

---

## Контрольний список

- ✅ Розумію що Python конфіг однаковий для всіх масштабів
- ✅ Масштабування через Docker Compose / Kubernetes
- ✅ Використовую змінні середовища замість хардкоду
- ✅ Знаю різницю між Redis та RabbitMQ
- ✅ Знаю різницю між MongoDB та PostgreSQL
- ✅ Для Playwright використовую більше RAM
- ✅ Моніторю ресурси (RAM, CPU, disk)

---

## Наступні кроки

- [SCALING.md](./SCALING.md) - Стратегії масштабування
- [KUBERNETES.md](./KUBERNETES.md) - Kubernetes deployment
- [PRODUCTION.md](./PRODUCTION.md) - Production practices

---

**Ключове правило:** Ваш Python код не змінюється! Тільки інфраструктурні параметри! 🚀
