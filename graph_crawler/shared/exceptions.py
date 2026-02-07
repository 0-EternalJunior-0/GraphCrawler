"""Custom exceptions для GraphCrawler.

Ієрархія винятків:
    GraphCrawlerError
     ConfigurationError
     URLError
        InvalidURLError
        URLBlockedError
     CrawlerError
        MaxPagesReachedError
        MaxDepthReachedError
     DriverError
        FetchError
     StorageError
         SaveError
         LoadError
"""


class GraphCrawlerError(Exception):
    """Базовий виняток для всіх помилок GraphCrawler."""

    pass


class ConfigurationError(GraphCrawlerError):
    """Помилка конфігурації."""

    pass


class URLError(GraphCrawlerError):
    """Базова помилка для URL операцій."""

    pass


class InvalidURLError(URLError):
    """URL недійсний або має неправильний формат."""

    pass


class URLBlockedError(URLError):
    """URL заблокований (наприклад, robots.txt)."""

    pass


class CrawlerError(GraphCrawlerError):
    """Базова помилка процесу краулінгу."""

    pass


class MaxPagesReachedError(CrawlerError):
    """Досягнуто максимальну кількість сторінок."""

    pass


class MaxDepthReachedError(CrawlerError):
    """Досягнуто максимальну глибину обходу."""

    pass


class DriverError(GraphCrawlerError):
    """Помилка драйвера (HTTP, Scrapy, Async, Playwright)."""

    pass


class FetchError(DriverError):
    """Не вдалося завантажити сторінку."""

    pass


class StorageError(GraphCrawlerError):
    """Помилка зберігання/завантаження даних."""

    pass


class SaveError(StorageError):
    """Не вдалося зберегти дані у storage."""

    pass


class LoadError(StorageError):
    """Не вдалося завантажити дані зі storage."""

    pass
