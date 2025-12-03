# GraphCrawler Documentation Index

> **Центральний індекс документації**  
> **Версія:** 3.2.0  
> **Дата:** Грудень 2025

---

## 📚 Структура документації

```
docs/
├── INDEX.md                    # Ви тут!
├── README.md                   # Огляд документації
├── architecture/               # Архітектура системи
│   ├── ARCHITECTURE_OVERVIEW.md
│   ├── LAYER_SPECIFICATION.md
│   ├── COMPONENT_CATALOG.md
│   ├── COMMUNICATION_CHANNELS.md
│   ├── FACTORY_LIFECYCLE.md
│   ├── EXTENSION_POINTS.md
│   └── PLUGIN_SYSTEM.md
├── api/                        # API документація
│   └── API.md
├── deployment_new/             # Deployment документація
│   ├── README.md
│   ├── QUICKSTART.md
│   ├── CONFIGS.md
│   ├── SCALING.md
│   ├── KUBERNETES.md
│   ├── PRODUCTION.md
│   └── MONITORING.md
└── DISTRIBUTED_CRAWLING_QUICKSTART.md
```

---

## 🎯 Швидкі посилання по темах

### Початківці

**Хочу швидко почати:**
1. [QUICKSTART](./deployment_new/QUICKSTART.md) - Запуск за 5 хвилин
2. [API Reference](./api/API.md) - Основні функції

**Розумію основи, хочу більше:**
1. [CONFIGS](./deployment_new/CONFIGS.md) - Всі типи конфігурацій
2. [Architecture Overview](./architecture/ARCHITECTURE_OVERVIEW.md) - Як працює система

---

### Розробники

**Хочу розширити функціональність:**
1. [PLUGIN_SYSTEM](./architecture/PLUGIN_SYSTEM.md) - Створення плагінів
2. [EXTENSION_POINTS](./architecture/EXTENSION_POINTS.md) - Точки розширення
3. [COMPONENT_CATALOG](./architecture/COMPONENT_CATALOG.md) - Каталог компонентів

**Розумію код, хочу deep dive:**
1. [LAYER_SPECIFICATION](./architecture/LAYER_SPECIFICATION.md) - Детальна специфікація шарів
2. [COMMUNICATION_CHANNELS](./architecture/COMMUNICATION_CHANNELS.md) - Канали комунікації
3. [FACTORY_LIFECYCLE](./architecture/FACTORY_LIFECYCLE.md) - Фабрики та життєвий цикл

---

### DevOps / SRE

**Хочу розгорнути в production:**
1. [SCALING](./deployment_new/SCALING.md) - Стратегії масштабування
2. [KUBERNETES](./deployment_new/KUBERNETES.md) - Kubernetes deployment
3. [PRODUCTION](./deployment_new/PRODUCTION.md) - Production practices

**Налаштовую моніторинг:**
1. [MONITORING](./deployment_new/MONITORING.md) - Моніторинг та алерти
2. [CONFIGS](./deployment_new/CONFIGS.md) - Інфраструктурні параметри

---

## 📖 Документація по категоріях

### 1. Architecture (Архітектура)

Для розуміння внутрішньої будови системи.

| Документ | Опис | Аудиторія |
|----------|------|-----------|
| [ARCHITECTURE_OVERVIEW](./architecture/ARCHITECTURE_OVERVIEW.md) | Високорівневий огляд архітектури | Архітектори, Senior Dev |
| [LAYER_SPECIFICATION](./architecture/LAYER_SPECIFICATION.md) | Детальна специфікація шарів | Middle/Senior Dev |
| [COMPONENT_CATALOG](./architecture/COMPONENT_CATALOG.md) | Каталог всіх компонентів | All Developers |
| [COMMUNICATION_CHANNELS](./architecture/COMMUNICATION_CHANNELS.md) | Канали комунікації між компонентами | Middle/Senior Dev |
| [FACTORY_LIFECYCLE](./architecture/FACTORY_LIFECYCLE.md) | Фабрики та життєвий цикл об'єктів | Middle/Senior Dev |
| [EXTENSION_POINTS](./architecture/EXTENSION_POINTS.md) | Точки розширення системи | All Developers |
| [PLUGIN_SYSTEM](./architecture/PLUGIN_SYSTEM.md) | Система плагінів | All Developers |

---

### 2. API Reference (Публічне API)

Для використання бібліотеки в коді.

| Документ | Опис | Аудиторія |
|----------|------|-----------|
| [API.md](./api/API.md) | Повна документація API | All Developers |

**Основні функції:**
- `crawl()` - Синхронний краулінг
- `async_crawl()` - Асинхронний краулінг
- `Crawler` - Reusable краулер
- `Graph`, `Node`, `Edge` - Базові класи

---

### 3. Deployment (Розгортання)

Для запуску та масштабування системи.

| Документ | Опис | Аудиторія |
|----------|------|-----------|
| [Deployment README](./deployment_new/README.md) | Огляд deployment документації | All |
| [QUICKSTART](./deployment_new/QUICKSTART.md) | Швидкий старт за 5 хвилин | Початківці |
| [CONFIGS](./deployment_new/CONFIGS.md) | Всі типи конфігурацій | Middle/Senior Dev |
| [SCALING](./deployment_new/SCALING.md) | Стратегії масштабування | DevOps, SRE |
| [KUBERNETES](./deployment_new/KUBERNETES.md) | Kubernetes deployment | DevOps, SRE |
| [PRODUCTION](./deployment_new/PRODUCTION.md) | Production best practices | Senior DevOps |
| [MONITORING](./deployment_new/MONITORING.md) | Моніторинг та алерти | DevOps, SRE |

---

## 🎓 Навчальні шляхи

### Шлях 1: Від нуля до героя

**Рівень 1: Початківець (Тиждень 1)**
1. [QUICKSTART](./deployment_new/QUICKSTART.md) - Перший краулінг
2. [API Reference](./api/API.md) - Вивчити основи API
3. [CONFIGS](./deployment_new/CONFIGS.md) - Зрозуміти конфігурацію

**Рівень 2: Junior (Тиждень 2-3)**
1. [Architecture Overview](./architecture/ARCHITECTURE_OVERVIEW.md) - Розуміння архітектури
2. [Component Catalog](./architecture/COMPONENT_CATALOG.md) - Вивчити компоненти
3. [Plugin System](./architecture/PLUGIN_SYSTEM.md) - Створити перший плагін

**Рівень 3: Middle (Місяць 2)**
1. [Layer Specification](./architecture/LAYER_SPECIFICATION.md) - Глибоке розуміння
2. [Extension Points](./architecture/EXTENSION_POINTS.md) - Розширення функціональності
3. [SCALING](./deployment_new/SCALING.md) - Масштабування системи

**Рівень 4: Senior (Місяць 3+)**
1. [Communication Channels](./architecture/COMMUNICATION_CHANNELS.md) - Протоколи
2. [Factory Lifecycle](./architecture/FACTORY_LIFECYCLE.md) - DI та фабрики
3. [KUBERNETES](./deployment_new/KUBERNETES.md) - Kubernetes deployment

---

### Шлях 2: DevOps траєкторія

**Крок 1: Локальне розгортання**
1. [QUICKSTART](./deployment_new/QUICKSTART.md)
2. Docker Compose basics

**Крок 2: Масштабування**
1. [CONFIGS](./deployment_new/CONFIGS.md)
2. [SCALING](./deployment_new/SCALING.md)

**Крок 3: Production**
1. [KUBERNETES](./deployment_new/KUBERNETES.md)
2. [PRODUCTION](./deployment_new/PRODUCTION.md)
3. [MONITORING](./deployment_new/MONITORING.md)

---

### Шлях 3: Архітектор траєкторія

**Етап 1: Розуміння системи**
1. [Architecture Overview](./architecture/ARCHITECTURE_OVERVIEW.md)
2. [Layer Specification](./architecture/LAYER_SPECIFICATION.md)

**Етап 2: Компоненти та зв'язки**
1. [Component Catalog](./architecture/COMPONENT_CATALOG.md)
2. [Communication Channels](./architecture/COMMUNICATION_CHANNELS.md)

**Етап 3: Розширення та оптимізація**
1. [Extension Points](./architecture/EXTENSION_POINTS.md)
2. [Factory Lifecycle](./architecture/FACTORY_LIFECYCLE.md)
3. [Plugin System](./architecture/PLUGIN_SYSTEM.md)

---

## 🔍 Пошук за темами

### Конфігурація
- [CONFIGS.md](./deployment_new/CONFIGS.md) - Всі типи конфігурацій
- [Architecture Overview](./architecture/ARCHITECTURE_OVERVIEW.md) - CrawlerConfig

### Масштабування
- [SCALING.md](./deployment_new/SCALING.md) - Стратегії масштабування
- [KUBERNETES.md](./deployment_new/KUBERNETES.md) - K8s deployment
- [Architecture Overview](./architecture/ARCHITECTURE_OVERVIEW.md) - Distributed архітектура

### Плагіни
- [PLUGIN_SYSTEM.md](./architecture/PLUGIN_SYSTEM.md) - Повна документація плагінів
- [Extension Points](./architecture/EXTENSION_POINTS.md) - Точки розширення
- [Component Catalog](./architecture/COMPONENT_CATALOG.md) - Вбудовані плагіни

### Драйвери та Storage
- [Component Catalog](./architecture/COMPONENT_CATALOG.md) - Drivers та Storage
- [Extension Points](./architecture/EXTENSION_POINTS.md) - Кастомні драйвери
- [Factory Lifecycle](./architecture/FACTORY_LIFECYCLE.md) - Factories

### Distributed Crawling
- [QUICKSTART.md](./deployment_new/QUICKSTART.md) - Швидкий старт
- [CONFIGS.md](./deployment_new/CONFIGS.md) - Distributed конфігурація
- [SCALING.md](./deployment_new/SCALING.md) - Celery та Redis
- [Architecture Overview](./architecture/ARCHITECTURE_OVERVIEW.md) - Celery Spider

### Production
- [PRODUCTION.md](./deployment_new/PRODUCTION.md) - Best practices
- [MONITORING.md](./deployment_new/MONITORING.md) - Моніторинг
- [KUBERNETES.md](./deployment_new/KUBERNETES.md) - K8s production

---

## 📊 Матриця документів

| Тема | Початківець | Middle | Senior | DevOps |
|------|-------------|--------|--------|--------|
| **Швидкий старт** | [QUICKSTART](./deployment_new/QUICKSTART.md) | - | - | - |
| **API** | [API.md](./api/API.md) | [API.md](./api/API.md) | [API.md](./api/API.md) | - |
| **Конфігурація** | [CONFIGS](./deployment_new/CONFIGS.md) | [CONFIGS](./deployment_new/CONFIGS.md) | [Extension Points](./architecture/EXTENSION_POINTS.md) | [CONFIGS](./deployment_new/CONFIGS.md) |
| **Архітектура** | [Overview](./architecture/ARCHITECTURE_OVERVIEW.md) | [Layer Spec](./architecture/LAYER_SPECIFICATION.md) | [All arch docs](./architecture/) | [Overview](./architecture/ARCHITECTURE_OVERVIEW.md) |
| **Плагіни** | [Plugin System](./architecture/PLUGIN_SYSTEM.md) | [Plugin System](./architecture/PLUGIN_SYSTEM.md) | [Extension Points](./architecture/EXTENSION_POINTS.md) | - |
| **Deployment** | [QUICKSTART](./deployment_new/QUICKSTART.md) | [CONFIGS](./deployment_new/CONFIGS.md) | [PRODUCTION](./deployment_new/PRODUCTION.md) | [KUBERNETES](./deployment_new/KUBERNETES.md) |
| **Масштабування** | - | [SCALING](./deployment_new/SCALING.md) | [SCALING](./deployment_new/SCALING.md) | [SCALING](./deployment_new/SCALING.md) + [K8s](./deployment_new/KUBERNETES.md) |

---

## 🆘 Потрібна допомога?

### По темах

**Не працює код:**
1. Перевірте [API Reference](./api/API.md)
2. Подивіться [Examples](./deployment_new/QUICKSTART.md)

**Проблеми з deployment:**
1. [QUICKSTART](./deployment_new/QUICKSTART.md) - Troubleshooting
2. [CONFIGS](./deployment_new/CONFIGS.md) - Перевірка конфігурації

**Проблеми з масштабуванням:**
1. [SCALING](./deployment_new/SCALING.md) - Калькулятор ресурсів
2. [KUBERNETES](./deployment_new/KUBERNETES.md) - K8s troubleshooting

**Хочу розширити функціональність:**
1. [Plugin System](./architecture/PLUGIN_SYSTEM.md)
2. [Extension Points](./architecture/EXTENSION_POINTS.md)

---

## 📞 Контакти

- **GitLab:** https://gitlab.com/demoprogrammer/web_graf
- **Issues:** Створіть issue на GitLab
- **License:** [MIT](../LICENSE)

---

## 📝 Примітки

- Всі документи використовують приклади з реального коду
- Архітектурна документація синхронізована з кодом версії 3.2.0
- Deployment документація перевірена на практиці
- Регулярно оновлюється

---

**Ласкаво просимо до GraphCrawler! Щасливого краулінгу! 🚀**
