"""
Application Layer Bootstrap - Clean Architecture initialization.

This module initializes all registries and factories required by Domain layer.
MUST be called before using graph_crawler functionality.

Usage:
    from graph_crawler.application.bootstrap import bootstrap
    bootstrap()  # Call once at application startup

Or use auto-bootstrap via:
    from graph_crawler import bootstrap
    bootstrap()
"""

import logging

logger = logging.getLogger(__name__)

_bootstrapped = False


def bootstrap(force: bool = False) -> None:
    """
    Initialize graph_crawler application.

    This function:
    1. Registers Spider classes in CrawlModeRegistry
    2. Registers Change Detection strategies
    3. Registers Merge strategies
    4. Sets up parser factory for Node

    Args:
        force: Force re-initialization even if already bootstrapped

    Example:
        >>> from graph_crawler.application.bootstrap import bootstrap
        >>> bootstrap()
        >>> # Now graph_crawler is ready to use
    """
    global _bootstrapped

    if _bootstrapped and not force:
        logger.debug("graph_crawler already bootstrapped, skipping")
        return

    logger.info("Bootstrapping graph_crawler application...")

    # 1. Register Crawl Modes
    _register_crawl_modes()

    # 2. Register Change Detection Strategies
    _register_change_detection_strategies()

    # 3. Register Merge Strategies
    _register_merge_strategies()

    # 4. Set up parser factory
    _setup_parser_factory()

    _bootstrapped = True
    logger.info("graph_crawler bootstrap complete")


def _register_crawl_modes() -> None:
    """Register Spider classes in CrawlModeRegistry."""
    from graph_crawler.domain.entities.registries import CrawlModeRegistry

    # Clear existing registrations (for re-bootstrap)
    CrawlModeRegistry.clear()

    # Import and register spider classes
    from graph_crawler.application.use_cases.crawling.spider import GraphSpider

    CrawlModeRegistry.register("sequential", GraphSpider)

    try:
        from graph_crawler.application.use_cases.crawling.multiprocess_spider import (
            MultiprocessSpider,
        )

        CrawlModeRegistry.register("multiprocessing", MultiprocessSpider)
    except ImportError:
        logger.debug("MultiprocessSpider not available")

    try:
        from graph_crawler.application.use_cases.crawling.celery_batch_spider import (
            CeleryBatchSpider,
        )

        CrawlModeRegistry.register("celery", CeleryBatchSpider)
    except ImportError:
        logger.debug("CeleryBatchSpider not available (celery not installed)")

    logger.debug("Registered crawl modes: %s", CrawlModeRegistry.get_all_names())


def _register_change_detection_strategies() -> None:
    """Register Change Detection strategies."""
    from graph_crawler.domain.entities.registries import ChangeDetectionStrategyRegistry

    # Clear existing registrations
    ChangeDetectionStrategyRegistry.clear()

    # Import and register strategies
    from graph_crawler.domain.entities.strategies import HashStrategy, MetadataStrategy

    ChangeDetectionStrategyRegistry.register("hash", HashStrategy)
    ChangeDetectionStrategyRegistry.register("metadata", MetadataStrategy)

    logger.debug(
        f"Registered change detection strategies: {ChangeDetectionStrategyRegistry.get_all_names()}"
    )


def _register_merge_strategies() -> None:
    """Register Merge strategies for Graph.union()."""
    from graph_crawler.domain.entities.registries import MergeStrategyRegistry

    # Clear existing registrations
    MergeStrategyRegistry.clear()

    # Import MergeStrategy enum and NodeMerger class
    from graph_crawler.domain.entities.merge_strategies import (
        MergeStrategy,
    )

    # Register strategy names with corresponding enum values
    MergeStrategyRegistry.register("first", MergeStrategy.FIRST)
    MergeStrategyRegistry.register("last", MergeStrategy.LAST)
    MergeStrategyRegistry.register("merge", MergeStrategy.MERGE)
    MergeStrategyRegistry.register("newest", MergeStrategy.NEWEST)
    MergeStrategyRegistry.register("oldest", MergeStrategy.OLDEST)
    MergeStrategyRegistry.register("custom", MergeStrategy.CUSTOM)

    logger.debug("Registered merge strategies: %s", MergeStrategyRegistry.get_all_names())


def _setup_parser_factory() -> None:
    """Set up parser factory for Node.process_html()."""
    from graph_crawler.domain.interfaces.parser import set_parser_factory
    from graph_crawler.infrastructure.adapters import create_parser_instance

    set_parser_factory(create_parser_instance)

    logger.debug("Parser factory configured")


def is_bootstrapped() -> bool:
    """Check if bootstrap has been called."""
    return _bootstrapped


def require_bootstrap() -> None:
    """
    Ensure bootstrap has been called, raise error if not.

    Use this in functions that require bootstrap to be called first.
    """
    if not _bootstrapped:
        raise RuntimeError(
            "graph_crawler not bootstrapped. Call bootstrap() first:\n"
            "  from graph_crawler.application.bootstrap import bootstrap\n"
            "  bootstrap()"
        )
