from __future__ import annotations

import re
import subprocess
import time
from typing import Any

from ..util import executable, run_capture, spawn

_UPGRADABLE_RE = re.compile(r"\bupgradable\b", re.IGNORECASE)


def count_upgradable(output: str) -> int:
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
        if name not in {"refresh", "open"}:
            return {"ok": False, "error": f"unknown updates command: {name}"}
        if name == "refresh":
            if not self.available():
                return {"ok": False, "error": "apt is not installed"}
            self._cached_snapshot = None
            snap = self.snapshot()
            if not snap.get("available"):
                return {"ok": False, "error": snap.get("last_error") or "refresh failed"}
            return {
                "ok": True,
                "count": snap["count"],
                "mintupdate_available": snap["mintupdate_available"],
            }
        if not self.mintupdate:
            return {"ok": False, "error": "mintupdate is not installed"}
        try:
            pid = spawn([self.mintupdate])
        except OSError as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "pid": pid}
