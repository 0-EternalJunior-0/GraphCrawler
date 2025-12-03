"""
Global Tracer - детальне логування всіх викликів у GraphCrawler.

Використання:
    from tracer import Tracer, trace_call
    
    tracer = Tracer()
    
    @trace_call(tracer)
    def my_function(...):
        ...
"""

import functools
import time
import inspect
import asyncio
from typing import Any, Callable, List, Dict, Optional
from datetime import datetime
from dataclasses import dataclass, field
import json


@dataclass
class TraceEntry:
    """Один запис трейсу."""
    timestamp: str
    call_id: int
    depth: int
    class_name: str
    method_name: str
    args: str
    kwargs: str
    result: str = ""
    duration_ms: float = 0.0
    error: str = ""
    is_async: bool = False
    
    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "call_id": self.call_id,
            "depth": self.depth,
            "class_name": self.class_name,
            "method_name": self.method_name,
            "args": self.args,
            "kwargs": self.kwargs,
            "result": self.result,
            "duration_ms": self.duration_ms,
            "error": self.error,
            "is_async": self.is_async,
        }


class Tracer:
    """Глобальний трейсер для відстеження всіх викликів."""
    
    def __init__(self, max_arg_length: int = 200, max_result_length: int = 300):
        self.traces: List[TraceEntry] = []
        self.call_stack: List[int] = []
        self.call_counter = 0
        self.max_arg_length = max_arg_length
        self.max_result_length = max_result_length
        self.start_time: Optional[float] = None
        self.enabled = True
        
    def clear(self):
        """Очищує всі трейси."""
        self.traces.clear()
        self.call_stack.clear()
        self.call_counter = 0
        self.start_time = None
        
    def _truncate(self, s: str, max_len: int) -> str:
        """Обрізає довгі рядки."""
        s = str(s)
        if len(s) > max_len:
            return s[:max_len] + "..."
        return s
    
    def _format_args(self, args: tuple, kwargs: dict) -> tuple:
        """Форматує аргументи для логування."""
        args_str = ", ".join(
            self._truncate(repr(a), self.max_arg_length) for a in args
        )
        kwargs_str = ", ".join(
            f"{k}={self._truncate(repr(v), self.max_arg_length)}" 
            for k, v in kwargs.items()
        )
        return args_str, kwargs_str
    
    def _format_result(self, result: Any) -> str:
        """Форматує результат."""
        result_str = repr(result)
        return self._truncate(result_str, self.max_result_length)
    
    def add_trace(
        self,
        class_name: str,
        method_name: str,
        args: tuple,
        kwargs: dict,
        result: Any = None,
        duration_ms: float = 0.0,
        error: str = "",
        is_async: bool = False,
    ) -> int:
        """Додає запис трейсу."""
        if not self.enabled:
            return -1
            
        self.call_counter += 1
        call_id = self.call_counter
        
        args_str, kwargs_str = self._format_args(args, kwargs)
        result_str = self._format_result(result) if result is not None else ""
        
        entry = TraceEntry(
            timestamp=datetime.now().strftime("%H:%M:%S.%f")[:-3],
            call_id=call_id,
            depth=len(self.call_stack),
            class_name=class_name,
            method_name=method_name,
            args=args_str,
            kwargs=kwargs_str,
            result=result_str,
            duration_ms=duration_ms,
            error=error,
            is_async=is_async,
        )
        
        self.traces.append(entry)
        return call_id
    
    def push_call(self, call_id: int):
        """Додає виклик до стеку."""
        self.call_stack.append(call_id)
        
    def pop_call(self):
        """Видаляє виклик зі стеку."""
        if self.call_stack:
            self.call_stack.pop()
            
    def get_report(self, format: str = "text") -> str:
        """Генерує звіт."""
        if format == "json":
            return json.dumps([t.to_dict() for t in self.traces], indent=2, ensure_ascii=False)
        
        # Text format
        lines = [
            "\n" + "=" * 100,
            "TRACE REPORT - GraphCrawler v3.0",
            "=" * 100,
            f"Total calls: {len(self.traces)}",
            "-" * 100,
        ]
        
        for entry in self.traces:
            indent = "  " * entry.depth
            async_marker = "[ASYNC]" if entry.is_async else "[SYNC]"
            
            call_line = (
                f"{entry.timestamp} #{entry.call_id:04d} {indent}"
                f"{async_marker} {entry.class_name}.{entry.method_name}()"
            )
            lines.append(call_line)
            
            if entry.args or entry.kwargs:
                args_line = f"{' ' * 22}{indent}  ARGS: ({entry.args})"
                if entry.kwargs:
                    args_line += f" | KWARGS: {{{entry.kwargs}}}"
                lines.append(args_line)
            
            if entry.result:
                lines.append(f"{' ' * 22}{indent}  RESULT: {entry.result}")
            
            if entry.error:
                lines.append(f"{' ' * 22}{indent}  ERROR: {entry.error}")
                
            if entry.duration_ms > 0:
                lines.append(f"{' ' * 22}{indent}  TIME: {entry.duration_ms:.2f}ms")
        
        lines.append("=" * 100)
        return "\n".join(lines)
    
    def get_summary(self) -> str:
        """Генерує короткий summary."""
        if not self.traces:
            return "No traces recorded."
        
        # Групуємо по класах
        class_counts: Dict[str, int] = {}
        class_times: Dict[str, float] = {}
        
        for entry in self.traces:
            key = entry.class_name
            class_counts[key] = class_counts.get(key, 0) + 1
            class_times[key] = class_times.get(key, 0.0) + entry.duration_ms
        
        lines = [
            "\n" + "=" * 60,
            "SUMMARY BY CLASS",
            "=" * 60,
        ]
        
        for cls in sorted(class_counts.keys()):
            lines.append(f"  {cls}: {class_counts[cls]} calls, {class_times[cls]:.2f}ms total")
        
        lines.append("=" * 60)
        return "\n".join(lines)


# Global tracer instance
_global_tracer: Optional[Tracer] = None


def get_tracer() -> Tracer:
    """Отримує глобальний трейсер."""
    global _global_tracer
    if _global_tracer is None:
        _global_tracer = Tracer()
    return _global_tracer


def set_tracer(tracer: Tracer):
    """Встановлює глобальний трейсер."""
    global _global_tracer
    _global_tracer = tracer


def trace_call(tracer: Optional[Tracer] = None):
    """Декоратор для трейсингу функцій/методів."""
    def decorator(func: Callable) -> Callable:
        tr = tracer or get_tracer()
        is_async = asyncio.iscoroutinefunction(func)
        
        # Отримуємо ім'я класу якщо це метод
        qualname_parts = func.__qualname__.split('.')
        if len(qualname_parts) > 1:
            class_name = qualname_parts[-2]
        else:
            class_name = func.__module__.split('.')[-1]
        method_name = func.__name__
        
        if is_async:
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                start = time.perf_counter()
                call_id = tr.add_trace(
                    class_name=class_name,
                    method_name=method_name,
                    args=args[1:] if args else (),  # Skip self
                    kwargs=kwargs,
                    is_async=True,
                )
                tr.push_call(call_id)
                try:
                    result = await func(*args, **kwargs)
                    duration = (time.perf_counter() - start) * 1000
                    # Update trace with result
                    if tr.traces and tr.traces[-1].call_id == call_id:
                        tr.traces[-1].result = tr._format_result(result)
                        tr.traces[-1].duration_ms = duration
                    return result
                except Exception as e:
                    duration = (time.perf_counter() - start) * 1000
                    if tr.traces and tr.traces[-1].call_id == call_id:
                        tr.traces[-1].error = str(e)
                        tr.traces[-1].duration_ms = duration
                    raise
                finally:
                    tr.pop_call()
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                start = time.perf_counter()
                call_id = tr.add_trace(
                    class_name=class_name,
                    method_name=method_name,
                    args=args[1:] if args else (),
                    kwargs=kwargs,
                    is_async=False,
                )
                tr.push_call(call_id)
                try:
                    result = func(*args, **kwargs)
                    duration = (time.perf_counter() - start) * 1000
                    if tr.traces and tr.traces[-1].call_id == call_id:
                        tr.traces[-1].result = tr._format_result(result)
                        tr.traces[-1].duration_ms = duration
                    return result
                except Exception as e:
                    duration = (time.perf_counter() - start) * 1000
                    if tr.traces and tr.traces[-1].call_id == call_id:
                        tr.traces[-1].error = str(e)
                        tr.traces[-1].duration_ms = duration
                    raise
                finally:
                    tr.pop_call()
            return sync_wrapper
    return decorator
