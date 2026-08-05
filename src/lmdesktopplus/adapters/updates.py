"""Apt upgradable count + Mint Update launcher (Stage B).

Preoptimized: try_run for apt list; ternary fail-soft snapshot; one loop in count.
@use levels: snapshot is medium (long TTL); refresh/open are low use.
"""

from __future__ import annotations

import re
import time
from typing import Any

from ..fncache import UseLevel, register_fn
from ..preopt import try_run
from ..util import executable, spawn
from .base import command_error, dispatch_command

_UPGRADABLE_RE = re.compile(r"\bupgradable\b", re.IGNORECASE)
# apt list may exit 100 when indexes are stale but still emits package lines.
_APT_OK = frozenset({0, 100})


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
        count += 1 if _UPGRADABLE_RE.search(stripped) else 0
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
        snapshot = self._probe_upgradable()
        self._cached_at = now
        self._cached_snapshot = snapshot
        return snapshot.copy()

    def _probe_upgradable(self) -> dict[str, Any]:
        # @use: medium use — purpose: one apt list probe → Outcome-shaped snapshot
        run = try_run([self.apt, "list", "--upgradable"], timeout=20)
        code = -1 if run.completed is None else run.completed.returncode
        # Launched + allowed exit → count; else fail-soft with last_error.
        return (
            {
                "available": True,
                "count": count_upgradable(run.stdout + "\n" + run.stderr),
                "mintupdate_available": bool(self.mintupdate),
            }
            if run.launched and code in _APT_OK
            else {
                "available": False,
                "last_error": run.error
                or (run.stderr.strip() or "apt list --upgradable failed"),
            }
        )

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
        return (
            {
                "ok": True,
                "count": snap["count"],
                "mintupdate_available": snap["mintupdate_available"],
            }
            if snap.get("available")
            else command_error("unavailable", snap.get("last_error") or "refresh failed")
        )

    def _open(self, _payload: dict[str, Any]) -> dict[str, Any]:
        # @use: low use — purpose: spawn Mint Update UI only
        if not self.mintupdate:
            return command_error("unavailable", "mintupdate is not installed")
        try:
            pid = spawn([self.mintupdate])
        except OSError as exc:
            return command_error("internal_error", str(exc))
        return {"ok": True, "pid": pid}
