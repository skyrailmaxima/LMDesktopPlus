"""Apt upgradable count + Mint Update launcher (Stage B).

@use levels: snapshot is medium (long TTL); refresh/open are low use.
Counting uses `apt list --upgradable`; open only launches mintupdate.
"""

from __future__ import annotations

import re
import subprocess
import time
from typing import Any

from ..fncache import UseLevel, register_fn
from ..util import executable, run_capture, spawn
from .base import command_error, dispatch_command

_UPGRADABLE_RE = re.compile(r"\bupgradable\b", re.IGNORECASE)


@register_fn(
    "updates.count_upgradable",
    UseLevel.MEDIUM,
    "Count upgradable lines from apt list --upgradable output",
)
def count_upgradable(output: str) -> int:
    # @use: medium use — purpose: Desktop updates badge count
    count = 0
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        lower = stripped.lower()
        if lower.startswith("listing") or lower.startswith("warning:"):
            continue
        if _UPGRADABLE_RE.search(stripped):
            count += 1
    return count


class UpdatesAdapter:
    """Fail-soft apt upgradable counter + optional mintupdate spawn."""

    id = "updates"

    def __init__(
        self,
        cache_ttl: float = 600.0,
        apt: str | None = None,
        mintupdate: str | None = None,
    ) -> None:
        self.apt = executable("apt") if apt is None else (apt or None)
        self.mintupdate = (
            executable("mintupdate") if mintupdate is None else (mintupdate or None)
        )
        self.cache_ttl = cache_ttl
        self._cached_at = 0.0
        self._cached_snapshot: dict[str, Any] | None = None

    def available(self) -> bool:
        return bool(self.apt)

    def snapshot(self) -> dict[str, Any]:
        # @use: medium use — purpose: Desktop updates count with long TTL
        if not self.available():
            return {"available": False}
        now = time.monotonic()
        if self._cached_snapshot is not None and now - self._cached_at < self.cache_ttl:
            return self._cached_snapshot.copy()
        try:
            result = run_capture([self.apt, "list", "--upgradable"], timeout=20)
            if result.returncode not in {0, 100}:
                # apt may return non-zero when lists are locked; keep fail-soft
                raise RuntimeError(result.stderr.strip() or "apt list --upgradable failed")
            snapshot = {
                "available": True,
                "count": count_upgradable(result.stdout + "\n" + result.stderr),
                "mintupdate_available": bool(self.mintupdate),
            }
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
            snapshot = {
                "available": False,
                "last_error": str(exc),
            }
        self._cached_at = now
        self._cached_snapshot = snapshot
        return snapshot.copy()

    def command(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        # @use: low use — purpose: refresh/open via command hashmap
        return dispatch_command(self._commands(), name, payload, adapter_id=self.id)

    def _commands(self) -> dict[str, Any]:
        return {
            "refresh": self._refresh,
            "open": self._open,
        }

    def _refresh(self, _payload: dict[str, Any]) -> dict[str, Any]:
        # @use: low use — purpose: invalidate cache and re-count upgradable
        if not self.available():
            return command_error("unavailable", "apt is not installed")
        self._cached_snapshot = None
        snap = self.snapshot()
        if not snap.get("available"):
            return command_error("unavailable", snap.get("last_error") or "refresh failed")
        return {
            "ok": True,
            "count": snap["count"],
            "mintupdate_available": snap["mintupdate_available"],
        }

    def _open(self, _payload: dict[str, Any]) -> dict[str, Any]:
        # @use: low use — purpose: spawn Mint Update UI only
        if not self.mintupdate:
            return command_error("unavailable", "mintupdate is not installed")
        try:
            pid = spawn([self.mintupdate])
        except OSError as exc:
            return command_error("internal_error", str(exc))
        return {"ok": True, "pid": pid}
