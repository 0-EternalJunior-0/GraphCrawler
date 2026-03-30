"""Константи для StructuredData плагіна.

Консистентно з graph_crawler.shared.constants
"""

import re

# Ліміти безпеки
MAX_JSONLD_BLOCKS: int = 10
MAX_JSONLD_SIZE: int = 100_000  # 100KB на блок
MAX_MICRODATA_ITEMS: int = 50
MAX_NESTING_DEPTH: int = 5
MAX_PROPERTY_LENGTH: int = 10_000  # 10KB на властивість

# Таймаути
DEFAULT_PARSER_TIMEOUT: float = 2.0  # секунди

# Regex patterns (компілюються один раз)
JSONLD_PATTERN = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)
