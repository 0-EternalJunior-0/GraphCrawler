# Kubernetes Deployment для GraphCrawler

> **Для масштабування 100+ workers**  
> **Версія:** 3.2.0

---

## Чому Kubernetes?

### Docker Compose → Kubernetes

| Аспект | Docker Compose | Kubernetes |
|--------|----------------|------------|
| Масштаб | 1-20 workers | 100-1000+ workers |
| Сервери | 1 машина | Multiple nodes |
| Auto-scaling | ❌ Немає | ✅ HPA |
| Self-healing | ❌ Немає | ✅ Automatic |
| Load balancing | ❌ Базовий | ✅ Advanced |
| Rolling updates | ❌ Manual | ✅ Automatic |
| Fault tolerance | ❌ Слабка | ✅ Висока |

**Коли переходити на Kubernetes:**
- 50+ workers
- Потрібен auto-scaling
- Multiple servers/regions
- Production критичність

---

## Архітектура в Kubernetes

```
┌─────────────────────────────────────────────────────────────┐
│                    KUBERNETES CLUSTER                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌───────────────┐   ┌────────────────┐   ┌──────────────┐ │
│  │ Redis         │   │ MongoDB        │   │ Workers      │ │
│  │ StatefulSet   │   │ StatefulSet    │   │ Deployment   │ │
│  │               │   │                │   │              │ │
│  │ • Service     │   │ • Service      │   │ • HPA        │ │
│  │ • PVC         │   │ • PVC          │   │ • ConfigMap  │ │
│  └───────────────┘   └────────────────┘   └──────────────┘ │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                    INGRESS                             │  │
│  │  External Load Balancer                                │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Базова конфігурація

### 1. Namespace

```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: crawler
  labels:
    name: crawler
```

---

### 2. ConfigMap (Конфігурація)

```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: crawler-config
  namespace: crawler
data:
  # Redis
  REDIS_HOST: "redis-service"
  REDIS_PORT: "6379"
  
  # MongoDB
  MONGO_HOST: "mongo-service"
  MONGO_PORT: "27017"
  MONGO_DB: "crawler_results"
  
  # Celery
  CELERY_BROKER_URL: "redis://redis-service:6379/0"
  CELERY_RESULT_BACKEND: "redis://redis-service:6379/1"
```

---

### 3. Secrets (Паролі)

```yaml
# secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: crawler-secrets
  namespace: crawler
type: Opaque
stringData:
  # Redis
  REDIS_PASSWORD: "your_redis_password"
  
  # MongoDB
  MONGO_USERNAME: "crawler_user"
  MONGO_PASSWORD: "your_mongo_password"
```

**Створення:**
```bash
kubectl apply -f secrets.yaml
```

---

### 4. Redis StatefulSet

```yaml
# redis-statefulset.yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: redis
  namespace: crawler
spec:
  serviceName: redis-service
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        command:
        - redis-server
        - --maxmemory
        - "4gb"
        - --maxmemory-policy
        - allkeys-lru
        - --requirepass
        - $(REDIS_PASSWORD)
        env:
        - name: REDIS_PASSWORD
          valueFrom:
            secretKeyRef:
              name: crawler-secrets
              key: REDIS_PASSWORD
        ports:
        - containerPort: 6379
          name: redis
        resources:
          limits:
            memory: 6Gi
            cpu: 2000m
          requests:
            memory: 4Gi
            cpu: 1000m
        volumeMounts:
        - name: redis-data
          mountPath: /data
  volumeClaimTemplates:
  - metadata:
      name: redis-data
    spec:
      accessModes: ["ReadWriteOnce"]
      storageClassName: "standard"
      resources:
        requests:
          storage: 10Gi
---
apiVersion: v1
kind: Service
metadata:
  name: redis-service
  namespace: crawler
spec:
  clusterIP: None  # Headless service
  selector:
    app: redis
  ports:
  - port: 6379
    targetPort: 6379
    name: redis
```

---

### 5. MongoDB StatefulSet

```yaml
# mongo-statefulset.yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: mongodb
  namespace: crawler
spec:
  serviceName: mongo-service
  replicas: 3  # Replica Set
  selector:
    matchLabels:
      app: mongodb
  template:
    metadata:
      labels:
        app: mongodb
    spec:
      containers:
      - name: mongodb
        image: mongo:7
        command:
        - mongod
        - --replSet
        - rs0
        - --bind_ip_all
        - --wiredTigerCacheSizeGB
        - "8"
        env:
        - name: MONGO_INITDB_ROOT_USERNAME
          valueFrom:
            secretKeyRef:
              name: crawler-secrets
              key: MONGO_USERNAME
        - name: MONGO_INITDB_ROOT_PASSWORD
          valueFrom:
            secretKeyRef:
              name: crawler-secrets
              key: MONGO_PASSWORD
        ports:
        - containerPort: 27017
          name: mongodb
        resources:
          limits:
            memory: 16Gi
            cpu: 4000m
          requests:
            memory: 8Gi
            cpu: 2000m
        volumeMounts:
        - name: mongo-data
          mountPath: /data/db
  volumeClaimTemplates:
  - metadata:
      name: mongo-data
    spec:
      accessModes: ["ReadWriteOnce"]
      storageClassName: "standard"
      resources:
        requests:
          storage: 100Gi
---
apiVersion: v1
kind: Service
metadata:
  name: mongo-service
  namespace: crawler
spec:
  clusterIP: None
  selector:
    app: mongodb
  ports:
  - port: 27017
    targetPort: 27017
    name: mongodb
```

**Ініціалізація Replica Set:**
```bash
# Підключитись до першого pod
kubectl exec -it mongodb-0 -n crawler -- mongosh

# В mongosh
rs.initiate({
  _id: "rs0",
  members: [
    { _id: 0, host: "mongodb-0.mongo-service.crawler.svc.cluster.local:27017" },
    { _id: 1, host: "mongodb-1.mongo-service.crawler.svc.cluster.local:27017" },
    { _id: 2, host: "mongodb-2.mongo-service.crawler.svc.cluster.local:27017" }
  ]
})
```

---

### 6. Worker Deployment

```yaml
# worker-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: crawler-worker
  namespace: crawler
spec:
  replicas: 50  # Базова кількість
  selector:
    matchLabels:
      app: crawler-worker
  template:
    metadata:
      labels:
        app: crawler-worker
    spec:
      containers:
      - name: worker
        image: your-registry/crawler-worker:latest
        command:
        - celery
        - -A
        - graph_crawler.infrastructure.messaging.celery_unified
        - worker
        - --loglevel=info
        - --concurrency=4
        - -Q
        - graph_crawler
        envFrom:
        - configMapRef:
            name: crawler-config
        env:
        - name: REDIS_PASSWORD
          valueFrom:
            secretKeyRef:
              name: crawler-secrets
              key: REDIS_PASSWORD
        - name: MONGO_USERNAME
          valueFrom:
            secretKeyRef:
              name: crawler-secrets
              key: MONGO_USERNAME
        - name: MONGO_PASSWORD
          valueFrom:
            secretKeyRef:
              name: crawler-secrets
              key: MONGO_PASSWORD
        resources:
          limits:
            memory: 2Gi
            cpu: 2000m
          requests:
            memory: 1Gi
            cpu: 500m
        livenessProbe:
          exec:
            command:
            - celery
            - -A
            - graph_crawler.infrastructure.messaging.celery_unified
            - inspect
            - ping
          initialDelaySeconds: 60
          periodSeconds: 30
          timeoutSeconds: 10
        readinessProbe:
          exec:
            command:
            - celery
            - -A
            - graph_crawler.infrastructure.messaging.celery_unified
            - inspect
            - ping
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
```

---

### 7. Horizontal Pod Autoscaler (HPA)

```yaml
# hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: crawler-worker-hpa
  namespace: crawler
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: crawler-worker
  minReplicas: 20
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
      - type: Pods
        value: 10
        periodSeconds: 60
      selectPolicy: Max
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 10
        periodSeconds: 60
      selectPolicy: Min
```

**Що робить HPA:**
- Мінімум 20 workers
- Максимум 500 workers
- Scale up: швидко (50% або +10 pods за 60 сек)
- Scale down: повільно (10% за 60 сек)
- Метрики: CPU 70%, Memory 80%

---

### 8. Flower (Моніторинг)

```yaml
# flower-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: flower
  namespace: crawler
spec:
  replicas: 1
  selector:
    matchLabels:
      app: flower
  template:
    metadata:
      labels:
        app: flower
    spec:
      containers:
      - name: flower
        image: mher/flower
        command:
        - celery
        - --broker=$(CELERY_BROKER_URL)
        - flower
        - --port=5555
        envFrom:
        - configMapRef:
            name: crawler-config
        env:
        - name: REDIS_PASSWORD
          valueFrom:
            secretKeyRef:
              name: crawler-secrets
              key: REDIS_PASSWORD
        ports:
        - containerPort: 5555
          name: flower
        resources:
          limits:
            memory: 512Mi
            cpu: 500m
          requests:
            memory: 256Mi
            cpu: 250m
---
apiVersion: v1
kind: Service
metadata:
  name: flower-service
  namespace: crawler
spec:
  type: LoadBalancer  # Або ClusterIP + Ingress
  selector:
    app: flower
  ports:
  - port: 5555
    targetPort: 5555
    name: flower
```

---

## Deployment команди

### Початкове розгортання

```bash
# Створити namespace
kubectl apply -f namespace.yaml

# Secrets та ConfigMap
kubectl apply -f secrets.yaml
kubectl apply -f configmap.yaml

# Інфраструктура
kubectl apply -f redis-statefulset.yaml
kubectl apply -f mongo-statefulset.yaml

# Ініціалізувати MongoDB Replica Set
kubectl exec -it mongodb-0 -n crawler -- mongosh
# rs.initiate({...})

# Workers
kubectl apply -f worker-deployment.yaml

# Auto-scaling
kubectl apply -f hpa.yaml

# Моніторинг
kubectl apply -f flower-deployment.yaml
```

---

### Перевірка статусу

```bash
# Всі ресурси
kubectl get all -n crawler

# Pods
kubectl get pods -n crawler

# Логи worker
kubectl logs -f deployment/crawler-worker -n crawler

# Логи Redis
kubectl logs -f statefulset/redis -n crawler

# HPA статус
kubectl get hpa -n crawler

# Описати pod
kubectl describe pod <pod-name> -n crawler
```

---

### Масштабування

```bash
# Manual scaling (перезаписує HPA)
kubectl scale deployment crawler-worker -n crawler --replicas=100

# Перевірити HPA
kubectl get hpa crawler-worker-hpa -n crawler

# Подивитись metrics
kubectl top pods -n crawler
kubectl top nodes
```

---

### Оновлення

```bash
# Оновити image
kubectl set image deployment/crawler-worker \
  worker=your-registry/crawler-worker:v2 \
  -n crawler

# Статус rollout
kubectl rollout status deployment/crawler-worker -n crawler

# Rollback
kubectl rollout undo deployment/crawler-worker -n crawler
```

---

## Production конфігурація

### 1. Redis Cluster (замість standalone)

Для 500+ workers використовуйте Redis Cluster:

```yaml
# redis-cluster.yaml (спрощена версія)
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: redis-cluster
  namespace: crawler
spec:
  serviceName: redis-cluster
  replicas: 6  # 3 masters + 3 replicas
  selector:
    matchLabels:
      app: redis-cluster
  template:
    metadata:
      labels:
        app: redis-cluster
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        command:
        - redis-server
        - /conf/redis.conf
        - --cluster-enabled
        - "yes"
        - --cluster-config-file
        - /data/nodes.conf
        - --maxmemory
        - "8gb"
        ports:
        - containerPort: 6379
          name: client
        - containerPort: 16379
          name: gossip
        volumeMounts:
        - name: conf
          mountPath: /conf
        - name: data
          mountPath: /data
      volumes:
      - name: conf
        configMap:
          name: redis-cluster-config
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 20Gi
```

**Ініціалізація Redis Cluster:**
```bash
kubectl exec -it redis-cluster-0 -n crawler -- redis-cli \
  --cluster create \
  $(kubectl get pods -n crawler -l app=redis-cluster -o jsonpath='{range.items[*]}{.status.podIP}:6379 ') \
  --cluster-replicas 1
```

---

### 2. MongoDB Sharded Cluster

Для 10M+ документів:

```yaml
# Спрощена структура
# Config Servers (3 replicas)
# Shard Servers (N shards × 3 replicas)
# Mongos Routers (3 replicas)
```

Детальна конфігурація дуже велика, рекомендуємо використати Helm chart:

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm install mongodb bitnami/mongodb-sharded \
  --namespace crawler \
  --set shards=10 \
  --set mongos.replicas=3 \
  --set configsvr.replicas=3
```

---

### 3. Persistent Volumes

```yaml
# pv.yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: crawler-redis-pv
spec:
  capacity:
    storage: 20Gi
  accessModes:
  - ReadWriteOnce
  persistentVolumeReclaimPolicy: Retain
  storageClassName: fast-ssd
  hostPath:  # Або AWS EBS, GCE PD, etc
    path: /mnt/redis-data
```

---

### 4. Resource Quotas (Namespace limits)

```yaml
# resource-quota.yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: crawler-quota
  namespace: crawler
spec:
  hard:
    requests.cpu: "500"      # 500 CPU cores
    requests.memory: 1Ti     # 1 TB RAM
    limits.cpu: "1000"
    limits.memory: 2Ti
    persistentvolumeclaims: "50"
```

---

## Моніторинг в Kubernetes

### Prometheus Operator

```bash
# Встановити Prometheus Operator
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace
```

### ServiceMonitor для Workers

```yaml
# servicemonitor.yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: crawler-worker-monitor
  namespace: crawler
spec:
  selector:
    matchLabels:
      app: crawler-worker
  endpoints:
  - port: metrics
    interval: 30s
```

---

## Troubleshooting

### Pod не стартує

```bash
# Перевірка
kubectl describe pod <pod-name> -n crawler
kubectl logs <pod-name> -n crawler

# Типові проблеми:
# 1. Image pull error - перевірити registry
# 2. Resource limits - збільшити memory/cpu
# 3. ConfigMap/Secret - перевірити наявність
```

### OOMKilled (Out of Memory)

```bash
# Симптом
kubectl get pods -n crawler
# STATUS: OOMKilled

# Рішення:
# 1. Збільшити memory limits в deployment
# 2. Зменшити concurrency workers
# 3. Увімкнути worker_max_tasks_per_child
```

### Проблеми з networking

```bash
# Перевірка з'єднання
kubectl exec -it <worker-pod> -n crawler -- ping redis-service
kubectl exec -it <worker-pod> -n crawler -- ping mongo-service

# DNS lookup
kubectl exec -it <worker-pod> -n crawler -- nslookup redis-service
```

---

## Контрольний список

- ✅ Створив namespace
- ✅ Налаштував ConfigMap та Secrets
- ✅ Розгорнув Redis (StatefulSet)
- ✅ Розгорнув MongoDB (StatefulSet або Sharded)
- ✅ Ініціалізував MongoDB Replica Set
- ✅ Розгорнув Workers (Deployment)
- ✅ Налаштував HPA (auto-scaling)
- ✅ Розгорнув Flower (моніторинг)
- ✅ Налаштував Prometheus/Grafana
- ✅ Протестував на малому масштабі
- ✅ Поступово збільшую replicas

---

## Наступні кроки

- [PRODUCTION.md](./PRODUCTION.md) - Production best practices
- [MONITORING.md](./MONITORING.md) - Детальний моніторинг
- [SCALING.md](./SCALING.md) - Стратегії масштабування

---

**Пам'ятайте:** Ваш Python код залишається незмінним! Kubernetes масштабує інфраструктуру! 🚀
