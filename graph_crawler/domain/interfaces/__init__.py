"""Domain Interfaces - Protocols та інтерфейси для GraphCrawler.

Storage інтерфейси тепер розділені на менші:
- IStorageReader - тільки читання
- IStorageWriter - тільки запис
- IStorageLifecycle - управління життєвим циклом
- IStorage - повний інтерфейс

Використання:
    from graph_crawler.domain.interfaces import IDriver, IStorage
    from graph_crawler.domain.interfaces.storage import IStorageReader
"""

from graph_crawler.domain.interfaces.driver import IDriver
from graph_crawler.domain.interfaces.filter import IDomainFilter, IPathFilter
from graph_crawler.domain.interfaces.processor import IProcessor
from graph_crawler.domain.interfaces.scanner import IScanner
from graph_crawler.domain.interfaces.scheduler import IScheduler
from graph_crawler.domain.interfaces.spider import ISpider
from graph_crawler.domain.interfaces.storage import (
    IStorage,
    IStorageLifecycle,
    IStorageReader,
    IStorageWriter,
)

# Alias для зворотної сумісності
IURLFilter = IDomainFilter

__all__ = [
    # Driver
    "IDriver",
    # Storage (ISP)
    "IStorage",
    "IStorageReader",
    "IStorageWriter",
    "IStorageLifecycle",
    # Filters
    "IDomainFilter",
    "IPathFilter",
    "IURLFilter",  # Alias
    # Other
    "IScanner",
    "IScheduler",
    "ISpider",
    "IProcessor",
]
