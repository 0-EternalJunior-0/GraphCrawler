# GraphCrawler Documentation Index

> **Центральний індекс документації**  
> **Версія:** 4.0.7 
> **Дата:** Лютий 2026  
> **Автор:** GraphCrawler Team

---

## 📚 Структура документації

```
docs/
├── INDEX.md                         # Ви тут!
├── index.md                         # Головна сторінка (MkDocs)
├── changelog.md                     # Історія змін
│
├── getting-started/                 # Початок роботи
│   ├── installation.md              # Встановлення
│   ├── quickstart.md                # Швидкий старт
│   └── examples.md                  # Приклади коду
│
├── core/                            # Основні концепції
│   ├── simple-crawling.md           # Простий краулінг
│   ├── deep-crawling.md             # Глибокий краулінг
│   ├── url-rules.md                 # URL правила
│   ├── graph-operations.md          # Операції з графами
│   └── cache-modes.md               # Режими кешування
│
├── extraction/                      # Екстракція даних
│   ├── plugins.md                   # Система плагінів
│   ├── structured-data.md           # Структуровані дані
│   └── custom-extractors.md         # Кастомні екстрактори
│
├── advanced/                        # Просунуті теми
│   ├── distributed-crawling.md      # Розподілений краулінг
│   ├── proxy-security.md            # Проксі та безпека
│   ├── hooks-auth.md                # Хуки та авторизація
│   └── session-management.md        # Управління сесіями
│
├── api/                             # API Reference
│   └── API.md                       # Повна документація API
│
└── architecture/                    # Архітектура системи
    ├── ARCHITECTURE_OVERVIEW.md     # Огляд архітектури
    ├── LAYER_SPECIFICATION.md       # Специфікація шарів
    ├── COMPONENT_CATALOG.md         # Каталог компонентів
    ├── COMMUNICATION_CHANNELS.md    # Канали комунікації
    ├── FACTORY_LIFECYCLE.md         # Фабрики та життєвий цикл
    ├── EXTENSION_POINTS.md          # Точки розширення
    ├── PLUGIN_SYSTEM.md             # Система плагінів (детально)
    └── STRUCTURED_DATA_PLUGIN.md    # Плагін мікророзмітки
```

---

## 🎯 Швидкі посилання по темах

### Початківці

**Хочу швидко почати:**
1. [API Reference](./api/API.md) - Основні функції
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
| [STRUCTURED_DATA_PLUGIN](./architecture/STRUCTURED_DATA_PLUGIN.md) | Плагін мікророзмітки (JSON-LD, Open Graph, Microdata) | All Developers |

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
