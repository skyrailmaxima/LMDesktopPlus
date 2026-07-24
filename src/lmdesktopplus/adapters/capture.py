from __future__ import annotations

import os
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from ..util import ensure_private_dir, executable, run_capture, spawn
from .base import dispatch_command

_GEOM_RE = re.compile(r"^\d+,\d+\s+\d+x\d+$")


class CaptureAdapter:
    id = "capture"

    def __init__(
        self,
        cache_ttl: float = 60.0,
        session_type: str | None = None,
        grim: str | None = None,
        slurp: str | None = None,
        gnome_screenshot: str | None = None,
        save_dir: Path | None = None,
    ) -> None:
        self.session_type = (session_type or os.environ.get("XDG_SESSION_TYPE") or "").lower()
        self.grim = executable("grim") if grim is None else (grim or None)
        self.slurp = executable("slurp") if slurp is None else (slurp or None)
        self.gnome_screenshot = (
            executable("gnome-screenshot")
            if gnome_screenshot is None
            else (gnome_screenshot or None)
        )
        self.save_dir = save_dir or (Path.home() / "Pictures" / "lmdesktopplus")
        self.cache_ttl = cache_ttl
        self._cached_at = 0.0
        self._cached_snapshot: dict[str, Any] | None = None
        self._last_path: str | None = None

    def _backend(self) -> str | None:
        if self.session_type == "wayland":
            if self.grim:
                return "grim"
            if self.gnome_screenshot:
                return "gnome-screenshot"
            return None
        if self.session_type == "x11":
            if self.gnome_screenshot:
                return "gnome-screenshot"
            if self.grim:
                return "grim"
            return None
        if self.grim and os.environ.get("WAYLAND_DISPLAY"):
            return "grim"
        if self.gnome_screenshot:
            return "gnome-screenshot"
        if self.grim:
            return "grim"
        return None

    def available(self) -> bool:
        return self._backend() is not None

    def snapshot(self) -> dict[str, Any]:
        backend = self._backend()
        if not backend:
            return {"available": False}
        now = time.monotonic()
        if self._cached_snapshot is not None and now - self._cached_at < self.cache_ttl:
            return self._cached_snapshot.copy()
        snapshot = {
            "available": True,
            "backend": backend,
            "region_available": (
                (backend == "grim" and bool(self.slurp))
                or backend == "gnome-screenshot"
            ),
            "save_dir": str(self.save_dir),
            "last_path": self._last_path,
        }
        self._cached_at = now
        self._cached_snapshot = snapshot
        return snapshot.copy()

    def command(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        if "path" in payload:
            return {"ok": False, "error": "client paths are not accepted"}
        return dispatch_command(self._commands(), name, payload, adapter_id=self.id)

    def _commands(self) -> dict[str, Any]:
        return {
            "full": lambda _payload: self._capture(region=False),
            "region": lambda _payload: self._capture(region=True),
            "open_folder": lambda _payload: self._open_folder(),
        }

    def _target_path(self) -> Path:
        ensure_private_dir(self.save_dir)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return self.save_dir / f"lmdp-{stamp}.png"

    def _capture(self, *, region: bool) -> dict[str, Any]:
        backend = self._backend()
        if not backend:
            return {"ok": False, "error": "no screenshot tool for this session"}
        path = self._target_path()
        try:
            if backend == "grim":
                if region:
                    if not self.slurp:
                        return {"ok": False, "error": "slurp is required for region capture"}
                    geom_result = run_capture([self.slurp], timeout=120)
                    if geom_result.returncode != 0:
                        return {
                            "ok": False,
                            "error": geom_result.stderr.strip() or "slurp cancelled",
                        }
                    geom = geom_result.stdout.strip()
                    if not _GEOM_RE.match(geom):
                        return {"ok": False, "error": f"invalid slurp geometry: {geom!r}"}
                    argv = [self.grim, "-g", geom, str(path)]
                else:
                    argv = [self.grim, str(path)]
            else:
                argv = [self.gnome_screenshot]
                if region:
                    argv.append("-a")
                argv.extend(["-f", str(path)])
            result = run_capture(argv, timeout=120)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"ok": False, "error": str(exc)}
        if result.returncode != 0:
            return {
                "ok": False,
                "error": result.stderr.strip() or "screenshot capture failed",
            }
        if not path.is_file():
            return {"ok": False, "error": "screenshot tool did not write an output file"}
        self._last_path = str(path)
        self._cached_snapshot = None
        return {"ok": True, "path": str(path), "backend": backend}

    def _open_folder(self) -> dict[str, Any]:
        ensure_private_dir(self.save_dir)
        opener = executable("xdg-open")
        if not opener:
            return {"ok": False, "error": "xdg-open is not installed"}
        try:
            pid = spawn([opener, str(self.save_dir)])
        except OSError as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "pid": pid, "path": str(self.save_dir)}
