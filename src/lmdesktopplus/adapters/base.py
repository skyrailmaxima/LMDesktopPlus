from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from typing import Any, Protocol

from ..fncache import UseLevel, register_fn


class Adapter(Protocol):
    id: str

    def available(self) -> bool: ...

    def snapshot(self) -> dict[str, Any]: ...

    def command(self, name: str, payload: dict[str, Any]) -> dict[str, Any]: ...


CommandHandler = Callable[[dict[str, Any]], dict[str, Any]]


@register_fn(
    "adapters.dispatch_command",
    UseLevel.HIGH,
    "O(1) adapter command hashmap dispatch for UI→host operations",
)
def dispatch_command(
    commands: Mapping[str, CommandHandler],
    name: str,
    payload: dict[str, Any],
    *,
    adapter_id: str | None = None,
) -> dict[str, Any]:
    """Resolve adapter commands through a name → handler map (no if/elif chains).

    @use: high use — purpose: every Settings/Monitor adapter click lands here.
    Looks up `name` in `commands`, runs the handler with `payload`, and returns a
    stable `command_error` when the name is unknown.
    """
    # Hash-map lookup replaces cascading conditionals.
    handler = commands.get(name)
    # Unknown names fail soft with an optional adapter-scoped label.
    if handler is None:
        label = (
            f"unknown {adapter_id} command: {name}"
            if adapter_id
            else f"unknown command: {name}"
        )
        return command_error("unavailable", label)
    # Handlers own payload validation and return shapes.
    return handler(payload)


class NullAdapter:
    def __init__(self, adapter_id: str) -> None:
        self.id = adapter_id

    def available(self) -> bool:
        return True

    def snapshot(self) -> dict[str, Any]:
        return envelope(self.id, {"available": True}, capabilities=())

    def command(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        return command_error(
            "unavailable",
            f"{self.id} does not support commands",
        )


@register_fn(
    "adapters.envelope",
    UseLevel.HIGH,
    "Shape adapter snapshots for /api/v1/state with nested state + status",
)
def envelope(
    adapter_id: str,
    snapshot: dict[str, Any],
    *,
    capabilities: tuple[str, ...] | list[str] = (),
    stale: bool = False,
    updated_at: float | None = None,
) -> dict[str, Any]:
    """Typed adapter snapshot envelope with backward-compatible flat fields.

    @use: high use — purpose: every adapter poll lands in this shaper.
    """
    # Derive availability once; status may already be set by the adapter.
    available = bool(snapshot.get("available"))
    status = snapshot.get("status")
    if not isinstance(status, str) or not status:
        # Fail-soft status ladder when adapters omit an explicit status.
        if not available:
            status = "unavailable"
        elif snapshot.get("last_error") or snapshot.get("error"):
            status = "degraded"
        else:
            status = "ready"
    # Prefer explicit error; fall back to last_error from probes.
    error = snapshot.get("error")
    if error is None:
        error = snapshot.get("last_error")
    # Nested `state` drops envelope keys so clients can read either shape.
    out = {
        **snapshot,
        "id": adapter_id,
        "available": available,
        "status": status,
        "backend": snapshot.get("backend"),
        "updated_at": float(updated_at if updated_at is not None else time.time()),
        "stale": bool(stale),
        "capabilities": list(capabilities),
        "state": {
            key: value
            for key, value in snapshot.items()
            if key
            not in {
                "id",
                "available",
                "status",
                "backend",
                "updated_at",
                "stale",
                "capabilities",
                "state",
                "error",
                "last_error",
            }
        },
        "error": error,
    }
    return out


def command_error(error_code: str, message: str, **extra: Any) -> dict[str, Any]:
    # @use: high use — purpose: stable fail-soft command error payload
    payload = {"ok": False, "error_code": error_code, "error": message}
    payload.update(extra)
    return payload


def classify_exception(exc: BaseException) -> tuple[str, str]:
    import subprocess

    if isinstance(exc, subprocess.TimeoutExpired):
        return "timeout", f"host command timed out after {exc.timeout}s"
    if isinstance(exc, TimeoutError):
        return "timeout", str(exc) or "operation timed out"
    if isinstance(exc, FileNotFoundError):
        return "unavailable", "required host binary is not installed"
    if isinstance(exc, PermissionError):
        return "permission_denied", "permission denied for host command"
    text = str(exc).lower()
    if "permission" in text or "denied" in text:
        return "permission_denied", str(exc)
    if "timed out" in text or "timeout" in text:
        return "timeout", str(exc)
    return "internal_error", "Adapter command failed"
