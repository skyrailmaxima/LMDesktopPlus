from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from typing import Any, Protocol


class Adapter(Protocol):
    id: str

    def available(self) -> bool: ...

    def snapshot(self) -> dict[str, Any]: ...

    def command(self, name: str, payload: dict[str, Any]) -> dict[str, Any]: ...


CommandHandler = Callable[[dict[str, Any]], dict[str, Any]]


def dispatch_command(
    commands: Mapping[str, CommandHandler],
    name: str,
    payload: dict[str, Any],
    *,
    adapter_id: str | None = None,
) -> dict[str, Any]:
    """Resolve adapter commands through a name → handler map."""
    handler = commands.get(name)
    if handler is None:
        label = (
            f"unknown {adapter_id} command: {name}"
            if adapter_id
            else f"unknown command: {name}"
        )
        return command_error("unavailable", label)
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


def envelope(
    adapter_id: str,
    snapshot: dict[str, Any],
    *,
    capabilities: tuple[str, ...] | list[str] = (),
    stale: bool = False,
    updated_at: float | None = None,
) -> dict[str, Any]:
    """Typed adapter snapshot envelope with backward-compatible flat fields."""
    available = bool(snapshot.get("available"))
    status = snapshot.get("status")
    if not isinstance(status, str) or not status:
        if not available:
            status = "unavailable"
        elif snapshot.get("last_error") or snapshot.get("error"):
            status = "degraded"
        else:
            status = "ready"
    error = snapshot.get("error")
    if error is None:
        error = snapshot.get("last_error")
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
