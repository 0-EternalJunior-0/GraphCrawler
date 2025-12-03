"""Node extractors for distributed crawling.

Цей модуль надає extractors для витягування структурованих даних з HTML:
- PhoneExtractorPlugin - телефонні номери
- EmailExtractorPlugin - email адреси
- PriceExtractorPlugin - ціни та зарплати

Usage:
    from graph_crawler.extensions.plugins.node.extractors import PhoneExtractorPlugin

    plugin = PhoneExtractorPlugin()
    context = plugin.execute(context)
    phones = context.user_data['phones']
"""

from graph_crawler.extensions.plugins.node.extractors.email_extractor import (
    EmailExtractorPlugin,
)
from graph_crawler.extensions.plugins.node.extractors.phone_extractor import (
    PhoneExtractorPlugin,
)
from graph_crawler.extensions.plugins.node.extractors.price_extractor import (
    PriceExtractorPlugin,
)

__all__ = [
    "PhoneExtractorPlugin",
    "EmailExtractorPlugin",
    "PriceExtractorPlugin",
]
