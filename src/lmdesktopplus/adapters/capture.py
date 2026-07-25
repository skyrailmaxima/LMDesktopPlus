"""Screenshot capture — grim(+slurp) or gnome-screenshot (Stage B).

@use levels: snapshot is medium; full/region are low use.
Saves only under ~/Pictures/lmdesktopplus/; never accepts client paths.
"""

from __future__ import annotations

import os
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from ..util import ensure_private_dir, executable, run_capture, spawn
from .base import command_error, dispatch_command

_GEOM_RE = re.compile(r"^\d+,\d+\s+\d+x\d+$")


class CaptureAdapter:
    """Session-routed screenshot tool with region support when available."""

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
        # @use: medium use — purpose: pick grim vs gnome-screenshot for session
        # Session → preferred backend order (first present wins).
        order_by_session = {
            "wayland": ("grim", "gnome-screenshot"),
            "x11": ("gnome-screenshot", "grim"),
        }
        order = order_by_session.get(self.session_type)
        if order is None:
            if self.grim and os.environ.get("WAYLAND_DISPLAY"):
                return "grim"
            order = ("gnome-screenshot", "grim")
        present = {
            "grim": self.grim,
            "gnome-screenshot": self.gnome_screenshot,
        }
        for name in order:
            if present.get(name):
                return name
        return None

    def available(self) -> bool:
        return self._backend() is not None

    def snapshot(self) -> dict[str, Any]:
        # @use: medium use — purpose: Desktop capture capability chip
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
        # @use: low use — purpose: full/region/open_folder; reject client paths
        if "path" in payload:
            return command_error("invalid_argument", "client paths are not accepted")
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
        # @use: low use — purpose: write screenshot under owned Pictures dir
        backend = self._backend()
        if not backend:
            return command_error("unavailable", "no screenshot tool for this session")
        path = self._target_path()
        try:
            argv = self._etch_capture_argv(backend, path, region=region)
            if isinstance(argv, dict):
                return argv  # already an error payload
            result = run_capture(argv, timeout=120)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return command_error("internal_error", str(exc))
        if result.returncode != 0:
            return command_error(
                "internal_error",
                result.stderr.strip() or "screenshot capture failed",
            )
        if not path.is_file():
            return command_error(
                "internal_error",
                "screenshot tool did not write an output file",
            )
        self._last_path = str(path)
        self._cached_snapshot = None
        return {"ok": True, "path": str(path), "backend": backend}

    def _etch_capture_argv(
        self,
        backend: str,
        path: Path,
        *,
        region: bool,
    ) -> list[str] | dict[str, Any]:
        # @use: low use — purpose: (backend, region) → screenshot argv without if-trees at call site
        etchers = {
            "grim": lambda: self._etch_grim_argv(path, region=region),
            "gnome-screenshot": lambda: self._etch_gnome_argv(path, region=region),
        }
        etcher = etchers.get(backend)
        if etcher is None:
            return command_error("unavailable", f"unsupported capture backend: {backend}")
        return etcher()

    def _etch_grim_argv(self, path: Path, *, region: bool) -> list[str] | dict[str, Any]:
        # @use: low use — purpose: grim full or grim -g from slurp geometry
        assert self.grim
        if not region:
            return [self.grim, str(path)]
        if not self.slurp:
            return command_error("unavailable", "slurp is required for region capture")
        geom_result = run_capture([self.slurp], timeout=120)
        if geom_result.returncode != 0:
            return command_error(
                "internal_error",
                geom_result.stderr.strip() or "slurp cancelled",
            )
        geom = geom_result.stdout.strip()
        if not _GEOM_RE.match(geom):
            return command_error("invalid_argument", f"invalid slurp geometry: {geom!r}")
        return [self.grim, "-g", geom, str(path)]

    def _etch_gnome_argv(self, path: Path, *, region: bool) -> list[str]:
        # @use: low use — purpose: gnome-screenshot [-a] -f path
        assert self.gnome_screenshot
        argv = [self.gnome_screenshot]
        if region:
            argv.append("-a")
        argv.extend(["-f", str(path)])
        return argv

    def _open_folder(self) -> dict[str, Any]:
        # @use: low use — purpose: open owned screenshot folder in file manager
        ensure_private_dir(self.save_dir)
        opener = executable("xdg-open")
        if not opener:
            return command_error("unavailable", "xdg-open is not installed")
        try:
            pid = spawn([opener, str(self.save_dir)])
        except OSError as exc:
            return command_error("internal_error", str(exc))
        return {"ok": True, "pid": pid, "path": str(self.save_dir)}
