"""Process list + SIGTERM for current-UID peers (Stage C).

@use levels: snapshot/_sample are high use (Monitor); terminate is low use.
Preoptimized: parse helpers return sentinels (no raise); one loop in _sample.
"""

from __future__ import annotations

import os
import signal
import time
from pathlib import Path
from typing import Any

from ..fncache import UseLevel, register_fn
from ..preopt import parse_int
from .base import command_error, dispatch_command

_PROC = Path("/proc")


def _read_text(path: Path) -> str | None:
    # @use: high use — purpose: fail-soft /proc file reads during sampling
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


@register_fn(
    "processes.parse_proc_stat",
    UseLevel.HIGH,
    "Parse /proc/<pid>/stat into pid, cpu ticks, rss pages",
)
def parse_proc_stat(stat_line: str) -> tuple[int, int, int] | None:
    """Return (pid, utime+stime, rss_pages) from a /proc/<pid>/stat line.

    @use: high use — purpose: Monitor process CPU/RSS sampling.
    """
    # Precheck delimiters so int() never sees bad slices.
    rparen = stat_line.rfind(")")
    if rparen < 0:
        return None
    prefix = stat_line[:rparen]
    lparen = prefix.find("(")
    if lparen < 0:
        return None
    pid = parse_int(prefix[:lparen].strip())
    rest = stat_line[rparen + 1 :].split()
    # Need utime(11), stime(12), rss(21) — bail without IndexError.
    if pid is None or len(rest) <= 21:
        return None
    utime = parse_int(rest[11])
    stime = parse_int(rest[12])
    rss = parse_int(rest[21])
    return None if utime is None or stime is None or rss is None else (pid, utime + stime, rss)


def parse_status_uids(status_text: str) -> int | None:
    # @use: high use — purpose: ownership gate for terminate + owned chip (one loop)
    for line in status_text.splitlines():
        if line.startswith("Uid:"):
            parts = line.split()
            return None if len(parts) < 2 else parse_int(parts[1])
    return None


def parse_status_name(status_text: str) -> str | None:
    # @use: high use — purpose: process display name from /proc status (one loop)
    for line in status_text.splitlines():
        if line.startswith("Name:"):
            name = line.split(":", 1)[1].strip()
            return name or None
    return None


def _cpu_percent(
    *,
    elapsed: float | None,
    pid: int,
    total_ticks: int,
    prev_ticks: dict[int, int],
    cpu_count: int,
) -> float:
    # @use: high use — purpose: ternary CPU% from tick delta (no nested if trees)
    prev = prev_ticks.get(pid) if elapsed and elapsed > 0 else None
    if prev is None:
        return 0.0
    delta = total_ticks - prev
    delta = 0 if delta < 0 else delta
    hz = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100
    raw = (delta / (elapsed * hz)) * 100.0  # type: ignore[operator]
    ceiling = 100.0 * cpu_count
    return ceiling if raw > ceiling else raw


class ProcessAdapter:
    """Sample top processes from /proc; SIGTERM only for current UID."""

    id = "processes"

    def __init__(
        self,
        cache_ttl: float = 2.0,
        top_n: int = 12,
        proc_root: Path | None = None,
        uid: int | None = None,
        page_size: int | None = None,
        cpu_count: int | None = None,
    ) -> None:
        self.cache_ttl = cache_ttl
        self.top_n = 1 if int(top_n) < 1 else (40 if int(top_n) > 40 else int(top_n))
        self.proc_root = proc_root or _PROC
        self.uid = os.getuid() if uid is None else uid
        self.page_size = page_size or os.sysconf("SC_PAGE_SIZE")
        self.cpu_count = max(1, cpu_count or (os.cpu_count() or 1))
        self._cached_at = 0.0
        self._cached_snapshot: dict[str, Any] | None = None
        self._prev_ticks: dict[int, int] = {}
        self._prev_mono: float | None = None

    def available(self) -> bool:
        return self.proc_root.is_dir()

    def snapshot(self) -> dict[str, Any]:
        # @use: high use — purpose: Monitor process panel poll
        if not self.available():
            return {"available": False}
        now = time.monotonic()
        cached = self._cached_snapshot
        if cached is not None and now - self._cached_at < self.cache_ttl:
            return cached.copy()
        # iterdir OSError is the only remaining edge; keep it local.
        try:
            snapshot = self._sample(now)
        except OSError as exc:
            snapshot = {"available": False, "last_error": str(exc)}
        self._cached_at = now
        self._cached_snapshot = snapshot
        return snapshot.copy()

    def _sample(self, now: float) -> dict[str, Any]:
        # @use: high use — purpose: one-loop /proc walk + rank by CPU/RSS
        current_ticks: dict[int, int] = {}
        rows: list[dict[str, Any]] = []
        elapsed = (
            (now - self._prev_mono)
            if self._prev_mono is not None and now > self._prev_mono
            else None
        )
        for entry in self.proc_root.iterdir():
            row = self._sample_pid(entry, elapsed, current_ticks)
            row is not None and rows.append(row)
        self._prev_ticks = current_ticks
        self._prev_mono = now
        rows.sort(key=lambda row: (-row["cpu_percent"], -row["rss_bytes"], row["pid"]))
        return {
            "available": True,
            "backend": "proc",
            "top_n": self.top_n,
            "processes": rows[: self.top_n],
            "owned_uid": self.uid,
        }

    def _sample_pid(
        self,
        entry: Path,
        elapsed: float | None,
        current_ticks: dict[int, int],
    ) -> dict[str, Any] | None:
        # @use: high use — purpose: one /proc/<pid> row for the Monitor table
        if not entry.name.isdigit():
            return None
        pid = parse_int(entry.name)
        if pid is None:
            return None
        parsed = parse_proc_stat(_read_text(entry / "stat") or "")
        if parsed is None:
            return None
        _, total_ticks, rss_pages = parsed
        status_text = _read_text(entry / "status") or ""
        owner = parse_status_uids(status_text)
        name = parse_status_name(status_text) or entry.name
        current_ticks[pid] = total_ticks
        cpu_percent = _cpu_percent(
            elapsed=elapsed,
            pid=pid,
            total_ticks=total_ticks,
            prev_ticks=self._prev_ticks,
            cpu_count=self.cpu_count,
        )
        rss_pages = 0 if rss_pages < 0 else rss_pages
        return {
            "pid": pid,
            "name": name[:64],
            "uid": owner,
            "cpu_percent": round(cpu_percent, 1),
            "rss_bytes": rss_pages * self.page_size,
            "owned": owner == self.uid,
        }

    def command(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        # @use: high use — purpose: refresh/terminate via command hashmap
        return dispatch_command(self._commands(), name, payload, adapter_id=self.id)

    def _commands(self) -> dict[str, Any]:
        return {
            "refresh": self._refresh,
            "terminate": self._terminate,
        }

    def _refresh(self, _payload: dict[str, Any]) -> dict[str, Any]:
        self._cached_snapshot = None
        return {"ok": True, **self.snapshot()}

    def _terminate(self, payload: dict[str, Any]) -> dict[str, Any]:
        # @use: low use — purpose: SIGTERM current-UID process from Monitor
        pid = parse_int(payload.get("pid"))
        if pid is None:
            return command_error("invalid_argument", "pid must be an integer")
        if pid <= 1 or pid == os.getpid():
            return command_error("invalid_argument", "refusing to terminate that process")
        status_text = _read_text(self.proc_root / str(pid) / "status")
        if status_text is None:
            return command_error("invalid_argument", f"process {pid} not found")
        owner = parse_status_uids(status_text)
        if owner != self.uid:
            return command_error(
                "permission_denied",
                "can only terminate processes owned by the current user",
            )
        return self._signal_term(pid)

    def _signal_term(self, pid: int) -> dict[str, Any]:
        # @use: low use — purpose: local SIGTERM edge mapped to command_error
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            return command_error("invalid_argument", f"process {pid} not found")
        except PermissionError:
            return command_error("permission_denied", f"permission denied for pid {pid}")
        except OSError as exc:
            return command_error("internal_error", str(exc))
        self._cached_snapshot = None
        return {"ok": True, "pid": pid, "signal": "SIGTERM"}
