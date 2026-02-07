# Changelog

Всі значні зміни в GraphCrawler.

---

## [4.0.4] - 2026-02

### Added
- 📚 Повна документація за аналогом Crawl4AI
- 🌱 Нові розділи: Getting Started, Core, Advanced, Extraction
- 📖 Розширено API.md: Settings, Exceptions, Factory Functions, Interfaces
- ⚙️ Додано CrawlerSettings, DriverSettings, StorageSettings, RetrySettings
- 🔧 Додано Factory функції: create_driver(), create_storage()
- 🔴 Повна ієрархія Exceptions з прикладами
- 📦 Повний список всіх імпортів

---

## [4.0.0] - 2026-01

### Added
- ⚡ **Python 3.14 Free-Threading** - підтримка роботи без GIL
- 🚀 **3.2x швидший** краулінг з free-threading
- 🌱 **seed_urls** - множинні точки входу
- 🔄 **base_graph** - інкрементальний краулінг
- 🏷️ **StructuredDataPlugin** - екстракція JSON-LD, Open Graph, Microdata

### Changed
- 📉 **16% менше** використання пам'яті
- ⏱️ **30% швидший** startup

### Fixed
- Виправлено memory leak при великих краулінгах
- Покращено обробку помилок SSL

---

## [3.2.0] - 2025-12

### Added
- 📞 **PhoneExtractorPlugin** - витягування телефонів (UA, US, RU)
- 📧 **EmailExtractorPlugin** - витягування email
- 💰 **PriceExtractorPlugin** - витягування цін
- 🧠 **RealTimeVectorizerPlugin** - векторизація в реальному часі

### Changed
- Оптимізовано HTML парсинг

---

## [3.1.0] - 2025-10

### Added
- 🖥️ **Playwright Driver** - підтримка JavaScript сайтів
- 🥷 **Stealth Driver** - обхід антибот захисту
- 🔄 **Middleware Chain** - ланцюжок middleware

---

## [3.0.0] - 2025-08

### Added
- 🏛️ **Нова архітектура** - Clean Architecture
- 🔌 **Plugin System** - 6 типів hooks
- 📦 **Storage Backends** - Memory, JSON, SQLite, PostgreSQL, MongoDB
- 📊 **Graph Operations** - Union, Difference, Intersection

### Breaking Changes
- Новий API: `crawl()` замість `GraphCrawler().run()`
- Змінено структуру Node та Edge

---

## [2.0.0] - 2025-05

### Added
- Async краулінг
- URL Rules
- Event System

---

## [1.0.0] - 2025-02

### Added
- Перший реліз
- Базовий краулінг
- Graph структура
- JSON експорт

---

## Посилання

- [GitHub Repository](https://github.com/0-EternalJunior-0/GraphCrawler)
- [Documentation](./index.md)
- [API Reference](./api/API.md)
