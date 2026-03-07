"""
Enum патерни для allowed_domains.
for backward compatibility. New code should import directly from Domain.

DEPRECATED: Use graph_crawler.domain.value_objects.domain_patterns instead.

Example:
    # Old (deprecated but still works):
    from graph_crawler.application.use_cases.crawling.filters.domain_patterns import AllowedDomains
    
    # New (recommended):
    from graph_crawler.domain.value_objects.domain_patterns import AllowedDomains
"""

import warnings

# Re-export from Domain layer for backward compatibility
from graph_crawler.domain.value_objects.domain_patterns import AllowedDomains

# Issue deprecation warning on import
warnings.warn(
    "Importing AllowedDomains from application.use_cases.crawling.filters.domain_patterns "
    "is deprecated. Import from graph_crawler.domain.value_objects.domain_patterns instead.",
    DeprecationWarning,
    stacklevel=2
)

# ==================== EXPORT ====================

__all__ = ["AllowedDomains"]
