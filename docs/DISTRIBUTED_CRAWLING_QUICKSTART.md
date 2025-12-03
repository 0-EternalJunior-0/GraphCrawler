# 🚀 Distributed Crawling - Швидкий Старт

## Архітектура

```
┌─────────────────────────────────────────────────────────────────┐
│                    DISTRIBUTED ARCHITECTURE                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Windows/Linux Client                    Docker Server          │
│   ┌──────────────────┐                   ┌──────────────────┐   │
│   │  Python Script   │                   │  Redis Container │   │
│   │  gc.crawl(...)   │──── Redis ────────│  port: 6579      │   │
│   │  wrapper=config  │     Protocol      │                  │   │
│   └──────────────────┘                   └────────┬─────────┘   │
│                                                   │              │
│                                          ┌────────▼─────────┐   │
│                                          │  Celery Worker   │   │
│                                          │  celery_unified  │   │
│                                          │  queue: graph_   │   │
│                                          │  crawler         │   │
│                                          └──────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 1. Запуск Docker (на сервері)

```bash
# Клонуємо репозиторій (якщо ще не зроблено)
git clone https://gitlab.com/demoprogrammer/web_graf.git
cd web_graf

# Запускаємо Redis + Worker
docker compose up -d

# Перевіряємо логи
docker compose logs -f worker
```

**Очікуваний вивід worker:**
```
celery@hostname ready.
[tasks]
  . graph_crawler.crawl_batch
  . graph_crawler.crawl_page
  . graph_crawler.health_check
```

## 2. Перевірка підключення

```bash
# Перевіряємо Redis
docker compose exec redis redis-cli ping
# Повинно вивести: PONG

# Перевіряємо порт ззовні (якщо потрібно)
nc -zv YOUR_SERVER_IP 6579
```

## 3. Запуск клієнта (на локальній машині)

```python
import graph_crawler as gc
from graph_crawler import AsyncDriver

# Конфігурація distributed crawling
config = {
    "broker": {
        "type": "redis",
        "host": "YOUR_SERVER_IP",  # IP вашого сервера з Docker
        "port": 6579               # Порт Redis
    },
    "database": {"type": "memory"}
}

# Запуск краулінгу
graph = gc.crawl(
    "https://example.com",
    max_depth=2,
    max_pages=50,
    wrapper=config,           # ← Вмикає distributed режим
    driver=AsyncDriver,       # Використовує async driver на воркерах
    timeout=120               # Timeout 2 хвилини
)

print(f"Знайдено {len(graph.nodes)} сторінок")
```

## 4. Troubleshooting

### ❌ Tasks не виконуються (worker не бачить)

**Причина:** Неправильна черга

**Рішення:** Переконайтесь що worker слухає чергу `graph_crawler`:
```bash
docker compose logs worker | grep "queues"
# Повинно показати: .> graph_crawler    exchange=...
```

### ❌ Connection refused до Redis

**Причина:** Файрвол або неправильний порт

**Рішення:**
```bash
# На сервері
sudo ufw allow 6579/tcp

# Перевірка
netstat -tlnp | grep 6579
```

### ❌ Worker не стартує

**Причина:** Помилки в коді

**Рішення:**
```bash
docker compose logs worker
# Подивіться на помилки імпорту або конфігурації
```

## 5. docker-compose.yml (референс)

```yaml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    container_name: crawler_redis
    ports:
      - "6579:6379"  # Доступний ззовні
    command: redis-server --maxmemory 2gb --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data
    networks:
      - crawler_net

  worker:
    build: .
    container_name: crawler_worker_1
    command: celery -A graph_crawler.infrastructure.messaging.celery_unified worker --loglevel=info --concurrency=2 -Q graph_crawler
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/1
    depends_on:
      - redis
    networks:
      - crawler_net

volumes:
  redis_data:

networks:
  crawler_net:
    driver: bridge
```

## 6. Масштабування

Щоб додати більше workers:

```bash
# Запуск 3 workers
docker compose up -d --scale worker=3
```

Або окремий docker-compose для workers на інших машинах:

```yaml
# docker-compose.worker.yml
services:
  worker:
    build: .
    command: celery -A graph_crawler.infrastructure.messaging.celery_unified worker --loglevel=info --concurrency=4 -Q graph_crawler
    environment:
      - CELERY_BROKER_URL=redis://MAIN_SERVER_IP:6579/0
      - CELERY_RESULT_BACKEND=redis://MAIN_SERVER_IP:6579/1
```

---

**Версія:** 3.2.0  
**Оновлено:** Грудень 2025
