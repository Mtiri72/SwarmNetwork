# timing_utils.py
import time
import functools
import logging
import threading
import json
import asyncio
from contextlib import contextmanager
from datetime import datetime

# Thread-local storage for nested timing
_local = threading.local()

# Configure performance logging
performance_logger = logging.getLogger("PerformanceLogger")
performance_logger.setLevel(logging.DEBUG)
#handler = logging.FileHandler("performance.log")
import os
log_dir = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(log_dir, exist_ok=True)
handler = logging.FileHandler(os.path.join(log_dir, "performance.log"))


formatter = logging.Formatter('%(message)s')
handler.setFormatter(formatter)
performance_logger.addHandler(handler)

# Helper to log performance entries
def _log_entry(function_name, duration_ms, args=None, kwargs=None):
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3],
        "function": function_name,
	"duration_sec": round(duration_ms / 1000, 6),
        "duration_ms": round(duration_ms, 3),
    }
    if args:
        entry["args"] = str(args)
    if kwargs:
        entry["kwargs"] = str(kwargs)
    performance_logger.debug(json.dumps(entry))

# Decorator for synchronous and async functions
def timeit(func):
    if asyncio.iscoroutinefunction(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = await func(*args, **kwargs)
            end = time.perf_counter()
            _log_entry(func.__name__, (end - start) * 1000, args, kwargs)
            return result
        return async_wrapper
    else:
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = func(*args, **kwargs)
            end = time.perf_counter()
            _log_entry(func.__name__, (end - start) * 1000, args, kwargs)
            return result
        return sync_wrapper

# Context manager for custom code block timing
@contextmanager
def time_block(name):
    start = time.perf_counter()
    yield
    end = time.perf_counter()
    _log_entry(name, (end - start) * 1000)

# Manual timer utilities
_manual_timers = {}

def start_timer(name):
    _manual_timers[name] = time.perf_counter()

def stop_timer(name):
    if name in _manual_timers:
        duration = (time.perf_counter() - _manual_timers[name]) * 1000
        _log_entry(name, duration)
        del _manual_timers[name]

# Optional: collect aggregate statistics
_statistics = {}

def record_stat(name, duration):
    stat = _statistics.setdefault(name, [])
    stat.append(duration)

def get_aggregate_stats():
    return {
        name: {
            "count": len(times),
            "min": min(times),
            "max": max(times),
            "avg": sum(times) / len(times)
        } for name, times in _statistics.items()
    }
