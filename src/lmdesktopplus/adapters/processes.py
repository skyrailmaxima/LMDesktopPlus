"""Process list + SIGTERM for current-UID peers (Stage C).

@use levels: snapshot/_sample are high use (Monitor); terminate is low use.
"""

from __future__ import annotations

import os
import signal
import time
from pathlib import Path
from typing import Any

from ..fncache import UseLevel, register_fn
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
    try:
        # Comm may contain spaces/parens — split after the last ')' of the name field.
        rparen = stat_line.rfind(")")
        if rparen < 0:
            return None
        prefix = stat_line[:rparen]
        lparen = prefix.find("(")
        if lparen < 0:
            return None
        pid = int(prefix[:lparen].strip())
        rest = stat_line[rparen + 1 :].split()
        # fields after comm: state(0) ppid(1) ... utime(11) stime(12) ... rss(21)
        utime = int(rest[11])
        stime = int(rest[12])
        rss = int(rest[21])
        return pid, utime + stime, rss
    except (IndexError, ValueError):
        return None


def parse_status_uids(status_text: str) -> int | None:
    # @use: high use — purpose: ownership gate for terminate + owned chip
    for line in status_text.splitlines():
        if line.startswith("Uid:"):
            parts = line.split()
            if len(parts) >= 2:
                try:
                    return int(parts[1])
                except ValueError:
                    return None
    return None


def parse_status_name(status_text: str) -> str | None:
    # @use: high use — purpose: process display name from /proc status
    for line in status_text.splitlines():
        if line.startswith("Name:"):
            return line.split(":", 1)[1].strip() or None
    return None


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
        self.top_n = max(1, min(int(top_n), 40))
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
        if self._cached_snapshot is not None and now - self._cached_at < self.cache_ttl:
            return self._cached_snapshot.copy()
        try:
            snapshot = self._sample(now)
        except OSError as exc:
            snapshot = {"available": False, "last_error": str(exc)}
        self._cached_at = now
        self._cached_snapshot = snapshot
        return snapshot.copy()

    def _sample(self, now: float) -> dict[str, Any]:
        # @use: high use — purpose: walk /proc and rank by CPU/RSS delta
        current_ticks: dict[int, int] = {}
        rows: list[dict[str, Any]] = []
        elapsed = (
            (now - self._prev_mono)
            if self._prev_mono is not None and now > self._prev_mono
            else None
        )
        for entry in self.proc_root.iterdir():
            row = self._sample_pid(entry, elapsed, current_ticks)
            if row is not None:
                rows.append(row)
        self._prev_ticks = current_ticks
        self._prev_mono = now
        rows.sort(key=lambda row: (-row["cpu_percent"], -row["rss_bytes"], row["pid"]))
        top = rows[: self.top_n]
        return {
            "available": True,
            "backend": "proc",
            "top_n": self.top_n,
            "processes": top,
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
        pid = int(entry.name)
        stat_text = _read_text(entry / "stat")
        if not stat_text:
            return None
        parsed = parse_proc_stat(stat_text)
        if parsed is None:
            return None
        _, total_ticks, rss_pages = parsed
        status_text = _read_text(entry / "status") or ""
        owner = parse_status_uids(status_text)
        name = parse_status_name(status_text) or entry.name
        current_ticks[pid] = total_ticks
        cpu_percent = 0.0
        if elapsed and elapsed > 0 and pid in self._prev_ticks:
            delta = max(0, total_ticks - self._prev_ticks[pid])
            hz = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100
            # Percent of one logical CPU; may exceed 100 on multi-threaded procs.
            cpu_percent = min(100.0 * self.cpu_count, (delta / (elapsed * hz)) * 100.0)
        rss_bytes = max(0, rss_pages) * self.page_size
        return {
            "pid": pid,
            "name": name[:64],
            "uid": owner,
            "cpu_percent": round(cpu_percent, 1),
            "rss_bytes": rss_bytes,
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
        pid_raw = payload.get("pid")
        try:
            pid = int(pid_raw)
        except (TypeError, ValueError):
            return command_error("invalid_argument", "pid must be an integer")
        if pid <= 1 or pid == os.getpid():
            return command_error("invalid_argument", "refusing to terminate that process")
        status_path = self.proc_root / str(pid) / "status"
        status_text = _read_text(status_path)
        if status_text is None:
            return command_error("invalid_argument", f"process {pid} not found")
        owner = parse_status_uids(status_text)
        if owner != self.uid:
            return command_error(
                "permission_denied",
                "can only terminate processes owned by the current user",
            )
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
