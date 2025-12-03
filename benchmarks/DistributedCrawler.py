import redis
import sys
import time
from functools import wraps
import graph_crawler as gc
from graph_crawler import AsyncDriver

# ==============================
# Декоратор для вимірювання часу
# ==============================
def measure_time(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        times = []
        for i in range(1):
            start = time.time()
            result = func(*args, **kwargs)
            end = time.time()
            duration = end - start
            times.append(duration)
            print(f"{func.__name__} | запуск {i+1}: {duration:.6f} секунд/ len(graph) = {len(result)}")

        avg = sum(times) / len(times)
        print(f"➡ Середній час для {func.__name__}: {avg:.6f} секунд\n")
        return result
    return wrapper


# ==============================
# Функція для перевірки Redis та workers
# ==============================
def check_redis_and_workers(host: str, port: int, retries=5, delay=2):
    """Перевіряє доступність Redis та Celery workers."""
    print("=" * 50)
    print("🔍 Перевірка підключення...")
    print("=" * 50)
    
    # 1. Перевірка Redis
    for i in range(retries):
        try:
            r = redis.Redis(host=host, port=port)
            if r.ping():
                print(f"✅ Redis доступний на {host}:{port}")
                
                # Перевіряємо черги
                queues = r.keys("*celery*") or []
                if queues:
                    print(f"   Знайдені черги: {[q.decode() for q in queues[:5]]}")
                break
        except redis.ConnectionError:
            print(f"❌ Не вдалося підключитися до Redis {host}:{port}, спроба {i+1}/{retries}")
            time.sleep(delay)
    else:
        print("🚨 Redis недоступний. Перевірте конфігурацію.")
        sys.exit(1)
    
    # 2. Перевірка Celery workers
    print("\n🔍 Перевірка Celery workers...")
    try:
        from graph_crawler.infrastructure.messaging.celery_unified import celery
        
        # Налаштовуємо broker URL
        broker_url = f"redis://{host}:{port}/0"
        celery.conf.update(broker_url=broker_url, result_backend=f"redis://{host}:{port}/1")
        
        inspect = celery.control.inspect(timeout=5)
        ping_result = inspect.ping()
        
        if ping_result:
            worker_count = len(ping_result)
            worker_names = list(ping_result.keys())
            print(f"✅ Знайдено {worker_count} worker(s): {', '.join(worker_names)}")
            
            # Перевіряємо активні задачі
            active = inspect.active() or {}
            active_count = sum(len(tasks) for tasks in active.values())
            print(f"   Активних задач: {active_count}")
            
            # Перевіряємо черги які слухають workers
            queues = inspect.active_queues() or {}
            for worker, worker_queues in queues.items():
                queue_names = [q.get('name', 'unknown') for q in worker_queues]
                print(f"   {worker}: черги {queue_names}")
        else:
            print("⚠️  Workers не відповідають! Переконайтесь що worker запущений:")
            print("   docker compose up -d")
            print("   docker compose logs -f worker")
    except Exception as e:
        print(f"⚠️  Помилка перевірки workers: {e}")
    
    print("=" * 50)


# ==============================
# Конфігурація для distributed
# ==============================
# ВАЖЛИВО: host та port повинні бути доступні як з клієнта так і з worker
# Якщо worker в Docker - він підключається через внутрішню мережу (redis:6379)
# Якщо клієнт ззовні - він підключається через публічний IP:port
config = {
    "broker": {
        "type": "redis",
        "host": "45.159.248.146",  # Публічний IP вашого сервера
        "port": 6579               # Порт Redis (проброшений з Docker)
    },
    "database": {"type": "memory"},
    
    # ========== НАЛАШТУВАННЯ ЧЕРЕЗ ПУЛЬТ ==========
    "batch_size": 12,              # URLs в одній задачі (більше = швидше, але більше RAM)
    "worker_prefetch_multiplier": 64  # Скільки задач брати наперед
}

# Перевірка Redis та workers
check_redis_and_workers(config["broker"]["host"], config["broker"]["port"])

batch_async = 30

# ==============================
# Функція краулінгу
# ==============================
@measure_time
def distributed_crawl():
    """Тест distributed краулінгу."""
    print("\n🚀 Запуск distributed crawl...")
    
    graph = gc.crawl(
        "https://netpeak.net/",
        max_depth=2,
        max_pages=1 + batch_async * 10,
        wrapper=config,
        driver=gc.AsyncDriver,
        edge_strategy=gc.EdgeCreationStrategy.NEW_ONLY,
        timeout=120  # 2 хвилини timeout
    )
    return graph


if __name__ == "__main__":
    try:
        result = distributed_crawl()
        print(f"\n📊 Результат:")
        print(f"   Вузлів: {len(result.nodes)}")
        print(f"   Ребер: {len(result.edges)}")
        print(f"\n✅ Тест завершено успішно!")
    except Exception as e:
        print(f"\n❌ Помилка: {e}")
        import traceback
        traceback.print_exc()