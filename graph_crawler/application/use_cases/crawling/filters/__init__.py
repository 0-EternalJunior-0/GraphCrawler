"""URL фільтри для GraphCrawler.


"""

from graph_crawler.application.use_cases.crawling.filters.base import BaseURLFilter
from graph_crawler.application.use_cases.crawling.filters.domain_filter import (
    DomainFilter,
)
from graph_crawler.application.use_cases.crawling.filters.domain_patterns import (
    AllowedDomains,
)
from graph_crawler.application.use_cases.crawling.filters.path_filter import PathFilter

__all__ = ["BaseURLFilter", "DomainFilter", "PathFilter", "AllowedDomains"]
