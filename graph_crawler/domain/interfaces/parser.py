"""
Interface for Parser Factory (Clean Architecture).
This interface allows Node to depend on abstraction for parser creation.

Usage:
    Node can receive IParserFactory through DI or module-level injection
    instead of importing create_parser_instance from Infrastructure.
"""

from typing import Any, Callable, Optional, Protocol, runtime_checkable

@runtime_checkable
class IParser(Protocol):
    """
    Interface for HTML/XML parser.
    
    Any parser (BeautifulSoup, lxml, etc.) must implement this protocol.
    """
    
    def parse(self, html: str) -> Any:
        """
        Parses HTML string into a tree structure.
        
        Args:
            html: HTML content to parse
            
        Returns:
            Parsed tree (implementation-specific)
        """
        ...

@runtime_checkable  
class IParserFactory(Protocol):
    """
    Interface for parser factory (Dependency Injection).
    without importing Infrastructure layer directly.
    
    Example:
        >>> # Module-level injection (recommended)
        >>> from graph_crawler.domain.interfaces import set_parser_factory
        >>> set_parser_factory(lambda: BeautifulSoupAdapter())
        
        >>> # Or per-Node injection
        >>> node = Node(url="...", tree_parser=custom_parser)
    """
    
    def __call__(self) -> IParser:
        """
        Creates a new parser instance.
        
        Returns:
            New IParser instance
        """
        ...

# Module-level parser factory (can be set from Application/Infrastructure layer)
_parser_factory: Optional[Callable[[], IParser]] = None

def set_parser_factory(factory: Callable[[], IParser]) -> None:
    """
    Sets the global parser factory.
    
    Should be called during application bootstrap from Application layer.
    
    Args:
        factory: Callable that creates IParser instances
        
    Example:
        >>> from graph_crawler.infrastructure.adapters import BeautifulSoupAdapter
        >>> set_parser_factory(lambda: BeautifulSoupAdapter())
    """
    global _parser_factory
    _parser_factory = factory

def get_parser_factory() -> Optional[Callable[[], IParser]]:
    """
    Gets the global parser factory.
    
    Returns:
        Parser factory or None if not set
    """
    return _parser_factory

def create_parser() -> Optional[IParser]:
    """
    Creates a parser using the registered factory.
    
    Returns:
        New IParser instance or None if factory not set
    """
    if _parser_factory is not None:
        return _parser_factory()
    return None

__all__ = [
    "IParser",
    "IParserFactory",
    "set_parser_factory",
    "get_parser_factory",
    "create_parser",
]
