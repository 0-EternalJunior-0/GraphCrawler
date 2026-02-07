"""Factories для створення компонентів GraphCrawler.

Фабрики дозволяють створювати драйвери та storage з простих string параметрів:

    >>> from graph_crawler.application.services import create_driver, create_storage
    >>>
    >>> # String shortcuts
    >>> driver = create_driver("http")
    >>> driver = create_driver("playwright")
    >>>
    >>> storage = create_storage("memory")
    >>> storage = create_storage("sqlite")
    >>>
    >>> # Або передати готовий instance
    >>> driver = create_driver(CustomDriver())
"""

from graph_crawler.application.services.application_container import (
    ApplicationContainer,
)
from graph_crawler.application.services.driver_factory import create_driver
from graph_crawler.application.services.storage_factory import create_storage

__all__ = [
    "create_driver",
    "create_storage",
    "ApplicationContainer",
]
