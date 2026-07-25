"""User journal logs adapter — capped journalctl panel (Stage D Task 21).

Preoptimized: try_run for journalctl; ternary fail-soft snapshot.
"""

from __future__ import annotations

import re
import time
from typing import Any

from ..fncache import UseLevel, register_fn
from ..preopt import clamp_int, try_run
from ..util import executable
from .base import command_error, dispatch_command

_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_MAX_LINES = 200
_MAX_CHARS = 80_000


@register_fn(
    "logs.sanitize_journal",
    UseLevel.HIGH,
    "Cap and strip control chars from journalctl --user output",
)
def sanitize_journal(
    text: str,
    *,
    max_lines: int = _MAX_LINES,
    max_chars: int = _MAX_CHARS,
) -> list[str]:
    """Return safe plain-text lines for HTML-escaped UI rendering.

    @use: high use — purpose: Monitor logs panel; never pass raw controls to DOM.
    """
    # Normalize newlines and drop NULs / other controls (keep tab via space).
    cleaned = _CTRL_RE.sub("", text.replace("\r\n", "\n").replace("\r", "\n"))
    cleaned = cleaned if len(cleaned) <= max_chars else cleaned[-max_chars:]
    lines = cleaned.split("\n")
    # Keep the newest N lines when over cap.
    lines = lines if len(lines) <= max_lines else lines[-max_lines:]
    # Drop a single trailing empty line from journalctl.
    return lines[:-1] if lines and lines[-1] == "" else lines


class LogsAdapter:
    """Read-only user journal tail for the Monitor scene."""

    id = "logs"

    def __init__(
        self,
        *,
        cache_ttl: float = 3.0,
        journalctl: str | None = None,
        max_lines: int = _MAX_LINES,
    ) -> None:
        self.journalctl = journalctl if journalctl is not None else executable("journalctl")
        self.cache_ttl = cache_ttl
        self.max_lines = clamp_int(int(max_lines), 10, 500)
        self._cached_at = 0.0
        self._cached_snapshot: dict[str, Any] | None = None

    def available(self) -> bool:
        return bool(self.journalctl)

    def snapshot(self) -> dict[str, Any]:
        # @use: high use — purpose: Monitor logs panel (TTL-cached)
        if not self.available():
            return {"available": False}
        now = time.monotonic()
        if self._cached_snapshot is not None and now - self._cached_at < self.cache_ttl:
            return self._cached_snapshot.copy()
        snapshot = self._probe_journal()
        self._cached_at = now
        self._cached_snapshot = snapshot
        return snapshot.copy()

    def _probe_journal(self) -> dict[str, Any]:
        # @use: high use — purpose: try_run journalctl --user → sanitized lines
        run = try_run(
            [
                self.journalctl,
                "--user",
                "-n",
                str(self.max_lines),
                "--no-pager",
                "-o",
                "short-iso",
            ],
            timeout=5,
        )
        if not run.ok:
            return {
                "available": False,
                "last_error": run.error or (run.stderr.strip() or "journalctl failed"),
            }
        lines = sanitize_journal(run.stdout, max_lines=self.max_lines)
        return {
            "available": True,
            "backend": "journalctl",
            "lines": lines,
            "count": len(lines),
            "max_lines": self.max_lines,
        }

    def command(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        return dispatch_command(self._commands(), name, payload, adapter_id=self.id)

    def _commands(self) -> dict[str, Any]:
        return {"refresh": lambda _payload: self._refresh()}

    def _refresh(self) -> dict[str, Any]:
        # @use: medium use — purpose: force journal re-read for Monitor panel
        self._cached_snapshot = None
        snap = self.snapshot()
        return (
            {"ok": True, **snap}
            if snap.get("available")
            else command_error(
                "unavailable", snap.get("last_error") or "journalctl unavailable"
            )
        )
