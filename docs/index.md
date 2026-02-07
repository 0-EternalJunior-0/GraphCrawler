# GraphCrawler Documentation Index

> **Центральний індекс документації**  
> **Версія:** 4.0.4  
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

<<<<<<< HEAD
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

## 🎓 Навчальні шляхи

### Шлях 1: Від нуля до героя

**Рівень 1: Початківець (Тиждень 1)**
1. [API Reference](./api/API.md) - Вивчити основи API
2. [Architecture Overview](./architecture/ARCHITECTURE_OVERVIEW.md) - Розуміння архітектури

**Рівень 2: Junior (Тиждень 2-3)**
1. [Component Catalog](./architecture/COMPONENT_CATALOG.md) - Вивчити компоненти
2. [Plugin System](./architecture/PLUGIN_SYSTEM.md) - Створити перший плагін

**Рівень 3: Middle (Місяць 2)**
1. [Layer Specification](./architecture/LAYER_SPECIFICATION.md) - Глибоке розуміння
2. [Extension Points](./architecture/EXTENSION_POINTS.md) - Розширення функціональності

**Рівень 4: Senior (Місяць 3+)**
1. [Communication Channels](./architecture/COMMUNICATION_CHANNELS.md) - Протоколи
2. [Factory Lifecycle](./architecture/FACTORY_LIFECYCLE.md) - DI та фабрики

---

### Шлях 2: Архітектор траєкторія

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

### Плагіни
- [PLUGIN_SYSTEM.md](./architecture/PLUGIN_SYSTEM.md) - Повна документація плагінів
- [Extension Points](./architecture/EXTENSION_POINTS.md) - Точки розширення
- [Component Catalog](./architecture/COMPONENT_CATALOG.md) - Вбудовані плагіни

### Драйвери та Storage
- [Component Catalog](./architecture/COMPONENT_CATALOG.md) - Drivers та Storage
- [Extension Points](./architecture/EXTENSION_POINTS.md) - Кастомні драйвери
- [Factory Lifecycle](./architecture/FACTORY_LIFECYCLE.md) - Factories

---

## 📊 Матриця документів

| Тема | Початківець | Middle | Senior |
|------|-------------|--------|--------|
| **API** | [API.md](./api/API.md) | [API.md](./api/API.md) | [API.md](./api/API.md) |
| **Архітектура** | [Overview](./architecture/ARCHITECTURE_OVERVIEW.md) | [Layer Spec](./architecture/LAYER_SPECIFICATION.md) | [All arch docs](./architecture/) |
| **Плагіни** | [Plugin System](./architecture/PLUGIN_SYSTEM.md) | [Plugin System](./architecture/PLUGIN_SYSTEM.md) | [Extension Points](./architecture/EXTENSION_POINTS.md) |

---

## 🆘 Потрібна допомога?

**Не працює код:**
1. Перевірте [API Reference](./api/API.md)

**Хочу розширити функціональність:**
1. [Plugin System](./architecture/PLUGIN_SYSTEM.md)
2. [Extension Points](./architecture/EXTENSION_POINTS.md)

---

## 📞 Контакти

- **GitLab:** https://gitlab.com/demoprogrammer/web_graf
- **Issues:** Створіть issue на GitLab
=======
- **GitHub Repository:** [github.com/0-EternalJunior-0/GraphCrawler](https://github.com/0-EternalJunior-0/GraphCrawler)
- **Issues:** Report bugs or request features via GitHub Issues
>>>>>>> 16be93affc1776fe905a617daf33744bd7bf81cc
- **License:** [MIT](../LICENSE)

---

## 📝 Примітки

- Всі документи використовують приклади з реального коду
- Архітектурна документація синхронізована з кодом версії 4.0.0
- Регулярно оновлюється

---

**Ласкаво просимо до GraphCrawler! Щасливого краулінгу! 🚀**
