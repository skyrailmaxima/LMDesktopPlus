"""User journal logs adapter — capped journalctl panel (Stage D Task 21)."""

from __future__ import annotations

import re
import time
from typing import Any

from ..fncache import UseLevel, register_fn
from ..util import executable, run_capture
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
    if len(cleaned) > max_chars:
        cleaned = cleaned[-max_chars:]
    lines = cleaned.split("\n")
    # Keep the newest N lines when over cap.
    if len(lines) > max_lines:
        lines = lines[-max_lines:]
    # Drop a single trailing empty line from journalctl.
    if lines and lines[-1] == "":
        lines = lines[:-1]
    return lines


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
        self.max_lines = max(10, min(500, int(max_lines)))
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
        try:
            cp = run_capture(
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
            if cp.returncode != 0:
                raise RuntimeError(cp.stderr.strip() or "journalctl failed")
            lines = sanitize_journal(cp.stdout, max_lines=self.max_lines)
            snapshot = {
                "available": True,
                "backend": "journalctl",
                "lines": lines,
                "count": len(lines),
                "max_lines": self.max_lines,
            }
        except (OSError, RuntimeError) as exc:
            snapshot = {"available": False, "last_error": str(exc)}
        self._cached_at = now
        self._cached_snapshot = snapshot
        return snapshot.copy()

    def command(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        return dispatch_command(self._commands(), name, payload, adapter_id=self.id)

    def _commands(self) -> dict[str, Any]:
        return {"refresh": lambda _payload: self._refresh()}

    def _refresh(self) -> dict[str, Any]:
        # @use: medium use — purpose: force journal re-read for Monitor panel
        self._cached_snapshot = None
        snap = self.snapshot()
        if not snap.get("available"):
            return command_error(
                "unavailable", snap.get("last_error") or "journalctl unavailable"
            )
        return {"ok": True, **snap}
