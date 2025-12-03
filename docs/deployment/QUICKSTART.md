# GraphCrawler: Швидкий старт

> **Мета:** Запустити перший краулінг за 5 хвилин  
> **Рівень:** Початківець

---

## За 5 хвилин до першого краулінгу

### Крок 1: Встановлення

```bash
# Клонування проекту
git clone https://gitlab.com/demoprogrammer/web_graf.git
cd web_graf

# Встановлення
pip install -e .
```

### Крок 2: Простий краулінг (локально)

```python
# simple_crawl.py
import graph_crawler as gc

# Найпростіший краулінг
graph = gc.crawl("https://example.com")

print(f"Знайдено {len(graph.nodes)} сторінок")
print(f"Знайдено {len(graph.edges)} посилань")
```

Запуск:
```bash
python simple_crawl.py
```

**Вітаємо! Ваш перший краулінг готовий!** 🎉

---

## Далі: Масштабування (той самий код!)

### Крок 3: Docker Compose (distributed)

Створіть `docker-compose.yml`:

```yaml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    command: redis-server --maxmemory 2gb --maxmemory-policy allkeys-lru
    networks:
      - crawler_net

  mongodb:
    image: mongo:7
    ports:
      - "27017:27017"
    environment:
      - MONGO_INITDB_ROOT_USERNAME=crawler
      - MONGO_INITDB_ROOT_PASSWORD=your_password
    volumes:
      - mongodb_data:/data/db
    networks:
      - crawler_net

  worker:
    build: .
    command: celery -A graph_crawler.infrastructure.messaging.celery_unified worker --loglevel=info --concurrency=4 -Q graph_crawler
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/1
    depends_on:
      - redis
      - mongodb
    deploy:
      replicas: 5  # 5 workers
      resources:
        limits:
          memory: 2G
    networks:
      - crawler_net

volumes:
  mongodb_data:

networks:
  crawler_net:
    driver: bridge
```

### Крок 4: Dockerfile

Створіть `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Системні залежності
RUN apt-get update && apt-get install -y gcc g++ && rm -rf /var/lib/apt/lists/*

# Python залежності
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Код
COPY . .
RUN pip install -e .

# Команда
CMD ["celery", "-A", "graph_crawler.infrastructure.messaging.celery_unified", "worker", "--loglevel=info", "-Q", "graph_crawler"]
```

### Крок 5: Той самий код з distributed

```python
# distributed_crawl.py
import graph_crawler as gc

# ТОЙ САМИЙ КОД, тільки з wrapper
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
        "database": "crawler_results",
        "username": "crawler",
        "password": "your_password"
    }
}

# Той самий crawl, тільки з wrapper!
graph = gc.crawl(
    "https://example.com",
    max_depth=3,
    wrapper=config  # <-- Увімкнення distributed
)

print(f"Знайдено {len(graph.nodes)} сторінок")
```

### Крок 6: Запуск

```bash
# Запустити інфраструктуру
docker-compose up -d

# Перевірити workers
docker-compose ps

# Запустити краулінг
python distributed_crawl.py

# Подивитись логи
docker-compose logs -f worker
```

---

## Конфігурація для різних масштабів

### 1-10 сайтів (локально)

```python
# Без wrapper - працює локально
graph = gc.crawl("https://example.com")
```

**Інфраструктура:** Ваш комп'ютер

---

### 10-100 сайтів (Docker Compose)

```python
config = {
    "broker": {"type": "redis", "host": "localhost", "port": 6379},
    "database": {"type": "mongodb", "host": "localhost", "port": 27017}
}
graph = gc.crawl("https://example.com", wrapper=config)
```

**Інфраструктура:**
```yaml
worker:
  replicas: 10
  resources:
    limits:
      memory: 2G
```

---

### 100-1000 сайтів (Kubernetes)

```python
# ТОЙ САМИЙ КОД!
config = {
    "broker": {"type": "redis", "host": "redis-service", "port": 6379},
    "database": {"type": "mongodb", "host": "mongo-service", "port": 27017}
}
graph = gc.crawl("https://example.com", wrapper=config)
```

**Інфраструктура:** `kubectl apply -f k8s/`
```yaml
spec:
  replicas: 50
  resources:
    limits:
      memory: 2Gi
```

---

### 10M+ сайтів (Production Kubernetes)

```python
# ТОЙ САМИЙ КОД!!!
config = {
    "broker": {"type": "redis", "host": "redis-cluster", "port": 6379},
    "database": {"type": "mongodb", "host": "mongo-cluster", "port": 27017}
}
graph = gc.crawl("https://example.com", wrapper=config)
```

**Інфраструктура:** 
```yaml
spec:
  replicas: 500
  autoscaling:
    enabled: true
    minReplicas: 100
    maxReplicas: 1000
```

---

## Універсальний шаблон коду

```python
import graph_crawler as gc

def crawl_with_config(urls: list, config: dict = None):
    """
    Універсальна функція краулінгу.
    
    Працює для:
    - 1 сайту (config=None)
    - 10 сайтів (config з Redis)
    - 10M сайтів (config з Redis Cluster)
    """
    results = []
    
    for url in urls:
        graph = gc.crawl(
            url,
            max_depth=3,
            max_pages=None,  # Без ліміту
            wrapper=config   # None або distributed
        )
        results.append(graph)
    
    return results

# Локально
graphs = crawl_with_config(["https://site1.com", "https://site2.com"])

# Distributed (той самий код!)
config = {...}
graphs = crawl_with_config(["https://site1.com", "https://site2.com"], config)
```

---

## Моніторинг

### Flower (Celery UI)

Додайте в `docker-compose.yml`:

```yaml
flower:
  image: mher/flower
  command: celery --broker=redis://redis:6379/0 flower --port=5555
  ports:
    - "5555:5555"
  environment:
    - CELERY_BROKER_URL=redis://redis:6379/0
  depends_on:
    - redis
  networks:
    - crawler_net
```

Відкрийте: http://localhost:5555

### Логи

```bash
# Worker логи
docker-compose logs -f worker

# Redis
docker-compose logs -f redis

# MongoDB
docker-compose logs -f mongodb

# Всі разом
docker-compose logs -f
```

---

## Типові проблеми

### Worker не стартує

```bash
# Перевірка
docker-compose ps
docker-compose logs worker

# Перезапуск
docker-compose restart worker
```

### Redis недоступний

```bash
# Перевірка з'єднання
docker-compose exec worker ping redis

# Перевірка порту
docker-compose exec redis redis-cli ping
```

### MongoDB недоступний

```bash
# Перевірка
docker-compose exec mongodb mongosh --eval "db.adminCommand('ping')"
```

### Out of Memory

```yaml
# Збільшити пам'ять
worker:
  deploy:
    resources:
      limits:
        memory: 4G  # Було 2G
```

---

## Наступні кроки

Після швидкого старту:

1. **Базова конфігурація:** [CONFIGS.md](./CONFIGS.md)
2. **Масштабування:** [SCALING.md](./SCALING.md)
3. **Kubernetes:** [KUBERNETES.md](./KUBERNETES.md)
4. **Production:** [PRODUCTION.md](./PRODUCTION.md)

---

## Контрольний список

- ✅ Встановив GraphCrawler
- ✅ Запустив простий краулінг локально
- ✅ Створив docker-compose.yml
- ✅ Запустив distributed режим
- ✅ Перевірив логи та моніторинг
- ✅ Розумію що код не міняється при масштабуванні

**Готово! Тепер ви можете масштабувати від 1 до 10M сайтів!** 🚀
