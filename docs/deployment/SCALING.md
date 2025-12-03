# Масштабування GraphCrawler

> **Філософія:** Один конфіг, масштабування через інфраструктуру  
> **Версія:** 3.2.0

---

## Принципи масштабування

### ✅ Що масштабується

1. **Кількість workers** (1 → 10 → 100 → 1000)
2. **Потужність БД** (memory → MongoDB → MongoDB Cluster)
3. **Потужність Broker** (Redis → Redis Cluster)
4. **RAM та CPU** на worker
5. **Мережева пропускна здатність**

### ❌ Що НЕ змінюється

1. **Ваш Python код** - завжди однаковий!
2. **API виклики** - `gc.crawl(..., wrapper=config)`
3. **Структура конфігу** - той самий dict
4. **Логіка краулінгу** - незмінна

---

## Вертикальне vs Горизонтальне масштабування

### Вертикальне (більший сервер)

```yaml
# Один потужний worker
worker:
  replicas: 1
  deploy:
    resources:
      limits:
        memory: 32G   # Багато RAM
        cpus: '16'    # Багато CPU
```

**Переваги:**
- ✅ Простіше налаштувати
- ✅ Менше overhead
- ✅ Швидша комунікація в межах процесу

**Недоліки:**
- ❌ Обмежений розмір сервера
- ❌ Single point of failure
- ❌ Дорожче масштабувати

**Коли використовувати:**
- Малі та середні проекти
- Обмежений бюджет на інфраструктуру
- Не критична відмовостійкість

---

### Горизонтальне (більше серверів)

```yaml
# Багато малих workers
worker:
  replicas: 100   # 100 workers
  deploy:
    resources:
      limits:
        memory: 2G    # Менше RAM
        cpus: '2'     # Менше CPU
```

**Переваги:**
- ✅ Необмежене масштабування
- ✅ Fault tolerance (один падає - інші працюють)
- ✅ Дешевше (commodity hardware)
- ✅ Cloud-friendly

**Недоліки:**
- ❌ Складніше налаштувати
- ❌ Більше overhead (мережа, координація)
- ❌ Потрібний оркестратор (Kubernetes)

**Коли використовувати:**
- Великі проекти (100+ сайтів)
- Критична відмовостійкість
- Cloud deployment
- Enterprise масштаб

---

## Калькулятор ресурсів

### Формули розрахунку

```python
# Базові параметри
pages_per_site = 1000
num_sites = 100
total_pages = pages_per_site * num_sites  # 100,000

# Workers
pages_per_hour_per_worker = 500  # HTTP driver
workers_needed = total_pages / pages_per_hour_per_worker / hours_available

# RAM на worker
ram_per_worker_http = 1 * 1024  # 1 GB для HTTP
ram_per_worker_playwright = 4 * 1024  # 4 GB для Playwright

# Redis
avg_url_size = 200  # bytes
redis_memory = (total_pages * avg_url_size) / (1024**3)  # GB

# MongoDB
avg_page_size = 50 * 1024  # 50 KB на сторінку
mongodb_storage = (total_pages * avg_page_size) / (1024**3)  # GB
```

### Приклади розрахунків

#### Сценарій 1: 10 сайтів × 1,000 сторінок = 10,000 сторінок

```python
# Параметри
total_pages = 10_000
hours_available = 2  # Хочу завершити за 2 години

# Workers
workers = 10_000 / 500 / 2 = 10 workers

# RAM
total_ram_workers = 10 × 1 GB = 10 GB

# Redis
redis_memory = 10_000 × 200 / (1024^3) ≈ 0.002 GB → 1 GB достатньо

# MongoDB
mongodb_storage = 10_000 × 50 KB / (1024^3) ≈ 0.5 GB → 1 GB достатньо
```

**Конфігурація:**
```yaml
redis:
  command: redis-server --maxmemory 1gb

worker:
  replicas: 10
  resources:
    limits:
      memory: 1G

mongodb:
  resources:
    limits:
      memory: 2G
      storage: 5G
```

---

#### Сценарій 2: 100 сайтів × 10,000 сторінок = 1,000,000 сторінок

```python
# Параметри
total_pages = 1_000_000
hours_available = 10

# Workers
workers = 1_000_000 / 500 / 10 = 200 workers

# RAM
total_ram_workers = 200 × 2 GB = 400 GB

# Redis
redis_memory = 1_000_000 × 200 / (1024^3) ≈ 0.2 GB → 2 GB

# MongoDB
mongodb_storage = 1_000_000 × 50 KB / (1024^3) ≈ 50 GB
```

**Конфігурація:**
```yaml
redis:
  command: redis-server --maxmemory 4gb

worker:
  replicas: 200
  resources:
    limits:
      memory: 2G

mongodb:
  replicas: 3  # Replica Set
  resources:
    limits:
      memory: 32G
      storage: 200G  # З запасом
```

---

#### Сценарій 3: 10,000 сайтів × 10,000 сторінок = 100,000,000 сторінок

```python
# Параметри
total_pages = 100_000_000
hours_available = 24 * 7  # Тиждень

# Workers
workers = 100_000_000 / 500 / 168 = 1,190 workers → 1,200 workers

# RAM
total_ram_workers = 1,200 × 2 GB = 2,400 GB = 2.4 TB

# Redis (Cluster потрібен!)
redis_memory = 100_000_000 × 200 / (1024^3) ≈ 20 GB → Redis Cluster

# MongoDB (Sharded Cluster)
mongodb_storage = 100_000_000 × 50 KB / (1024^3) ≈ 5,000 GB = 5 TB
```

**Конфігурація:**
```yaml
redis:
  type: RedisCluster
  shards: 10
  replicas: 3
  resources:
    limits:
      memory: 8Gi

worker:
  replicas: 1200
  autoscaling:
    enabled: true
    minReplicas: 500
    maxReplicas: 2000
  resources:
    limits:
      memory: 2Gi

mongodb:
  type: ShardedCluster
  shards: 20
  replicas: 3
  resources:
    limits:
      memory: 64Gi
      storage: 1Ti
```

---

## Bloom Filter та пам'ять

### Код з scheduler.py

```python
# graph_crawler/crawler/scheduler.py
bloom_capacity = 10_000_000  # За замовчуванням 10M URLs
bloom_error_rate = 0.001     # 0.1% false positive

# Економія пам'яті:
# 10M URLs в Python set:  ~800 MB
# 10M URLs в Bloom Filter: ~12 MB
# Економія: 67x
```

### Масштабування Bloom Filter

```python
# Для 100M URLs
bloom_capacity = 100_000_000  # 100M
# Пам'ять: ~120 MB (замість ~8 GB для set!)

# Для 1B URLs
bloom_capacity = 1_000_000_000  # 1B
# Пам'ять: ~1.2 GB (замість ~80 GB!)
```

**Bloom Filter автоматично масштабується!** Просто працює! 🎉

---

## Celery параметри

### Worker Prefetch Multiplier

```python
# celery_unified.py
worker_prefetch_multiplier = 4  # За замовчуванням
```

**Що це означає:**
- Кожен worker бере 4 задачі одночасно
- 100 workers × 4 = 400 задач паралельно

**Коли змінювати:**

```python
# Багато workers (100+) - зменшити
worker_prefetch_multiplier = 2
# 100 workers × 2 = 200 задач
# Краще розподіл навантаження

# Мало workers (1-10) - збільшити
worker_prefetch_multiplier = 8
# 10 workers × 8 = 80 задач
# Менше idle часу
```

**Налаштування:**
```bash
celery -A graph_crawler.infrastructure.messaging.celery_unified worker \
  --prefetch-multiplier=2
```

---

### Worker Max Tasks Per Child

```python
# celery_unified.py
worker_max_tasks_per_child = 100
```

**Що це означає:**
- Worker перезапускається після 100 задач
- Звільняє пам'ять від leaks
- Запобігає memory bloat

**Коли змінювати:**

```python
# Memory leaks - зменшити
worker_max_tasks_per_child = 50
# Частіший перезапуск

# Стабільна пам'ять - збільшити
worker_max_tasks_per_child = 500
# Рідший перезапуск, менше overhead
```

---

### Task Time Limit

```python
# celery_unified.py
task_time_limit = 600       # 10 хвилин hard limit
task_soft_time_limit = 540  # 9 хвилин soft limit
```

**Коли змінювати:**

```python
# Повільні сайти - збільшити
task_time_limit = 1200      # 20 хвилин
task_soft_time_limit = 1080

# Швидкі сайти - зменшити
task_time_limit = 300       # 5 хвилин
task_soft_time_limit = 270
```

---

## Auto-scaling (Kubernetes)

### Horizontal Pod Autoscaler (HPA)

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: crawler-worker-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: crawler-worker
  minReplicas: 10
  maxReplicas: 500
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 10
        periodSeconds: 60
```

**Що це робить:**
- Автоматично додає workers при CPU > 70%
- Автоматично видаляє workers при CPU < 70%
- Scale up: швидко (50% за 60 сек)
- Scale down: повільно (10% за 60 сек)

---

### Custom Metrics (Celery Queue)

```yaml
apiVersion: v2
kind: HorizontalPodAutoscaler
metadata:
  name: crawler-worker-queue-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: crawler-worker
  minReplicas: 10
  maxReplicas: 1000
  metrics:
  - type: Pods
    pods:
      metric:
        name: celery_queue_length
      target:
        type: AverageValue
        averageValue: "100"  # 100 задач на worker
```

**Що це робить:**
- Масштабує на основі довжини черги Celery
- 1000 задач → 10 workers
- 10,000 задач → 100 workers
- 100,000 задач → 1000 workers

---

## Redis масштабування

### Standalone → Sentinel → Cluster

#### 1. Standalone (< 100 workers)

```yaml
redis:
  image: redis:7-alpine
  command: redis-server --maxmemory 4gb
```

**Обмеження:**
- Single point of failure
- Max ~16 GB RAM
- Max ~100,000 ops/sec

---

#### 2. Sentinel (100-500 workers)

```yaml
# Master
redis-master:
  image: redis:7-alpine
  command: redis-server --maxmemory 8gb

# Replica 1
redis-replica-1:
  image: redis:7-alpine
  command: redis-server --replicaof redis-master 6379

# Replica 2
redis-replica-2:
  image: redis:7-alpine
  command: redis-server --replicaof redis-master 6379

# Sentinel
redis-sentinel:
  image: redis:7-alpine
  command: redis-sentinel /etc/sentinel.conf
```

**Переваги:**
- ✅ High availability (auto failover)
- ✅ Read scaling (replicas)
- ❌ НЕ масштабує writes

---

#### 3. Cluster (500+ workers)

```yaml
redis:
  type: RedisCluster
  shards: 10       # 10 shards
  replicas: 2      # 2 replicas per shard
  resources:
    limits:
      memory: 16Gi
```

**Переваги:**
- ✅ Write scaling (sharding)
- ✅ Необмежене масштабування
- ✅ Automatic sharding
- ✅ High availability

**Конфігурація:**
```bash
# Кожен shard отримує частину ключів
# 10 shards = 10x write throughput
# 20 nodes (10 masters + 10 replicas)
```

---

## MongoDB масштабування

### Standalone → Replica Set → Sharded Cluster

#### 1. Standalone (< 1M документів)

```yaml
mongodb:
  image: mongo:7
  command: mongod --wiredTigerCacheSizeGB 4
```

**Обмеження:**
- Single point of failure
- Max ~16 GB WiredTiger cache
- Не масштабується

---

#### 2. Replica Set (1M-10M документів)

```yaml
mongodb:
  replicas: 3
  command: |
    mongod --replSet rs0 --wiredTigerCacheSizeGB 16
```

**Переваги:**
- ✅ High availability
- ✅ Read scaling (secondaries)
- ❌ НЕ масштабує writes

**Ініціалізація:**
```javascript
rs.initiate({
  _id: "rs0",
  members: [
    { _id: 0, host: "mongo-1:27017" },
    { _id: 1, host: "mongo-2:27017" },
    { _id: 2, host: "mongo-3:27017" }
  ]
})
```

---

#### 3. Sharded Cluster (10M+ документів)

```yaml
# Config Servers
mongocfg:
  replicas: 3

# Shards
mongod:
  shards: 10
  replicas: 3  # Per shard

# Router (mongos)
mongos:
  replicas: 3
```

**Архітектура:**
```
Client → mongos → Config Servers
              ↓
         Shard 1 (RS)
         Shard 2 (RS)
         ...
         Shard N (RS)
```

**Shard Key:**
```javascript
// Sharding по URL hash
sh.shardCollection("crawler_db.nodes", { url: "hashed" })
```

**Переваги:**
- ✅ Write scaling (sharding)
- ✅ Необмежене зберігання
- ✅ Automatic balancing

---

## Моніторинг та алерти

### Метрики для моніторингу

```python
# Worker metrics
- Active workers
- Tasks per second
- Average task duration
- Memory usage per worker
- CPU usage per worker

# Redis metrics
- Queue length
- Memory usage
- Operations per second
- Connected clients

# MongoDB metrics
- Documents count
- Storage size
- Query latency
- Connections count
```

### Prometheus + Grafana

```yaml
# docker-compose.yml
prometheus:
  image: prom/prometheus
  volumes:
    - ./prometheus.yml:/etc/prometheus/prometheus.yml
  ports:
    - "9090:9090"

grafana:
  image: grafana/grafana
  ports:
    - "3000:3000"
  environment:
    - GF_AUTH_ANONYMOUS_ENABLED=true
```

**prometheus.yml:**
```yaml
scrape_configs:
  - job_name: 'celery'
    static_configs:
      - targets: ['flower:5555']
  
  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']
  
  - job_name: 'mongodb'
    static_configs:
      - targets: ['mongodb-exporter:9216']
```

---

## Контрольний список масштабування

- ✅ Визначив цільовий масштаб (кількість сайтів, сторінок)
- ✅ Розрахував потрібні ресурси (workers, RAM, storage)
- ✅ Обрав архітектуру (standalone, cluster)
- ✅ Налаштував auto-scaling (для Kubernetes)
- ✅ Налаштував моніторинг
- ✅ Протестував на малому масштабі
- ✅ Поступово збільшую навантаження
- ✅ Моніторю метрики та налаштовую

---

## Наступні кроки

- [KUBERNETES.md](./KUBERNETES.md) - Kubernetes deployment
- [PRODUCTION.md](./PRODUCTION.md) - Production best practices
- [MONITORING.md](./MONITORING.md) - Детальний моніторинг

---

**Пам'ятайте:** Ваш код не міняється! Тільки кількість workers та потужність інфраструктури! 🚀
