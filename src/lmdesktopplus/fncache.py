"""Memory hashmap of use-level annotated callables for fast UI→operation dispatch.

Typology / levels
-----------------
| Level        | Meaning |
|--------------|---------|
| high use     | Hot path every poll or click (dispatch, adapterCommand, bindings) |
| medium use   | Settings / roster / vault ops; warm but not per-tick |
| low use      | Rare setup, install, or cold helpers |

`FUNCTION_CACHE` stores `{name → {fn, level, purpose, hits}}` for O(1) resolve.
Prefer `resolve_fn(name)(*args)` on hot paths instead of deep attribute walks.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum
from functools import wraps
from typing import Any, TypeVar

F = TypeVar("F", bound=Callable[..., Any])

# Global memory hashmap — name to callable metadata (thread-local hits are fine).
FUNCTION_CACHE: dict[str, dict[str, Any]] = {}


class UseLevel(str, Enum):
    """Relative how often a function is hit from the machine UI."""

    LOW = "low use"
    MEDIUM = "medium use"
    HIGH = "high use"


def register_fn(name: str, level: UseLevel, purpose: str) -> Callable[[F], F]:
    """Decorate a function: document use level + purpose and index it in FUNCTION_CACHE."""

    def decorator(fn: F) -> F:
        # Wrap so every call increments hit counters for audit / warm decisions.
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            entry = FUNCTION_CACHE.get(name)
            if entry is not None:
                entry["hits"] = int(entry.get("hits", 0)) + 1
            return fn(*args, **kwargs)

        # Index the wrapper so resolve_fn always returns the instrumented callable.
        FUNCTION_CACHE[name] = {
            "fn": wrapper,
            "level": level.value,
            "purpose": purpose,
            "hits": 0,
            "qualname": getattr(fn, "__qualname__", name),
        }
        return wrapper  # type: ignore[return-value]

    return decorator


def resolve_fn(name: str) -> Callable[..., Any]:
    """O(1) hashmap lookup for a registered callable; bumps hit count."""
    entry = FUNCTION_CACHE.get(name)
    if entry is None:
        raise KeyError(f"fncache miss: {name}")
    entry["hits"] = int(entry.get("hits", 0)) + 1
    return entry["fn"]


def fn_meta(name: str) -> dict[str, Any] | None:
    """Return cache metadata for audits (without invoking the callable)."""
    entry = FUNCTION_CACHE.get(name)
    if entry is None:
        return None
    return {
        "name": name,
        "level": entry.get("level"),
        "purpose": entry.get("purpose"),
        "hits": entry.get("hits", 0),
        "qualname": entry.get("qualname"),
    }


def warm_high_use() -> list[str]:
    """Return names of high-use callables (for startup warm / UI prefetch lists)."""
    return sorted(
        name
        for name, entry in FUNCTION_CACHE.items()
        if entry.get("level") == UseLevel.HIGH.value
    )


def cache_snapshot() -> dict[str, dict[str, Any]]:
    """Serializable view of the memory hashmap for diagnostics."""
    return {
        name: {
            "level": entry.get("level"),
            "purpose": entry.get("purpose"),
            "hits": entry.get("hits", 0),
        }
        for name, entry in sorted(FUNCTION_CACHE.items())
    }
