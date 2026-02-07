"""Enhanced Error Tracing для GraphCrawler.

Features:
- Structured error context
- Stack trace з контекстом
- Error categorization
- Correlation ID tracking
- Error aggregation

Usage:
    >>> from graph_crawler.observability.error_tracing import (
    ...     ErrorTracer,
    ...     trace_error,
    ...     get_error_summary,
    ... )
    >>> 
    >>> # Trace an error
    >>> try:
    ...     fetch(url)
    ... except Exception as e:
    ...     trace_error(e, context={"url": url, "depth": 2})
    >>> 
    >>> # Get error summary
    >>> summary = get_error_summary()
"""

import logging
import sys
import threading
import traceback
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Type
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class ErrorContext:
    """Context for an error occurrence."""
    
    error_id: str = field(default_factory=lambda: str(uuid4())[:8])
    timestamp: datetime = field(default_factory=datetime.now)
    correlation_id: Optional[str] = None
    
    # Error info
    error_type: str = ""
    error_message: str = ""
    error_category: str = "unknown"
    
    # Stack trace
    traceback_str: str = ""
    traceback_frames: List[Dict[str, Any]] = field(default_factory=list)
    
    # Custom context
    context: Dict[str, Any] = field(default_factory=dict)
    
    # Location
    module: str = ""
    function: str = ""
    line_number: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "error_id": self.error_id,
            "timestamp": self.timestamp.isoformat(),
            "correlation_id": self.correlation_id,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "error_category": self.error_category,
            "traceback": self.traceback_str,
            "frames": self.traceback_frames,
            "context": self.context,
            "location": {
                "module": self.module,
                "function": self.function,
                "line": self.line_number,
            },
        }


class ErrorTracer:
    """
    Central error tracing and aggregation.
    
    Tracks errors with full context for debugging and monitoring.
    
    Example:
        >>> tracer = ErrorTracer(max_errors=1000)
        >>> 
        >>> try:
        ...     do_something()
        ... except Exception as e:
        ...     tracer.trace(e, context={"operation": "crawl"})
        >>> 
        >>> # Get summary
        >>> print(tracer.get_summary())
    """
    
    # Error categories
    CATEGORIES = {
        # Network errors
        "ConnectionError": "network",
        "TimeoutError": "network",
        "aiohttp.ClientError": "network",
        "asyncio.TimeoutError": "network",
        
        # HTTP errors
        "HTTPError": "http",
        "ClientResponseError": "http",
        
        # Parsing errors
        "ParseError": "parsing",
        "HTMLParseError": "parsing",
        "UnicodeDecodeError": "parsing",
        "JSONDecodeError": "parsing",
        
        # Validation errors
        "ValidationError": "validation",
        "ValueError": "validation",
        "TypeError": "validation",
        
        # System errors
        "MemoryError": "system",
        "OSError": "system",
        "IOError": "system",
    }
    
    def __init__(
        self,
        max_errors: int = 1000,
        enable_aggregation: bool = True,
    ):
        """
        Initialize error tracer.
        
        Args:
            max_errors: Maximum errors to keep in memory
            enable_aggregation: Aggregate similar errors
        """
        self.max_errors = max_errors
        self.enable_aggregation = enable_aggregation
        
        self._errors: List[ErrorContext] = []
        self._error_counts: Dict[str, int] = defaultdict(int)
        self._category_counts: Dict[str, int] = defaultdict(int)
        self._lock = threading.Lock()
    
    def trace(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
    ) -> ErrorContext:
        """
        Trace an error with full context.
        
        Args:
            error: The exception to trace
            context: Additional context dictionary
            correlation_id: Request correlation ID
            
        Returns:
            ErrorContext with full trace information
        """
        # Get exception info
        exc_type = type(error).__name__
        exc_module = type(error).__module__
        full_type = f"{exc_module}.{exc_type}" if exc_module != "builtins" else exc_type
        
        # Categorize error
        category = self._categorize_error(error)
        
        # Get traceback
        tb_str = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        frames = self._extract_frames(error.__traceback__)
        
        # Get location
        if frames:
            last_frame = frames[-1]
            module = last_frame.get("module", "")
            function = last_frame.get("function", "")
            line_number = last_frame.get("line", 0)
        else:
            module = function = ""
            line_number = 0
        
        # Create error context
        error_ctx = ErrorContext(
            correlation_id=correlation_id,
            error_type=full_type,
            error_message=str(error),
            error_category=category,
            traceback_str=tb_str,
            traceback_frames=frames,
            context=context or {},
            module=module,
            function=function,
            line_number=line_number,
        )
        
        # Store and count
        with self._lock:
            self._errors.append(error_ctx)
            if len(self._errors) > self.max_errors:
                self._errors.pop(0)
            
            self._error_counts[full_type] += 1
            self._category_counts[category] += 1
        
        # Log
        logger.error(
            f"Error traced: {full_type}: {error}",
            extra={
                "error_id": error_ctx.error_id,
                "error_type": full_type,
                "error_category": category,
                "correlation_id": correlation_id,
                **(context or {}),
            }
        )
        
        return error_ctx
    
    def _categorize_error(self, error: Exception) -> str:
        """Categorize error by type."""
        error_type = type(error).__name__
        full_type = f"{type(error).__module__}.{error_type}"
        
        # Check full type first
        if full_type in self.CATEGORIES:
            return self.CATEGORIES[full_type]
        
        # Check simple type
        if error_type in self.CATEGORIES:
            return self.CATEGORIES[error_type]
        
        # Check parent classes
        for parent in type(error).__mro__:
            parent_name = parent.__name__
            if parent_name in self.CATEGORIES:
                return self.CATEGORIES[parent_name]
        
        return "unknown"
    
    def _extract_frames(self, tb) -> List[Dict[str, Any]]:
        """Extract frame info from traceback with memory-safe limits."""
        frames = []
        max_frames = 20  # Limit stack depth
        while tb is not None and len(frames) < max_frames:
            frame = tb.tb_frame
            # Limit locals to prevent memory bloat
            locals_subset = {}
            local_items = [(k, v) for k, v in frame.f_locals.items() if not k.startswith("_")]
            for k, v in local_items[:10]:  # Max 10 local vars per frame
                try:
                    locals_subset[k] = repr(v)[:50]  # Shorter repr
                except Exception:
                    locals_subset[k] = "<unrepresentable>"
            
            frames.append({
                "file": frame.f_code.co_filename,
                "module": frame.f_globals.get("__name__", ""),
                "function": frame.f_code.co_name,
                "line": tb.tb_lineno,
                "locals": locals_subset,
            })
            tb = tb.tb_next
        return frames
    
    def get_recent_errors(self, limit: int = 10) -> List[ErrorContext]:
        """Get most recent errors."""
        with self._lock:
            return list(reversed(self._errors[-limit:]))
    
    def get_errors_by_type(self, error_type: str) -> List[ErrorContext]:
        """Get errors filtered by type."""
        with self._lock:
            return [e for e in self._errors if e.error_type == error_type]
    
    def get_errors_by_category(self, category: str) -> List[ErrorContext]:
        """Get errors filtered by category."""
        with self._lock:
            return [e for e in self._errors if e.error_category == category]
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get error summary statistics.
        
        Returns:
            Dictionary with error counts and top errors
        """
        with self._lock:
            total = len(self._errors)
            
            # Top error types
            top_types = sorted(
                self._error_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
            
            # Category distribution
            categories = dict(self._category_counts)
            
            return {
                "total_errors": total,
                "unique_types": len(self._error_counts),
                "top_error_types": dict(top_types),
                "by_category": categories,
                "recent_errors": [
                    e.to_dict() for e in self.get_recent_errors(5)
                ],
            }
    
    def get_summary_text(self) -> str:
        """Get formatted text summary."""
        summary = self.get_summary()
        
        lines = [
            "=" * 60,
            "ERROR TRACING SUMMARY",
            "=" * 60,
            "",
            f"Total Errors: {summary['total_errors']}",
            f"Unique Types: {summary['unique_types']}",
            "",
            "By Category:",
        ]
        
        for cat, count in summary["by_category"].items():
            lines.append(f"  • {cat}: {count}")
        
        lines.extend([
            "",
            "Top Error Types:",
        ])
        
        for err_type, count in summary["top_error_types"].items():
            lines.append(f"  • {err_type}: {count}")
        
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    def clear(self) -> None:
        """Clear all tracked errors."""
        with self._lock:
            self._errors.clear()
            self._error_counts.clear()
            self._category_counts.clear()


# Global error tracer (singleton)
_global_tracer: Optional[ErrorTracer] = None


def get_error_tracer() -> ErrorTracer:
    """Get global error tracer (singleton)."""
    global _global_tracer
    if _global_tracer is None:
        _global_tracer = ErrorTracer()
    return _global_tracer


def trace_error(
    error: Exception,
    context: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None,
) -> ErrorContext:
    """
    Convenience function to trace error with global tracer.
    
    Args:
        error: The exception to trace
        context: Additional context
        correlation_id: Request correlation ID
        
    Returns:
        ErrorContext
    """
    return get_error_tracer().trace(error, context, correlation_id)


def get_error_summary() -> Dict[str, Any]:
    """Get error summary from global tracer."""
    return get_error_tracer().get_summary()


__all__ = [
    "ErrorContext",
    "ErrorTracer",
    "get_error_tracer",
    "trace_error",
    "get_error_summary",
]
