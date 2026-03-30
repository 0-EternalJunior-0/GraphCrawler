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

# Phase 2: Control Channel
from graph_crawler.domain.interfaces.control_channel import (
    AsyncQueueControlChannel,
    ControlMessage,
    CrawlCommand,
    IControlChannel,
    SyncControlChannel,
    force_visit_command,
    pause_command,
    reprioritize_command,
    resume_command,
    stop_command,
)
from graph_crawler.domain.interfaces.distributed_spider import IDistributedSpider
from graph_crawler.domain.interfaces.driver import IDriver
from graph_crawler.domain.interfaces.eviction_storage import (
    IEvictionStorage,
    IEvictionStorageAsync,
)
from graph_crawler.domain.interfaces.filter import IDomainFilter, IPathFilter

# Phase 0: AI Agent Integration
from graph_crawler.domain.interfaces.language_model import (
    ILanguageModel,
    LLMError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from graph_crawler.domain.interfaces.processor import IProcessor
from graph_crawler.domain.interfaces.scanner import IScanner
from graph_crawler.domain.interfaces.scheduler import IScheduler
from graph_crawler.domain.interfaces.spider import ISpider
from graph_crawler.domain.interfaces.stop_condition import (
    BaseStopCondition,
    CallableStopCondition,
    CompositeStopCondition,
    IStopCondition,
    MaxPagesStopCondition,
    SchemaCompleteStopCondition,
    TargetFoundStopCondition,
)
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
    "IEvictionStorage",
    "IEvictionStorageAsync",
    # Filters
    "IDomainFilter",
    "IPathFilter",
    "IURLFilter",  # Alias
    # Spider interfaces
    "IScanner",
    "IScheduler",
    "ISpider",
    "IDistributedSpider",
    "IProcessor",
    # Phase 0: AI Agent Integration
    "ILanguageModel",
    "LLMError",
    "LLMRateLimitError",
    "LLMTimeoutError",
    "IStopCondition",
    "BaseStopCondition",
    "TargetFoundStopCondition",
    "SchemaCompleteStopCondition",
    "MaxPagesStopCondition",
    "CallableStopCondition",
    "CompositeStopCondition",
    # Phase 2: Control Channel
    "IControlChannel",
    "CrawlCommand",
    "ControlMessage",
    "AsyncQueueControlChannel",
    "SyncControlChannel",
    "stop_command",
    "pause_command",
    "resume_command",
    "reprioritize_command",
    "force_visit_command",
]
