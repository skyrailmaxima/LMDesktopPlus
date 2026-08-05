"""Printers adapter — read-only lpstat + open printer UI (Stage D Task 20).

Preoptimized: try_run for lpstat; ternary fail-soft snapshot; one loop in parse.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

from ..fncache import UseLevel, register_fn
from ..preopt import try_run
from ..util import executable, spawn
from .base import command_error, dispatch_command

_PRINTER_RE = re.compile(r"^printer\s+(\S+)\s+is\s+(.+)$", re.IGNORECASE)
_DEFAULT_RE = re.compile(r"^system default destination:\s*(\S+)\s*$", re.IGNORECASE)


@register_fn(
    "printers.parse_lpstat",
    UseLevel.MEDIUM,
    "Parse lpstat -p -d into printer rows + default name",
)
def parse_lpstat(output: str) -> dict[str, Any]:
    # @use: medium use — purpose: turn lpstat text into UI printer rows
    printers: list[dict[str, Any]] = []
    default: str | None = None
    for line in output.splitlines():
        text = line.strip()
        if not text:
            continue
        match_default = _DEFAULT_RE.match(text)
        if match_default:
            default = match_default.group(1)
            continue
        match_printer = _PRINTER_RE.match(text)
        if match_printer:
            name, status = match_printer.group(1), match_printer.group(2).strip()
            printers.append(
                {
                    "name": name,
                    "status": status,
                    "idle": "idle" in status.lower(),
                    "disabled": "disabled" in status.lower(),
                }
            )
    printers.sort(key=lambda row: (not row["idle"], row["name"].lower()))
    return {"printers": printers, "default": default, "count": len(printers)}


class PrintersAdapter:
    """CUPS printer status via lpstat; open system-config-printer when present."""

    id = "printers"

    def __init__(
        self,
        *,
        cache_ttl: float = 5.0,
        lpstat: str | None = None,
        printer_ui: str | None = None,
    ) -> None:
        self.lpstat = lpstat if lpstat is not None else executable("lpstat")
        if printer_ui is None:
            printer_ui = executable("system-config-printer") or executable("xdg-open")
        self.printer_ui = printer_ui or None
        self.cache_ttl = cache_ttl
        self._cached_at = 0.0
        self._cached_snapshot: dict[str, Any] | None = None

    def available(self) -> bool:
        return bool(self.lpstat)

    def snapshot(self) -> dict[str, Any]:
        # @use: medium use — purpose: Display printers panel poll
        if not self.available():
            return {"available": False, "can_open": bool(self.printer_ui)}
        now = time.monotonic()
        if self._cached_snapshot is not None and now - self._cached_at < self.cache_ttl:
            return self._cached_snapshot.copy()
        snapshot = self._probe_lpstat()
        self._cached_at = now
        self._cached_snapshot = snapshot
        return snapshot.copy()

    def _probe_lpstat(self) -> dict[str, Any]:
        # @use: medium use — purpose: try_run lpstat → printer rows or last_error
        run = try_run([self.lpstat, "-p", "-d"], timeout=4)
        return (
            {
                "available": True,
                "backend": "lpstat",
                "can_open": bool(self.printer_ui),
                **parse_lpstat(run.stdout),
            }
            if run.ok
            else {
                "available": False,
                "can_open": bool(self.printer_ui),
                "last_error": run.error or (run.stderr.strip() or "lpstat failed"),
            }
        )

    def command(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        return dispatch_command(self._commands(), name, payload, adapter_id=self.id)

    def _commands(self) -> dict[str, Any]:
        return {
            "refresh": lambda _payload: self._refresh(),
            "open": lambda _payload: self._open_ui(),
        }

    def _refresh(self) -> dict[str, Any]:
        # @use: medium use — purpose: invalidate printers TTL and re-probe
        self._cached_snapshot = None
        snap = self.snapshot()
        return (
            {"ok": True, **snap}
            if snap.get("available")
            else command_error(
                "unavailable", snap.get("last_error") or "lpstat unavailable"
            )
        )

    def _open_ui(self) -> dict[str, Any]:
        # @use: low use — purpose: spawn printer settings UI
        if not self.printer_ui:
            return command_error("unavailable", "no printer settings UI found")
        argv = (
            [self.printer_ui, "system-settings"]
            if Path(self.printer_ui).name == "xdg-open"
            else [self.printer_ui]
        )
        try:
            pid = spawn(argv)
        except OSError as exc:
            return command_error("internal_error", str(exc))
        return {"ok": True, "pid": pid}
